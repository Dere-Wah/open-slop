"""The one validator, shared by CI and the projector.

An Open Slop screenplay is a set of episode files at the root of the `story`
branch. One file is one episode; one episode is a run of scenes separated by
`---` blocks. This module is the single implementation of what a legal episode
is: CI runs it to gate a pull request, and the projector runs the same code to
read the film it broadcasts. If the projector cannot parse an episode, CI has
already rejected it.

It reads and validates; it never writes. It has no third-party dependency, so
the CI shim on the `story` branch can run it straight from a checkout with a
bare Python.

Run it:

    python validate.py <story-root>                          # the whole film
    python validate.py <story-root> --changed 0015-x.md      # plus the allowlist
    python validate.py <story-root> --changed-file changed.tsv --report

`--changed-file` is what CI uses: one changed file per line as
`<status>\\t<path>\\t<previous path>` straight off the pull-request file list, so
renames and deletions are judged as what they are, not as bare paths.

Import it:

    from validate import load_film, build_film, validate_paths, Change
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# fast-h3's fixed output rate and its legal clip lengths. A clip is a frame
# count of the form 17n + 5 between 124 and 345 frames, so exactly 14 lengths
# are legal, 5.167 s to 14.375 s, stepping ~0.708 s. Authors name one of these
# exactly, so the render is deterministic — the model would otherwise snap a
# free value and the seed would land on a length nobody chose.
FPS = 24
_MIN_FRAMES = 124
_MAX_FRAMES = 345
_FRAME_STEP = 17
LEGAL_FRAMES = list(range(_MIN_FRAMES, _MAX_FRAMES + 1, _FRAME_STEP))
LEGAL_SECONDS = [round(frames / FPS, 3) for frames in LEGAL_FRAMES]

# The model's hard cap on one prompt, enforced server-side.
MAX_PROMPT_CHARS = 800

# Caps on the two strings that ride the model's 2000-character metadata field
# with every clip. Generous for a title; tight enough that no legal episode
# can push the tag over the wire limit.
MAX_TITLE_CHARS = 120
MAX_FILENAME_CHARS = 72

_EPISODE_RE = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")
_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$")
_HARD_CUT_RE = re.compile(r"^\s*(hard\s+)?cut to\b", re.IGNORECASE)
_INT_RE = re.compile(r"^[0-9]+$")  # ASCII digits only; `\d` would admit other scripts
_FENCE = "---"
_ALLOWED_KEYS = ("seed", "seconds", "continue")

# What a story pull request may add or change at the branch root. Everything
# else — every subdirectory, and above all `.github/` (which lives on this
# branch only because the default-branch trigger rule forces it there) — is
# refused. This is the wall that keeps code off the story branch.
_ROOT_ALLOWLIST = frozenset({"README.md", "STYLE.md", "LICENSE"})

# Pull-request file statuses as GitHub reports them.
_STATUS_REMOVED = "removed"
_STATUS_RENAMED = "renamed"


class StoryError(Exception):
    """Raised by `load_film` when the film does not validate."""

    def __init__(self, issues: list["Issue"]) -> None:
        self.issues = issues
        super().__init__("\n".join(str(issue) for issue in issues))


@dataclass(frozen=True)
class Issue:
    """One validation problem, addressed to a file and (when known) a line."""

    path: str
    line: int | None
    message: str

    def __str__(self) -> str:
        where = self.path if self.line is None else f"{self.path}:{self.line}"
        return f"{where}: {self.message}"

    def annotation(self) -> str:
        """The GitHub Actions `::error` form, for inline PR annotations."""
        loc = f"file={_annotation_safe(self.path)}"
        if self.line is not None:
            loc += f",line={self.line}"
        return f"::error {loc}::{self.message}"


def _annotation_safe(path: str) -> str:
    """A path that cannot break out of a `::error` property list."""
    return re.sub(r"[^\w./-]", "_", path)[:200]


@dataclass
class Scene:
    """One clip: a prompt, a seed, a length, and how it joins the previous one.

    `body_line_start` / `body_line_end` are 1-indexed lines in the source file,
    covering the prompt prose only — never the `---` header, and never the
    blank lines around the prose. The projector blames exactly that range to
    credit the words to their author, so a blank separator line someone added
    while appending the next scene must not fall inside it.
    """

    index: int  # 0-based position within its episode
    seed: int
    seconds: float
    declared_continue: bool | None
    body: str
    body_line_start: int
    body_line_end: int
    # Filled once the whole film is known: the first scene of the film is
    # always a fresh start; every other scene continues unless it says not to.
    effective_continue: bool = False


@dataclass
class Episode:
    """One file: an ordering index, an optional title, and its scenes in order."""

    path: str  # the filename, e.g. "0010-the-arrival.md"
    order_index: int  # the four-digit prefix as an int
    title: str | None
    scenes: list[Scene] = field(default_factory=list)

    @property
    def seconds(self) -> float:
        return sum(scene.seconds for scene in self.scenes)


@dataclass
class Film:
    """The whole screenplay, episodes in play order."""

    episodes: list[Episode] = field(default_factory=list)

    @property
    def scenes(self) -> list[tuple[Episode, Scene]]:
        return [(episode, scene) for episode in self.episodes for scene in episode.scenes]

    @property
    def total_seconds(self) -> float:
        return sum(episode.seconds for episode in self.episodes)


@dataclass(frozen=True)
class Change:
    """One file a pull request touches, as GitHub reports it."""

    path: str
    status: str = "modified"  # added | modified | removed | renamed | ...
    previous_path: str | None = None

    @staticmethod
    def parse_tsv_line(line: str) -> "Change | None":
        """`status<TAB>path<TAB>previous` (the last field optional), or None."""
        stripped = line.rstrip("\r\n")
        if not stripped.strip():
            return None
        parts = stripped.split("\t")
        if len(parts) == 1:
            return Change(path=parts[0])
        status = parts[0].strip() or "modified"
        previous = parts[2] if len(parts) > 2 and parts[2] else None
        return Change(path=parts[1], status=status, previous_path=previous)


# --------------------------------------------------------------- frontmatter


def _as_int(value: str) -> int | None:
    """A plain decimal integer — no sign, no underscores, no exotic digits."""
    return int(value) if _INT_RE.match(value) else None


def _as_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _as_bool(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def _match_legal_seconds(value: float) -> float | None:
    """The canonical legal length `value` names, or None if it names none."""
    for legal in LEGAL_SECONDS:
        if abs(value - legal) < 0.005:
            return legal
    return None


def _nearest_legal(value: float) -> tuple[float, float]:
    """The two legal lengths closest to `value`, low then high where possible."""
    ordered = sorted(LEGAL_SECONDS, key=lambda legal: abs(legal - value))
    pair = sorted(ordered[:2])
    return pair[0], pair[1]


def _parse_frontmatter(
    path: str, fm_lines: list[tuple[int, str]]
) -> tuple[dict, list[Issue]]:
    """Parse a scene's `key: value` header into typed, validated fields."""
    issues: list[Issue] = []
    data: dict = {}
    seen: set[str] = set()
    for lineno, raw in fm_lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if ":" not in stripped:
            issues.append(
                Issue(
                    path,
                    lineno,
                    f"expected 'key: value' in a scene header, got {stripped!r} "
                    "— a stray '---' line inside a prompt body can cause this",
                )
            )
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if key not in _ALLOWED_KEYS:
            issues.append(
                Issue(
                    path,
                    lineno,
                    f"unknown scene key {key!r}; a scene sets only "
                    "seed, seconds, and the optional continue",
                )
            )
            continue
        if key in seen:
            issues.append(Issue(path, lineno, f"duplicate key {key!r} in one scene header"))
            continue
        seen.add(key)
        if key == "seed":
            parsed = _as_int(value)
            if parsed is None:
                issues.append(
                    Issue(path, lineno, f"seed must be a plain integer >= 0 (digits only), got {value!r}")
                )
            else:
                data["seed"] = parsed
        elif key == "seconds":
            parsed = _as_float(value)
            if parsed is None:
                issues.append(Issue(path, lineno, f"seconds must be a number, got {value!r}"))
            else:
                legal = _match_legal_seconds(parsed)
                if legal is None:
                    low, high = _nearest_legal(parsed)
                    issues.append(
                        Issue(
                            path,
                            lineno,
                            f"{value} is not a legal clip length — try {low} or {high}",
                        )
                    )
                else:
                    data["seconds"] = legal
        else:  # continue
            parsed = _as_bool(value)
            if parsed is None:
                issues.append(
                    Issue(path, lineno, f"continue must be exactly true or false, got {value!r}")
                )
            else:
                data["continue"] = parsed
    if "seed" not in data:
        issues.append(Issue(path, None, "a scene header is missing the required key 'seed'"))
    if "seconds" not in data:
        issues.append(Issue(path, None, "a scene header is missing the required key 'seconds'"))
    return data, issues


