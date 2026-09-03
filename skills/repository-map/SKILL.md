---
name: repository-map
description: How the Open Slop repository is laid out — the two orphan branches, what lives on each, and how the projector turns this branch into a broadcast. Read this first to know where anything is.
---

# The repository map

Open Slop is one GitHub repository with **two branches that share no history**.
This is unusual, so it is worth understanding before you look for anything.

## Two branches, on purpose

| Branch | It holds | You are here to… | License |
| --- | --- | --- | --- |
| **`story`** (the default branch) | The film: `NNNN-title.md` episodes, `STYLE.md`, this `skills/` folder, and the workflows that gate story pull requests. | write the film. | CC BY-SA 4.0 |
| **`code`** | The machine that plays the film: `projector/` (Python), `viewer/` (Next.js), `story-tools/` (the validator). | change how the film is played. | Apache-2.0 |

The two branches are **orphans**: `git log` on one never reaches the other.
That is what makes "you cannot sneak code into the film" structurally true — a
story pull request's diff can only ever contain writing, because there is no
code on this branch to change. It also means the branches are never merged into
each other; each has its own life.

To read or change the code, `git checkout code`, or browse the `code` branch on
GitHub. To write the film, stay here.

## What lives at the root of this branch

```
0010-the-arrival.md        an episode (one file = one episode = many scenes)
0020-the-signal.md
0030-what-the-keeper-saw.md
README.md                  the landing page and the how-to-contribute guide
STYLE.md                   the show bible — the look, the world, the cast
LICENSE                    CC BY-SA 4.0, for the writing
AGENTS.md                  points coding agents at these guides (maintained by the project)
skills/                    these guides (maintained by the project)
.github/workflows/         the checks and the vote counter (maintained by the project)
```

A story pull request may add, change, rename, or delete episode files, and
change the three named documents. Everything else here is maintained by the
project and is off-limits to a story change — the format checker refuses the
whole pull request if it touches anything else, adds a folder, or deletes or
renames one of the three documents.

## How this branch becomes a broadcast

The projector (on the `code` branch) does this, in a loop, forever:

1. **Snapshot the branch.** Shortly before a screening starts — about a minute
   of film before the previous one ends — it pulls the tip of `story` and
   parses every episode file with the shared validator in `story-tools/`. That
   snapshot is the screening: nothing merged after it plays until the next one.
   If a file would not validate, it never got merged — the same validator gates
   every pull request. (If the branch tip is broken anyway, the projector keeps
   airing the last good snapshot and the bot opens an issue.)
2. **Render each scene.** Scene by scene, in file order, it asks the video model
   for a clip at that scene's `seed` and `seconds`, keeping about a minute of
   film queued ahead of what is playing — the model's queue is short, so it
   feeds a few scenes at a time. Scenes marked `continue: true` are chained onto
   the one before with no cut; the rest cut from black.
3. **Broadcast.** The clips play into a LiveKit room. The viewer plays that room
   and shows the rundown, the countdown, and who wrote what. The countdown
   names the story version the next screening was snapshotted at.
4. **Loop.** When the last scene plays, the next snapshot is already queued and
   plays straight through. A pull request merged during a screening appears in
   the first screening snapshotted after the merge — never in the middle of the
   film.

When the projector starts, or comes back after losing the video model, nothing
plays until about half a minute of the opening is built; the viewer shows a
pre-show with the programme meanwhile. If the model is lost mid-screening, the
stream shows downtime and the same screening restarts from the top once the
model is back and that buffer is rebuilt.

Because the film is re-read every loop, there is nothing to deploy. Merging is
publishing.

## Where to go next

- To write: [writing-a-scene](../writing-a-scene/SKILL.md).
- To get merged: [how-approval-works](../how-approval-works/SKILL.md).
- To change the machine: the `code` branch's `README.md`.
