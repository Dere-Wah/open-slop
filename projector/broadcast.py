"""What the viewer knows: a live cursor at 1 Hz, and the rundown on join.

Two facts reach the viewer, and each rides the transport that fits it.

The **cursor** — which scene is on air and when the film loops — is small and
changes every second, so it goes out as a data packet on the `show.state`
topic once a second. The model gives no playhead, so the countdown is derived:
on every `clip_started` the projectionist hands over a fresh anchor (wall time,
this clip's length, and the seconds of film left after it), and the end time is
recomputed from that. Re-anchoring per scene keeps stall drift from compounding
across a screening. Between clips the countdown reads "at least", because a
build may not be ready the instant the last clip ends.

The **rundown** — every scene, its length, and everyone who wrote it — is large
and changes once a screening, so it goes into LiveKit room metadata. Room
metadata is retained and delivered to a participant on join, so a late viewer
gets the whole rundown as part of connecting, with no request to GitHub and no
polling. It holds 512 KiB, which is thousands of scenes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from publisher import LiveKitPublisher
from story import Rundown

logger = logging.getLogger(__name__)

STATE_TOPIC = "show.state"
_TICK_S = 1.0


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
    stalled: bool = False


class Broadcast:
    """Publish the 1 Hz cursor and the per-screening rundown to the room."""

    def __init__(self, publisher: LiveKitPublisher) -> None:
        self._pub = publisher
        self._cursor: Cursor | None = None
        self._stalled = True  # true until the first clip anchors the countdown
        self._pending: tuple[int, Rundown] | None = None
        self._published_screening: int | None = None

    # --------------------------------------------------------- from screening

    def update(self, cursor: Cursor) -> None:
        """Anchor the countdown to a freshly started clip."""
        self._cursor = cursor
        self._stalled = False

    def mark_stalled(self) -> None:
        """A clip finished and the next is not on air yet; countdown is a floor."""
        self._stalled = True

    def set_rundown(self, screening_id: int, rundown: Rundown) -> None:
        """Register the screening's rundown for the next room-metadata write."""
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
        if cursor is None:
            self._pub.publish_state(
                {"v": 1, "topic": "state", "status": "warming", "stalled": True, "now": _ms(now)}
            )
            return

        ends_at = cursor.started_wall + cursor.clip_seconds + cursor.remaining_after
        elapsed = min(max(now - cursor.started_wall, 0.0), cursor.clip_seconds)
        played = cursor.scene_offset + elapsed
        progress = played / cursor.screening_total if cursor.screening_total > 0 else 0.0
        self._pub.publish_state(
            {
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
                "stalled": self._stalled,
                "progress": round(progress, 4),
            }
        )

    async def _maybe_write_rundown(self) -> None:
        if self._pending is None:
            return
        screening_id, rundown = self._pending
        if screening_id == self._published_screening:
            return
        payload = _rundown_payload(screening_id, rundown)
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


def _rundown_payload(screening_id: int, rundown: Rundown) -> str:
    """The room-metadata JSON: display data for every scene, no prompt bodies."""
    episodes = []
    for episode in rundown.episodes:
        scenes = []
        for scene in episode.scenes:
            scenes.append(
                {
                    "n": scene.scene_number,
                    "seconds": scene.seconds,
                    "author": scene.author.display,
                    "author_url": scene.author.url,
                    "commit": scene.commit,
                    "commit_url": scene.commit_url,
                    "contributors": [
                        {"name": person.display, "url": person.url}
                        for person in scene.contributors
                    ],
                }
            )
        episodes.append(
            {
                "i": episode.index,
                "file": episode.file,
                "title": episode.title,
                "seconds": round(episode.seconds, 3),
                "scenes": scenes,
            }
        )
    return json.dumps(
        {
            "v": 1,
            "screening": screening_id,
            "sha": rundown.sha,
            "story_url": rundown.story_url,
            "total_seconds": round(rundown.total_seconds, 3),
            "episodes": episodes,
        },
        ensure_ascii=False,
    )
