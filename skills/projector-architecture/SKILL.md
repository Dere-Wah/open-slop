---
name: projector-architecture
description: How the OpenSlop projector turns the story branch into a 24/7 broadcast — the reel snapshot, the bounded pre-roll against the model's short queue, the curtain that buffers before the first frame, chaining and refusals, the restart-on-disconnect rule, and the two payloads the viewer receives. Read before changing anything under projector/.
---

# The projector

`projector/` is one Python process. It reads the `story` branch, asks the
`reactor/fast-h3` video model for one clip per scene, and publishes the clips
into a LiveKit room together with a live cursor and a per-screening rundown.
The viewer reads only the room; it never calls GitHub.

```
story.py ──▶ screening.py ──▶ reactor_link.py ──▶ (model) ──▶ pacer.py ──▶ publisher.py ──▶ LiveKit
 read +          reels,          one session,        clips      real-time      video/audio,
 blame           queue feed      commands/events                pacing         data, metadata
                    │
                    └──▶ broadcast.py  (cursor 1 Hz on `show.state`; rundown in room metadata)
```

| Module | Owns |
| --- | --- |
| `story.py` | A blobless mirror of the story branch. Parses the film with `story-tools/validate.py`, credits each scene by `git blame` over its prompt lines, collects `Co-authored-by` trailers. Every git call has a timeout. |
| `screening.py` | The queue's only writer. Snapshots the film into a `Reel`, keeps the model fed, holds the curtain until enough is built, tags each clip, turns model events into broadcast state. |
| `reactor_link.py` | The one model session: connects, reconnects, sends commands, fans out model messages plus two synthetic events, `session_ready` and `session_lost`. Exposes `built_seconds` and `set_autoplay()`. |
| `broadcast.py` | What the viewer sees: the cursor, the status (`warming`, `loading`, `downtime`, `live`), and the rundown, cut to fit LiveKit's metadata cap. |
| `pacer.py`, `publisher.py` | The media path from the Reactor livestream example, unchanged in spirit. |
| `main.py` | Wires the above and runs them. |

## The reel: a screening is a snapshot

The model's queue is short (a handful of clips), so the projector cannot queue
a whole film. It also must not read the branch mid-film — a scene merged at
minute three must not change what plays at minute four. The two constraints
meet in the `Reel`:

- A reel is **one screening**: a `Rundown` (the parsed film at one sha) plus
  bookkeeping — which scene to enqueue next, which have started, which have
  finished, whether the reel is on air.
- The feeder always works on the **current feeding reel**. When it has
  enqueued that reel's last scene, the next call to `_feeding_reel()` reads the
  branch **once**, snapshots the result into a new reel, and continues from
  there. That read is the only time the branch is consulted.
- Because the feed runs about `PREROLL_SECONDS` of film ahead of playout, the
  snapshot for screening N+1 is taken roughly one minute of film before
  screening N ends. A film shorter than the pre-roll is snapshotted more than
  one screening ahead; that is expected.
- Reels are kept until their finish events arrive (`_MAX_REELS` caps the
  memory). A missing finish event is tolerated: the narration uses the newest
  reel that has started.

If the branch cannot be read or does not validate, the feeder airs the last
good rundown and sets a viewer notice. On a cold start with no last good film
it holds, tells the viewer, and retries. After every merge, the story branch's
own CI validates the tip and opens an issue when it is broken, so this state
is visible rather than silent.

## Feeding the queue

`_room_for_more()` gates every enqueue on two conditions, both required:

1. **Under the model's caps, with headroom.** `generation_queued` and
   `playout_queued` are read live off the model's state messages;
   `_GEN_HEADROOM` / `_PLAY_HEADROOM` keep a slot free so a finished build
   always has somewhere to land.
2. **Under the pre-roll.** Pending film (queued but not finished) is below
   `PREROLL_SECONDS` **or** fewer than `PREROLL_MIN_CLIPS` clips are pending.
   The seconds bound is what absorbs a slow build; the clips floor stops a run
   of long scenes from leaving the queue one clip deep.

When there is room, `_enqueue()` sends one scene: `prompt`, `seed`, `seconds`,
a `metadata` tag naming the screening, the episode and scene indices, and the
commit sha, and — when the scene's effective `continue` is true —
`continue_from_clip_id` pointing at the previous clip. Prompts go to the model
verbatim; there is no upsampling anywhere.

Refusals are read from the model's `command_error` and handled by reason:

- `queue is full` → wait and retry, up to a minute (`_MAX_FULL_WAITS`); this is
  not a failure, the state message was stale.
- `No clip with id` on a chained enqueue → the source clip is gone (a new
  session, or evicted); retry the scene standalone. The chain is dropped before
  the scene is.
- Anything else → retry a few times (`_MAX_ATTEMPTS`), then skip the scene and
  log it.

Every retry checks `link.session_serial` first: a command meant for the session
that refused it must not land on a session that came up in between.

## The curtain: nothing plays until the opening is built

A session starts with the model's autoplay **off** (`reactor_link.py` no longer
turns it on at connect). Built clips therefore wait in the playout queue, and
`screening.py` decides when the first one starts:

