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
skills/                    these guides (maintained by the project)
.github/workflows/         the checks and the vote counter (maintained by the project)
```

A story pull request may only add or change the episode files and the three
named documents. Everything else here is maintained by the project and is
off-limits to a story change — the format checker enforces that.

## How this branch becomes a broadcast

The projector (on the `code` branch) does this, in a loop, forever:

1. **Read the branch.** It pulls the tip of `story` and parses every episode
   file with the shared validator in `story-tools/`. If a file would not
   validate, it never got merged — the same validator gates every pull request.
2. **Render each scene.** Scene by scene, in file order, it asks the video model
   for a clip at that scene's `seed` and `seconds`. Scenes marked
   `continue: true` are chained onto the one before with no cut; the rest cut
   from black.
3. **Broadcast.** The clips play into a LiveKit room. The viewer plays that room
   and shows the rundown, the countdown, and who wrote what.
4. **Loop.** When the last scene plays, the projector reads the branch again. A
   pull request merged during a screening appears in the next one — never in the
   middle of the film.

Because the film is re-read every loop, there is nothing to deploy. Merging is
publishing.

## Where to go next

- To write: [writing-a-scene](../writing-a-scene/SKILL.md).
- To get merged: [how-approval-works](../how-approval-works/SKILL.md).
- To change the machine: the `code` branch's `README.md`.
