# OpenSlop code skills

Short guides to the machine that plays the film. Read the one that matches what
you are about to change.

| Guide | Read it before you… |
| --- | --- |
| [projector-architecture](./projector-architecture/SKILL.md) | touch anything under `projector/`: how a screening is snapshotted into a reel, how the model's short queue is fed, what happens on a disconnect, what the viewer is told and when. |
| [story-format-validator](./story-format-validator/SKILL.md) | change what a legal episode is: every rule `story-tools/validate.py` enforces, why each exists, and how to change one without the projector and CI drifting apart. |
| [story-ci-and-approval](./story-ci-and-approval/SKILL.md) | touch the story branch's workflows or the repository's rulesets: the security invariants, the vote anchor, the quorum algorithm, auto-merge, and how to test a change to them. |
| [viewer-design](./viewer-design/SKILL.md) | touch anything under `viewer/`: the GitHub-repository look and its tokens, the component map, the one grid that serves phone and desktop, the curtain's container queries, the rundown's paging, and the `/preview` route for checking every state. |

The film's own guides — how to write a scene, how the vote works from a
contributor's side, the repository map — live on the `story` branch under
`skills/`. Keep the two sets in agreement: when a rule changes here, the story
branch's guide that states it changes in the same piece of work.
