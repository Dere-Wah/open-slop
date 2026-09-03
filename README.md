# Open Slop

**A movie that never stops playing. Anyone can write the next scene.**

Watch it at **[openslop.live](https://openslop.live)**.

This branch is the movie. Each `NNNN-title.md` file is one episode. A projector
reads the files, renders every scene with an AI video model, and streams the
result 24/7. When the movie ends, it starts over with whatever is on this branch
now. Merge a scene, and it is on air in the next run, with your name on screen.

Nobody approves the story. The audience does: open a pull request, get enough
approving reviews, and it merges on its own.

## Write a scene

One file is one episode. One episode is a list of scenes. Add a file or edit
one, then open a pull request.

```markdown
# The Arrival

---
seed: 481516
seconds: 8.0
continue: false
---
A wide shot of a fog-bound harbour at dawn, one lighthouse turning. Flat 2D cel
animation, thick black outlines, briny blues. Gulls, a low bell, water on stone.

---
seed: 481517
seconds: 10.125
---
A close-up of the keeper's face, half-lit by the turning lamp. Flat 2D cel
animation, thick black outlines, briny blues. He says, low: "They only come when
the light is wrong." Wind against glass.
```

A scene is a `---` header and a prompt.

| Key | Required | Meaning |
| --- | --- | --- |
| `seed` | yes | An integer. Same seed, same clip. |
| `seconds` | yes | Clip length. One of the [legal lengths](#legal-lengths). |
| `continue` | no | `true`: this scene starts from the last frame of the previous one. `false`: it starts fresh, after a cut to black. Default `true`. |

The prompt is the scene, in plain English, up to 800 characters. The model sees
**only this one prompt**, so describe the whole look every time. Read
[STYLE.md](./STYLE.md) first.

**About `continue`.** Every continued scene is generated from a generated frame.
A few in a row look great; a long chain of them slowly degrades. Drop a
`continue: false` in now and then to reset the picture.

## Order

Files play in the order of their number. Numbers step by 10, so `0015` goes
between `0010` and `0020`. To add to the end, pick a higher number. To reorder,
rename. That is the whole system.

## Get it merged

1. Your pull request may touch only `NNNN-title.md` files and `README.md`,
   `STYLE.md`, `LICENSE`. No folders, nothing else.
2. A bot checks the format and comments where your episode lands and how long
   the movie now runs.
3. Anyone can approve it like any pull request: **Files changed → Review
   changes → Approve**. The bot's comment shows how many are needed and how
   long it waits after your last push. Reach it, and it merges by itself.
4. An approval is for the commit it was given on, so pushing new commits clears
   the votes. Finish editing, then ask for approvals.

A maintainer can `/block` something harmful. The video model also moderates
every prompt. Keep it something a stranger can enjoy.

Details: [`skills/how-approval-works`](./skills/how-approval-works/SKILL.md).

## Credit

The name on screen is whoever last wrote the scene's words, straight from
`git blame`. Everyone who touched the scene is listed too. Rewrite a scene and
it becomes yours; the history is one click away.

## Legal lengths

`seconds` must be one of:

```
5.167  5.875  6.583  7.292  8.0    8.708  9.417
10.125 10.833 11.542 12.25  12.958 13.667 14.375
```

Pick another and the bot tells you the nearest two.

## Around here

- [`STYLE.md`](./STYLE.md) — the show bible.
- [`skills/`](./skills) — guides: the repository map, writing a scene, how
  approval works. [`AGENTS.md`](./AGENTS.md) points coding agents at them.
- The code that plays the movie lives on the `code` branch. This branch is only
  the screenplay.

## License

The screenplay is **CC BY-SA 4.0** ([LICENSE](./LICENSE)). Opening a pull
request licenses your writing under the same terms. The code on the `code`
branch is Apache-2.0.
