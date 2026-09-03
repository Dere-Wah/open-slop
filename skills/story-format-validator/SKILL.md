---
name: story-format-validator
description: The Open Slop episode format as story-tools/validate.py enforces it — file and filename rules, scene header parsing, the legal clip lengths, the continue/hard-cut rule, the pull-request path allowlist with renames and deletions, and the procedure for changing a rule without CI, the projector, and the story branch's guides drifting apart.
---

# The story format and its validator

`story-tools/validate.py` is the **single definition** of a legal film. Three
things run it and nothing else defines the format:

- the story branch's `story-validate` workflow, on every pull request and on
  every push to the branch tip;
- the projector (`projector/story.py`), to parse the film it airs;
- a contributor offline, before opening a pull request.

It has no third-party dependency, on purpose: CI checks it out from this branch
and runs it against the pull request as data, and a dependency install would be
one more thing that could execute foreign code.

## What a film is

A film is the sorted list of `NNNN-title.md` files at the root of the story
branch. Nothing else in the root is a film file; unknown files are ignored by
the parser (the allowlist, below, is what keeps them out of pull requests).

Per file:

- Filename `^\d{4}-[a-z0-9-]+\.md$`, at most `MAX_FILENAME_CHARS` (72).
  Sorted by name; ties are impossible because names are unique.
- Optional `# Title` on the first non-blank line, at most `MAX_TITLE_CHARS`
  (120). Any other line starting with `#` anywhere in the file is an error.
- Then one or more scenes. A scene is a header fenced by two lines that are
  exactly `---`, followed by a prompt body that runs to the next `---` or the
  end of the file. Fences must alternate; an odd count, a header with no body,
  or a body that is only blank lines is an error naming the line.
- Text is UTF-8; a byte-order mark is stripped and CRLF is folded to LF before
  parsing, so a Windows editor does not fail a contributor.
- The file must not be a symlink.

Per scene header, `key: value` lines only:

| Key | Rule |
| --- | --- |
| `seed` | required; ASCII digits only (`^[0-9]+$`), so `1e3`, `0x10`, and Unicode digits are refused rather than guessed. |
| `seconds` | required; one of `LEGAL_SECONDS`. The list is derived, not typed: `frames = 124 + 17·k` up to 345 at 24 fps, rounded to 3 decimals — the exact set `fast-h3` can build. An illegal value is reported with the nearest two legal ones. |
| `continue` | optional; exactly `true` or `false`. |

Any other key is an error: a key nothing reads is a contributor believing they
set something.

Per prompt body: at most `MAX_PROMPT_CHARS` (800) after collapsing whitespace.
The parser records `body_line_start` / `body_line_end` **trimmed of surrounding
blank lines**; the projector blames exactly that range, so credit lands on the
words and not on a stray empty line someone else added.

## Cross-scene rules (`build_film`)

- **Effective `continue`.** Absent, it is `true` for every scene that has a
  predecessor — including the first scene of a file, which then continues from
  the previous episode's last scene — and `false` for the first scene of the
  whole film.
- **The first scene of the film cannot set `continue: true`.** This check is
  skipped when an earlier file failed to parse, so one broken file does not
  cascade a misleading error onto its neighbour.
- **A continued scene must open on a hard cut.** When the effective `continue`
  is true, the prompt must open on `_HARD_CUT_RE` — `cut to` with an optional
  `hard`, case-insensitive: `Hard cut to a wide shot…`, `Cut to: the lamp
  room…`. A continuation generates
  forward from the previous clip's last frame; without a described cut the
  picture smears. When `continue` is false the rule does not apply.
- An empty film (no scenes at all) is an error.

## The pull-request allowlist (`validate_paths`)

CI passes the pull request's file list as `--changed-file changed.tsv`, one
`status<TAB>path<TAB>previous_path` per line (`Change.parse_tsv_line`). Judging
by status is what closes the rename and deletion holes:

- Paths are normalised strictly (`_normalize_path`): exactly one leading `./`
  is tolerated; surrounding whitespace, control characters, backslashes, a
  leading `/`, and `..` segments are refused rather than cleaned, because a
  cleaned path is not the path the pull request changes. Anything with a `/`
  left in it is a subdirectory and fails the allowlist — a story pull request
  can only ever touch the root.
- An episode file may be **added, modified, removed, or renamed**, and a rename
  is judged by **both** its source and its target: episode → episode only. A
  rename whose source is a workflow or a skill is a deletion of that file in
  disguise and is refused.
- `README.md`, `STYLE.md`, `LICENSE` may be modified, **never** removed or
  renamed.
- Everything else — `.github/**`, `skills/**`, `AGENTS.md`, any folder, any
  other root file — is refused. This is the load-bearing guard: GitHub's native
  path restriction is a push-ruleset rule and unavailable on public
  repositories, so the workflow files that gate the story live on the story
  branch **only because this allowlist keeps pull requests off them**.
- A changed path that is a symlink in the checkout is refused.

## The report

With `--report`, a passing run prints where each changed episode lands (its
neighbours), its scene count and runtime, and the film's new total. CI posts
this into the pull request; it is the contributor's confirmation that the
ordering they intended is the one they got.

## Changing a rule

1. Change `validate.py`. Keep the change data-driven where the code already is
   (the legal lengths are derived from `fast-h3`'s frame arithmetic; do not
   type a list).
2. Add or change a test in `test_validate.py`. Every rule above has one; a rule
   without a test is a rule the next change silently drops. Run
   `python3 story-tools/test_validate.py` (or `pytest story-tools -q`).
3. Update the **story branch's** `skills/writing-a-scene` (format) or
   `skills/how-approval-works` (allowlist) so the contributor-facing text says
   what the code does. Those guides live on the other branch; do it in the same
   piece of work.
4. If the projector reads the field (`seed`, `seconds`, `continue`, the blame
   range), check `projector/story.py` and `screening.py` still agree.
5. The story branch's workflows check this branch out **at a ref**. Until the
   pinned sha in `story-validate.yml` moves, CI runs the old validator; see
   `story-ci-and-approval`.
