"""LiveKit publisher: the show's room, its media, and its chat.

The streamer is the room's only media publisher. It creates the LiveKit
room explicitly (idempotently) with a generous empty timeout, so the room —
like this publisher — survives a streamer restart, and it publishes the
paced stream into it. It mints its own publish-capable token from the
LiveKit API key/secret; viewers get subscribe-plus-data tokens from the
viewer app's server and can never publish media. Tracks are published under
the model's wire names, `main_video` and `main_audio`.

Chat rides the room's data channel on the `show.chat` topic as JSON
packets (`PROTOCOL.md`: `author` and `text` required, `v` and `source`
tags). The publisher hands every incoming
chat message to the registered handler (viewer ideas), and `send_chat`
lets the streamer answer — episode announcements, capacity notes, errors —
as the author "show".

Delivery rules:
  * `send_video` converts one rgb24 frame to RGBA and hands it to the
    `VideoSource` — a non-blocking FFI call.
  * `send_audio` enqueues one tick of samples for a pump task, because
    `AudioSource.capture_frame` awaits buffer room and must stay off the
    pacer's tick path. Overflow drops the oldest tick.
  * The LiveKit SDK resumes dropped connections on its own; if it gives up
    and disconnects, the publisher rebuilds the connection itself with a
    cooldown and a failure cap.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from livekit import api, rtc

logger = logging.getLogger(__name__)

CHAT_TOPIC = "show.chat"
STATE_TOPIC = "show.state"
STREAMER_AUTHOR = "show"

# Keep the room alive across streamer restarts; viewers waiting in an empty
# room should not be evicted while the streamer comes back.
_ROOM_EMPTY_TIMEOUT_S = 10 * 60

# Restart policy for a connection the SDK could not resume.
_RECONNECT_COOLDOWN_S = 5.0
_MAX_CONSECUTIVE_FAILURES = 5

# One audio entry per video tick; ~2 s absorbs a hiccup without adding latency.
_AUDIO_QUEUE_SECONDS = 2.0

_IDENTITY = "streamer"
_VIDEO_BITRATE_K = 4500

_CHAT_TEXT_MAX = 500


@dataclass(frozen=True)
class VideoFormat:
    """Geometry and rate of the paced video stream."""

    width: int
    height: int
    fps: int


@dataclass(frozen=True)
class AudioFormat:
    """Sample layout of the paced audio stream (int16 PCM)."""

    sample_rate: int
    channels: int


def _http_url(livekit_url: str) -> str:
    """The REST form of a LiveKit URL (`wss://` host -> `https://` host)."""
    for ws_scheme, http_scheme in (("wss://", "https://"), ("ws://", "http://")):
        if livekit_url.startswith(ws_scheme):
            return http_scheme + livekit_url[len(ws_scheme):]
    return livekit_url


class LiveKitPublisher:
    """Publish paced A/V as the single producer of one LiveKit room."""

    def __init__(
        self,
        *,
        room_name: str,
        livekit_url: str,
        api_key: str,
        api_secret: str,
    ) -> None:
        self._room_name = room_name
        self._url = livekit_url
        self._api_key = api_key
        self._api_secret = api_secret

        self._video: VideoFormat | None = None
        self._audio: AudioFormat | None = None
        self._room: rtc.Room | None = None
        self._video_source: rtc.VideoSource | None = None
        self._audio_source: rtc.AudioSource | None = None
        self._audio_queue: asyncio.Queue[bytes] | None = None
        self._on_chat: Callable[[str, str], None] | None = None
        self._tasks: list[asyncio.Task] = []
        self._disconnected = asyncio.Event()
        self._connected = False
        self._stopping = False
        self._frames_sent = 0
        self._audio_dropped = 0

    # ------------------------------------------------------------------ chat

    def on_chat(self, handler: Callable[[str, str], None]) -> None:
        """Register the chat handler, called as `handler(author, text)`.

        Messages authored by the streamer itself are not echoed back. The
        handler runs on the event loop and must not raise or block.
        """
        self._on_chat = handler

    def send_chat(self, text: str) -> None:
        """Say something in the room chat as the show. Non-blocking."""
        self._publish_chat({"v": 1, "source": "open-slop", "author": STREAMER_AUTHOR, "text": text})

    def publish_state(self, payload: dict) -> None:
        """Publish one `show.state` cursor packet. Non-blocking, best-effort.

        The cursor is a fresh snapshot every second, so a dropped packet costs
        nothing — the next tick supersedes it.
        """
        room = self._room
        if room is None or not self._connected:
            return

        async def _publish() -> None:
            try:
                await room.local_participant.publish_data(
                    json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    reliable=True,
                    topic=STATE_TOPIC,
                )
            except Exception as error:  # noqa: BLE001
                logger.debug("[livekit] state publish failed: %s", error)

        asyncio.get_running_loop().create_task(_publish())

    async def set_room_metadata(self, metadata: str) -> None:
        """Set the room's metadata (the rundown), delivered to viewers on join.

        Written through the server API, which the streamer is entitled to as the
        room's creator; viewers read it with no extra grant.
        """
        lkapi = api.LiveKitAPI(
            url=_http_url(self._url),
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        try:
            await lkapi.room.update_room_metadata(
                api.UpdateRoomMetadataRequest(room=self._room_name, metadata=metadata)
            )
        finally:
            await lkapi.aclose()

    def _publish_chat(self, message: dict) -> None:
        room = self._room
        if room is None or not self._connected:
            return

        async def _publish() -> None:
            try:
                await room.local_participant.publish_data(
                    json.dumps(message).encode("utf-8"),
                    reliable=True,
                    topic=CHAT_TOPIC,
                )
            except Exception as error:
                logger.warning("[livekit] chat publish failed: %s", error)

        asyncio.get_running_loop().create_task(_publish())

    def _handle_data(self, packet: rtc.DataPacket) -> None:
        if packet.topic != CHAT_TOPIC or self._on_chat is None:
            return
        try:
            message = json.loads(packet.data.decode("utf-8"))
            author = str(message.get("author", "")).strip()[:32]
            text = str(message.get("text", "")).strip()[:_CHAT_TEXT_MAX]
        except (ValueError, UnicodeDecodeError):
            return
        if not author or not text or author == STREAMER_AUTHOR:
            return
        self._on_chat(author, text)

    # ------------------------------------------------------------ lifecycle

    async def start(self, video: VideoFormat, audio: AudioFormat) -> None:
        """Create the room, connect, publish tracks, and start the pumps."""
        self._video = video
        self._audio = audio
        self._audio_queue = asyncio.Queue(maxsize=int(video.fps * _AUDIO_QUEUE_SECONDS))
        await self._ensure_livekit_room()
        await self._connect_and_publish()
        self._tasks = [
            asyncio.create_task(self._pump_audio(), name="livekit-audio"),
            asyncio.create_task(self._watch_connection(), name="livekit-watch"),
        ]

    async def _ensure_livekit_room(self) -> None:
        """Create the LiveKit room (idempotent) with a restart-friendly TTL."""
        lkapi = api.LiveKitAPI(
            url=_http_url(self._url),
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        try:
            await lkapi.room.create_room(
                api.CreateRoomRequest(
                    name=self._room_name, empty_timeout=_ROOM_EMPTY_TIMEOUT_S
                )
            )
        finally:
            await lkapi.aclose()

    def _publisher_token(self) -> str:
        """A fresh publish-capable token; minted per connection attempt."""
        return (
            api.AccessToken(self._api_key, self._api_secret)
            .with_identity(_IDENTITY)
            .with_name(_IDENTITY)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=self._room_name,
                    can_publish=True,
                    can_publish_data=True,
                    can_subscribe=False,
                )
            )
            .to_jwt()
        )

    async def _connect_and_publish(self) -> None:
        assert self._video and self._audio
        video, audio = self._video, self._audio

        room = rtc.Room()
        room.on("disconnected", lambda *_: self._disconnected.set())
        room.on("data_received", self._handle_data)
        await room.connect(self._url, self._publisher_token())

        video_source = rtc.VideoSource(video.width, video.height)
        video_track = rtc.LocalVideoTrack.create_video_track("main_video", video_source)
        await room.local_participant.publish_track(
            video_track,
            rtc.TrackPublishOptions(
                source=rtc.TrackSource.SOURCE_CAMERA,
                video_encoding=rtc.VideoEncoding(
                    max_framerate=video.fps,
                    max_bitrate=_VIDEO_BITRATE_K * 1000,
                ),
            ),
        )
        audio_source = rtc.AudioSource(audio.sample_rate, audio.channels)
        audio_track = rtc.LocalAudioTrack.create_audio_track("main_audio", audio_source)
        await room.local_participant.publish_track(
            audio_track,
            rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
        )

        self._room = room
        self._video_source = video_source
        self._audio_source = audio_source
        self._disconnected.clear()
        self._connected = True
        logger.info(
            "[livekit] publishing %dx%d@%dfps + %dHz mono to room %r on %s",
            video.width, video.height, video.fps, audio.sample_rate,
            self._room_name, self._url,
        )

    async def _watch_connection(self) -> None:
        """Rebuild the connection when the SDK's own resume gives up."""
        failures = 0
        while not self._stopping:
            await self._disconnected.wait()
            if self._stopping:
                return
            self._connected = False
            logger.warning("[livekit] room connection lost; rebuilding")
            await self._teardown_connection()
            while not self._stopping:
                await asyncio.sleep(_RECONNECT_COOLDOWN_S)
                try:
                    await self._ensure_livekit_room()
                    await self._connect_and_publish()
                    failures = 0
                    break
                except Exception as error:
                    failures += 1
                    logger.error(
                        "[livekit] reconnect failed (%d/%d): %s",
                        failures, _MAX_CONSECUTIVE_FAILURES, error,
                    )
                    if failures >= _MAX_CONSECUTIVE_FAILURES:
                        logger.error("[livekit] giving up on the room connection")
                        return

    async def _teardown_connection(self) -> None:
        room, self._room = self._room, None
        self._video_source = None
        self._audio_source = None
        if room is not None:
            try:
                await room.disconnect()
            except Exception:
                pass

    # ------------------------------------------------------------- delivery

    def send_video(self, frame: np.ndarray) -> None:
        """Accept one rgb24 frame; called once per period, never blocks."""
        source = self._video_source
        video = self._video
        if source is None or video is None or not self._connected:
            return
        if frame.shape[0] != video.height or frame.shape[1] != video.width:
            logger.error(
                "[livekit] refusing %sx%s frame (expected %dx%d)",
                frame.shape[1], frame.shape[0], video.width, video.height,
            )
            return
        rgba = np.empty((video.height, video.width, 4), dtype=np.uint8)
        rgba[:, :, :3] = frame
        rgba[:, :, 3] = 255
        source.capture_frame(
            rtc.VideoFrame(
                video.width, video.height, rtc.VideoBufferType.RGBA, rgba.tobytes()
            )
        )
        self._frames_sent += 1

    def send_audio(self, samples: np.ndarray) -> None:
        """Accept one tick of int16 mono samples; never blocks."""
        queue = self._audio_queue
        if queue is None:
            return
        payload = np.ascontiguousarray(samples, dtype=np.int16).tobytes()
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
                self._audio_dropped += 1
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                self._audio_dropped += 1

    async def _pump_audio(self) -> None:
        """Feed the AudioSource off the tick path; it awaits buffer room."""
        assert self._audio_queue is not None and self._audio is not None
        audio = self._audio
        bytes_per_sample = 2 * audio.channels
        while True:
            payload = await self._audio_queue.get()
            source = self._audio_source
            if source is None or not self._connected:
                continue
            frame = rtc.AudioFrame(
                data=payload,
                sample_rate=audio.sample_rate,
                num_channels=audio.channels,
                samples_per_channel=len(payload) // bytes_per_sample,
            )
            try:
                await source.capture_frame(frame)
            except Exception:
                # The watcher rebuilds the connection; dropping audio for a
                # tick is the correct behaviour meanwhile.
                pass

    async def stop(self) -> None:
        """Close the room connection and release resources. Idempotent."""
        self._stopping = True
        self._disconnected.set()  # release the watcher
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        await self._teardown_connection()
        logger.info("[livekit] stopped after %d frames", self._frames_sent)
