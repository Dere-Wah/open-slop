"""What the viewer knows: a live cursor at 1 Hz, and the rundown on join.

Two facts reach the viewer, and each rides the transport that fits it.

The **cursor** — which scene is on air and when the film loops — is small and
changes every second, so it goes out as a data packet on the `show.state`
topic once a second. The model gives no playhead, so the countdown is derived:
on every `clip_started` the projectionist hands over a fresh anchor (wall time,
this clip's length, and the seconds of film left after it), and the end time is
recomputed from that. Re-anchoring per scene keeps stall drift from compounding
across a screening. Between clips the countdown reads "at least", because a
build may not be ready the instant the last clip ends — after a short grace, so
the seamless handover between two chained clips, where `clip_finished` and the
next `clip_started` arrive milliseconds apart, never flickers.

The cursor has five statuses. `live` is a scene on air. `warming` is the time
before the model has answered, or while the story cannot be read; the packet
carries a `detail` line saying which. `loading` is the curtain: the model is
connected and building the screening's opening clips, and nothing plays until
enough film is buffered that playout cannot outrun the builds; the packet
carries how much is built against the target so the viewer can draw it.
`downtime` is the model's session having been lost: everything queued died
with it, and the screening that was on air will play again from the top once
the model is back — through `loading` again. `intermission` is the loop point:
a screening's last clip has ended and the stream is held for a fixed pause
before the next screening's first frame; the packet says which screening ended,
when the next one resumes, and how much of its opening is built. The viewer
shows each as what it is rather than a frozen countdown.

The **rundown** — every scene, its length, and everyone who wrote it — is large
and changes once a screening, so it goes into LiveKit room metadata. Room
metadata is retained and delivered to a participant on join, so a late viewer
gets the whole rundown as part of connecting, with no request to GitHub and no
polling. It holds 512 KiB, which is thousands of scenes; past a budget under
that cap the payload sheds its contributor lists, then its tail, and says so.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

from publisher import LiveKitPublisher
from story import Rundown

logger = logging.getLogger(__name__)

STATE_TOPIC = "show.state"
_TICK_S = 1.0

# A clip_finished with no clip_started this long after it is a real gap.
_STALL_GRACE_S = 1.5

# LiveKit caps room metadata at 512 KiB; stay well under it.
_METADATA_BUDGET_BYTES = 480_000


@dataclass
class Cursor:
    """The anchor for the currently-playing scene, set on each `clip_started`."""

    screening: int
    sha: str
    episode_index: int
    episodes_total: int
    episode_title: str
    episode_file: str
    scene_number: int
    scene_count: int
    global_index: int
    global_total: int
    author: str
    author_url: str | None
    commit: str
    commit_url: str | None
    started_wall: float  # epoch seconds when this clip started playing
    clip_seconds: float
    remaining_after: float  # seconds of film after this scene, this screening
    scene_offset: float  # seconds of film before this scene, this screening
    screening_total: float
    next_sha: str | None = None  # the sha the next screening was snapshotted at, if known
    intermission_seconds: float = 0.0  # the pause between this screening's end and the next


@dataclass
class Intermission:
    """The loop point: one screening has ended, the next starts after a pause."""

    ended_screening: int
    resumes_at: float  # epoch seconds when the next screening's first frame is due
    hold_seconds: float  # the whole pause, for drawing its progress
    screening: int | None  # the next screening, once snapshotted
    sha: str | None
    episode_title: str  # what the next screening opens on
    buffered_seconds: float  # of the next screening's opening, built so far
    target_seconds: float
    film_seconds: float
    scene_total: int


@dataclass
class Loading:
    """The curtain: how much of the screening's opening is built so far."""

    screening: int
    sha: str
    episode_title: str  # the film's first episode, what the screening opens on
    buffered_seconds: float  # film built and waiting in the playout queue
    target_seconds: float  # what must be built before the first frame goes out
    film_seconds: float
    scene_total: int
    restart: bool  # this screening was on air and is starting over


