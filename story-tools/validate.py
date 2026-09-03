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

    python validate.py <story-root>                    # validate the whole film
    python validate.py <story-root> --changed 0015-x.md --report

Import it:

    from validate import load_film, build_film, LEGAL_SECONDS
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

_EPISODE_RE = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")
_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$")
_HARD_CUT_RE = re.compile(r"^\s*(hard\s+)?cut to\b", re.IGNORECASE)
_FENCE = "---"
_ALLOWED_KEYS = ("seed", "seconds", "continue")

# What a story pull request may add or change at the branch root. Everything
# else — every subdirectory, and above all `.github/` (which lives on this
# branch only because the default-branch trigger rule forces it there) — is
# refused. This is the wall that keeps code off the story branch.
_ROOT_ALLOWLIST = frozenset({"README.md", "STYLE.md", "LICENSE"})


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
        loc = f"file={self.path}"
        if self.line is not None:
            loc += f",line={self.line}"
        return f"::error {loc}::{self.message}"


@dataclass
class Scene:
    """One clip: a prompt, a seed, a length, and how it joins the previous one.

    `body_line_start` / `body_line_end` are 1-indexed lines in the source file,
    covering the prompt prose only (never the `---` header). The projector
    blames exactly that range to credit the words to their author.
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


# --------------------------------------------------------------- frontmatter


def _as_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _as_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _as_bool(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
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
            if parsed is None or parsed < 0:
                issues.append(Issue(path, lineno, f"seed must be an integer >= 0, got {value!r}"))
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
                issues.append(Issue(path, lineno, f"continue must be true or false, got {value!r}"))
            else:
                data["continue"] = parsed
    if "seed" not in data:
        issues.append(Issue(path, None, "a scene header is missing the required key 'seed'"))
    if "seconds" not in data:
        issues.append(Issue(path, None, "a scene header is missing the required key 'seconds'"))
    return data, issues


# ------------------------------------------------------------- episode parse


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
    order_index = int(name[:4]) if name[:4].isdigit() else 0

    lines = text.split("\n")
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    title: str | None = None
    if i < len(lines) and lines[i].lstrip().startswith("#"):
        match = _TITLE_RE.match(lines[i])
        if match:
            title = match.group(1)
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
            issues.append(Issue(name, open_line + 1, "unterminated scene header: no closing '---'"))
            return None, issues
        close_line = i
        i += 1

        body_start = i
        body_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != _FENCE:
            body_lines.append(lines[i])
            i += 1
        body_end = i - 1

        data, fm_issues = _parse_frontmatter(name, fm_lines)
        issues.extend(fm_issues)

        body = "\n".join(body_lines).strip()
        if not body:
            issues.append(Issue(name, close_line + 1, f"scene {len(scenes) + 1} has no prompt body"))
        else:
            collapsed = " ".join(body.split())
            if len(collapsed) > MAX_PROMPT_CHARS:
                issues.append(
                    Issue(
                        name,
                        body_start + 1,
                        f"prompt is {len(collapsed)} characters; the model caps a scene at "
                        f"{MAX_PROMPT_CHARS}",
                    )
                )

        scenes.append(
            Scene(
                index=len(scenes),
                seed=data.get("seed", 0),
                seconds=data.get("seconds", 0.0),
                declared_continue=data.get("continue"),
                body=body,
                body_line_start=body_start + 1,
                body_line_end=max(body_start + 1, body_end + 1),
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
    files = sorted(
        (p for p in root.iterdir() if p.is_file() and _EPISODE_RE.match(p.name)),
        key=lambda p: (int(p.name[:4]), p.name),
    )
    if not files:
        issues.append(Issue(str(root), None, "no episode files found (expected NNNN-title.md at the root)"))
        return Film(), issues

    episodes: list[Episode] = []
    for path in files:
        episode, episode_issues = parse_episode(path.name, path.read_text(encoding="utf-8"))
        issues.extend(episode_issues)
        if episode is not None:
            episodes.append(episode)

    first = True
    for episode in episodes:
        for scene in episode.scenes:
            if first:
                if scene.declared_continue is True:
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


def validate_paths(changed: list[str]) -> list[Issue]:
    """Reject any changed path a story pull request is not allowed to touch."""
    issues: list[Issue] = []
    for path in changed:
        normalized = path.strip().lstrip("./")
        if not normalized:
            continue
        if "/" in normalized:
            issues.append(
                Issue(
                    path,
                    None,
                    "a story pull request may only touch files at the branch root; "
                    "this path is in a subdirectory (code, workflows, and skills are "
                    "off-limits to a story change)",
                )
            )
            continue
        if normalized in _ROOT_ALLOWLIST or _EPISODE_RE.match(normalized):
            continue
        issues.append(
            Issue(
                path,
                None,
                f"{normalized!r} is not an allowed story file (allowed: NNNN-title.md "
                "episodes, plus README.md, STYLE.md, LICENSE)",
            )
        )
    return issues


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
    parser.add_argument("--report", action="store_true", help="print the ordering/runtime summary")
    args = parser.parse_args(argv)

    in_actions = bool(os.environ.get("GITHUB_ACTIONS"))
    issues: list[Issue] = []
    if args.changed:
        issues.extend(validate_paths(args.changed))
    film, film_issues = build_film(Path(args.root))
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
        changed_episodes = [c for c in args.changed if _EPISODE_RE.match(c.lstrip('./'))]
        if changed_episodes:
            print()
            print(report(film, [c.lstrip('./') for c in changed_episodes]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
