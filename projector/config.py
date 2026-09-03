"""Configuration for the projector.

Everything comes from the environment (a `.env` file next to this module is
loaded when present). `Config.load` is the only reader; the rest of the
projector takes a `Config` and never touches `os.environ`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_DEFAULT_MIRROR = "~/.cache/open-slop/story"
_DEFAULT_HTML_URL = "https://github.com/Dere-Wah/open-slop"


def _derive_html_url(repo: str) -> str:
    """A best-effort browse URL for building commit/file links in the viewer.

    Uses the story repo when it already is an https GitHub URL; otherwise the
    canonical project URL. Links are cosmetic, so a wrong guess costs a link,
    never the broadcast.
    """
    cleaned = repo.strip()
    if cleaned.startswith("https://") and cleaned.endswith(".git"):
        return cleaned[: -len(".git")]
    if cleaned.startswith("https://"):
        return cleaned
    return _DEFAULT_HTML_URL


@dataclass(frozen=True)
class Config:
    """One immutable snapshot of everything the projector is configured with."""

    # Reactor
    reactor_api_key: str
    reactor_model: str

    # LiveKit (the room the show is broadcast into)
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    livekit_room: str

    # The story: where the screenplay branch lives, and how to link to it.
    story_repo: str  # a git URL or local path holding the story branch
    story_branch: str
    story_mirror_dir: str
    story_html_url: str

    @staticmethod
    def load() -> "Config":
        """Read `.env` + environment and validate."""
        load_dotenv(Path(__file__).parent / ".env")

        story_repo = os.environ.get("STORY_REPO", "")
        config = Config(
            reactor_api_key=os.environ.get("REACTOR_API_KEY", ""),
            reactor_model=os.environ.get("REACTOR_MODEL", "reactor/fast-h3"),
            livekit_url=os.environ.get("LIVEKIT_URL", ""),
            livekit_api_key=os.environ.get("LIVEKIT_API_KEY", ""),
            livekit_api_secret=os.environ.get("LIVEKIT_API_SECRET", ""),
            livekit_room=os.environ.get("LIVEKIT_ROOM", "open-slop"),
            story_repo=story_repo,
            story_branch=os.environ.get("STORY_BRANCH", "story"),
            story_mirror_dir=os.environ.get("STORY_MIRROR_DIR", _DEFAULT_MIRROR),
            story_html_url=os.environ.get("STORY_HTML_URL", "").strip()
            or _derive_html_url(story_repo),
        )
        if not config.reactor_api_key:
            raise SystemExit("REACTOR_API_KEY is required (rk_... from the dashboard).")
        if not config.livekit_url:
            raise SystemExit("LIVEKIT_URL is required (wss://... from your LiveKit project).")
        if not config.livekit_api_key or not config.livekit_api_secret:
            raise SystemExit("LIVEKIT_API_KEY and LIVEKIT_API_SECRET are required.")
        if not config.story_repo:
            raise SystemExit(
                "STORY_REPO is required: a git URL or local path holding the story "
                "branch (e.g. https://github.com/Dere-Wah/open-slop.git, or a local "
                "clone path for iterating offline)."
            )
        return config
