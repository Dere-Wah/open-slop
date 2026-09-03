# OpenSlop skills

Short guides for finding your way around OpenSlop. Read the one that matches
what you are trying to do.

| Guide | Read it when you want to… |
| --- | --- |
| [repository-map](./repository-map/SKILL.md) | understand how this repository is laid out — the two branches, where the film lives, where the code lives, and how the machine reads the film. |
| [writing-a-scene](./writing-a-scene/SKILL.md) | write or edit a scene: the file format, the `continue` flag, seeds, lengths, and how to get a clean pass from the checker. |
| [how-approval-works](./how-approval-works/SKILL.md) | get your pull request merged: who can vote, the wait counted from the last push, approving reviews, `/block`, and how credit lands on screen. The numbers live in the bot's comment, not here. |

These guides live on the `story` branch and are maintained by the project. A
story pull request cannot change them — it may only touch episode files and the
three root documents (`README.md`, `STYLE.md`, `LICENSE`). That is on purpose:
the rules of the game are not edited by a move in the game. `AGENTS.md` at the
root points coding agents here.

The machine that plays the film has its own guides on the `code` branch, under
`skills/` there: the projector's architecture, the story format as the validator
enforces it, and the CI and approval workflows.
