# Open Slop

**A film that never stops playing, that anyone can write.**

Watch it live at **[openslop.live](https://openslop.live)**.

This branch _is_ the film. Every `NNNN-title.md` file here is one episode of a
single, communally-written movie. A projector reads this branch, renders every
scene with an AI video model, and broadcasts the result into a 24/7 stream.
When the film ends, the projector reads the branch again — so the moment your
pull request merges, your scene is in the next screening, with your name on it.

No studio. No director. No maintainer approves the story. **The audience does:
three approvals from anyone and your scene is canon.**

## Watch

Go to **[openslop.live](https://openslop.live)**. You will see what is playing,
who wrote it, the whole rundown, and a countdown to when the film loops. To read
the screenplay, you are already in the right place — scroll up to the episode
files.

## Write a scene

A film is a list of episode files. One file is one episode; one episode is a run
of scenes. You add or edit a file and open a pull request.

### The shape of an episode

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
continue: true
---
Hard cut to a close-up of the keeper's face, half-lit by the turning lamp. Flat
2D cel animation, thick black outlines, briny blues. He says, low: "They only
come when the light is wrong." Wind against glass.
```

Each scene has a `---` header and a prompt body. The header sets three things:

| Key | Required | What it does |
| --- | --- | --- |
| `seed` | yes | An integer. The same seed always renders the same clip, so your scene is reproducible. |
| `seconds` | yes | The clip length. Must be one of the [14 legal lengths](#legal-lengths). |
| `continue` | no | `true` chains this scene onto the previous one with no cut; `false` cuts to black. Defaults to `true` (and to `false` for the very first scene of the film). |

The prompt body is the scene, in plain English, up to 800 characters. **The
model reads only that one scene**, so re-describe the whole look and setting
every time — read [STYLE.md](./STYLE.md) first, it is the show bible.

### The two kinds of cut

- **`continue: false` — a cut to black.** A fresh start: a new place, a jump in
  time, the end of a beat. Write it self-contained.
- **`continue: true` — a hard cut inside a continuous take.** The scene opens on
  the exact last frame of the one before it. Because of that, its prompt **must
  open on a described hard cut** to a new shot — `Hard cut to a wide shot of …`
  — or the picture smears. This is checked automatically.

### Order

Files play in the order of their four-digit number. Numbers step by 10, so to
put an episode between `0010` and `0020`, call it `0015`. To add to the end,
pick a higher number. That is the whole ordering system — no lists to maintain.

### Open the pull request

1. Add or edit one `NNNN-title.md` file. A pull request may only touch episode
   files and `README.md` / `STYLE.md` / `LICENSE` — nothing else.
2. Open it. A bot checks the format and comments what it found, including where
   your episode lands and the film's new runtime.
3. Ask people to watch and approve.

## How approval works

- Anyone can approve. Comment **`/approve`** on the pull request.
- **Three distinct approvals** (not counting the author) merges it, once it has
  been open past a short cooling-off window.
- Editing the scene after approvals resets them — people approve the words that
  are there.
- A maintainer can `/block` something harmful; the video model also moderates
  every prompt. This is a public, communal film — keep it something a stranger
  can enjoy.

Full detail is in [`skills/how-approval-works`](./skills/how-approval-works/SKILL.md).

## How credit works

Your name on screen means **you wrote those words**. Credit is per scene, read
straight from `git blame` on the scene's lines: the most recent author is the
headline credit, and everyone who shaped the scene is listed. Rewrite someone's
scene and the screen names you — the full history is one click away on the
commit. This is a defensible rule for a film written together; it is not an
accident.

## Legal lengths

A scene's `seconds` must be one of these (the model can only make these):

```
5.167  5.875  6.583  7.292  8.0    8.708  9.417
10.125 10.833 11.542 12.25  12.958 13.667 14.375
```

The bot suggests the nearest two if you pick another.

## Navigating this repository

- [`STYLE.md`](./STYLE.md) — the show bible. Read before writing.
- [`skills/`](./skills) — short guides: the repository map, writing a scene, and
  how approval works.
- The **code** that plays the film — the projector and the viewer — lives on the
  `code` branch, not here. This branch is only the screenplay.

## License

The screenplay is licensed **CC BY-SA 4.0** (see [LICENSE](./LICENSE)). By
opening a pull request you license your writing under the same terms. The
projector and viewer code, on the `code` branch, is Apache-2.0.
