# Agent instructions for the `story` branch

You are on the branch that **is the film**. There is no code here — only
episode files, the show bible, and the guides in `skills/`. Read the guide that
matches the task before you write a line:

| Task | Read |
| --- | --- |
| Find your way around — two orphan branches, what lives where, how the film becomes a broadcast | [`skills/repository-map`](./skills/repository-map/SKILL.md) |
| Write or edit a scene, and pass the format check on the first try | [`skills/writing-a-scene`](./skills/writing-a-scene/SKILL.md) |
| Get a pull request merged — the vote, the anchor, the wait after a push, credit | [`skills/how-approval-works`](./skills/how-approval-works/SKILL.md) |

## Rules that apply to every change here

- A story pull request may touch **only** `NNNN-title.md` episode files and the
  three root documents (`README.md`, `STYLE.md`, `LICENSE`). Never touch
  `skills/`, `.github/`, `AGENTS.md`, or any folder — the format check refuses
  the whole pull request if you do. Those are maintained by the project on this
  branch directly.
- Read [`STYLE.md`](./STYLE.md) before writing a prompt. Every scene must
  re-describe the whole look; the model has no memory of other scenes, and
  nothing is added to a prompt before it is rendered.
- A prompt is 200 to 800 characters of plain prose (aim for 500 to 700) and
  ends with a sound clause. When someone speaks, name who speaks, give the
  exact words in quotes, and say how the voice sounds; the model renders
  speech and will invent words you do not give it. Describe only what the
  camera sees and the microphone hears: no text on screen, no "cut to", no
  film jargon. The full recipe is in
  [`skills/writing-a-scene`](./skills/writing-a-scene/SKILL.md).
- Describe a recurring character the way `STYLE.md` describes them, every
  time. A new character goes into `STYLE.md` in the same pull request.
- Run the validator before opening a pull request. It lives on the `code`
  branch: `python3 story-tools/validate.py <path-to-this-checkout>`.
- Do not edit the code that plays the film from here. It lives on the `code`
  branch, which has its own `AGENTS.md` and `skills/`.
- Never commit, push, or open a pull request without the human in the
  conversation asking for it.
