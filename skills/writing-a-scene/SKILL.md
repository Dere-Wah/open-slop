---
name: writing-a-scene
description: Write or edit an Open Slop scene — the episode file format, the seed/seconds/continue header, the two kinds of cut and the hard-cut rule, the legal clip lengths, and how to pass the format checker on the first try.
---

# Writing a scene

An episode is one Markdown file at the root of the `story` branch. One file is
one episode; one episode is a run of scenes. This guide is the format in full.

## The file

```markdown
# The Title Of The Episode

---
seed: 481516
seconds: 8.0
continue: false
---
The first scene's prompt, in plain English…

---
seed: 481517
seconds: 10.125
continue: true
---
Hard cut to the second scene's prompt…
```

- An optional `# Title` heading on the first line.
- Then one or more scenes. Each scene is a `---` header, the two-or-three keys,
  a closing `---`, and the prompt body.
- Nothing else in the file. A line that is exactly `---` inside a prompt body is
  an error — it reads as a scene break.

## The filename sets the order

`NNNN-lower-kebab.md`: four digits, a dash, then lowercase letters, digits, and
dashes. Files play in number order. Numbers step by 10 so you can insert:
between `0010` and `0020`, add `0015`. To add to the end, pick a higher number.
If two people pick `0015`, both merge and the tie breaks by the rest of the
name — nothing collides except editing the same file.

## The header keys

| Key | Required | Type | Meaning |
| --- | --- | --- | --- |
| `seed` | yes | integer ≥ 0 | Fixes the render. The same seed and prompt always make the same clip, so your scene is reproducible and stable across screenings. Pick any number and keep it. |
| `seconds` | yes | one of the legal lengths | The clip's length. |
| `continue` | no | `true` / `false` | How this scene joins the previous one. Defaults to `true` when the scene has a predecessor, and to `false` for the very first scene of the whole film. |

Only these three keys. Any other key is rejected — a key nothing reads is a
contributor thinking they set something that never took effect. (There is no
`length`; the key is `seconds`, because that is what the model itself accepts.)

## Legal lengths

`seconds` must be one of these fourteen values (the model can only make these):

```
5.167  5.875  6.583  7.292  8.0    8.708  9.417
10.125 10.833 11.542 12.25  12.958 13.667 14.375
```

Pick another and the checker tells you the nearest two.

## The two kinds of cut

`continue` chooses between the model's two ways from one clip to the next:

- **`continue: false` — a cut to black.** The scene is rendered on its own and
  the stream cuts to black before it. Use it for a fresh start: a new place, a
  jump in time, a new beat. Write the prompt self-contained.
- **`continue: true` — a hard cut in a continuous take.** The scene opens on the
  exact final frame of the scene before it, with no black between them. This is
  seamless and it is also the trap: the clip generates forward from a generated
  frame, so if you write "the camera keeps following…" the picture smears and
  degrades within a few scenes. **So a `continue: true` scene must open on a
  described hard cut to a new shot** — `Hard cut to a wide shot of …`, `Cut to:
  inside the lamp room, a close-up of …`. The checker requires it. The cut makes
  the model rebuild the whole image, which keeps a chain sharp indefinitely.

`continue: true` can even be the first scene of a file — it then continues from
the last scene of the previous episode, letting two episodes flow together.
Only the very first scene of the whole film cannot continue, since there is
nothing before it.

## Write the prompt for a model that has no memory

The video model reads **only the scene you are writing**. It never sees the
other scenes. So every prompt must re-describe everything: the look from
[STYLE.md](../../STYLE.md), the setting, who is in frame, the light, the mood.
Leaving something out means it vanishes or mutates. Yes, this repeats across
scenes. That repetition is what holds the film together.

Other prompt rules:

- Up to **800 characters** per prompt (after collapsing whitespace). The checker
  counts for you.
- The model renders **sound with picture**. Name the ambience in a short clause.
  When someone speaks, write the exact words in quotes and say how they sound.
- Describe only what the camera sees and the microphone hears. No text overlays,
  no scene numbers, no camera jargon the model cannot show.

## Check it before you open the pull request

The same checker that gates your pull request runs offline. From a checkout of
the `code` branch:

```bash
python3 story-tools/validate.py <path-to-your-story-checkout>
```

It lists every problem at once, with the file and line. A clean run is a clean
pull request.
