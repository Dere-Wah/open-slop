---
name: writing-a-scene
description: Write or edit an OpenSlop scene — the episode file format, the seed/seconds/continue header, what `continue` does and why long chains degrade, the legal clip lengths, and how to pass the format checker on the first try.
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

- An optional `# Title` heading on the first line, up to 120 characters. It is
  the only heading allowed in the file.
- Then one or more scenes. Each scene is a `---` header, the two-or-three keys,
  a closing `---`, and the prompt body.
- Nothing else in the file. A line that is exactly `---` inside a prompt body is
  an error — it reads as a scene break. A prompt line that starts with `#` is an
  error too — it reads as a heading that landed in the wrong place.
- Plain UTF-8 text. Windows line endings and a byte-order mark are tolerated.

## The filename sets the order

`NNNN-lower-kebab.md`: four digits, a dash, then lowercase letters, digits, and
dashes, at most 72 characters in all. Files play in number order. Numbers step
by 10 so you can insert: between `0010` and `0020`, add `0015`. To add to the
end, pick a higher number. If two people pick `0015`, both merge and the tie
breaks by the rest of the name — nothing collides except editing the same file.

Renaming an episode to another legal name is how you reorder it, and deleting
one is allowed; both go through the same pull request and vote. Mind the
neighbours: the scene after a deleted or moved episode may start with
`continue: true` and now continue from something else, and the very first scene
of the film can never continue. The check after the merge catches a film that
broke this way, but the vote is the better place to catch it.

## The header keys

| Key | Required | Type | Meaning |
| --- | --- | --- | --- |
| `seed` | yes | integer ≥ 0, plain digits | Fixes the render. The same seed and prompt always make the same clip, so your scene is reproducible and stable across screenings. Pick any number and keep it. |
| `seconds` | yes | one of the legal lengths | The clip's length. |
| `continue` | no | exactly `true` or `false` | How this scene joins the previous one. Defaults to `true` when the scene has a predecessor, and to `false` for the very first scene of the whole film. |

Only these three keys, written as `key: value`, one per line. Any other key is
rejected — a key nothing reads is a contributor thinking they set something that
never took effect. (There is no `length`; the key is `seconds`, because that is
what the model itself accepts.) Values are read strictly: `seed: 1e3`,
`seed: 0x10`, `continue: yes` are all errors, not guesses.

## Legal lengths

`seconds` must be one of these fourteen values (the model can only make these):

```
5.167  5.875  6.583  7.292  8.0    8.708  9.417
10.125 10.833 11.542 12.25  12.958 13.667 14.375
```

Pick another and the checker tells you the nearest two.

## `continue`

`continue` is one true/false choice: does this scene start from the last frame
of the scene before it?

- **`true`** (the default) — the scene picks up from the previous clip's final
  frame, with no black between them.
- **`false`** — the scene starts fresh, after a cut to black.

The checker does not look at the prompt for this; it only reads the flag.

**Warning:** a continued scene is generated from a generated frame. A few in a
row look fine; a long chain of them degrades — the picture drifts, softens, and
loses detail. Put a `continue: false` in every few scenes to reset it.

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
# with the pull request's allowlist and the runtime report too:
python3 story-tools/validate.py <path-to-your-story-checkout> --changed 0015-x.md --report
```

It lists every problem at once, with the file and line. A clean run is a clean
pull request.

## What happens after the merge

The projector snapshots the branch about a minute of film before each screening
starts, so your scene is on air from the first screening snapshotted after the
merge — the viewer's countdown says which story version comes up next. Credit
comes from `git blame` on your scene's prompt lines; see
[how-approval-works](../how-approval-works/SKILL.md).