- `_tend_curtain()` runs on every pass of the feed loop while
  `curtain_down` (autoplay has not been turned on for the current
  `session_serial`). It reads `link.built_seconds` — the sum of `seconds` over
  the model's `playout` list — against a target from `_curtain_target()`:
  `CURTAIN_SECONDS`, or the whole film if shorter, or what fits in the playout
  queue's free slots if that is smaller still.
- When built ≥ target, or the reel is fully built, or `CURTAIN_MAX_WAIT_S` has
  passed with something built, it sends `set_autoplay(true)` once, records the
  serial, and the model plays the front clip. Playout then runs on top of a
  buffer instead of chasing the builds, which is what removes the stutter a
  cold start showed.
- While waiting it publishes `Loading` through `broadcast.mark_loading()`:
  screening, sha, the opening episode's title, `buffered_seconds`,
  `target_seconds`, `film_seconds`, `scene_total`, and `restart` (true when
  this screening was on air and is starting over). The viewer draws this as
  the pre-show.
- The curtain comes down again on every new session — a reconnect after
  downtime buffers before it restarts the screening.
- While nothing is on air, the reel's rundown is written to room metadata at
  **snapshot** time (not first frame), so the pre-show can show the programme.
  With a screening on air the rule is unchanged: the rundown follows the first
  `clip_started`.

`CURTAIN_SECONDS` must stay under what the playout queue can hold
(`playout_capacity - _PLAY_HEADROOM` clips), or the target is unreachable;
`_curtain_target()` clamps to that, but keep the constant sane.

## Losing the model

A Reactor session can drop and come back. The rule, chosen on purpose: **show
downtime, and restart the screening that was on air from its first scene.**
Trying to resume mid-film would either skip scenes (the queue died with the
session) or replay from a guess; a clean restart is honest and the viewer is
told.

`reactor_link.py` fans out `session_lost` when a live session goes away and
`session_ready` when one is up. On `session_lost`, `screening.py` forgets the
chain (`_last_clip_id`), rewinds the on-air reel to scene zero, drops any later
reel (its snapshot will be taken again), and calls `broadcast.mark_downtime()`.
On `session_ready` the feeder resumes behind the curtain: the status goes
`downtime` → `loading` (with `restart: true`) → `live` on the first
`clip_started`. `send_command()` returns `None` immediately when there is no
session rather than waiting for one, so nothing is queued against a session
that does not exist yet.

## What the viewer is told

Two payloads, both owned by `broadcast.py`:

- **The cursor**, on data topic `show.state`, once a second: status, the reel
  and sha on air, the episode/scene indices, author and commit with links, the
  server clock (`now`) and the projected end of the screening (`ends_at`),
  `stalled`, and — when a later reel is already snapshotted — `next_sha`, so
  the countdown can say which story version comes up. Between clips the stall
  flag waits `_STALL_GRACE_S` before showing, so a seamless `continue` does not
  flicker an intermission. While `loading` the packet carries the buffer
  fields listed under the curtain instead of a cursor.
- **The rundown**, written into room metadata when a reel's **first** clip
  starts — or at snapshot when nothing is on air, so the curtain can show the
  programme (the viewer must never see a pre-rolled film described as the one
  on air). It carries every episode and scene with
  its credit and links, no prompt bodies. LiveKit caps metadata; the payload is
  cut by degrees to `_METADATA_BUDGET_BYTES` — contributors first, then
  episodes from the tail with `truncated: true` — and the viewer says so.

`ends_at` is computed from the reel's total seconds minus what has finished;
the viewer corrects it into its own clock using `now`.

## Where to look when

- The story is not being picked up → `story.py` logs around `fetch`; check
  `STORY_REPO`/`STORY_BRANCH`; remember the snapshot is taken one pre-roll
  before a screening starts, not at merge time.
- Scenes skipped or credited wrong → `story.py` blame is loud on failure and
  falls back to `unknown`; the validator's `body_line_start/end` is what is
  blamed.
- The stream stalls with clips queued → `_room_for_more()` and the model's
  `generation_capacity`/`playout_capacity` in the state message.
- The curtain never lifts → the `[screening] curtain up` log line is missing;
  check `built_seconds` (is `queue_update` arriving?), the target against the
  playout cap, and whether `set_autoplay` was refused.
- The first seconds on air stutter → the curtain lifted too early; raise
  `CURTAIN_SECONDS` within the playout cap.
- The countdown is wrong → `broadcast.py` `ends_at`; the viewer's skew
  correction in `ShowApp.tsx`.

## Changing this module

Run `python3 -m py_compile projector/*.py` and, for anything in
`screening.py`/`broadcast.py`, drive it with fake `link`/`publisher`/`story`
objects the way the repository's smoke checks do: enqueue a short film, move
clips from the fake's generation list to its playout list and assert autoplay
is not requested before the target and is requested once at it, fire
`clip_started`/`clip_finished`, drop the session, and assert the reel rewinds,
the curtain comes back down with `restart: true`, and the rundown is published
once. Keep the queue's single-writer rule: nothing but `screening.py` sends
`enqueue`, and nothing but `_tend_curtain()` sends `set_autoplay`.
