"""Tests for the shared validator.

Runnable with pytest, or directly with `python test_validate.py` (a tiny
runner at the bottom executes every `test_*` and reports), so the story-branch
CI shim can prove the validator without installing pytest.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import validate
from validate import (
    LEGAL_SECONDS,
    build_film,
    parse_episode,
    validate_paths,
)

# A legal scene body that opens on a hard cut, reused across chained cases.
_CUT = "Hard cut to a wide shot of a harbour at dawn. Gulls, a low bell."
_FRESH = "A wide shot of a harbour at dawn, one lighthouse turning. Gulls, a bell."
_LEN = LEGAL_SECONDS[5]  # a mid-range legal length


def _episode(*blocks: str, title: str = "The Arrival") -> str:
    """Assemble an episode file from (frontmatter, body) scene blocks."""
    parts = [f"# {title}", ""]
    for frontmatter, body in zip(blocks[0::2], blocks[1::2]):
        parts += ["---", frontmatter.strip(), "---", body.strip(), ""]
    return "\n".join(parts)


def _film(files: dict[str, str]) -> tuple[validate.Film, list[validate.Issue]]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, text in files.items():
            (root / name).write_text(text, encoding="utf-8")
        return build_film(root)


def _messages(issues: list[validate.Issue]) -> str:
    return "\n".join(str(issue) for issue in issues)


# ---------------------------------------------------------------- acceptance


def test_accepts_a_clean_two_scene_episode():
    text = _episode(
        f"seed: 481516\nseconds: {_LEN}\ncontinue: false",
        _FRESH,
        f"seed: 481517\nseconds: {_LEN}\ncontinue: true",
        _CUT,
    )
    _film_obj, issues = _film({"0010-the-arrival.md": text})
    assert issues == [], _messages(issues)


def test_effective_continue_defaults_by_position():
    text = _episode(
        f"seed: 1\nseconds: {_LEN}",  # first scene of the film: defaults false
        _FRESH,
        f"seed: 2\nseconds: {_LEN}",  # has a predecessor: defaults true
        _CUT,
    )
    film, issues = _film({"0010-the-arrival.md": text})
    assert issues == [], _messages(issues)
    scenes = film.episodes[0].scenes
    assert scenes[0].effective_continue is False
    assert scenes[1].effective_continue is True


def test_continue_crosses_the_file_boundary():
    # The first scene of the second episode continues from the first episode.
    first = _episode(f"seed: 1\nseconds: {_LEN}", _FRESH)
    second = _episode(f"seed: 2\nseconds: {_LEN}\ncontinue: true", _CUT, title="The Signal")
    film, issues = _film({"0010-a.md": first, "0020-b.md": second})
    assert issues == [], _messages(issues)
    assert film.episodes[1].scenes[0].effective_continue is True


# ----------------------------------------------------------------- rejection


def test_rejects_bad_filename_via_allowlist():
    # A misnamed episode is not a subdirectory and not a named doc, so the
    # path allowlist is what refuses it on a pull request. build_film simply
    # does not treat a non-matching name as an episode.
    assert validate_paths(["the-arrival.md"]), "an un-indexed name must be refused"
    assert validate_paths(["0010-BadCaps.md"]), "uppercase in an episode name must be refused"
    assert validate_paths(["0010-ok.md"]) == []


def test_rejects_unknown_scene_key():
    text = _episode(f"seed: 1\nseconds: {_LEN}\nlength: 10", _FRESH)
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("unknown scene key" in issue.message for issue in issues), _messages(issues)


def test_rejects_missing_seed():
    text = _episode(f"seconds: {_LEN}", _FRESH)
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("missing the required key 'seed'" in issue.message for issue in issues), _messages(issues)


def test_rejects_illegal_seconds_and_suggests_neighbours():
    text = _episode("seed: 1\nseconds: 10", _FRESH)  # 10.0 is not legal
    _film_obj, issues = _film({"0010-a.md": text})
    offending = [i for i in issues if "not a legal clip length" in i.message]
    assert offending, _messages(issues)
    assert "try" in offending[0].message


def test_rejects_non_boolean_continue():
    text = _episode(f"seed: 1\nseconds: {_LEN}\ncontinue: maybe", _FRESH)
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("continue must be true or false" in issue.message for issue in issues), _messages(issues)


def test_rejects_continue_true_on_the_first_scene():
    text = _episode(f"seed: 1\nseconds: {_LEN}\ncontinue: true", _CUT)
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("first scene cannot set continue" in issue.message for issue in issues), _messages(issues)


def test_rejects_overlong_prompt():
    text = _episode(f"seed: 1\nseconds: {_LEN}", "word " * 400)
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("caps a scene at" in issue.message for issue in issues), _messages(issues)


def test_rejects_continue_true_without_a_hard_cut():
    text = _episode(
        f"seed: 1\nseconds: {_LEN}",
        _FRESH,
        f"seed: 2\nseconds: {_LEN}\ncontinue: true",
        "The camera keeps following her down the hall.",  # no described cut
    )
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("must open on a described hard cut" in issue.message for issue in issues), _messages(issues)


def test_rejects_dangling_block_with_no_body():
    text = "# X\n\n---\nseed: 1\nseconds: %s\n---\n" % _LEN
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("no prompt body" in issue.message for issue in issues), _messages(issues)


def test_rejects_empty_film():
    _film_obj, issues = _film({"README.md": "not an episode"})
    assert any("no episode files found" in issue.message for issue in issues), _messages(issues)


# ------------------------------------------------------------- path allowlist


def test_path_allowlist_accepts_episodes_and_named_docs():
    assert validate_paths(["0010-a.md", "README.md", "STYLE.md", "LICENSE"]) == []


def test_path_allowlist_rejects_subdirectories_and_workflows():
    issues = validate_paths([".github/workflows/story-validate.yml"])
    assert issues and "subdirectory" in issues[0].message


def test_path_allowlist_rejects_a_stray_root_file():
    issues = validate_paths(["hack.py"])
    assert issues and "not an allowed story file" in issues[0].message


def _run() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"ok   {test.__name__}")
        except AssertionError as error:
            failures += 1
            print(f"FAIL {test.__name__}: {error}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run())
