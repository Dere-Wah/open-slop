"""The projectionist: read the film, keep the model's queue fed, run the loop.

One `Screening` is the only writer to the model's queue. It walks the film in
order, enqueuing each scene at its own seed and length, chaining the scenes a
contributor marked `continue: true` into one unbroken take and cutting to black
where they did not. When the film's scenes run out it reads the story branch
again and begins the next screening — so a pull request merged mid-screening
airs at the next one, never mid-film, and the next screening's opening clips
build while the last one still plays, leaving no dead air at the loop.

The projectionist also narrates. It reads its own metadata echo back off each
`clip_started`, works out where that clip sits in its screening, and hands the
broadcaster a cursor: which scene is on air, who wrote it, and how long until
the film loops. It keeps no scheduling state the model's queue does not already
hold, beyond the small per-screening tables the cursor and the room rundown are
built from.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict

from broadcast import Broadcast, Cursor
from reactor_link import ReactorLink
from story import Rundown, Scene, StorySource

logger = logging.getLogger(__name__)

# Headroom kept in the generation queue: fill to capacity minus this, so a
# built clip always has somewhere to land and builds never pause on a full
# playout queue.
_GEN_HEADROOM = 2

# How often the feeder re-checks queue depth when it is already full enough.
_POLL_S = 2.0

# Enqueue retry cadence while the model refuses (a reconnect mid-command, a
# lost source clip for a chain).
_RETRY_DELAY_S = 3.0
_MAX_REFUSALS = 3

# Bounds on the small correlation tables, so a long-running channel does not
# grow them without limit.
_MAX_TRACKED_CLIPS = 256
_MAX_TRACKED_SCREENINGS = 3


class Screening:
    """Feed the model's queue from the story branch, screening after screening."""

    def __init__(
        self,
        link: ReactorLink,
        story: StorySource,
        broadcast: Broadcast,
    ) -> None:
        self._link = link
        self._story = story
        self._broadcast = broadcast
        self._feed = self._scene_feed()
        self._last_good: Rundown | None = None
        # clip_id -> (screening_id, scene); the correlation for narration.
        self._by_clip: "OrderedDict[str, tuple[int, Scene]]" = OrderedDict()
        # screening_id -> its scenes in play order; the cursor reads durations here.
        self._screening_scenes: "OrderedDict[int, list[Scene]]" = OrderedDict()
        self._last_clip_id: str | None = None
        link.add_listener(self._on_model_message)

    # -------------------------------------------------------------- the feed

    async def _read_story(self) -> Rundown:
        """Read the story tip off-thread; hold the last good film on failure."""
        loop = asyncio.get_running_loop()
        try:
            rundown = await loop.run_in_executor(None, self._story.read)
            self._last_good = rundown
            return rundown
        except Exception as error:  # noqa: BLE001 — a bad tip must never stop the show
            logger.error("[screening] could not read the story: %s", error)
            if self._last_good is not None:
                logger.warning("[screening] airing the last good film instead")
                return self._last_good
            raise

    async def _scene_feed(self):
        """Yield `(screening_id, rundown, scene)` forever, re-reading each pass."""
        screening_id = 0
        while True:
            screening_id += 1
            rundown = await self._read_story()
            if not rundown.scenes:
                logger.warning("[screening] the film has no scenes; waiting")
                await asyncio.sleep(_POLL_S)
                screening_id -= 1
                continue
            self._register_screening(screening_id, rundown)
            logger.info(
                "[screening] screening %d begins: %d scene(s) at %s",
                screening_id,
                len(rundown.scenes),
                rundown.sha,
            )
            for scene in rundown.scenes:
                yield screening_id, rundown, scene

    def _register_screening(self, screening_id: int, rundown: Rundown) -> None:
        self._screening_scenes[screening_id] = rundown.scenes
        while len(self._screening_scenes) > _MAX_TRACKED_SCREENINGS:
            self._screening_scenes.popitem(last=False)
        # The broadcaster writes the room rundown once per screening.
        self._broadcast.set_rundown(screening_id, rundown)

    # ------------------------------------------------------------- the driver

    async def run(self) -> None:
        """Keep the generation queue fed, screening after screening, forever."""
        await self._link.wait_first_state()
        while True:
            if not self._link.connected:
                await asyncio.sleep(1.0)
                continue
            gen_target = max(1, self._link.generation_capacity - _GEN_HEADROOM)
            play_target = max(1, self._link.playout_capacity - 1)
            if (
                self._link.generation_queued < gen_target
                and self._link.playout_queued < play_target
            ):
                screening_id, rundown, scene = await self._feed.__anext__()
                await self._enqueue(screening_id, rundown, scene)
            else:
                await asyncio.sleep(_POLL_S)

    async def _enqueue(self, screening_id: int, rundown: Rundown, scene: Scene) -> None:
        """Enqueue one scene: seed, length, metadata, and the chain when asked."""
        payload = {
            "prompt": scene.prompt,
            "seed": scene.seed,
            "seconds": scene.seconds,
            "metadata": self._metadata(screening_id, rundown, scene),
        }
        chained = (
            scene.continued
            and self._link.supports_continuation
            and self._last_clip_id is not None
        )
        if chained:
            payload["continue_from_clip_id"] = self._last_clip_id

        clip_id = await self._enqueue_with_retries(payload, screening_id, scene)
        if clip_id is None:
            logger.error(
                "[screening] scene %d/%d of %r was refused; dropping it",
                scene.scene_number,
                scene.scene_count,
                scene.episode_file,
            )
            self._last_clip_id = None  # the chain is broken; the next scene starts fresh
            return

        self._last_clip_id = clip_id
        self._by_clip[clip_id] = (screening_id, scene)
        while len(self._by_clip) > _MAX_TRACKED_CLIPS:
            self._by_clip.popitem(last=False)

    async def _enqueue_with_retries(
        self, payload: dict, screening_id: int, scene: Scene
    ) -> str | None:
        """Enqueue with bounded retries; drop the chain before dropping the scene."""
        refusals = 0
        while refusals < _MAX_REFUSALS:
            reply = await self._link.send_command("enqueue", payload)
            if isinstance(reply, dict) and "clip" in reply:
                clip = reply["clip"]
                logger.info(
                    "[screening] queued s%d %s scene %d/%d as %s (seed %d, %.3fs)%s",
                    screening_id,
                    scene.episode_file,
                    scene.scene_number,
                    scene.scene_count,
                    clip["clip_id"][:8],
                    scene.seed,
                    scene.seconds,
                    " ← chained" if payload.get("continue_from_clip_id") else "",
                )
                return clip["clip_id"]
            refusals += 1
            if refusals == 2 and "continue_from_clip_id" in payload:
                del payload["continue_from_clip_id"]
                logger.warning(
                    "[screening] %s scene %d: dropping the continuation after two refusals, "
                    "retrying standalone",
                    scene.episode_file,
                    scene.scene_number,
                )
            await asyncio.sleep(_RETRY_DELAY_S)
        return None

    # -------------------------------------------------------------- metadata

    def _metadata(self, screening_id: int, rundown: Rundown, scene: Scene) -> str:
        """The opaque echo the model returns on every message about this clip.

        Carries the primary credit only — the full contributor list rides the
        room rundown, which has room the 2000-char wire field does not.
        """
        tag = {
            "v": 1,
            "screening": screening_id,
            "sha": rundown.sha,
            "ep": scene.episode_index,
            "eps": len(rundown.episodes),
            "epf": scene.episode_file,
            "title": scene.episode_title or scene.episode_file,
            "sc": scene.scene_number,
            "scs": scene.scene_count,
            "gi": scene.global_index,
            "gn": len(rundown.scenes),
            "seed": scene.seed,
            "cont": scene.continued,
            "author": scene.author.display,
            "url": scene.author.url,
            "commit": scene.commit,
            "commit_url": scene.commit_url,
        }
        return json.dumps(tag, ensure_ascii=False)

    # ------------------------------------------------------------- narration

    def _on_model_message(self, kind: str, data: dict) -> None:
        clip = data.get("clip") if isinstance(data, dict) else None
        if not isinstance(clip, dict):
            return
        tag = _parse_tag(clip)
        if tag is None:
            return
        if kind == "clip_started":
            self._on_started(tag, clip)
        elif kind in ("clip_finished", "clip_stopped"):
            # Between clips: the broadcaster reads the countdown as "at least"
            # until the next clip anchors it again.
            self._broadcast.mark_stalled()
        elif kind == "clip_failed":
            logger.error(
                "[screening] render failed for %s scene %s/%s: %s",
                tag.get("epf"),
                tag.get("sc"),
                tag.get("scs"),
                data.get("reason"),
            )

    def _on_started(self, tag: dict, clip: dict) -> None:
        screening_id = tag.get("screening")
        global_index = tag.get("gi", 0)
        scenes = self._screening_scenes.get(screening_id, [])
        if scenes and 0 <= global_index < len(scenes):
            offset = sum(scene.seconds for scene in scenes[:global_index])
            remaining_after = sum(scene.seconds for scene in scenes[global_index + 1 :])
            screening_total = sum(scene.seconds for scene in scenes)
        else:
            offset = 0.0
            remaining_after = 0.0
            screening_total = float(clip.get("seconds", 0.0))

        cursor = Cursor(
            screening=screening_id or 0,
            sha=tag.get("sha", ""),
            episode_index=tag.get("ep", 0),
            episodes_total=tag.get("eps", 1),
            episode_title=tag.get("title", ""),
            episode_file=tag.get("epf", ""),
            scene_number=tag.get("sc", 1),
            scene_count=tag.get("scs", 1),
            global_index=global_index,
            global_total=tag.get("gn", 1),
            author=tag.get("author", ""),
            author_url=tag.get("url"),
            commit=tag.get("commit", ""),
            commit_url=tag.get("commit_url"),
            started_wall=time.time(),
            clip_seconds=float(clip.get("seconds", 0.0)),
            remaining_after=remaining_after,
            scene_offset=offset,
            screening_total=screening_total,
            stalled=False,
        )
        logger.info(
            "[now playing] s%d %s scene %d/%d by %s",
            cursor.screening,
            cursor.episode_file,
            cursor.scene_number,
            cursor.scene_count,
            cursor.author,
        )
        self._broadcast.update(cursor)


def _parse_tag(clip: dict) -> dict | None:
    """Read this projector's metadata tag back off a clip echo."""
    try:
        tag = json.loads(clip.get("metadata") or "")
    except (TypeError, ValueError):
        return None
    if not isinstance(tag, dict) or "screening" not in tag:
        return None
    return tag