# ------------------------------------------------------------- episode parse


def _normalize_text(text: str) -> str:
    """Drop a BOM and fold Windows line endings so line numbers stay honest."""
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_episode(name: str, text: str) -> tuple[Episode | None, list[Issue]]:
    """Parse one episode file into scenes, collecting every problem found.

    Returns the episode (None when its structure is too broken to trust) and
    the list of issues. `effective_continue` and the cross-file hard-cut rule
    are filled later by `build_film`, since they depend on film order.
    """
    issues: list[Issue] = []
    if not _EPISODE_RE.match(name):
        issues.append(
            Issue(
                name,
                None,
                "episode filename must be NNNN-lower-kebab.md "
                "(four digits, a dash, then lowercase letters, digits, and dashes)",
            )
        )
    if len(name) > MAX_FILENAME_CHARS:
        issues.append(
            Issue(name, None, f"episode filename is {len(name)} characters; the cap is {MAX_FILENAME_CHARS}")
        )
    order_index = int(name[:4]) if name[:4].isdigit() else 0

    lines = _normalize_text(text).split("\n")
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    title: str | None = None
    if i < len(lines) and lines[i].lstrip().startswith("#"):
        match = _TITLE_RE.match(lines[i])
        if match:
            title = match.group(1)
            if len(title) > MAX_TITLE_CHARS:
                issues.append(
                    Issue(name, i + 1, f"title is {len(title)} characters; the cap is {MAX_TITLE_CHARS}")
                )
        else:
            issues.append(Issue(name, i + 1, "malformed title heading; use '# Title'"))
        i += 1

    scenes: list[Scene] = []
    while i < len(lines):
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        if i >= len(lines):
            break
        if lines[i].strip() != _FENCE:
            hint = (
                "text before the first scene"
                if not scenes
                else "stray text between scenes — a line that is exactly '---' "
                "inside a prompt body also lands here"
            )
            issues.append(Issue(name, i + 1, f"expected a scene block opening with '---' ({hint})"))
            return None, issues
        open_line = i
        i += 1

        fm_lines: list[tuple[int, str]] = []
        while i < len(lines) and lines[i].strip() != _FENCE:
            fm_lines.append((i + 1, lines[i]))
            i += 1
        if i >= len(lines):
            issues.append(
                Issue(
                    name,
                    open_line + 1,
                    "unterminated scene header: no closing '---' — if this '---' sits inside "
                    "a prompt body, reword the prompt; a line that is exactly '---' always "
                    "reads as a scene break",
                )
            )
            return None, issues
        close_line = i
        i += 1

        body_start = i
        body_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != _FENCE:
            body_lines.append(lines[i])
            i += 1

        data, fm_issues = _parse_frontmatter(name, fm_lines)
        issues.extend(fm_issues)

        # The blame range covers the prose only: trim the blank lines an
        # author leaves around it, so appending the next scene (which adds a
        # blank separator) never puts the appender's line inside this scene.
        first = 0
        while first < len(body_lines) and body_lines[first].strip() == "":
            first += 1
        last = len(body_lines) - 1
        while last >= first and body_lines[last].strip() == "":
            last -= 1
        prose_lines = body_lines[first : last + 1]
        body = "\n".join(prose_lines).strip()

        if not body:
            issues.append(Issue(name, close_line + 1, f"scene {len(scenes) + 1} has no prompt body"))
            prose_start = close_line + 1
            prose_end = close_line + 1
        else:
            prose_start = body_start + first + 1
            prose_end = body_start + last + 1
            collapsed = " ".join(body.split())
            if len(collapsed) > MAX_PROMPT_CHARS:
                issues.append(
                    Issue(
                        name,
                        prose_start,
                        f"prompt is {len(collapsed)} characters; the model caps a scene at "
                        f"{MAX_PROMPT_CHARS}",
                    )
                )
            for offset, line in enumerate(prose_lines):
                if line.lstrip().startswith("#"):
                    issues.append(
                        Issue(
                            name,
                            prose_start + offset,
                            "a prompt line cannot start with '#': the only heading is the "
                            "episode title on the first line",
                        )
                    )
                    break

        scenes.append(
            Scene(
                index=len(scenes),
                seed=data.get("seed", 0),
                seconds=data.get("seconds", 0.0),
                declared_continue=data.get("continue"),
                body=body,
                body_line_start=prose_start,
                body_line_end=prose_end,
            )
        )

    if not scenes:
        issues.append(Issue(name, None, "an episode needs at least one scene"))
        return None, issues

    return Episode(path=name, order_index=order_index, title=title, scenes=scenes), issues


