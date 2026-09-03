"""Resolve a story commit to the GitHub login that authored it.

`git blame` yields a name and an email. When the email is a GitHub noreply
address the login is in it; when it is a real address — which is what most
people commit with — the login is not, and the credits would show a lettered
disc instead of a face. GitHub itself knows the association: its commits API
returns the `author.login` it shows on the commit page. This asks it once per
commit and remembers the answer on disk, so a screening never repeats a lookup
and a restart does not spend the rate budget again.

Unauthenticated, GitHub allows 60 requests an hour per address; a token in
`GITHUB_TOKEN` raises that to 5000. The resolver stops asking for the rest of
a reading on the first limit or network error and credits by name meanwhile,
so a rate limit degrades a face to a letter and nothing else.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_API = "https://api.github.com"
_TIMEOUT_S = 10
# A miss (commit not on GitHub, or not linked to an account) is asked again
# after this long; a hit is kept for good.
_MISS_TTL_S = 24 * 3600
_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


def repo_slug(html_url: str) -> tuple[str, str] | None:
    """`owner, repo` from a github.com repository URL, or None for any other host."""
    parsed = urlparse(html_url)
    if parsed.hostname not in ("github.com", "www.github.com"):
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    return owner, repo


class LoginResolver:
    """Commit sha → GitHub login, cached on disk, rate-limit aware."""

    def __init__(self, html_url: str, cache_path: Path, token: str | None = None) -> None:
        self._slug = repo_slug(html_url)
        self._cache_path = Path(cache_path).expanduser()
        self._token = (token or "").strip() or None
        self._cache: dict[str, dict] = self._load()
        self._dirty = False
        self._paused_until = 0.0

    @property
    def enabled(self) -> bool:
        return self._slug is not None

    # ----------------------------------------------------------------- cache

    def _load(self) -> dict[str, dict]:
        try:
            data = json.loads(self._cache_path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def flush(self) -> None:
        """Write the cache if anything changed since the last flush."""
        if not self._dirty:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._cache, sort_keys=True))
            tmp.replace(self._cache_path)
            self._dirty = False
        except OSError as error:
            logger.warning("[logins] could not write %s: %s", self._cache_path, error)

    # ---------------------------------------------------------------- lookup

    def login_for_commit(self, sha: str) -> str | None:
        """The GitHub login for a full commit sha, or None when unknown."""
        if not self._slug or not re.fullmatch(r"[0-9a-f]{40}", sha):
            return None
        entry = self._cache.get(sha)
        now = time.time()
        if entry is not None:
            login = entry.get("login")
            if login or now - float(entry.get("at", 0)) < _MISS_TTL_S:
                return login or None
        if now < self._paused_until:
            return None
        login = self._fetch(sha)
        if login is _SKIP:
            return None
        self._cache[sha] = {"login": login, "at": now}
        self._dirty = True
        return login

    def _fetch(self, sha: str) -> str | None | object:
        owner, repo = self._slug  # type: ignore[misc]
        url = f"{_API}/repos/{owner}/{repo}/commits/{sha}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "open-slop-projector",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in (403, 429):
                self._pause(error.headers.get("X-RateLimit-Reset"))
                return _SKIP
            if error.code in (404, 422):
                return None  # not a commit GitHub knows; cache the miss
            logger.warning("[logins] GitHub answered %s for %s", error.code, sha[:7])
            return _SKIP
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            logger.warning("[logins] lookup failed for %s: %s", sha[:7], error)
            self._paused_until = time.time() + 60
            return _SKIP
        author = payload.get("author") if isinstance(payload, dict) else None
        login = author.get("login") if isinstance(author, dict) else None
        return login if isinstance(login, str) and _LOGIN_RE.match(login) else None

    def _pause(self, reset_header: str | None) -> None:
        try:
            until = float(reset_header) if reset_header else time.time() + 3600
        except ValueError:
            until = time.time() + 3600
        self._paused_until = max(until, time.time() + 60)
        logger.warning(
            "[logins] GitHub rate limit hit; crediting by name until %s",
            time.strftime("%H:%M", time.localtime(self._paused_until)),
        )


_SKIP = object()
