"""Read the screenplay off the story branch, with per-scene attribution.

The story lives on its own git branch: one episode per file at the root, each
file a run of scenes. This module keeps a local mirror of that branch, reads
the film at its current tip through the same validator CI runs, and credits
every scene to the author who last wrote its words.

The mirror is a blobless partial clone (`--filter=blob:none`) with a working
tree. That keeps the checkout small while retaining full history, which
`git blame` needs — a shallow clone would silently mis-credit every scene to
whoever last touched the file. Each read fetches the branch, resets the tree
to its tip, parses the episodes, and blames each file once to attach authors.

Nothing here writes to the story branch. The projector only ever reads it.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# The validator is the shared source of truth for the episode format. It lives
# beside the projector on the code branch, in a hyphenated directory that is
# not an importable package name, so it joins the path explicitly.
_STORY_TOOLS = Path(__file__).resolve().parent.parent / "story-tools"
if str(_STORY_TOOLS) not in sys.path:
    sys.path.insert(0, str(_STORY_TOOLS))

import validate  # noqa: E402  (path set above)
from logins import LoginResolver  # noqa: E402
from validate import Film, StoryError  # noqa: E402

logger = logging.getLogger(__name__)

# `<id>+<login>@users.noreply.github.com` or `<login>@users.noreply.github.com`
_NOREPLY_RE = re.compile(r"^(?:\d+\+)?([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)@users\.noreply\.github\.com$")

# `Co-authored-by: Name <email>` trailers, which a squash merge writes for
# every extra author on the pull request. Without them a scene four people
# refined would credit only the one whose commit came last.
_COAUTHOR_RE = re.compile(r"^Co-authored-by:\s*(.*?)\s*<([^>]*)>\s*$", re.IGNORECASE | re.MULTILINE)

# A hung git must never freeze the feed: the network fetch gets the long
# budget, local plumbing the short one.
_FETCH_TIMEOUT_S = 180
_LOCAL_TIMEOUT_S = 60


@dataclass(frozen=True)
class Person:
    """A contributor, with a GitHub handle when the commit email carries one."""

    name: str
    login: str | None = None
    url: str | None = None

    @property
    def display(self) -> str:
        return f"@{self.login}" if self.login else self.name


@dataclass
class Scene:
    """One scene, ready to enqueue and to narrate."""

    global_index: int  # 0-based across the whole film
    episode_index: int  # 0-based
    episode_file: str
    episode_title: str | None
    scene_number: int  # 1-based within the episode
    scene_count: int
    seed: int
    seconds: float
    continued: bool  # the effective continue flag
    prompt: str
    author: Person
    commit: str  # short sha of the newest commit on this scene's body
    commit_url: str | None
    # The prose lines in `episode_file` at `Rundown.sha`, 1-based and inclusive:
    # what an edit link highlights. The header and its fences stay out so a
    # contributor lands on the words, not on the `---` they tend to break.
    line_start: int = 0
    line_end: int = 0
    contributors: list[Person] = field(default_factory=list)


@dataclass
class Episode:
    index: int
    file: str
    title: str | None
    seconds: float
    scenes: list[Scene] = field(default_factory=list)


@dataclass
class Rundown:
    """One reading of the film at a specific story-branch commit."""

    sha: str  # short sha of the story tip
    story_url: str  # link to the branch, for the viewer
    episodes: list[Episode] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    total_seconds: float = 0.0


def _is_bot(person: Person) -> bool:
    """GitHub Apps sign as `name[bot]` with a `<id>+name[bot]@users.noreply` email."""
    return person.name.endswith("[bot]") or (person.login or "").endswith("[bot]")


def _person_from_commit(name: str, email: str) -> Person:
    """Resolve a git author to a Person, reading a GitHub login off a noreply."""
    match = _NOREPLY_RE.match(email.strip())
    if match:
        login = match.group(1)
        return Person(name=name, login=login, url=f"https://github.com/{login}")
    return Person(name=name or "unknown", login=None, url=None)


class StorySource:
    """A local mirror of the story branch that reads films from its tip."""

    def __init__(
        self,
        repo: str,
        branch: str,
        mirror_dir: Path,
        html_url: str,
        github_token: str | None = None,
    ) -> None:
        self._repo = repo
        self._branch = branch
        self._dir = Path(mirror_dir).expanduser()
        self._html_url = html_url.rstrip("/")
        # A real commit email carries no login; GitHub's commits API does. The
        # answers live beside the mirror so a restart does not ask again.
        self._logins = LoginResolver(
            self._html_url,
            cache_path=self._dir.with_name(self._dir.name + "-logins.json"),
            token=github_token,
        )

    # ------------------------------------------------------------ git plumbing

    def _git(self, *args: str, check: bool = True, timeout: float = _LOCAL_TIMEOUT_S) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(self._dir), *args],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"git {' '.join(args)} timed out after {timeout:.0f}s") from error
        if check and result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    def _sync(self) -> str:
        """Fetch the branch and hard-reset the tree to its tip; return the sha."""
        if not (self._dir / ".git").exists():
            self._dir.parent.mkdir(parents=True, exist_ok=True)
            logger.info("[story] cloning %s (%s) into %s", self._repo, self._branch, self._dir)
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--filter=blob:none",
                    "--branch",
                    self._branch,
                    "--single-branch",
                    self._repo,
                    str(self._dir),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=_FETCH_TIMEOUT_S,
            )
        else:
            self._git("fetch", "--filter=blob:none", "origin", self._branch, timeout=_FETCH_TIMEOUT_S)
            self._git("reset", "--hard", f"origin/{self._branch}")
        return self._git("rev-parse", "HEAD").strip()

    def _blame(self, file: str) -> tuple[dict[int, str], dict[str, dict]]:
        """Blame one file once: map final line -> sha, and sha -> author meta.

        A blame that fails is an error, not a quiet "unknown" on every scene:
        the credit is the product, so the projector says so and the scenes
        of that file are marked unknown for this reading only.
        """
        try:
            porcelain = self._git("blame", "--porcelain", "--", file, timeout=_FETCH_TIMEOUT_S)
        except RuntimeError as error:
            logger.error("[story] blame failed for %s; crediting unknown: %s", file, error)
            return {}, {}
        line_sha: dict[int, str] = {}
        meta: dict[str, dict] = {}
        current: str | None = None
        for raw in porcelain.split("\n"):
            header = re.match(r"^([0-9a-f]{40}) \d+ (\d+)", raw)
            if header:
                current = header.group(1)
                final_line = int(header.group(2))
                line_sha[final_line] = current
                meta.setdefault(current, {})
                continue
            if current is None:
                continue
            if raw.startswith("author "):
                meta[current]["name"] = raw[len("author ") :]
            elif raw.startswith("author-mail "):
                meta[current]["mail"] = raw[len("author-mail ") :].strip("<>")
            elif raw.startswith("author-time "):
                meta[current]["time"] = int(raw[len("author-time ") :])
        return line_sha, meta

    def _coauthors(self, sha: str, cache: dict[str, list[Person]]) -> list[Person]:
        """The `Co-authored-by` people of one commit, read once per reading."""
        if sha in cache:
            return cache[sha]
        people: list[Person] = []
        try:
            message = self._git("show", "-s", "--format=%B", sha)
        except RuntimeError as error:
            logger.warning("[story] could not read commit %s for co-authors: %s", sha[:7], error)
            message = ""
        for name, mail in _COAUTHOR_RE.findall(message):
            person = _person_from_commit(name.strip(), mail)
            # A committed review suggestion names its bot as a co-author; the
            # words are still the contributor's, so the bot takes no credit.
            if _is_bot(person):
                continue
            people.append(person)
        cache[sha] = people
        return people

    # ---------------------------------------------------------------- reading

    def read(self) -> Rundown:
        """Sync the mirror and return the validated film with attribution.

        Raises `StoryError` when the film does not validate — the caller holds
        the last good rundown, because a bad tip should never happen (CI gates
        it) and must never take the broadcast down if it somehow does.
        """
        sha = self._sync()
        film: Film = validate.load_film(self._dir)  # raises StoryError on bad input

        story_url = f"{self._html_url}/tree/{self._branch}"
        rundown = Rundown(sha=sha[:7], story_url=story_url)
        global_index = 0
        coauthor_cache: dict[str, list[Person]] = {}
        for episode in film.episodes:
            line_sha, meta = self._blame(episode.path)
            r_episode = Episode(
                index=len(rundown.episodes),
                file=episode.path,
                title=episode.title,
                seconds=episode.seconds,
            )
            for scene in episode.scenes:
                author, commit, contributors = self._attribute(
                    line_sha, meta, scene.body_line_start, scene.body_line_end, coauthor_cache
                )
                commit_url = f"{self._html_url}/commit/{commit}" if commit else None
                card = Scene(
                    global_index=global_index,
                    episode_index=r_episode.index,
                    episode_file=episode.path,
                    episode_title=episode.title,
                    scene_number=scene.index + 1,
                    scene_count=len(episode.scenes),
                    seed=scene.seed,
                    seconds=scene.seconds,
                    continued=scene.effective_continue,
                    prompt=scene.prompt,
                    author=author,
                    commit=commit[:7] if commit else "",
                    commit_url=commit_url,
                    line_start=scene.body_line_start,
                    line_end=scene.body_line_end,
                    contributors=contributors,
                )
                r_episode.scenes.append(card)
                rundown.scenes.append(card)
                global_index += 1
            rundown.episodes.append(r_episode)
        self._logins.flush()

        rundown.total_seconds = film.total_seconds
        logger.info(
            "[story] read %d episode(s), %d scene(s), %s at %s",
            len(rundown.episodes),
            len(rundown.scenes),
            validate.format_duration(rundown.total_seconds),
            rundown.sha,
        )
        return rundown

    def _attribute(
        self,
        line_sha: dict[int, str],
        meta: dict[str, dict],
        start: int,
        end: int,
        coauthor_cache: dict[str, list[Person]],
    ) -> tuple[Person, str, list[Person]]:
        """Credit a scene from the commits touching its prose lines.

        The primary author is the newest commit over the range; contributors
        are the distinct authors across it, newest first, followed by every
        `Co-authored-by` a squash merge recorded on those commits. A login
        comes off a noreply email when there is one, else from GitHub's
        record of the commit (see logins.py). A range
        with no blame (a brand-new file blamed before its blob is local)
        yields an unknown author rather than an error.
        """
        shas: list[str] = []
        for line in range(start, end + 1):
            sha = line_sha.get(line)
            if sha and sha not in shas:
                shas.append(sha)
        if not shas:
            return Person(name="unknown"), "", []

        shas.sort(key=lambda sha: meta.get(sha, {}).get("time", 0), reverse=True)
        people: list[Person] = []
        seen: set[str] = set()

        def add(person: Person) -> None:
            key = person.login or person.name
            if key and key not in seen:
                seen.add(key)
                people.append(person)

        for sha in shas:
            info = meta.get(sha, {})
            person = _person_from_commit(info.get("name", "unknown"), info.get("mail", ""))
            if person.login is None:
                login = self._logins.login_for_commit(sha)
                if login:
                    person = Person(name=person.name, login=login, url=f"https://github.com/{login}")
            add(person)
        for sha in shas:
            for person in self._coauthors(sha, coauthor_cache):
                add(person)
        return people[0], shas[0], people