# ------------------------------------------------------------------ the film


def build_film(root: Path) -> tuple[Film, list[Issue]]:
    """Read and validate every episode at `root`, in play order.

    Aggregates all problems rather than stopping at the first, so a
    contributor sees every fix a pull request needs in one pass.
    """
    issues: list[Issue] = []
    candidates = sorted(
        (p for p in root.iterdir() if _EPISODE_RE.match(p.name)),
        key=lambda p: (int(p.name[:4]), p.name),
    )
    files: list[Path] = []
    for path in candidates:
        if path.is_symlink():
            issues.append(Issue(path.name, None, "an episode must be a regular file, not a symlink"))
        elif path.is_file():
            files.append(path)
        else:
            issues.append(Issue(path.name, None, "an episode name is taken by something that is not a file"))
    if not files:
        issues.append(Issue(str(root), None, "no episode files found (expected NNNN-title.md at the root)"))
        return Film(), issues

    episodes: list[Episode] = []
    any_failed = False
    for path in files:
        episode, episode_issues = parse_episode(path.name, path.read_text(encoding="utf-8-sig"))
        issues.extend(episode_issues)
        if episode is not None:
            episodes.append(episode)
        else:
            any_failed = True

    first = True
    for episode in episodes:
        for scene in episode.scenes:
            if first:
                # When an earlier file failed to parse, this may not really be
                # the film's first scene; the failed file's own errors already
                # fail the run, so do not add a misleading one here.
                if scene.declared_continue is True and not any_failed:
                    issues.append(
                        Issue(
                            episode.path,
                            scene.body_line_start,
                            "the film's first scene cannot set continue: true — "
                            "there is nothing to continue from",
                        )
                    )
                scene.effective_continue = False
                first = False
            else:
                scene.effective_continue = (
                    scene.declared_continue if scene.declared_continue is not None else True
                )
            if scene.effective_continue and scene.body and not _HARD_CUT_RE.match(scene.body):
                issues.append(
                    Issue(
                        episode.path,
                        scene.body_line_start,
                        f"scene {scene.index + 1} continues the previous shot, so its prompt "
                        "must open on a described hard cut, e.g. 'Hard cut to a wide shot of …'",
                    )
                )

    return Film(episodes), issues


