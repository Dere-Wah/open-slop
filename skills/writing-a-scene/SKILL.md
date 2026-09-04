---
name: writing-a-scene
description: Write or edit an OpenSlop scene — the episode file format, the seed/seconds/continue header, what `continue` does and why long chains degrade, how lengths round to what the model can make, how to write a prompt the video model renders well (self-contained, sound and quoted dialogue included, 200–800 characters), and how to pass the format checker on the first try.
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
The first scene's prompt, in plain English, 200 to 800 characters…

---
seed: 481517
seconds: 10.125
continue: true
---
The second scene's prompt, describing the whole picture again…
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
| `seconds` | yes | a number above zero | The clip's length. Rounded up to the nearest length the model can make; see below. |
| `continue` | no | exactly `true` or `false` | How this scene joins the previous one. Defaults to `true` when the scene has a predecessor, and to `false` for the very first scene of the whole film. |

Only these three keys, written as `key: value`, one per line. Any other key is
rejected — a key nothing reads is a contributor thinking they set something that
never took effect. (There is no `length`; the key is `seconds`, because that is
what the model itself accepts.) Values are read strictly: `seed: 1e3`,
`seed: 0x10`, `continue: yes` are all errors, not guesses.

## Lengths

Write any number of seconds. The model makes clips in fixed steps, so your
value is rounded **up** to the next one and clamped to the range; the bot's
report says what will play. The lengths it can make are:

```
5.167  5.875  6.583  7.292  8.0    8.708  9.417
10.125 10.833 11.542 12.25  12.958 13.667 14.375
```

So `seconds: 10` plays as 10.125 and `seconds: 3` as 5.167. Use the short end,
under 8 seconds, only for a transition, an establishing shot, or a reaction
beat; a scene that carries a line of dialogue or an action needs 8 seconds or
more. The clip ends when the time is up, mid-sentence if it must.

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
other scenes, and nothing is added to your prompt before it is rendered: no
rewriting, no expansion, no hidden style. What you write is what it reads. So
every prompt must re-describe everything: the look from
[STYLE.md](../../STYLE.md), the setting, who is in frame, the light, the mood,
the sound. Leaving something out means it vanishes or mutates. Yes, this repeats
across scenes. That repetition is what holds the movie together.

### Length

Between **200 and 800 characters**, measured after collapsing every run of
whitespace (line breaks included) to one space; that collapsed text is exactly
what the model receives, so the checker's count is the model's count. The cap is
the model's hard limit. The floor is ours: a prompt that cannot name the look,
the setting, the subject, the light, and the sound in 200 characters is not
describing a scene. Aim for 500 to 700. The checker reports each scene's length
in the pull request.

### Order

Write the prompt in this order; it is the order the model weighs it:

1. The shot and the subject: wide, medium, close-up, extreme close-up, and who
   or what is in it, described in full every time.
2. The action: one thing happening.
3. The setting.
4. The camera: holding still, drifting forward, slowly pushing in. Plain words.
5. The look and the light: the house look, then this scene's palette and where
   the light comes from.
6. The mood, in two or three words.
7. The sound, always last, always present.

### Sound and dialogue

The model renders **sound with the picture, speech included**. A prompt that
says nothing about sound comes out flat or with a noise the model invented.

- End every prompt with a soundscape clause. `Sound: low surf, a buoy bell far
  off, a faint electric hum.` Three or four sounds is plenty.
- When someone speaks, write **who speaks**, the **exact words in quotes**, and
  **how the voice sounds**:

  ```
  He speaks slowly in a low, tired, gravelly voice: "They only come when the
  light is wrong."
  ```

  The model says the words you give it. `He mutters something` makes it invent
  the something.
- One line of dialogue per scene. A speech does not fit in ten seconds.
- Silence is a sound: `No gulls, no bell.` tells the model what to leave out.

### What not to write

- Nothing the camera cannot see or the microphone cannot hear: no text on
  screen, no titles, no scene numbers, no "cut to", no "as before" or "the same
  as the last scene" (there is no last scene, as far as the model knows).
- No film jargon. Say "the camera slowly pushes in", not "slow dolly in".
- Plain punctuation: commas, full stops, colons, quotes.

### A worked example

```
A close-up of the lighthouse keeper's face at the lamp-room window: an old man
with a salt-white beard, deep lines around his eyes, a dark wool cap, and the
high collar of a heavy blue coat. Flat 2D cel animation, thick black outlines,
flat fills. Briny blues and fog greys, one side of his face washed warm
lamp-yellow each time the great lens turns past behind him. He watches the grey
sea below without blinking, then speaks slowly in a low, tired, gravelly voice:
"They only come when the light is wrong." The camera holds on his face. Sound:
wind hums against the glass, the lamp mechanism ticks in a steady rhythm, the
surf is faint and far below.
```

Shot and subject, action, setting, look and light, dialogue with a named voice,
camera, soundscape. 653 characters. Every scene in `0010-the-arrival.md` is
built this way; copy the shape, not the words.

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

If you open the pull request anyway and the check fails, a second bot reads the
same file and leaves one-click fixes as review suggestions under **Files
changed**: the header rewritten to `seed` / `seconds` / `continue` (a missing
`seconds` becomes `8`, a missing `seed` is picked for you), a prompt over 800
characters cut at its last full sentence with the dropped tail quoted, a `----`
made `---`, a missing title taken from the filename. Read each before you press
**Commit suggestion**; the cut it proposes is the shortest legal one, not the
best one. What it cannot fix (the filename, a prompt under 200 characters) it
describes in the check's comment instead.

## What happens after the merge

The projector snapshots the branch about a minute of film before each screening
starts, so your scene is on air from the first screening snapshotted after the
merge — the viewer's countdown says which story version comes up next. Credit
comes from `git blame` on your scene's prompt lines; see
[how-approval-works](../how-approval-works/SKILL.md).
