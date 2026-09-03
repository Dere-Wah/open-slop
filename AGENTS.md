# Agent instructions for the `code` branch

This branch holds the machine that plays Open Slop — the Python projector, the
Next.js viewer, and the validator that defines the film's format. The film
itself lives on the `story` branch, which has its own `AGENTS.md` and `skills/`.

Read the guide that matches the task before you change anything:

| Task | Read |
| --- | --- |
| Anything under `projector/` — feeding the model's queue, reels and snapshots, disconnects, what the viewer is told | [`skills/projector-architecture`](./skills/projector-architecture/SKILL.md) |
| What a legal episode is — `story-tools/validate.py`, its tests, the pull-request allowlist | [`skills/story-format-validator`](./skills/story-format-validator/SKILL.md) |
| The story branch's workflows, the vote, auto-merge, rulesets | [`skills/story-ci-and-approval`](./skills/story-ci-and-approval/SKILL.md) |
| Anything under `viewer/` — the page's GitHub-repository look, tokens, layout, curtain, rundown scaling | [`skills/viewer-design`](./skills/viewer-design/SKILL.md) |

## Rules that apply to every change here

- **`story-tools/validate.py` is the only definition of the format.** CI on the
  story branch, the projector, and contributors all run it. Change it there,
  add a test in `test_validate.py`, and update the story branch's
  `skills/writing-a-scene` or `skills/how-approval-works` in the same piece of
  work. Never let the code and the contributor-facing text say two things.
- **Nothing but `projector/screening.py` writes to the model's queue.** It
  snapshots a screening into a reel, keeps about a minute of film queued, and
  restarts the screening from the top when the model session is lost.
- **The story workflows never execute pull-request content and never
  interpolate untrusted values with `${{ }}`.** They are thin shims on the
  story branch that run this branch's `story-tools/` at a pinned ref. Keep the
  logic here, where a story contributor cannot edit it.
- **The viewer trusts only the `streamer` participant** for `show.state` and
  for chat signed as the show, and renders only http(s) `href`s. Keep it that
  way; every viewer holds a data-publish grant for chat.
- **The viewer looks like a GitHub repository page and uses no UI package.**
  Colours, type, and radii are the tokens in `viewer/app/globals.css`; the
  icons are inline. Check a change at 390px and 1440px through
  `/preview?state=…&episodes=120` before calling it done.
- Before opening a pull request: `python3 story-tools/test_validate.py`,
  `python3 -m py_compile projector/*.py story-tools/*.py`, and
  `cd viewer && pnpm build`. `.github/workflows/code-ci.yml` runs the same.
- Use `pnpm` in `viewer/`. Do not commit `.env*`, `node_modules/`, build
  output, or a virtualenv.
- `GITHUB_SETUP.todo.md` is intentionally uncommitted; it is the operator's
  record of the repository settings (rulesets, auto-merge, Actions
  permissions, the validator pin) and how they were applied. The public facts
  it holds are restated in `skills/story-ci-and-approval`.
- Both branches have rulesets that require a pull request; repository admins
  bypass them so a solo maintainer can move the validator pin on `story` and
  land changes here. Prefer a pull request for anything a reviewer should see.
- Never commit, push, or open a pull request without the human in the
  conversation asking for it.
