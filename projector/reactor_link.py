"""The Reactor side: one supervised connection to the fast-h3 model.

`ReactorLink` owns everything that touches `reactor_sdk`:

  * the connect/reconnect loop — the streamer keeps trying forever, and a
    dropped session is rebuilt from scratch (the model's queues die with a
    session server-side), while the pacer and the LiveKit publisher outside
    this class keep the broadcast alive;
  * the media path — the model's video and audio tracks feed the pacer;
  * a live mirror of the model's `state_update` / `queue_update`, so the
    rest of the streamer reads state instead of re-deriving it;
  * a fan-out of every model message to registered listeners.

The contract this speaks is the fast-h3 clip queue: `enqueue` replies
`clip_queued`, builds cross into the playout queue on `clip_generated`, and
with autoplay on (this streamer's mode) the front of the playout queue
starts on its own the instant the stream idles. A scene enqueued with
`continue_from_clip_id` opens on the named clip's last frame, and autoplay
hands a continuing scene over seamlessly — no cut to black. That chaining
is what turns an episode's scenes into one uninterrupted video.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from reactor_sdk import Reactor, ReactorStatus

from config import Config
from pacer import Pacer

logger = logging.getLogger(__name__)

RECONNECT_DELAY_S = 5.0

# fast-h3's fixed output timing. The canvas (width/height) is read from
# state_update instead — it depends on the deployment's aspect — but the
# rates are pinned by the model.
MODEL_FPS = 24
MODEL_SAMPLE_RATE = 48_000

# The model's hard cap on one scene prompt, enforced server-side.
MAX_PROMPT_CHARS = 800

# Defaults used only until the first state_update arrives.
_DEFAULT_STATE: dict[str, Any] = {
    "width": 1344,
    "height": 768,
    "clip_seconds_min": 5.167,
    "clip_seconds_max": 14.375,
    "generation_queued": 0,
    "generation_capacity": 20,
    "playout_queued": 0,
    "playout_capacity": 10,
}


def payload(reply: Any) -> Any:
    """Unwrap a send_command reply envelope ({"type", "data"}) to its data."""
    if isinstance(reply, dict) and "data" in reply and "type" in reply:
        return reply["data"]
    return reply


class ReactorLink:
    """Supervised fast-h3 session: media into the pacer, commands out."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._pacer: Pacer | None = None
        self._reactor: Reactor | None = None
        self._ready = asyncio.Event()
        self._first_state = asyncio.Event()
        self._listeners: list[Callable[[str, dict], None]] = []
        self.state: dict[str, Any] = dict(_DEFAULT_STATE)
        self.generation_clips: list[dict] = []
        self.playout_clips: list[dict] = []

    # -------------------------------------------------------------- wiring

    def attach_pacer(self, pacer: Pacer) -> None:
        """Point the media path at the pacer (built after the first state)."""
        self._pacer = pacer

    def add_listener(self, listener: Callable[[str, dict], None]) -> None:
        """Register for every model message as `(kind, data)`. Must not raise."""
        self._listeners.append(listener)

    # ------------------------------------------------------- state mirror

    @property
    def min_seconds(self) -> float:
        return float(self.state.get("clip_seconds_min", 5.167))

    @property
    def max_seconds(self) -> float:
        return float(self.state.get("clip_seconds_max", 14.375))

    @property
    def generation_queued(self) -> int:
        return int(self.state.get("generation_queued", 0))

    @property
    def generation_capacity(self) -> int:
        return int(self.state.get("generation_capacity", 20))

    @property
    def playout_queued(self) -> int:
        return int(self.state.get("playout_queued", 0))

    @property
    def playout_capacity(self) -> int:
        return int(self.state.get("playout_capacity", 10))

    @property
    def canvas(self) -> tuple[int, int]:
        """(width, height) the deployment generates at."""
        return int(self.state["width"]), int(self.state["height"])

    @property
    def supports_continuation(self) -> bool:
        """Whether the deployment supports `continue_from_clip_id`.

        Detected from a field only the continuation-capable contract
        publishes in `state_update` — never assumed from the model name.
        When false, episodes fall back to independent scenes with a cut to
        black between them.
        """
        return "flush_on_clip_end" in self.state

    @property
    def connected(self) -> bool:
        """Whether a session is live right now (commands would go through)."""
        return self._ready.is_set()

    async def wait_first_state(self) -> None:
        """Resolve once the first session delivered its `state_update`."""
        await self._first_state.wait()

    def _on_message(self, message: Any) -> None:
        if not isinstance(message, dict):
            return
        kind = message.get("type")
        data = message.get("data") or {}
        if kind == "state_update":
            self.state = data
        elif kind == "queue_update":
            self.generation_clips = data.get("generation", [])
            self.playout_clips = data.get("playout", [])
        elif kind == "command_error":
            logger.warning(
                "[reactor] command refused: %s — %s",
                data.get("command"), data.get("reason"),
            )
        for listener in self._listeners:
            listener(kind, data)

    # ------------------------------------------------------------ commands

    async def send_command(self, command: str, data: dict) -> Any:
        """Send one command on the live session; None when disconnected.

        Waits for a session to exist first, so callers ride out a reconnect
        instead of failing. A None / bodyless reply means the model refused
        the command (it broadcast `command_error` with the reason).
        """
        await self._ready.wait()
        reactor = self._reactor
        if reactor is None:
            return None
        try:
            return payload(await reactor.send_command(command, data))
        except Exception as error:
            logger.warning("[reactor] %s failed: %s", command, error)
            return None

    # ----------------------------------------------------------- lifecycle

    async def run(self) -> None:
        """Connect, and keep reconnecting forever. Cancelled only at shutdown.

        A failed connect (the model at capacity, a network blip, a session
        that never turns ready) is logged and retried on a fixed delay; the
        broadcast side keeps showing the last frame meanwhile.
        """
        while True:
            try:
                await self._run_session()
            except asyncio.CancelledError:
                await self._teardown()
                raise
            except Exception as error:
                logger.error("[reactor] session error: %s", error)
                await self._teardown()
            logger.info("[reactor] reconnecting in %.0fs", RECONNECT_DELAY_S)
            await asyncio.sleep(RECONNECT_DELAY_S)

    async def _run_session(self) -> None:
        reactor = Reactor(
            self._config.reactor_model, api_key=self._config.reactor_api_key
        )
        disconnected = asyncio.Event()

        reactor.on("message", self._on_message)
        reactor.on_status(self._make_status_handler(disconnected))
        # Registered by wire name *before* connect: the SDK allows handler
        # registration ahead of the session declaring its tracks, whereas
        # querying `reactor.tracks` right after connect races that
        # declaration (an empty list on a slow session start).
        reactor.track("main_video").on_frame(self._on_video_frame)
        reactor.track("main_audio").on_frame(self._on_audio_frame)

        logger.info("[reactor] connecting to %s...", self._config.reactor_model)
        await reactor.connect()
        logger.info(
            "[reactor] connected, session=%s status=%s",
            reactor.session_id, reactor.status,
        )

        self._reactor = reactor
        state = await asyncio.wait_for(self._raw_command(reactor, "get_state"), 30)
        if isinstance(state, dict) and "width" in state:
            self.state = state
        logger.info(
            "[reactor] canvas %dx%d, clip range %.3f-%.3fs, "
            "generation %d/%d, playout %d/%d, continuation %s",
            *self.canvas, self.min_seconds, self.max_seconds,
            self.generation_queued, self.generation_capacity,
            self.playout_queued, self.playout_capacity,
            "supported" if self.supports_continuation else "unsupported",
        )

        # Autoplay on: the model starts the playout queue's front clip the
        # instant the stream idles, which keeps scene-to-scene gaps at
        # milliseconds — and hands a continuing scene over with no cut at
        # all. The streamer only decides what enters the queue and where.
        await self._raw_command(reactor, "set_autoplay", {"enabled": True})
        self._first_state.set()
        self._ready.set()
        try:
            await disconnected.wait()
            logger.warning("[reactor] session disconnected")
        finally:
            await self._teardown()

    @staticmethod
    def _make_status_handler(disconnected: asyncio.Event):
        loop = asyncio.get_running_loop()

        def on_status(status: ReactorStatus) -> None:
            logger.info("[reactor] status: %s", status.value)
            if status == ReactorStatus.DISCONNECTED:
                loop.call_soon_threadsafe(disconnected.set)

        return on_status

    @staticmethod
    async def _raw_command(reactor: Reactor, command: str, data: dict | None = None) -> Any:
        return payload(await reactor.send_command(command, data or {}))

    async def _teardown(self) -> None:
        self._ready.clear()
        # The queues died with the session; a stale mirror would make the
        # director believe scenes are still queued.
        self.generation_clips = []
        self.playout_clips = []
        reactor, self._reactor = self._reactor, None
        if reactor is None:
            return
        try:
            await reactor.disconnect()
        except Exception as error:
            logger.warning("[reactor] disconnect failed: %s", error)

    # ---------------------------------------------------------- media path

    def _on_video_frame(self, frame) -> None:
        if self._pacer is not None:
            self._pacer.submit_video(frame)

    def _on_audio_frame(self, frame, sample_rate=MODEL_SAMPLE_RATE) -> None:
        if sample_rate != MODEL_SAMPLE_RATE:
            logger.warning(
                "[reactor] audio at %dHz, expected %d — timing will drift",
                sample_rate, MODEL_SAMPLE_RATE,
            )
        if self._pacer is not None:
            self._pacer.submit_audio(frame)