class Broadcast:
    """Publish the 1 Hz cursor and the per-screening rundown to the room."""

    def __init__(self, publisher: LiveKitPublisher) -> None:
        self._pub = publisher
        self._cursor: Cursor | None = None
        self._loading: Loading | None = None
        self._intermission: Intermission | None = None
        self._status = "warming"  # warming | loading | intermission | downtime | live
        self._notice: str | None = None
        self._stall_since: float | None = None
        self._pending: tuple[int, Rundown] | None = None
        self._published_screening: int | None = None

    # --------------------------------------------------------- from screening

    def update(self, cursor: Cursor) -> None:
        """Anchor the countdown to a freshly started clip."""
        self._cursor = cursor
        self._loading = None
        self._intermission = None
        self._status = "live"
        self._notice = None
        self._stall_since = None

    def mark_stalled(self) -> None:
        """A clip finished and the next is not on air yet; countdown is a floor."""
        if self._stall_since is None:
            self._stall_since = time.time()

    def mark_loading(self, loading: Loading) -> None:
        """The curtain is down: the opening is being built; say how far along."""
        self._cursor = None
        self._loading = loading
        self._intermission = None
        self._status = "loading"
        self._notice = None
        self._stall_since = None

    def mark_intermission(self, intermission: Intermission) -> None:
        """A screening has ended; the next starts after the pause."""
        self._cursor = None
        self._loading = None
        self._intermission = intermission
        self._status = "intermission"
        self._notice = None
        self._stall_since = None

    def mark_downtime(self) -> None:
        """The model's session is gone; the screening will restart from the top."""
        self._cursor = None
        self._loading = None
        self._intermission = None
        self._status = "downtime"
        self._notice = None
        self._stall_since = None

    def set_notice(self, detail: str) -> None:
        """Say why nothing is on air yet (only shown while not live)."""
        self._notice = detail

    def set_rundown(self, screening_id: int, rundown: Rundown) -> None:
        """Register the screening's rundown for the next room-metadata write.

        Called when the screening's first clip starts playing, so the rundown
        the room carries is always the one on air.
        """
        self._pending = (screening_id, rundown)

    # ------------------------------------------------------------- the 1 Hz loop

    async def run(self) -> None:
        while True:
            await self._maybe_write_rundown()
            self._publish_cursor()
            await asyncio.sleep(_TICK_S)

    def _publish_cursor(self) -> None:
        now = time.time()
        cursor = self._cursor
        loading = self._loading
        if self._status == "loading" and loading is not None:
            packet = {
                "v": 1,
                "topic": "state",
                "status": "loading",
                "screening": loading.screening,
                "sha": loading.sha,
                "episode_title": loading.episode_title,
                "buffered_seconds": round(loading.buffered_seconds, 3),
                "target_seconds": round(loading.target_seconds, 3),
                "film_seconds": round(loading.film_seconds, 3),
                "scene_total": loading.scene_total,
                "restart": loading.restart,
                "stalled": True,
                "now": _ms(now),
            }
            self._pub.publish_state(packet)
            return
        intermission = self._intermission
        if self._status == "intermission" and intermission is not None:
            packet = {
                "v": 1,
                "topic": "state",
                "status": "intermission",
                "ended_screening": intermission.ended_screening,
                "resumes_at": _ms(intermission.resumes_at),
                "hold_seconds": round(intermission.hold_seconds, 3),
                "buffered_seconds": round(intermission.buffered_seconds, 3),
                "target_seconds": round(intermission.target_seconds, 3),
                "film_seconds": round(intermission.film_seconds, 3),
                "scene_total": intermission.scene_total,
                "episode_title": intermission.episode_title,
                # A floor only while the next opening is still being built.
                "stalled": intermission.buffered_seconds + 1e-6 < intermission.target_seconds,
                "now": _ms(now),
            }
            if intermission.screening is not None:
                packet["screening"] = intermission.screening
                packet["sha"] = intermission.sha
            self._pub.publish_state(packet)
            return
        if cursor is None or self._status != "live":
            packet = {
                "v": 1,
                "topic": "state",
                "status": self._status,
                "stalled": True,
                "now": _ms(now),
            }
            if self._notice:
                packet["detail"] = self._notice
            elif self._status == "downtime":
                packet["detail"] = "the model was lost; this screening restarts from the top"
            self._pub.publish_state(packet)
            return

        ends_at = cursor.started_wall + cursor.clip_seconds + cursor.remaining_after
        elapsed = min(max(now - cursor.started_wall, 0.0), cursor.clip_seconds)
        played = cursor.scene_offset + elapsed
        progress = played / cursor.screening_total if cursor.screening_total > 0 else 0.0
        stalled = self._stall_since is not None and now - self._stall_since > _STALL_GRACE_S
        packet = {
            "v": 1,
            "topic": "state",
            "status": "live",
            "screening": cursor.screening,
            "sha": cursor.sha,
            "episode_index": cursor.episode_index,
            "episodes_total": cursor.episodes_total,
            "episode_title": cursor.episode_title,
            "episode_file": cursor.episode_file,
            "scene_number": cursor.scene_number,
            "scene_count": cursor.scene_count,
            "global_index": cursor.global_index,
            "global_total": cursor.global_total,
            "author": cursor.author,
            "author_url": cursor.author_url,
            "commit": cursor.commit,
            "commit_url": cursor.commit_url,
            "now": _ms(now),
            "ends_at": _ms(ends_at),
            "next_start_at": _ms(ends_at + cursor.intermission_seconds),
            "stalled": stalled,
            "progress": round(progress, 4),
        }
        if cursor.next_sha:
            packet["next_sha"] = cursor.next_sha
        self._pub.publish_state(packet)

    async def _maybe_write_rundown(self) -> None:
        if self._pending is None:
            return
        screening_id, rundown = self._pending
        if screening_id == self._published_screening:
            return
        payload = rundown_payload(screening_id, rundown)
        try:
            await self._pub.set_room_metadata(payload)
            self._published_screening = screening_id
            logger.info(
                "[broadcast] wrote rundown for screening %d (%d bytes)",
                screening_id,
                len(payload),
            )
        except Exception as error:  # noqa: BLE001 — a failed write retries next tick
            logger.warning("[broadcast] room metadata write failed: %s", error)


