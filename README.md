# Open Slop — the code

> **You are on the `code` branch** of
> [Dere-Wah/open-slop](https://github.com/Dere-Wah/open-slop). This branch
> holds the machine that plays the film: a Python **projector** and a Next.js
> **viewer**. The film itself — the screenplay anyone can write — lives on the
> [**`story` branch**](https://github.com/Dere-Wah/open-slop/tree/story), which
> is the repository's default branch. Watch at **openslop.live**.

Open Slop is a film that never stops playing, that anyone can write. The
screenplay lives in git as one episode per file. A projector reads the story
branch, renders every scene with the [`reactor/fast-h3`](https://docs.reactor.inc)
video model at the seed the scene names, and broadcasts the result into a
LiveKit room. Shortly before each screening starts, the projector snapshots the
branch and plays exactly that — so a pull request merged at 16:00 is on air
from the first screening snapshotted after it, credited to its author on screen.

```
 story branch (git) ──▶ projector (Python) ──▶ LiveKit room ──▶ viewer (Next.js)
   episodes, scenes        snapshots a screening,   the broadcast     player, rundown,
   at fixed seeds          keeps the queue fed                        countdown, chat
```

The model's queue is short, so the projector cannot queue a film; it keeps
about a minute of clips ahead of playout and takes the next screening's
snapshot with that same lead. If the model session drops, the stream shows
downtime and the screening restarts from the top when it is back.

## The two branches

| Branch | Holds | License |
| --- | --- | --- |
| **`story`** (default) | The screenplay: `NNNN-title.md` episodes, `STYLE.md`, `skills/`, `AGENTS.md`, workflows | CC BY-SA 4.0 |
| **`code`** (here) | `projector/`, `viewer/`, `story-tools/`, `skills/`, `assets/`, `AGENTS.md` | Apache-2.0 |

They are orphan branches with no shared history, so a story pull request can
never show code in its diff, and the two are never merged into one another.
To work on the film, `git checkout story`. To read how the story is structured
and how to contribute a scene, read the story branch's `README.md` and its
`skills/`.

## Layout

| Path | What it is |
| --- | --- |
| `projector/` | The Python projector: reads the story, drives the model, publishes to LiveKit. |
| `projector/story.py` | Mirrors the story branch and credits each scene by `git blame` (plus `Co-authored-by`). |
| `projector/screening.py` | The queue's only writer: snapshots a screening into a reel, feeds and chains scenes, restarts on a lost session. |
| `projector/broadcast.py` | The 1 Hz cursor (`warming` / `downtime` / `live`) and the per-screening rundown in room metadata. |
| `projector/reactor_link.py` | The one model session, with `session_ready` / `session_lost` events. |
| `projector/{pacer,publisher}.py` | The media path, unchanged from the Reactor example. |
| `story-tools/validate.py` | The one validator, shared by CI and the projector. |
| `viewer/` | The Next.js viewer: player, overlay, countdown, rundown, chat. |
| `skills/` | Guides for changing this branch: the projector, the format, the CI and vote. |
| `assets/how-to-approve.png` | The three-step screenshot strip the story bot embeds in its "Audience vote" comment. Served raw from this branch. |
| `AGENTS.md` | Points coding agents at the skills and states the rules that apply everywhere. |

## Run it locally

You need a [Reactor API key](https://www.reactor.inc/account/api-keys), a
[LiveKit](https://livekit.io) project (the free tier works), and a checkout of
the story branch to read from.

**1. The projector** (drives the model, publishes the broadcast):

```bash
cd projector
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env      # REACTOR_API_KEY, LIVEKIT_*, and STORY_REPO
.venv/bin/python main.py
```

For offline iteration, point `STORY_REPO` at a local clone that has the `story`
branch, instead of the GitHub URL. The projector keeps a blobless partial-clone
mirror of it and re-reads the tip once per screening, when it takes the next
snapshot.

**2. The viewer** (plays the room, carries chat):

```bash
cd viewer
cp .env.example .env.local   # the same LIVEKIT_* values and room name
pnpm install
pnpm dev                     # http://localhost:3000
```

## Develop

```bash
# The validator and its tests (no third-party dependency):
python3 story-tools/test_validate.py
python3 story-tools/validate.py <path-to-a-story-checkout>

# The projector compiles:
python3 -m py_compile projector/*.py story-tools/*.py

# The viewer builds:
cd viewer && pnpm install && pnpm build
```

`story-tools/validate.py` is the single definition of a legal episode. CI on
the story branch runs it to gate a pull request and to re-check the branch tip
after every merge, and the projector imports the same code to read the film.
If the projector cannot parse an episode, CI has already rejected it — or has
opened an issue about it. See [CONTRIBUTING.md](./CONTRIBUTING.md) for how to
change the code, [`skills/`](./skills/README.md) for how each part works, and
the story branch for how to change the film.

## License

The projector and viewer are Apache-2.0 (see [LICENSE](./LICENSE) and
[NOTICE](./NOTICE)); they derive from a Reactor example under the same license.
The screenplay on the `story` branch is CC BY-SA 4.0.