def load_film(root: Path) -> Film:
    """Return the validated film, or raise `StoryError` with every problem."""
    film, issues = build_film(root)
    if issues:
        raise StoryError(issues)
    return film


# ------------------------------------------------------------- path allowlist


def _normalize_path(path: str) -> str | None:
    """The path as it sits in the tree, or None when it is not a plain one.

    Exactly one leading `./` is tolerated (a tool artefact). Anything else that
    is not the literal path — surrounding whitespace, control characters,
    backslashes, `..` segments — is refused rather than cleaned, because a
    cleaned path is not the path the pull request actually changes.
    """
    if path != path.strip() or not path:
        return None
    if any(ord(ch) < 32 or ch == "\x7f" for ch in path):
        return None
    if "\\" in path:
        return None
    if path.startswith("./"):
        path = path[2:]
    if not path or path.startswith("/") or path in (".", "..") or path.startswith("../"):
        return None
    return path


def _is_allowed_root_file(name: str) -> bool:
    return name in _ROOT_ALLOWLIST or bool(_EPISODE_RE.match(name))


def validate_paths(changed: list[Change] | list[str], root: Path | None = None) -> list[Issue]:
    """Reject any change a story pull request is not allowed to make.

    Judges each file by what happened to it, not only by its name: a rename
    is allowed only between two legal episode names, the three root documents
    may be edited but not deleted or renamed, and nothing may leave the root.
    When `root` is given, a changed path that is a symlink in the checkout is
    refused too.
    """
    issues: list[Issue] = []
    for item in changed:
        change = item if isinstance(item, Change) else Change(path=item)
        raw = change.path
        normalized = _normalize_path(raw)
        if normalized is None:
            issues.append(Issue(raw, None, "this path is not a plain filename at the branch root"))
            continue
        if "/" in normalized:
            issues.append(
                Issue(
                    raw,
                    None,
                    "a story pull request may only touch files at the branch root; "
                    "this path is in a subdirectory (code, workflows, and skills are "
                    "off-limits to a story change)",
                )
            )
            continue
        if not _is_allowed_root_file(normalized):
            issues.append(
                Issue(
                    raw,
                    None,
                    f"{normalized!r} is not an allowed story file (allowed: NNNN-title.md "
                    "episodes, plus README.md, STYLE.md, LICENSE)",
                )
            )
            continue
        if len(normalized) > MAX_FILENAME_CHARS:
            issues.append(
                Issue(raw, None, f"filename is {len(normalized)} characters; the cap is {MAX_FILENAME_CHARS}")
            )
            continue

        status = change.status.strip().lower()
        if normalized in _ROOT_ALLOWLIST and status in (_STATUS_REMOVED, _STATUS_RENAMED):
            issues.append(
                Issue(
                    raw,
                    None,
                    f"{normalized} may be edited by a story pull request but not "
                    f"{'deleted' if status == _STATUS_REMOVED else 'renamed'}",
                )
            )
            continue
        if status == _STATUS_RENAMED:
            previous = _normalize_path(change.previous_path or "")
            if (
                previous is None
                or "/" in previous
                or previous in _ROOT_ALLOWLIST
                or not _EPISODE_RE.match(previous)
            ):
                issues.append(
                    Issue(
                        raw,
                        None,
                        f"a rename may only move one episode file to another episode name; "
                        f"renaming {change.previous_path!r} is not allowed",
                    )
                )
                continue
        if root is not None and status != _STATUS_REMOVED:
            candidate = root / normalized
            if candidate.is_symlink():
                issues.append(Issue(raw, None, "a story file must be a regular file, not a symlink"))
                continue
    return issues


