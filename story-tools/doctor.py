# Copyright (c) 2026 Reactor Technologies, Inc. All rights reserved.
"""Propose fixes for a story pull request as GitHub review suggestions.

The validator judges; the doctor offers the smallest edit that would satisfy
it. It reads the pull request's changed episode files as text, finds what the
validator refuses, and emits line-range edits as JSON. The workflow renders
each one as a ```suggestion``` review comment, which the author commits with
one click; what no suggestion can express (a rename, a prompt too short to
keep) becomes a note in the same review.

Nothing here executes or imports pull request content, and nothing is written
back: the doctor prints, the author decides. Every file's suggestions are
applied in memory and re-read with the validator before they are offered, so
a suggestion that would not pass is never shown.

Usage: doctor.py ROOT --changed-file changed.tsv  (prints JSON to stdout)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import textwrap
from dataclasses import asdict, dataclass, field
from pathlib import Path

import validate
from validate import (
    MAX_PROMPT_CHARS,
    MAX_TITLE_CHARS,
    MIN_PROMPT_CHARS,
    Change,
)

# A header the author got almost right: the key, in any case, under any of
# the names people reach for. Anything else is dropped, and the drop is said.
_KEY_ALIASES = {
    "seed": {"seed", "seeds"},
    "seconds": {"seconds", "second", "secs", "sec", "s", "length", "duration", "time"},
    "continue": {"continue", "continues", "cont", "continued"},
}
_KNOWN_KEYS = frozenset(alias for names in _KEY_ALIASES.values() for alias in names)
_TRUE_WORDS = frozenset({"true", "yes", "y", "on", "1"})
_FALSE_WORDS = frozenset({"false", "no", "n", "off", "0"})

# A row of three or more dashes reads as a fence even when it is not exactly
# `---`; the strict parser wants it exact, so the doctor suggests that.
_FENCE_RE = re.compile(r"^\s*-{3,}\s*$")
_KV_RE = re.compile(r"^\s*([A-Za-z_][\w -]*?)\s*[:=]\s*(.*?)\s*$")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_SENTENCE_END_RE = re.compile(r"[.!?…][\"”’')\]]*(?=\s|$)")

# When a scene names no length, this one fits a line of dialogue or an action.
_DEFAULT_SECONDS = "8"
_WRAP_COLUMNS = 80
_INDEX_STEP = 10


@dataclass
class Suggestion:
    """Replace lines `start_line..end_line` (1-based, inclusive) with `replacement`.

    An empty replacement removes the lines. `why` is the sentence shown above
    the suggestion block.
    """

    path: str
    start_line: int
    end_line: int
    replacement: str
    why: str


@dataclass
class Note:
    """A fix no suggestion can carry, said in words."""

    path: str
    body: str


@dataclass
class FileReport:
    path: str
    suggestions: list[Suggestion] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    # Validator messages still standing after every suggestion is applied.
    remaining: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ helpers


def apply(text: str, suggestions: list[Suggestion]) -> str:
    """The file after every suggestion is committed, for checks and tests."""
    lines = validate._normalize_text(text).split("\n")
    for suggestion in sorted(suggestions, key=lambda s: s.start_line, reverse=True):
        new = suggestion.replacement.split("\n") if suggestion.replacement != "" else []
        lines[suggestion.start_line - 1 : suggestion.end_line] = new
    return "\n".join(lines)


def _derived_seed(prose: str) -> int:
    """A seed drawn from the words, so re-running the doctor picks the same one."""
    digest = hashlib.sha1(" ".join(prose.split()).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _title_from_name(name: str) -> str:
    stem = re.sub(r"\.md$", "", name, flags=re.IGNORECASE)
    stem = re.sub(r"^\d{4}[-_ ]*", "", stem)
    words = [w for w in re.split(r"[-_\s]+", stem) if w]
    return " ".join(w[:1].upper() + w[1:] for w in words) or "Untitled"


def _next_free_index(root: Path, exclude: str) -> int:
    highest = 0
    for path in root.iterdir():
        if path.name != exclude and validate._EPISODE_RE.match(path.name):
            highest = max(highest, int(path.name[:4]))
    return min(9999, (highest // _INDEX_STEP + 1) * _INDEX_STEP)


def fixed_name(root: Path, name: str) -> str | None:
    """The legal filename for `name`, or None when it already is one or none fits."""
    if validate._EPISODE_RE.match(name):
        return None
    stem = name[:-3] if name.lower().endswith(".md") else name
    match = re.match(r"^(\d{4})[-_ ]*(.*)$", stem)
    if match:
        number, title = match.groups()
    else:
        number, title = f"{_next_free_index(root, name):04d}", stem
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    candidate = f"{number}-{slug}.md"
    if not slug or not validate._EPISODE_RE.match(candidate):
        return None
    if len(candidate) > validate.MAX_FILENAME_CHARS:
        candidate = candidate[: validate.MAX_FILENAME_CHARS - 3].rstrip("-") + ".md"
    return candidate


def truncate_prompt(collapsed: str) -> tuple[str, str]:
    """Cut a collapsed prompt to the cap at the last full sentence that fits.

    Returns (kept, dropped). Falls back to a word boundary when no sentence end
    leaves at least the floor standing.
    """
    cut = -1
    for match in _SENTENCE_END_RE.finditer(collapsed):
        if match.end() <= MAX_PROMPT_CHARS:
            cut = match.end()
        else:
            break
    if cut >= MIN_PROMPT_CHARS:
        return collapsed[:cut].rstrip(), collapsed[cut:].strip()
    cut = collapsed.rfind(" ", 0, MAX_PROMPT_CHARS - 1)
    kept = collapsed[:cut].rstrip(" ,;:") + "."
    return kept, collapsed[cut:].strip()


def _wrap(prose: str) -> str:
    return "\n".join(textwrap.wrap(prose, _WRAP_COLUMNS, break_long_words=False, break_on_hyphens=False))


def _looks_like_header(seg_lines: list[str]) -> bool:
    """A segment is a header when every line is `key: value` and one key is known.

    Prose can start with `Sound:`; the known-key requirement keeps a one-line
    scene from reading as a header.
    """
    nonblank = [line for line in seg_lines if line.strip()]
    if not nonblank or len(nonblank) > 8:
        return False
    known = False
    for line in nonblank:
        match = _KV_RE.match(line)
        if not match:
            return False
        key = match.group(1).strip().lower()
        if key in _KNOWN_KEYS:
            known = True
        elif len(line) > 40:
            return False
    return known


def normalize_header(
    seg_lines: list[str], prose: str, *, first_scene_of_film: bool
) -> tuple[list[str], list[str]]:
    """The canonical header for a nearly-right one, and what changed, in words."""
    changes: list[str] = []
    values: dict[str, str] = {}
    raw_keys: dict[str, str] = {}
    for line in seg_lines:
        stripped = line.strip()
        if not stripped:
            continue
        match = _KV_RE.match(stripped)
        if not match:
            changes.append(f"dropped `{stripped}`, which is not `key: value`")
            continue
        key, quoted = match.group(1).strip(), match.group(2).strip()
        value = quoted.strip("\"'")
        canonical = next((k for k, names in _KEY_ALIASES.items() if key.lower() in names), None)
        if canonical is None:
            changes.append(f"dropped `{key}`; a header sets only `seed`, `seconds`, and `continue`")
            continue
        if canonical in values:
            changes.append(f"kept the first `{canonical}` and dropped the repeat")
            continue
        if key != canonical:
            changes.append(f"renamed `{key}` to `{canonical}`")
        if value != quoted:
            changes.append(f"removed the quotes around `{canonical}`")
        if "=" in stripped and ":" not in stripped.split("=", 1)[0]:
            changes.append(f"wrote `{canonical}` with a colon, not `=`")
        values[canonical] = value
        raw_keys[canonical] = key

    out: list[str] = []

    if "seed" in values:
        raw = values["seed"]
        if validate._INT_RE.match(raw):
            seed = str(int(raw))
            if seed != raw:
                changes.append(f"wrote `seed: {raw}` as `{seed}`")
        else:
            digits = re.search(r"\d+", raw)
            if digits:
                seed = str(int(digits.group()))
                changes.append(f"read `seed: {seed}` out of `{raw}`; a seed is a plain whole number")
            else:
                seed = str(_derived_seed(prose))
                changes.append(f"replaced `seed: {raw}` with one drawn from the words; any whole number works")
    else:
        seed = str(_derived_seed(prose))
        changes.append("added a `seed`, drawn from the words so it stays put; any whole number works")
    out.append(f"seed: {seed}")

    if "seconds" in values:
        raw = values["seconds"]
        parsed = validate._as_float(raw)
        if parsed is not None and parsed > 0:
            seconds = raw
        else:
            number = _NUMBER_RE.search(raw)
            value = float(number.group().replace(",", ".")) if number else 0.0
            if value > 0:
                seconds = f"{value:g}"
                changes.append(f"read `seconds: {seconds}` out of `{raw}`")
            else:
                seconds = _DEFAULT_SECONDS
                changes.append(f"replaced `seconds: {raw}` with {_DEFAULT_SECONDS}; it must be a number above zero")
    else:
        seconds = _DEFAULT_SECONDS
        changes.append(f"added `seconds: {_DEFAULT_SECONDS}`, room for a line of dialogue or one action")
    out.append(f"seconds: {seconds}")

    if "continue" in values:
        raw = values["continue"]
        lowered = raw.lower()
        if lowered in _TRUE_WORDS:
            flag: str | None = "true"
        elif lowered in _FALSE_WORDS:
            flag = "false"
        else:
            flag = None
            changes.append(f"dropped `continue: {raw}`; it is `true` or `false`, and left out it means true")
        if flag is not None and flag != raw:
            changes.append(f"wrote `continue: {raw}` as `{flag}`")
        if flag == "true" and first_scene_of_film:
            flag = None
            changes.append("dropped `continue: true` on the film's first scene; there is nothing before it to continue from")
        if flag is not None:
            out.append(f"continue: {flag}")

    return out, changes


# ------------------------------------------------------------------ per file


def _blank(line: str) -> bool:
    return line.strip() == ""


def doctor_file(root: Path, name: str, text: str) -> FileReport:
    """Every suggestion and note for one episode file, verified against the validator."""
    report = FileReport(path=name)
    lines = validate._normalize_text(text).split("\n")
    total = len(lines)

    target = fixed_name(root, name)
    if target is not None:
        if (root / target).exists() and target != name:
            report.notes.append(
                Note(
                    name,
                    f"`{name}` needs a legal name, but `{target}` already exists. Rename the file "
                    f"(open it here, click the pencil, edit the name at the top) to another "
                    f"`NNNN-title-with-dashes.md`.",
                )
            )
        else:
            report.notes.append(
                Note(
                    name,
                    f"Rename `{name}` to `{target}`: open the file in this pull request, click the "
                    f"pencil, and change the name at the top. Episode names are "
                    f"`NNNN-title-with-dashes.md`, lowercase, dashes for spaces.",
                )
            )
    elif not validate._EPISODE_RE.match(name):
        report.notes.append(
            Note(
                name,
                f"`{name}` is not a legal episode name and no name could be made from it. Rename it to "
                f"`NNNN-title-with-dashes.md`: four digits, a dash, a lowercase title.",
            )
        )
    legal_name = target or name
    first_of_film = _is_first_episode(root, name, legal_name)

    # --- title
    i = 0
    while i < total and _blank(lines[i]):
        i += 1
    if i >= total:
        return report  # nothing to work with; the validator says so
    if lines[i].lstrip().startswith("#"):
        match = validate._TITLE_RE.match(lines[i])
        if not match:
            title = lines[i].lstrip("#").strip() or _title_from_name(legal_name)
            report.suggestions.append(
                Suggestion(name, i + 1, i + 1, f"# {title}", "The title is `# Title`: one `#`, a space, the words.")
            )
        elif len(match.group(1)) > MAX_TITLE_CHARS:
            short = match.group(1)[: MAX_TITLE_CHARS - 1].rstrip() + "…"
            report.suggestions.append(
                Suggestion(
                    name, i + 1, i + 1, f"# {short}", f"The title is {len(match.group(1))} characters; the cap is {MAX_TITLE_CHARS}."
                )
            )
        body_from = i + 1
    else:
        nxt = i + 1
        while nxt < total and _blank(lines[nxt]):
            nxt += 1
        first = lines[i].strip()
        reads_as_title = (
            len(first) <= MAX_TITLE_CHARS
            and not first.endswith((".", "!", "?", ",", ";", ":"))
            and nxt < total
            and _FENCE_RE.match(lines[nxt]) is not None
        )
        if reads_as_title:
            report.suggestions.append(
                Suggestion(name, i + 1, i + 1, f"# {first}", "The first line is the title; it needs a `# ` in front.")
            )
            body_from = i + 1
        else:
            derived = _title_from_name(legal_name)
            report.suggestions.append(
                Suggestion(
                    name, i + 1, i + 1, f"# {derived}\n\n{lines[i]}", "An episode opens with its title on the first line."
                )
            )
            body_from = i

    # --- segments between fences
    pieces: list[tuple[str, int, int]] = []  # ("seg", start, end_exclusive) | ("fence", idx, idx)
    start = body_from
    for idx in range(body_from, total):
        if _FENCE_RE.match(lines[idx]):
            pieces.append(("seg", start, idx))
            pieces.append(("fence", idx, idx))
            start = idx + 1
    pieces.append(("seg", start, total))

    fence_lines = [idx for kind, idx, _ in pieces if kind == "fence"]
    removed_fences: set[int] = set()
    fence_deletes: dict[int, Suggestion] = {}

    @dataclass
    class _Scene:
        header: tuple[int, int] | None  # [start, end) of header lines, None when missing
        header_close: int | None  # index of the fence closing the header
        bodies: list[tuple[int, int]]

    scenes: list[_Scene] = []
    pending: tuple[int, int, int] | None = None  # (start, end, closing fence idx)
    for n, (kind, seg_start, seg_end) in enumerate(pieces):
        if kind == "fence":
            continue
        seg = lines[seg_start:seg_end]
        if not any(line.strip() for line in seg):
            # Empty between two fences is an empty header; empty elsewhere is nothing.
            fenced_before = n > 0 and pieces[n - 1][0] == "fence"
            fenced_after = n + 1 < len(pieces) and pieces[n + 1][0] == "fence"
            if fenced_before and fenced_after:
                if pending is not None:
                    report.notes.append(Note(name, f"Scene {len(scenes) + 1} has a header but no words after it."))
                    scenes.append(_Scene((pending[0], pending[1]), pending[2], []))
                pending = (seg_start, seg_end, pieces[n + 1][1])
            continue
        if _looks_like_header(seg):
            if pending is not None:
                report.notes.append(Note(name, f"Scene {len(scenes) + 1} has a header but no words after it."))
                scenes.append(_Scene((pending[0], pending[1]), pending[2], []))
            closing = pieces[n + 1][1] if n + 1 < len(pieces) and pieces[n + 1][0] == "fence" else None
            pending = (seg_start, seg_end, closing)
            continue
        # prose
        if pending is not None:
            scenes.append(_Scene((pending[0], pending[1]), pending[2], [(seg_start, seg_end)]))
            pending = None
            continue
        collapsed = " ".join(" ".join(seg).split())
        previous_fence = pieces[n - 1][1] if n > 0 and pieces[n - 1][0] == "fence" else None
        if scenes and scenes[-1].bodies and previous_fence is not None and len(collapsed) < MIN_PROMPT_CHARS:
            # A short paragraph after a `---` inside a scene: the dash row was a rule, not a scene break.
            removed_fences.add(previous_fence)
            fence_deletes[previous_fence] = Suggestion(
                name,
                previous_fence + 1,
                previous_fence + 1,
                "",
                "A line of dashes always starts a new scene; this one sits inside the prose, so it goes.",
            )
            report.suggestions.append(fence_deletes[previous_fence])
            scenes[-1].bodies.append((seg_start, seg_end))
            continue
        scenes.append(_Scene(None, previous_fence, [(seg_start, seg_end)]))
    if pending is not None:
        report.notes.append(Note(name, f"Scene {len(scenes) + 1} has a header but no words after it."))
        scenes.append(_Scene((pending[0], pending[1]), pending[2], []))

    # --- fences that are not exactly `---`
    for idx in fence_lines:
        if idx not in removed_fences and lines[idx].strip() != validate._FENCE:
            report.suggestions.append(
                Suggestion(name, idx + 1, idx + 1, validate._FENCE, "A scene fence is exactly `---`.")
            )

    # --- each scene
    for k, scene in enumerate(scenes):
        prose_lines: list[str] = []
        for b_start, b_end in scene.bodies:
            prose_lines.extend(lines[b_start:b_end])
        prose_clean = [re.sub(r"^\s*#+\s*", "", line) for line in prose_lines]
        collapsed = " ".join(" ".join(prose_clean).split())
        first_scene = first_of_film and k == 0

        if scene.header is None:
            header_lines, _changes = normalize_header([], collapsed, first_scene_of_film=first_scene)
            b_start = scene.bodies[0][0]
            while _blank(lines[b_start]):
                b_start += 1
            if scene.header_close is not None:
                # `---` then prose: the header is missing between the fence and the words.
                report.suggestions.append(
                    Suggestion(
                        name,
                        scene.header_close + 1,
                        scene.header_close + 1,
                        validate._FENCE + "\n" + "\n".join(header_lines) + "\n" + validate._FENCE,
                        "Every scene opens with a header between two `---` lines; this one has the fence but not the header.",
                    )
                )
            else:
                report.suggestions.append(
                    Suggestion(
                        name,
                        b_start + 1,
                        b_start + 1,
                        validate._FENCE + "\n" + "\n".join(header_lines) + "\n" + validate._FENCE + "\n" + lines[b_start],
                        "Every scene opens with a header between two `---` lines: a seed and a length.",
                    )
                )
        else:
            h_start, h_end = scene.header
            fm = [(idx + 1, lines[idx]) for idx in range(h_start, h_end)]
            _data, issues = validate._parse_frontmatter(name, fm)
            declared_true = any(
                (m := _KV_RE.match(line.strip())) and m.group(1).strip().lower() in _KEY_ALIASES["continue"]
                and m.group(2).strip().strip("\"'").lower() in _TRUE_WORDS
                for _, line in fm
            )
            if issues or (first_scene and declared_true):
                header_lines, changes = normalize_header(
                    [line for _, line in fm], collapsed, first_scene_of_film=first_scene
                )
                said = "; ".join(changes) or "the same fields, written the one way the format reads"
                why = f"The header did not read cleanly; this one does. {said[:1].upper()}{said[1:]}."
                if h_end > h_start:
                    report.suggestions.append(
                        Suggestion(name, h_start + 1, h_end, "\n".join(header_lines), why)
                    )
                elif scene.header_close is not None:
                    report.suggestions.append(
                        Suggestion(
                            name,
                            scene.header_close + 1,
                            scene.header_close + 1,
                            "\n".join(header_lines) + "\n" + validate._FENCE,
                            why,
                        )
                    )

        if not scene.bodies:
            continue
        if not collapsed:
            report.notes.append(Note(name, f"Scene {k + 1} has no words. Write the prompt after its header."))
            continue

        # trimmed prose range, over all body pieces of this scene
        p_start = scene.bodies[0][0]
        p_end = scene.bodies[-1][1] - 1
        while p_start <= p_end and _blank(lines[p_start]):
            p_start += 1
        while p_end >= p_start and _blank(lines[p_end]):
            p_end -= 1

        if len(collapsed) > MAX_PROMPT_CHARS:
            # The cut rewrites the whole range, fences inside it included; a
            # separate delete on one of those lines would overlap it.
            for idx, delete in list(fence_deletes.items()):
                if p_start <= idx <= p_end and delete in report.suggestions:
                    report.suggestions.remove(delete)
            kept, dropped = truncate_prompt(collapsed)
            shown = dropped if len(dropped) <= 300 else dropped[:297].rstrip() + "…"
            report.suggestions.append(
                Suggestion(
                    name,
                    p_start + 1,
                    p_end + 1,
                    _wrap(kept),
                    f"The prompt is {len(collapsed)} characters; the model caps a scene at {MAX_PROMPT_CHARS}. "
                    f"This keeps the first {len(kept)} and ends at the last full sentence that fits, dropping: “{shown}”",
                )
            )
        else:
            for idx in range(p_start, p_end + 1):
                if lines[idx].lstrip().startswith("#"):
                    report.suggestions.append(
                        Suggestion(
                            name,
                            idx + 1,
                            idx + 1,
                            re.sub(r"^\s*#+\s*", "", lines[idx]),
                            "A prompt line cannot start with `#`; only the title is a heading.",
                        )
                    )
            if len(collapsed) < MIN_PROMPT_CHARS:
                report.notes.append(
                    Note(
                        name,
                        f"Scene {k + 1} is {len(collapsed)} characters; a scene needs at least {MIN_PROMPT_CHARS} "
                        f"to carry the look, the setting, who is in frame, the light, and the sound. "
                        f"Only you can write those: see `STYLE.md`.",
                    )
                )

    # --- verify: with every suggestion taken, what does the validator still say?
    if report.suggestions:
        healed = apply(text, report.suggestions)
        _episode, issues = validate.parse_episode(legal_name, healed)
        report.remaining = [issue.message for issue in issues if not _explained_by_note(issue.message)]
    return report


def _explained_by_note(message: str) -> bool:
    return "at least" in message or "has no prompt body" in message


def _is_first_episode(root: Path, name: str, legal_name: str) -> bool:
    if not validate._EPISODE_RE.match(legal_name):
        return False
    mine = (int(legal_name[:4]), legal_name)
    for path in root.iterdir():
        if path.name != name and validate._EPISODE_RE.match(path.name):
            if (int(path.name[:4]), path.name) < mine:
                return False
    return True


# ------------------------------------------------------------------ driver


def diagnose(root: Path, changes: list[Change]) -> list[FileReport]:
    """Reports for every changed file that is, or is trying to be, an episode."""
    reports: list[FileReport] = []
    for change in changes:
        if change.status in (validate._STATUS_REMOVED,):
            continue
        name = change.path
        if "/" in name or "\\" in name or not name.lower().endswith(".md"):
            continue
        if name in validate._ROOT_ALLOWLIST:
            continue
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        report = doctor_file(root, name, text)
        if report.suggestions or report.notes:
            reports.append(report)
    return reports


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Suggest fixes for an OpenSlop pull request.")
    parser.add_argument("root", help="the story root directory (the pull request's tree)")
    parser.add_argument("--changed-file", required=True, metavar="TSV", help="status<TAB>path<TAB>previous")
    args = parser.parse_args(argv)
    changes = validate.read_changes(Path(args.changed_file))
    reports = diagnose(Path(args.root), changes)
    json.dump({"v": 1, "files": [asdict(report) for report in reports]}, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
