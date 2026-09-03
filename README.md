# Open Slop — the code

> **You are on the `code` branch.** This branch holds the machine that plays
> the film: a Python **projector** and a Next.js **viewer**. The film itself —
> the screenplay anyone can write — lives on the **`story` branch**, which is
> the repository's default branch. Watch at **openslop.live**.

Open Slop is a film that never stops playing, that anyone can write. The
screenplay lives in git as one episode per file. A projector reads the story
branch, renders every scene with the [`reactor/fast-h3`](https://docs.reactor.inc)
video model at the seed the scene names, and broadcasts the result into a
LiveKit room. When the film ends the projector reads the branch again — so a
pull request merged at 16:00 is on air in the next screening, credited to its
author on screen.

```
 story branch (git) ──▶ projector (Python) ──▶ LiveKit room ──▶ viewer (Next.js)
   episodes, scenes        renders each scene       the broadcast     player, rundown,
   at fixed seeds          keeps the queue fed                        countdown, chat
```

## The two branches

| Branch | Holds | License |
| --- | --- | --- |
| **`story`** (default) | The screenplay: `NNNN-title.md` episodes, `STYLE.md`, `skills/`, workflows | CC BY-SA 4.0 |
| **`code`** (here) | `projector/`, `viewer/`, `story-tools/` | Apache-2.0 |

They are orphan branches with no shared history, so a story pull request can
never show code in its diff, and the two are never merged into one another.
To work on the film, `git checkout story`. To read how the story is structured
and how to contribute a scene, read the story branch's `README.md` and its
`skills/`.

## Layout

| Path | What it is |
| --- | --- |
| `projector/` | The Python projector: reads the story, drives the model, publishes to LiveKit. |
| `projector/story.py` | Reads the story branch and credits each scene by `git blame`. |
| `projector/screening.py` | The queue's only writer: feeds scenes, chains them, runs the loop. |
| `projector/broadcast.py` | The 1 Hz cursor and the per-screening rundown in room metadata. |
| `projector/{pacer,publisher,reactor_link}.py` | The media path, unchanged from the Reactor example. |
| `story-tools/validate.py` | The one validator, shared by CI and the projector. |
| `viewer/` | The Next.js viewer: player, overlay, countdown, rundown, chat. |

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
mirror of it and re-reads the tip every screening.

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
the story branch runs it to gate a pull request, and the projector imports the
same code to read the film. If the projector cannot parse an episode, CI has
already rejected it. See [CONTRIBUTING.md](./CONTRIBUTING.md) for how to change
the code, and the story branch for how to change the film.

## License

The projector and viewer are Apache-2.0 (see [LICENSE](./LICENSE) and
[NOTICE](./NOTICE)); they derive from a Reactor example under the same license.
The screenplay on the `story` branch is CC BY-SA 4.0.
