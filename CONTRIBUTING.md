# Contributing to Open Slop

There are two ways to contribute, and they live on two different branches.

## To write the film — the `story` branch

You do **not** need this code. Everything about writing, revising, and
approving a scene lives on the `story` branch, which is the repository's
default branch. Start with its `README.md` and its `skills/`. In short: one
episode is one `NNNN-title.md` file at the branch root, scenes are separated by
`---` blocks that set `seed` and `seconds`, and a pull request merges once
three people comment `/approve`. No maintainer gate.

## To change the code — this branch (`code`)

The projector and viewer live here. Before opening a pull request:

```bash
python3 story-tools/test_validate.py            # the validator's tests pass
python3 -m py_compile projector/*.py story-tools/*.py
cd viewer && pnpm install && pnpm build          # the viewer builds
```

Guidelines:

- **`story-tools/validate.py` is the single source of truth for the episode
  format.** CI on the story branch and the projector both run it. If you change
  what a legal episode is, change it there, add a test, and update the story
  branch's `skills/` in the same spirit — never let the two drift.
- **Keep the story-branch workflows thin.** They check this branch's
  `story-tools/` out at a pinned ref and run it. The logic that decides whether
  a story pull request may merge must stay here, on a branch a story
  contributor cannot edit.
- **Match the surrounding style.** The projector's media path (`pacer.py`,
  `publisher.py`, `reactor_link.py`) is inherited from the Reactor example and
  should stay close to it. Comments explain non-obvious intent, not the obvious.
- Do not commit secrets or `.env` files. Do not commit `node_modules/`, build
  output, or a virtualenv.

New source files need no per-file copyright header; authorship lives in git
history, matching the example this derives from.
