"""Tests for the shared validator.

Runnable with pytest, or directly with `python test_validate.py` (a tiny
runner at the bottom executes every `test_*` and reports), so the story-branch
CI shim can prove the validator without installing pytest.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import validate
from validate import (
    LEGAL_SECONDS,
    MAX_FILENAME_CHARS,
    MAX_PROMPT_CHARS,
    MAX_TITLE_CHARS,
    MIN_PROMPT_CHARS,
    Change,
    build_film,
    parse_episode,
    validate_paths,
)

# Two legal prompts, each past the floor: a scene must carry the look, the
# setting, who is in frame, the light, and the sound. `_CUT` is reused across
# chained (continue: true) cases.
_CUT = (
    "A wide shot of a small fog-bound harbour town at dawn. Flat 2D cel animation, "
    "thick black outlines, flat fills, briny blues and fog greys. Low houses and moored "
    "boats sit still under a pale sky. Gulls cry, a buoy bell rings slow, water laps "
    "against stone."
)
_FRESH = (
    "A wide shot of a small fog-bound harbour town at dawn, one tall lighthouse turning "
    "its beam over the water. Flat 2D cel animation, thick black outlines, flat fills, "
    "briny blues and fog greys warmed by a low sun. Gulls cry, a buoy bell rings slow, "
    "water laps against stone."
)
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


def test_accepts_bom_and_crlf():
    text = "\ufeff" + _episode(f"seed: 1\nseconds: {_LEN}", _FRESH).replace("\n", "\r\n")
    episode, issues = parse_episode("0010-a.md", text)
    assert issues == [], _messages(issues)
    assert episode is not None and episode.title == "The Arrival"


# ------------------------------------------------------------ blame range


def test_body_range_excludes_surrounding_blank_lines():
    # Line numbers (1-based):
    # 1 # T | 2 (blank) | 3 --- | 4 seed | 5 seconds | 6 --- | 7 (blank)
    # 8 prose | 9 prose | 10 (blank) | 11 (blank) | 12 --- ...
    text = "\n".join(
        [
            "# T",
            "",
            "---",
            "seed: 1",
            f"seconds: {_LEN}",
            "---",
            "",
            _CUT[:120],
            _CUT[120:],
            "",
            "",
            "---",
            "seed: 2",
            f"seconds: {_LEN}",
            "---",
            _CUT,
            "",
        ]
    )
    episode, issues = parse_episode("0010-a.md", text)
    assert issues == [], _messages(issues)
    assert episode is not None
    first, second = episode.scenes
    assert (first.body_line_start, first.body_line_end) == (8, 9)
    assert (second.body_line_start, second.body_line_end) == (16, 16)


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


def test_rejects_non_plain_seeds():
    for bad in ("+5", "05x", "1_000", "1e3", "-1", "٣"):
        text = _episode(f"seed: {bad}\nseconds: {_LEN}", _FRESH)
        _film_obj, issues = _film({"0010-a.md": text})
        assert any("seed must be a plain integer" in i.message for i in issues), (bad, _messages(issues))
    # A leading zero is still a plain decimal integer.
    text = _episode(f"seed: 007\nseconds: {_LEN}", _FRESH)
    film, issues = _film({"0010-a.md": text})
    assert issues == [] and film.episodes[0].scenes[0].seed == 7


def test_rejects_illegal_seconds_and_suggests_neighbours():
    text = _episode("seed: 1\nseconds: 10", _FRESH)  # 10.0 is not legal
    _film_obj, issues = _film({"0010-a.md": text})
    offending = [i for i in issues if "not a legal clip length" in i.message]
    assert offending, _messages(issues)
    assert "try" in offending[0].message


def test_rejects_non_boolean_continue():
    for bad in ("maybe", "yes", "on", "1"):
        text = _episode(f"seed: 1\nseconds: {_LEN}\ncontinue: {bad}", _FRESH)
        _film_obj, issues = _film({"0010-a.md": text})
        assert any("continue must be exactly true or false" in i.message for i in issues), bad


def test_rejects_continue_true_on_the_first_scene():
    text = _episode(f"seed: 1\nseconds: {_LEN}\ncontinue: true", _CUT)
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("first scene cannot set continue" in issue.message for issue in issues), _messages(issues)


def test_first_scene_rule_is_silent_when_an_earlier_file_failed():
    broken = "# X\n\nno fence here\n"
    later = _episode(f"seed: 1\nseconds: {_LEN}\ncontinue: true", _CUT)
    _film_obj, issues = _film({"0010-a.md": broken, "0020-b.md": later})
    assert any("expected a scene block" in i.message for i in issues), _messages(issues)
    assert not any("first scene cannot set continue" in i.message for i in issues), _messages(issues)


def test_rejects_overlong_prompt():
    text = _episode(f"seed: 1\nseconds: {_LEN}", "word " * 400)
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("caps a scene at" in issue.message for issue in issues), _messages(issues)


def test_rejects_too_short_prompt():
    text = _episode(f"seed: 1\nseconds: {_LEN}", "A harbour at dawn. Gulls.")
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("at least" in issue.message for issue in issues), _messages(issues)


def test_prompt_length_is_measured_collapsed_and_at_the_bounds():
    # Line breaks and runs of spaces count as one character each, because that
    # is the form the projector sends. Exactly the floor and exactly the cap pass.
    word = "abcd "  # 5 chars per word
    floor = (word * (MIN_PROMPT_CHARS // 5)).strip()
    assert len(floor) == MIN_PROMPT_CHARS - 1
    floor = floor + "x"
    cap = (word * (MAX_PROMPT_CHARS // 5)).strip() + "."
    assert len(cap) == MAX_PROMPT_CHARS
    spread = cap.replace(" ", "  \n   ")  # far over 800 raw, exactly 800 collapsed
    text = _episode(f"seed: 1\nseconds: {_LEN}", floor, f"seed: 2\nseconds: {_LEN}", spread)
    episode, issues = parse_episode("0010-a.md", text)
    assert issues == [], _messages(issues)
    assert episode is not None
    assert len(episode.scenes[0].prompt) == MIN_PROMPT_CHARS
    assert episode.scenes[1].prompt == cap
    assert "\n" in episode.scenes[1].body and "\n" not in episode.scenes[1].prompt
    # One character over the cap, once collapsed, fails.
    text = _episode(f"seed: 1\nseconds: {_LEN}", cap + "x")
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("caps a scene at" in issue.message for issue in issues), _messages(issues)


def test_rejects_overlong_title_and_filename():
    text = _episode(f"seed: 1\nseconds: {_LEN}", _FRESH, title="t" * (MAX_TITLE_CHARS + 1))
    _episode_obj, issues = parse_episode("0010-a.md", text)
    assert any("title is" in i.message for i in issues), _messages(issues)
    long_name = "0010-" + "a" * MAX_FILENAME_CHARS + ".md"
    _episode_obj, issues = parse_episode(long_name, _episode(f"seed: 1\nseconds: {_LEN}", _FRESH))
    assert any("filename is" in i.message for i in issues), _messages(issues)
    assert any("filename is" in i.message for i in validate_paths([long_name]))


def test_continue_true_puts_no_constraint_on_the_prompt():
    text = _episode(
        f"seed: 1\nseconds: {_LEN}",
        _FRESH,
        f"seed: 2\nseconds: {_LEN}\ncontinue: true",
        _CUT,
    )
    _film_obj, issues = _film({"0010-a.md": text})
    assert issues == [], _messages(issues)


def test_rejects_heading_inside_a_prompt():
    text = _episode(f"seed: 1\nseconds: {_LEN}", "# Not a title\n" + _FRESH)
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("cannot start with '#'" in i.message for i in issues), _messages(issues)


def test_rejects_dangling_block_with_no_body():
    text = "# X\n\n---\nseed: 1\nseconds: %s\n---\n" % _LEN
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("no prompt body" in issue.message for issue in issues), _messages(issues)


def test_stray_fence_in_a_body_names_the_cause():
    text = _episode(f"seed: 1\nseconds: {_LEN}", _FRESH + "\n---\nmore prose")
    _film_obj, issues = _film({"0010-a.md": text})
    assert any("'---'" in i.message for i in issues), _messages(issues)


def test_rejects_empty_film():
    _film_obj, issues = _film({"README.md": "not an episode"})
    assert any("no episode files found" in issue.message for issue in issues), _messages(issues)


def test_rejects_a_symlinked_episode():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "0010-a.md").write_text(_episode(f"seed: 1\nseconds: {_LEN}", _FRESH), encoding="utf-8")
        os.symlink(root / "0010-a.md", root / "0020-b.md")
        _film_obj, issues = build_film(root)
        assert any("symlink" in i.message for i in issues), _messages(issues)
        assert validate_paths([Change("0020-b.md", "added")], root)


# ------------------------------------------------------------- path allowlist


def test_path_allowlist_accepts_episodes_and_named_docs():
    assert validate_paths(["0010-a.md", "README.md", "STYLE.md", "LICENSE"]) == []
    assert validate_paths(["./0010-a.md"]) == []


def test_path_allowlist_rejects_subdirectories_and_workflows():
    issues = validate_paths([".github/workflows/story-validate.yml"])
    assert issues and "subdirectory" in issues[0].message
    assert validate_paths(["skills/README.md"])


def test_path_allowlist_rejects_a_stray_root_file():
    issues = validate_paths(["hack.py"])
    assert issues and "not an allowed story file" in issues[0].message
    assert validate_paths([".github"])
    assert validate_paths([".gitattributes"])


def test_path_allowlist_refuses_dressed_up_paths():
    for bad in ("..README.md", ".LICENSE", ".0010-x.md", "0010-x.md ", " 0010-x.md",
                "0010-x.md\n", "../0010-x.md", "/0010-x.md", "0010\\x.md", "./"):
        assert validate_paths([bad]), repr(bad)


def test_path_allowlist_blocks_deleting_or_renaming_the_root_documents():
    for name in ("README.md", "STYLE.md", "LICENSE"):
        assert validate_paths([Change(name, "removed")]), name
        assert validate_paths([Change(name, "renamed", "0010-x.md")]), name
        assert validate_paths([Change(name, "modified")]) == [], name


def test_path_allowlist_judges_renames_by_their_source():
    # Renumbering an episode is fine.
    assert validate_paths([Change("0015-b.md", "renamed", "0020-b.md")]) == []
    # Pulling anything else into an episode name is not — a rename reported
    # only by its new name would otherwise walk a workflow out of .github/.
    assert validate_paths([Change("0040-x.md", "renamed", ".github/workflows/story-quorum.yml")])
    assert validate_paths([Change("0040-x.md", "renamed", "skills/README.md")])
    assert validate_paths([Change("0040-x.md", "renamed", "README.md")])
    assert validate_paths([Change("0040-x.md", "renamed", None)])


def test_path_allowlist_allows_deleting_an_episode():
    assert validate_paths([Change("0020-b.md", "removed")]) == []


def test_change_parses_tsv_lines():
    assert Change.parse_tsv_line("") is None
    assert Change.parse_tsv_line("0010-a.md") == Change("0010-a.md")
    assert Change.parse_tsv_line("renamed\t0015-b.md\t0020-b.md\n") == Change(
        "0015-b.md", "renamed", "0020-b.md"
    )
    assert Change.parse_tsv_line("removed\tLICENSE\t") == Change("LICENSE", "removed", None)


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
