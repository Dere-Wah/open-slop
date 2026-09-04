# Add a scene to the movie

Three steps, all in the browser. No clone, no setup.

## 1. Open the editor

- **New episode** → [create a file on this branch](https://github.com/Dere-Wah/open-slop/new/story?filename=0040-your-title.md).
  Name it `NNNN-your-title.md`. Files play in number order; pick a number
  after the last episode, or in between two to slot one in.
- **Edit a scene** → press **Edit** next to any scene on
  [openslop.live](https://openslop.live); the green one is the scene on air.
  It opens this editor on that scene's lines. Change the words; rewrite it and
  it becomes yours. (Or open the episode here and press the pencil.)

GitHub forks the repository for you when you save.

## 2. Write the scene

Paste this and fill it in. One `---` block per scene; put as many as you like
in one file.

```markdown
# Your Title

---
seed: 20260903
seconds: 8.0
continue: false
---
A wide shot of a small fog-bound harbour town at dawn, one tall white lighthouse
turning its beam slowly over flat grey water. Flat 2D cel animation, thick black
outlines, flat fills. Briny blues and fog greys, warmed at the horizon by a low
orange sun. The camera holds steady. Quiet and a little eerie. Sound: gulls cry
far off, a buoy bell rings slow, small waves lap against the stone quay.
```

- `seed`: any whole number. Same seed, same picture, every screening.
- `seconds`: how long the clip runs, 5 to 14. The model rounds it up to a length
  it can make (`8` stays `8.0`, `10` plays as `10.125`); the bot tells you.
- `continue: true` starts from the last frame of the scene before; `false` cuts
  to black first. Leave it out for `true`.
- The prompt is 200 to 800 characters of plain English. The model sees only
  this prompt, so describe the whole look every time — copy it from
  [STYLE.md](./STYLE.md). End with what we hear. If someone speaks, give the
  exact words in quotes and say how the voice sounds.

## 3. Open the pull request

Click **Propose changes**, then **Create pull request**. A bot checks the
format within a minute and tells you where your scene lands. If something is
off (a missing `seconds`, a prompt over 800 characters, a header written
sideways), it also leaves one-click fixes under **Files changed**: read each,
press **Commit suggestion** on the ones you agree with, and the check runs
again. Then ask the
viewers in the chat at [openslop.live](https://openslop.live) to review: they
approve it like any pull request (**Files changed → Review changes →
Approve**), and when enough have, it merges by itself. Your scene is on air in
the next screening, with your name on screen.

Pushing a new commit clears the approvals, so finish editing before you ask.

## Or hand it to an agent

This branch is written for coding agents too. The agent button at the top of
[openslop.live](https://openslop.live) opens Cursor, Codex, Claude Code, Copilot,
or Warp with the prompt already typed. Or paste this yourself:

> Clone `https://github.com/Dere-Wah/open-slop` and check out the `story`
> branch. Read `AGENTS.md` and `skills/writing-a-scene/SKILL.md`. Then add a
> new episode to the movie about ⟨your idea⟩ that matches `STYLE.md`, run the
> validator it names, and open a pull request.

Swap "add a new episode" for "edit scene 2 of `0020-the-signal.md` so that…"
to change a scene instead.

---

Want the details — the exact lengths, how the vote is counted, how credit works?
The [README](./README.md) has them, and [`skills/`](./skills) has the rest.