def read_changes(path: Path) -> list[Change]:
    """Read a `--changed-file` (status, path, previous path per line)."""
    changes: list[Change] = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        change = Change.parse_tsv_line(line)
        if change is not None:
            changes.append(change)
    return changes


# ------------------------------------------------------------------- reports


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}m {total % 60:02d}s"


def report(film: Film, changed_episodes: list[str]) -> str:
    """The human PR summary that makes ordering and runtime visible."""
    lines: list[str] = []
    by_name = {episode.path: index for index, episode in enumerate(film.episodes)}
    count = len(film.episodes)
    for name in changed_episodes:
        index = by_name.get(name)
        if index is None:
            continue
        episode = film.episodes[index]
        previous = film.episodes[index - 1].path if index > 0 else "the top"
        following = film.episodes[index + 1].path if index + 1 < count else "the end"
        scene_word = "scene" if len(episode.scenes) == 1 else "scenes"
        lines.append(
            f"`{name}` lands as episode {index + 1} of {count}, between `{previous}` "
            f"and `{following}`. {len(episode.scenes)} {scene_word}, "
            f"{format_duration(episode.seconds)}."
        )
    lines.append(
        f"The film is now {format_duration(film.total_seconds)} across {count} "
        f"episode{'s' if count != 1 else ''}; each screening restarts when it ends."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------- main


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate an Open Slop screenplay.")
    parser.add_argument("root", help="the story root directory (holds the episode files)")
    parser.add_argument(
        "--changed",
        action="append",
        default=[],
        metavar="PATH",
        help="a path changed by a pull request (repeatable); enables the allowlist and report",
    )
    parser.add_argument(
        "--changed-file",
        metavar="TSV",
        help="a file with one changed path per line: status<TAB>path<TAB>previous-path",
    )
    parser.add_argument("--report", action="store_true", help="print the ordering/runtime summary")
    args = parser.parse_args(argv)

    root = Path(args.root)
    in_actions = bool(os.environ.get("GITHUB_ACTIONS"))
    changes: list[Change] = [Change(path=p) for p in args.changed]
    if args.changed_file:
        changes.extend(read_changes(Path(args.changed_file)))

    issues: list[Issue] = []
    if changes:
        issues.extend(validate_paths(changes, root))
    film, film_issues = build_film(root)
    issues.extend(film_issues)

    if issues:
        for issue in issues:
            print(issue.annotation() if in_actions else str(issue))
        print(f"\n{len(issues)} problem(s) found.", file=sys.stderr)
        return 1

    print(
        f"story OK: {len(film.episodes)} episode(s), {len(film.scenes)} scene(s), "
        f"{format_duration(film.total_seconds)}."
    )
    if args.report:
        changed_episodes = []
        for change in changes:
            normalized = _normalize_path(change.path)
            if normalized and _EPISODE_RE.match(normalized) and change.status != _STATUS_REMOVED:
                changed_episodes.append(normalized)
        if changed_episodes:
            print()
            print(report(film, changed_episodes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
