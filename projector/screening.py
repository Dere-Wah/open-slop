"""The projectionist: snapshot the film, keep the model's queue fed, run the loop.

One `Screening` is the only writer to the model's queue. The unit it works in
is a **reel**: one reading of the story branch, taken at one moment, listing
every scene that screening will play. A reel is snapshotted once and then
enqueued a scene at a time, because the model's queue is small — it holds a
bounded number of prompts waiting to build and a bounded number of built clips
waiting to play (about a gigabyte each), and `enqueue` is refused past those
caps. So the projectionist cannot hand the model a whole film; it hands it the
next scene whenever the queue has room, reading from the reel.

When does the branch get read? When the current reel has been fully enqueued
and the queue asks for more. The feed keeps a fixed pre-roll ahead of playout
(`PREROLL_SECONDS`), so that moment lands a predictable lead before the next
screening starts on air: the snapshot for screening N+1 is taken while the
tail of screening N is still queued. A pull request merged before that
snapshot airs in N+1; one merged after it airs in N+2. The lead is the price of
never having dead air at the loop, and it is stated to viewers rather than
hidden: the cursor carries the sha the next screening was snapshotted at.

Two facts follow from reels that the old "walk the film, re-read at the end"
shape got wrong: the rundown a viewer sees is published when a reel's first
clip *starts playing*, not when it is snapshotted, so it always describes the
screening on air; and the tables the countdown reads from live as long as the
reel does, so a screening's timing cannot be evicted while it is still playing.

The model's queues die with its session. When the session is lost, everything
queued is gone: the projectionist declares downtime, rewinds the reel that was
on air to its first scene, drops any reel queued after it, and — once the
model is back — plays that screening again from the top. That is the promised
behaviour, not a recovery heuristic: a reconnect means the screening restarts.

Nothing plays until the curtain goes up. A session starts with autoplay off,
so built clips wait in the playout queue; the projectionist watches how much
film is built and only turns autoplay on once `CURTAIN_SECONDS` of it (or the
whole film, if shorter) is sitting ready. Without that, the first clip would
start the moment it was built and outrun the builds behind it — the stutter a
cold start used to show. While the curtain is down the broadcast reports
`loading` with the buffered-versus-target seconds, and the viewer draws the
wait as a pre-show rather than a black frame. The curtain comes down again on
every new session, which is what makes a restart after downtime clean.

The loop point is a stop, not a splice. When a screening's last scene starts
playing, the projectionist turns autoplay off, so the model holds the next
reel's built clips rather than starting them the instant the last frame is
out. From the moment that clip ends the broadcast reports `intermission` for
`INTERMISSION_SECONDS`, the viewer draws the pause as the end of one screening
and the count into the next, and only then — with the next reel's opening
already built during the pre-roll — autoplay goes back on and the new
screening starts from its first frame. Viewers see the film end and start over
instead of two screenings running into each other.

The projectionist also narrates. It reads its own metadata echo back off each
`clip_started`, finds the reel and the scene, and hands the broadcaster a
cursor: which scene is on air, who wrote it, how long until the film loops, and
what the next screening will be.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field

from broadcast import Broadcast, Cursor, Intermission, Loading
from reactor_link import SESSION_LOST, SESSION_READY, ReactorLink
from story import Rundown, Scene, StorySource

logger = logging.getLogger(__name__)

# The pre-roll: how much film, in seconds of not-yet-playing clips, the feed
# keeps ahead of playout. The model builds at roughly real time, so this
# absorbs a slow build without starving the stream, and it is also the lead
# with which the next screening's snapshot is taken. `PREROLL_MIN_CLIPS`
# floors it so a run of long scenes cannot leave the queue one clip deep.
PREROLL_SECONDS = 60.0
PREROLL_MIN_CLIPS = 3

# The curtain: how much film must be *built* (finished clips waiting in the
# playout queue) before autoplay is turned on for a fresh session. A film
# shorter than this only needs to be built in full. Bounded by the playout
# cap, so it must stay under `playout_capacity - _PLAY_HEADROOM` clips' worth.
CURTAIN_SECONDS = 30.0
# If the buffer cannot reach the target (refusals, a slow model) but something
# is built, raise the curtain anyway after this long rather than hold forever.
CURTAIN_MAX_WAIT_S = 180.0

# The intermission: how long the stream holds between one screening's last
# frame and the next one's first. The next reel is already built during the
# pre-roll, so this is a deliberate pause, not a wait for the model; it is what
# makes the loop read as an ending and a fresh start rather than a splice.
INTERMISSION_SECONDS = 10.0

# Headroom kept under the model's own caps, so a built clip always has
# somewhere to land and builds never pause on a full playout queue.
_GEN_HEADROOM = 2
_PLAY_HEADROOM = 1

# How often the feeder re-checks when the queue is full enough.
_POLL_S = 2.0

# Enqueue retry policy. A "queue full" refusal is a wait, not a failure; any
# other refusal counts, and the continuation is dropped before the scene is.
_RETRY_DELAY_S = 3.0
_MAX_ATTEMPTS = 3
_MAX_FULL_WAITS = 30  # × _POLL_S: a minute of "queue full" before giving up

# How many reels to keep for narration when finish events go missing.
_MAX_REELS = 6

# What the model says when the chain's source clip is no longer available.
_REFUSAL_NO_SOURCE = "No clip with id"
_REFUSAL_QUEUE_FULL = "queue is full"


@dataclass
class Reel:
    """One screening: a snapshot of the film, and how far it has gone."""

    screening_id: int
    rundown: Rundown
    snapshot_wall: float
    next_to_enqueue: int = 0  # index into rundown.scenes
    started: set[int] = field(default_factory=set)  # global indices with clip_started
    finished: set[int] = field(default_factory=set)  # … and clip_finished/stopped/failed
    on_air: bool = False

    @property
    def scenes(self) -> list[Scene]:
        return self.rundown.scenes

    @property
    def fully_enqueued(self) -> bool:
        return self.next_to_enqueue >= len(self.scenes)

    @property
    def done(self) -> bool:
        return len(self.finished) >= len(self.scenes)

    def rewind(self) -> None:
        """Forget every clip: the session that held them is gone."""
        self.next_to_enqueue = 0
        self.started.clear()
        self.finished.clear()
        self.on_air = False


class Screening:
    """Feed the model's queue from the story branch, reel after reel."""

    def __init__(
        self,
        link: ReactorLink,
        story: StorySource,
        broadcast: Broadcast,
    ) -> None:
        self._link = link
        self._story = story
        self._broadcast = broadcast
        self._reels: "OrderedDict[int, Reel]" = OrderedDict()
        self._next_screening_id = 1
        self._last_good: Rundown | None = None
        # The chain: the last clip queued, and the session it belongs to. A
        # clip id from a dead session names nothing the model still holds.
        self._last_clip_id: str | None = None
        self._chain_serial = -1
        # Seconds of the most recently enqueued scenes, so the pre-roll can be
        # measured in film time from the model's own queue counts.
        self._recent_seconds: deque[float] = deque(maxlen=64)
        # The curtain: the session serial autoplay has been turned on for.
        # Any other serial means the current session is still buffering.
        self._autoplay_serial = -1
        self._curtain_since: float | None = None
        # Whether the screening behind the curtain was on air before and is
        # starting over (a restart after downtime), for the viewer's wording.
        self._restarting = False
        # The loop point. `_hold_for` is the screening whose last clip has
        # started, so autoplay must go off before it ends; `_held` is the
        # screening it went off for; `_intermission_since` is when that
        # screening's last clip ended and the pause began.
        self._hold_for: int | None = None
        self._held: int | None = None
        self._intermission_since: float | None = None
        self._wake = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        link.add_listener(self._on_model_message)

    # ------------------------------------------------------------------ reels

    async def _read_story(self) -> Rundown | None:
        """Read the story tip off-thread; hold the last good film on failure."""
        loop = asyncio.get_running_loop()
        try:
            rundown = await loop.run_in_executor(None, self._story.read)
        except Exception as error:  # noqa: BLE001 — a bad tip must never stop the show
            logger.error("[screening] could not read the story: %s", error)
            if self._last_good is not None:
                logger.warning("[screening] airing the last good film instead")
                return self._last_good
            self._broadcast.set_notice("the story branch cannot be read; holding")
            return None
        if not rundown.scenes:
            logger.warning("[screening] the film has no scenes; waiting")
            self._broadcast.set_notice("the film has no scenes yet")
            return self._last_good
        self._last_good = rundown
        return rundown

    async def _feeding_reel(self) -> Reel | None:
        """The reel with scenes still to enqueue, snapshotting a new one if none."""
        if self._reels:
            last = next(reversed(self._reels.values()))
            if not last.fully_enqueued:
                return last
        rundown = await self._read_story()
        if rundown is None:
            return None
        reel = Reel(
            screening_id=self._next_screening_id,
            rundown=rundown,
            snapshot_wall=time.time(),
        )
        self._next_screening_id += 1
        self._reels[reel.screening_id] = reel
        self._prune_reels()
        logger.info(
            "[screening] snapshot for screening %d: %d scene(s) at %s, %s of pre-roll ahead",
            reel.screening_id,
            len(reel.scenes),
            rundown.sha,
            f"{self._pending_seconds():.0f}s",
        )
        if self._on_air_reel() is reel and not any(r.on_air for r in self._reels.values()):
            # Nothing is on air, so this reel is the one behind the curtain:
            # the viewer can have its programme now rather than at first frame.
            self._broadcast.set_rundown(reel.screening_id, reel.rundown)
        return reel

    def _prune_reels(self) -> None:
        """Drop reels that have finished playing; cap the rest."""
        ids = list(self._reels)
        for screening_id in ids[:-1]:
            if self._reels[screening_id].done:
                del self._reels[screening_id]
        while len(self._reels) > _MAX_REELS:
            self._reels.popitem(last=False)

    def _on_air_reel(self) -> Reel | None:
        for reel in reversed(self._reels.values()):
            if reel.on_air:
                return reel
        return next(iter(self._reels.values()), None)

    def _next_reel_after(self, screening_id: int) -> Reel | None:
        for reel in self._reels.values():
            if reel.screening_id > screening_id:
                return reel
        return None

    # -------------------------------------------------------------- the feed

    def _pending_clips(self) -> int:
        """Clips the model holds that have not started playing."""
        return self._link.generation_queued + self._link.playout_queued

    def _pending_seconds(self) -> float:
        """Film time queued ahead of playout, from the model's own counts."""
        pending = self._pending_clips()
        if pending <= 0:
            return 0.0
        recent = list(self._recent_seconds)[-pending:]
        return sum(recent)

    def _room_for_more(self) -> bool:
        link = self._link
        under_caps = (
            link.generation_queued < max(1, link.generation_capacity - _GEN_HEADROOM)
            and link.playout_queued < max(1, link.playout_capacity - _PLAY_HEADROOM)
        )
        if not under_caps:
            return False
        return (
            self._pending_clips() < PREROLL_MIN_CLIPS
            or self._pending_seconds() < PREROLL_SECONDS
        )

    async def run(self) -> None:
        """Keep the queue fed, reel after reel, forever."""
        self._loop = asyncio.get_running_loop()
        await self._link.wait_first_state()
        while True:
            if not self._link.connected:
                await self._nap(1.0)
                continue
            await self._tend_hold()
            await self._tend_curtain()
            if not self._room_for_more():
                await self._nap(_POLL_S)
                continue
            reel = await self._feeding_reel()
            if reel is None:
                await self._nap(_POLL_S)
                continue
            scene = reel.scenes[reel.next_to_enqueue]
            await self._enqueue(reel, scene)

    async def _nap(self, seconds: float) -> None:
        """Sleep, but wake early when a model event needs the loop's attention."""
        try:
            await asyncio.wait_for(self._wake.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass
        self._wake.clear()

    def _poke(self) -> None:
        """Wake the feed loop from a listener, whichever thread delivers it."""
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._wake.set)

    # -------------------------------------------------------- the loop point

    async def _tend_hold(self) -> None:
        """Turn autoplay off while a screening's last clip plays, so its end is a stop."""
        screening_id = self._hold_for
        if screening_id is None:
            return
        self._hold_for = None
        reel = self._reels.get(screening_id)
        if reel is None or reel.done or self.curtain_down:
            return  # the clip is already over, or nothing is playing anyway
        serial = self._link.session_serial
        if not await self._link.set_autoplay(False):
            logger.warning(
                "[screening] could not hold the stream at the end of screening %d; "
                "the next one follows at once",
                screening_id,
            )
            return
        if serial != self._link.session_serial:
            return  # the session turned over; the new one buffers behind the curtain
        later_started = any(
            r.started for r in self._reels.values() if r.screening_id > screening_id
        )
        if later_started:
            # The last clip ended and the next screening began while the
            # command was in flight; the hold must not stall that screening.
            await self._link.set_autoplay(True)
            return
        self._held = screening_id
        logger.info("[screening] holding the stream at the end of screening %d", screening_id)
        if reel.done:
            self._begin_intermission()

    def _begin_intermission(self) -> None:
        """The held screening's last clip has ended: lower the curtain for the pause."""
        self._intermission_since = time.time()
        self._autoplay_serial = -1
        self._curtain_since = None
        self._restarting = False
        logger.info(
            "[screening] screening %d has ended; intermission for %.0fs",
            self._held,
            INTERMISSION_SECONDS,
        )
        following = self._next_reel_after(self._held or 0)
        if following is not None:
            # Nothing is on air now, so the room's rundown can describe the
            # screening about to start, and the curtain can show its programme.
            self._broadcast.set_rundown(following.screening_id, following.rundown)
        self._publish_intermission()
        self._poke()

    def _publish_intermission(self) -> None:
        held = self._held
        if held is None or self._intermission_since is None:
            return
        following = self._next_reel_after(held)
        self._broadcast.mark_intermission(
            Intermission(
                ended_screening=held,
                resumes_at=self._intermission_since + INTERMISSION_SECONDS,
                hold_seconds=INTERMISSION_SECONDS,
                screening=following.screening_id if following else None,
                sha=following.rundown.sha if following else None,
                episode_title=_opening_title(following) if following else "",
                buffered_seconds=self._link.built_seconds,
                target_seconds=self._curtain_target(following) if following else 0.0,
                film_seconds=sum(s.seconds for s in following.scenes) if following else 0.0,
                scene_total=len(following.scenes) if following else 0,
            )
        )

    # ----------------------------------------------------------- the curtain

    @property
    def curtain_down(self) -> bool:
        """Whether the current session is still buffering, autoplay off."""
        return self._autoplay_serial != self._link.session_serial

    def _curtain_target(self, reel: Reel) -> float:
        """Seconds that must be built before this reel's first frame goes out."""
        film = sum(scene.seconds for scene in reel.scenes)
        # The playout queue can only hold so many finished clips; a target
        # past what fits would wait forever. Measure the fit in this reel's
        # own opening scenes.
        slots = max(1, self._link.playout_capacity - _PLAY_HEADROOM)
        fits = sum(scene.seconds for scene in reel.scenes[:slots])
        return min(CURTAIN_SECONDS, film, fits)

    async def _tend_curtain(self) -> None:
        """While buffering, report progress; once enough is built, start playout."""
        if not self.curtain_down:
            return
        if self._held is not None and self._intermission_since is None:
            return  # the held screening's last clip is still on air
        intermission = self._intermission_since is not None
        reel = self._next_reel_after(self._held) if intermission else self._on_air_reel()
        if reel is None:
            if intermission:
                self._publish_intermission()
            # No reel yet (the story is unreadable); the notice says so.
            return
        now = time.time()
        if self._curtain_since is None:
            self._curtain_since = now
        built = self._link.built_seconds
        target = self._curtain_target(reel)
        all_built = (
            reel.fully_enqueued
            and self._link.generation_queued == 0
            and self._link.playout_queued > 0
        )
        overdue = built > 0 and now - self._curtain_since > CURTAIN_MAX_WAIT_S
        if intermission:
            self._publish_intermission()
            if now - self._intermission_since < INTERMISSION_SECONDS:
                return
        else:
            self._broadcast.mark_loading(
                Loading(
                    screening=reel.screening_id,
                    sha=reel.rundown.sha,
                    episode_title=_opening_title(reel),
                    buffered_seconds=built,
                    target_seconds=target,
                    film_seconds=sum(scene.seconds for scene in reel.scenes),
                    scene_total=len(reel.scenes),
                    restart=self._restarting,
                )
            )
        if built + 1e-6 < target and not all_built and not overdue:
            return
        serial = self._link.session_serial
        if not await self._link.set_autoplay(True):
            logger.warning("[screening] could not turn autoplay on; retrying")
            return
        if serial != self._link.session_serial:
            return  # the session turned over mid-command; the next one buffers again
        self._autoplay_serial = serial
        self._curtain_since = None
        self._held = None
        self._intermission_since = None
        logger.info(
            "[screening] curtain up for screening %d: %.1fs built of a %.1fs target%s",
            reel.screening_id,
            built,
            target,
            " (all built)" if all_built else " (overdue)" if overdue else "",
        )

    async def _enqueue(self, reel: Reel, scene: Scene) -> None:
        """Enqueue one scene: seed, length, metadata, and the chain when asked."""
        payload = {
            "prompt": scene.prompt,
            "seed": scene.seed,
            "seconds": scene.seconds,
            "metadata": self._metadata(reel, scene),
        }
        chained = (
            scene.continued
            and self._link.supports_continuation
            and self._last_clip_id is not None
            and self._chain_serial == self._link.session_serial
        )
        if chained:
            payload["continue_from_clip_id"] = self._last_clip_id

        serial = self._link.session_serial
        clip_id = await self._enqueue_with_retries(payload, reel, scene, serial)
        if serial != self._link.session_serial or not self._link.connected:
            # The session turned over underneath this scene; the restart
            # handler has already rewound the reel. Nothing to record.
            return
        reel.next_to_enqueue += 1
        if clip_id is None:
            logger.error(
                "[screening] scene %d/%d of %r was refused; skipping it",
                scene.scene_number,
                scene.scene_count,
                scene.episode_file,
            )
            reel.started.add(scene.global_index)
            reel.finished.add(scene.global_index)
            self._last_clip_id = None  # the chain is broken; the next scene starts fresh
            return
        self._last_clip_id = clip_id
        self._chain_serial = serial
        self._recent_seconds.append(scene.seconds)

    async def _enqueue_with_retries(
        self, payload: dict, reel: Reel, scene: Scene, serial: int
    ) -> str | None:
        """Enqueue with bounded retries, reading the model's reason for a refusal.

        A full queue is waited out (the feed gate makes it rare). A chain
        whose source clip the model no longer holds is retried standalone at
        once. Anything else — a moderated prompt, a transport hiccup — gets a
        few paced attempts, losing the continuation before losing the scene.
        Gives up the moment the session turns over: the scene belongs to a
        reel the restart handler has already rewound.
        """
        attempts = 0
        full_waits = 0
        while attempts < _MAX_ATTEMPTS:
            if self._link.session_serial != serial or not self._link.connected:
                return None
            reply = await self._link.send_command("enqueue", payload)
            if isinstance(reply, dict) and "clip" in reply:
                clip = reply["clip"]
                logger.info(
                    "[screening] queued s%d %s scene %d/%d as %s (seed %d, %.3fs)%s",
                    reel.screening_id,
                    scene.episode_file,
                    scene.scene_number,
                    scene.scene_count,
                    clip["clip_id"][:8],
                    scene.seed,
                    scene.seconds,
                    " ← chained" if payload.get("continue_from_clip_id") else "",
                )
                return clip["clip_id"]
            if not self._link.connected:
                return None
            reason = self._refusal_reason()
            if _REFUSAL_QUEUE_FULL in reason:
                full_waits += 1
                if full_waits > _MAX_FULL_WAITS:
                    return None
                await asyncio.sleep(_POLL_S)
                continue
            if _REFUSAL_NO_SOURCE in reason and "continue_from_clip_id" in payload:
                del payload["continue_from_clip_id"]
                logger.warning(
                    "[screening] %s scene %d: the chain's source clip is gone; retrying standalone",
                    scene.episode_file,
                    scene.scene_number,
                )
                continue
            attempts += 1
            if attempts == 2 and "continue_from_clip_id" in payload:
                del payload["continue_from_clip_id"]
                logger.warning(
                    "[screening] %s scene %d: dropping the continuation after two refusals, "
                    "retrying standalone",
                    scene.episode_file,
                    scene.scene_number,
                )
            await asyncio.sleep(_RETRY_DELAY_S)
        return None

    def _refusal_reason(self) -> str:
        refusal = self._link.last_refusal
        if refusal is None or refusal[0] != "enqueue":
            return ""
        return refusal[1]

    # -------------------------------------------------------------- metadata

    def _metadata(self, reel: Reel, scene: Scene) -> str:
        """The opaque echo the model returns on every message about this clip.

        Carries the primary credit only — the full contributor list rides the
        room rundown, which has room the 2000-char wire field does not. The
        validator caps the title and filename so a legal episode never pushes
        this over the limit.
        """
        rundown = reel.rundown
        tag = {
            "v": 1,
            "screening": reel.screening_id,
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
        if kind == SESSION_LOST:
            self._on_session_lost()
            return
        if kind == SESSION_READY:
            reel = self._on_air_reel()
            if reel is not None:
                logger.info(
                    "[screening] model is back; screening %d plays again from the top",
                    reel.screening_id,
                )
            return
        clip = data.get("clip") if isinstance(data, dict) else None
        if not isinstance(clip, dict):
            return
        tag = _parse_tag(clip)
        if tag is None:
            return
        reel = self._reels.get(tag.get("screening"))
        global_index = int(tag.get("gi", 0))
        if kind == "clip_started":
            self._on_started(tag, clip, reel, global_index)
        elif kind in ("clip_finished", "clip_stopped"):
            if reel is not None:
                reel.finished.add(global_index)
            # Between clips the countdown reads "at least" until the next
            # clip anchors it again; the broadcaster applies a grace so a
            # seamless handover never flickers.
            self._broadcast.mark_stalled()
            self._prune_reels()
            self._on_maybe_ended(reel, global_index)
        elif kind == "clip_failed":
            logger.error(
                "[screening] render failed for %s scene %s/%s: %s",
                tag.get("epf"),
                tag.get("sc"),
                tag.get("scs"),
                data.get("reason"),
            )
            if reel is not None:
                reel.started.add(global_index)
                reel.finished.add(global_index)
            if clip.get("clip_id") == self._last_clip_id:
                self._last_clip_id = None
            self._on_maybe_ended(reel, global_index)

    def _on_maybe_ended(self, reel: Reel | None, global_index: int) -> None:
        """A clip is over; if it was the held screening's last, the pause begins."""
        if reel is None or self._held != reel.screening_id:
            return
        if global_index == len(reel.scenes) - 1 and self._intermission_since is None:
            self._begin_intermission()

    def _on_session_lost(self) -> None:
        """The model's queues are gone: restart the screening that was on air."""
        self._last_clip_id = None
        self._recent_seconds.clear()
        self._curtain_since = None
        self._hold_for = None
        self._held = None
        self._intermission_since = None
        reel = self._on_air_reel()
        if reel is None:
            self._broadcast.mark_downtime()
            return
        for later in [r for r in self._reels if r > reel.screening_id]:
            del self._reels[later]
        self._restarting = reel.on_air or bool(reel.started)
        reel.rewind()
        logger.warning(
            "[screening] model session lost; screening %d restarts from the top when it returns",
            reel.screening_id,
        )
        self._broadcast.mark_downtime()

    def _on_started(self, tag: dict, clip: dict, reel: Reel | None, global_index: int) -> None:
        screening_id = int(tag.get("screening") or 0)
        self._restarting = False
        if self._held is not None and screening_id != self._held:
            # A clip of the next screening is playing, so autoplay is on
            # whatever this side believed; forget the hold.
            self._held = None
            self._intermission_since = None
            self._autoplay_serial = self._link.session_serial
        if reel is not None:
            reel.started.add(global_index)
            if global_index == len(reel.scenes) - 1:
                # The screening's last scene is on air: hold the stream when
                # it ends rather than run straight into the next reel.
                self._hold_for = reel.screening_id
                self._poke()
            if not reel.on_air:
                reel.on_air = True
                self._broadcast.set_rundown(reel.screening_id, reel.rundown)
                logger.info(
                    "[screening] screening %d is on air: %d scene(s) at %s",
                    reel.screening_id,
                    len(reel.scenes),
                    reel.rundown.sha,
                )
            scenes = reel.scenes
        else:
            scenes = []
        if scenes and 0 <= global_index < len(scenes):
            offset = sum(scene.seconds for scene in scenes[:global_index])
            remaining_after = sum(scene.seconds for scene in scenes[global_index + 1 :])
            screening_total = sum(scene.seconds for scene in scenes)
        else:
            offset = 0.0
            remaining_after = 0.0
            screening_total = float(clip.get("seconds", 0.0))

        following = self._next_reel_after(screening_id)
        cursor = Cursor(
            screening=screening_id,
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
            next_sha=following.rundown.sha if following is not None else None,
            intermission_seconds=INTERMISSION_SECONDS,
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


def _opening_title(reel: Reel) -> str:
    """What the screening opens on: the first episode's title, else its file."""
    if not reel.scenes:
        return ""
    first = reel.scenes[0]
    return first.episode_title or first.episode_file


def _parse_tag(clip: dict) -> dict | None:
    """Read this projector's metadata tag back off a clip echo."""
    try:
        tag = json.loads(clip.get("metadata") or "")
    except (TypeError, ValueError):
        return None
    if not isinstance(tag, dict) or "screening" not in tag:
        return None
    return tag
