<h1 align="center">OpenSlop | The First Ever Open Source Movie</h1>

<p align="center">
  <a href="https://openslop.live">
    <img src="https://raw.githubusercontent.com/Dere-Wah/open-slop/code/assets/screening.png" alt="OpenSlop on air at openslop.live — the player, the rundown, and the chat" width="900">
  </a>
</p>

<p align="center"><b><a href="https://openslop.live">▶&nbsp;&nbsp;Watch the screening</a></b></p>

OpenSlop is a movie made the way open source software is made. There is no
director and no studio. The screenplay is this branch; every `NNNN-title.md`
file is one episode, and every scene in it is a pull request somebody opened.
A projector reads the branch, renders each scene live on
[Reactor](https://reactor.inc), and screens the movie 24/7 at
[openslop.live](https://openslop.live). When it reaches the end, it starts over
with whatever the branch says now.

**You can add to it.** Write a scene, open a pull request, and other viewers
approve it the way they would review code. Reach the bar and it merges on its
own — no maintainer in the loop. Your scene is on air in the next screening,
with your name on screen.

<p align="center"><b><a href="./CONTRIBUTING.md">✍&nbsp;&nbsp;Add a scene in three steps</a></b> · or hand it to a coding agent, the same page says how</p>

## Running on Reactor

Every frame on air is generated the moment you see it. The projector hands each
scene's prompt and seed to [Reactor](https://reactor.inc), a platform for
real-time video and world models, and the `fast-h3` model streams the picture
back as it renders — there is no render farm, no pre-made clips, and no editor
between your pull request and the screen. Same seed, same clip, every screening.
Reactor sponsors the show and keeps the projector on air.

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
A wide shot of a small fog-bound harbour town at dawn, one tall white lighthouse
turning its beam slowly over flat grey water. Flat 2D cel animation, thick black
outlines, flat fills. Briny blues and fog greys, warmed at the horizon by a low
orange sun. The camera holds steady. Quiet and a little eerie. Sound: gulls cry
far off, a buoy bell rings slow, small waves lap against the stone quay.

---
seed: 481517
seconds: 10.125
---
A close-up of the lighthouse keeper's face at the lamp-room window: an old man
with a salt-white beard, a dark wool cap, and a heavy blue coat. Flat 2D cel
animation, thick black outlines, flat fills. Briny blues, one side of his face
washed lamp-yellow as the lens turns past. He speaks slowly in a low, tired,
gravelly voice: "They only come when the light is wrong." The camera holds on
his face. Sound: wind hums against the glass, the lamp mechanism ticks.
```

A scene is a `---` header and a prompt.

| Key | Required | Meaning |
| --- | --- | --- |
| `seed` | yes | An integer. Same seed, same clip. |
| `seconds` | yes | Clip length in seconds. Rounded up to the nearest length the model can make; see [lengths](#lengths). |
| `continue` | no | `true`: this scene starts from the last frame of the previous one. `false`: it starts fresh, after a cut to black. Default `true`. |

The prompt is the scene, in plain English, 200 to 800 characters. The model sees
**only this one prompt**, exactly as written, so describe the whole look every
time. It renders sound and speech too: end every prompt with what we hear, and
when someone talks, give the exact words in quotes and say how the voice
sounds. Read [STYLE.md](./STYLE.md) first; it has the recipe.

**About `continue`.** Every continued scene is generated from a generated frame.
A few in a row look great; a long chain of them slowly degrades. Drop a
`continue: false` in now and then to reset the picture.

## Order

Files play in the order of their number. Numbers step by 10, so `0015` goes
between `0010` and `0020`. To add to the end, pick a higher number. To reorder,
rename. That is the whole system.

## Get it merged

1. Your pull request may touch only `NNNN-title.md` files and `README.md`,
   `STYLE.md`, `LICENSE`. No folders, nothing else (`CONTRIBUTING.md`,
   `AGENTS.md`, and `skills/` are maintained by the project).
2. A bot checks the format and comments where your episode lands and how long
   the movie now runs. When the format is off, it also suggests the fix on
   the lines themselves; **Commit suggestion** applies it. A filename it
   cannot fix for you; the comment tells you the name to use.
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

## Lengths

Write any number of seconds. The model makes clips in fixed steps, so the value
is rounded up to the next one it can make, and the bot's report says what will
play. Those steps are:

```
5.167  5.875  6.583  7.292  8.0    8.708  9.417
10.125 10.833 11.542 12.25  12.958 13.667 14.375
```

## Around here

- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — add or edit a scene in three steps,
  by hand or with an agent.
- [`STYLE.md`](./STYLE.md) — the show bible.
- [`skills/`](./skills) — guides: the repository map, writing a scene, how
  approval works. [`AGENTS.md`](./AGENTS.md) points coding agents at them.
- The code that plays the movie lives on the `code` branch. This branch is only
  the screenplay.

## License

The screenplay is **CC BY-SA 4.0** ([LICENSE](./LICENSE)). Opening a pull
request licenses your writing under the same terms. The code on the `code`
branch is Apache-2.0.