def _ms(epoch_seconds: float) -> int:
    return int(epoch_seconds * 1000)


def rundown_payload(screening_id: int, rundown: Rundown) -> str:
    """The room-metadata JSON: display data for every scene, no prompt bodies.

    Fits the LiveKit budget by degrees: full detail first; then without the
    per-scene contributor lists; then with episodes cut from the tail and
    `truncated: true` set, so the viewer can say the list is incomplete.
    """
    full = _rundown_dict(screening_id, rundown, contributors=True)
    payload = _dump(full)
    if len(payload.encode("utf-8")) <= _METADATA_BUDGET_BYTES:
        return payload

    slim = _rundown_dict(screening_id, rundown, contributors=False)
    payload = _dump(slim)
    if len(payload.encode("utf-8")) <= _METADATA_BUDGET_BYTES:
        logger.warning("[broadcast] rundown too large with contributors; publishing without")
        return payload

    slim["truncated"] = True
    while slim["episodes"] and len(_dump(slim).encode("utf-8")) > _METADATA_BUDGET_BYTES:
        slim["episodes"].pop()
    logger.warning(
        "[broadcast] rundown truncated to %d of %d episodes to fit room metadata",
        len(slim["episodes"]),
        len(rundown.episodes),
    )
    return _dump(slim)


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _rundown_dict(screening_id: int, rundown: Rundown, *, contributors: bool) -> dict:
    episodes = []
    for episode in rundown.episodes:
        scenes = []
        for scene in episode.scenes:
            entry = {
                "n": scene.scene_number,
                "seconds": scene.seconds,
                "author": scene.author.display,
                "author_url": scene.author.url,
                "commit": scene.commit,
                "commit_url": scene.commit_url,
                "contributors": (
                    [{"name": person.display, "url": person.url} for person in scene.contributors]
                    if contributors
                    else []
                ),
            }
            scenes.append(entry)
        episodes.append(
            {
                "i": episode.index,
                "file": episode.file,
                "title": episode.title,
                "seconds": round(episode.seconds, 3),
                "scenes": scenes,
            }
        )
    return {
        "v": 1,
        "screening": screening_id,
        "sha": rundown.sha,
        "story_url": rundown.story_url,
        "total_seconds": round(rundown.total_seconds, 3),
        "episodes": episodes,
    }
