# Copyright (c) 2026 Reactor Technologies, Inc. All rights reserved.
"""Tests for doctor.py: every suggestion must leave a file the validator accepts."""

from __future__ import annotations

import tempfile
from pathlib import Path

import doctor
import validate
from doctor import apply, diagnose, doctor_file, fixed_name, truncate_prompt
from validate import MAX_PROMPT_CHARS, MIN_PROMPT_CHARS, Change

_PROSE = (
    "A lighthouse keeper in a yellow oilskin climbs the spiral stair, lantern swinging, "
    "as the beam sweeps the fog. Flat 2D cel animation, thick black outlines, flat fills, "
    "briny blues and fog greys warmed by a low sun. Gulls cry, a buoy bell rings slow, "
    "water laps against stone."
)
_LONG = " ".join([_PROSE] * 4)  # well over the cap


def _heal(name: str, text: str, others: dict[str, str] | None = None):
    """Run the doctor on one file and return (report, healed_text, remaining issues)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for other, body in (others or {}).items():
            (root / other).write_text(body, encoding="utf-8")
        (root / name).write_text(text, encoding="utf-8")
        report = doctor_file(root, name, text)
        healed = apply(text, report.suggestions)
        legal = fixed_name(root, name) or name
        _, issues = validate.parse_episode(legal, healed)
        return report, healed, issues


def test_a_clean_file_gets_no_suggestions():
    text = f"# The Arrival\n\n---\nseed: 7\nseconds: 8\n---\n{_PROSE}\n"
    report, healed, issues = _heal("0010-the-arrival.md", text)
    assert report.suggestions == [] and report.notes == [], report
    assert healed == validate._normalize_text(text)
    assert issues == []


def test_missing_seconds_and_odd_keys_become_one_header_suggestion():
    text = f"# The Arrival\n\n---\nSeed: 7\nlength = 8s\ncontinued: yes\n---\n{_PROSE}\n"
    report, healed, issues = _heal("0010-the-arrival.md", text)
    assert len(report.suggestions) == 1, report.suggestions
    s = report.suggestions[0]
    assert (s.start_line, s.end_line) == (4, 6)
    assert s.replacement == "seed: 7\nseconds: 8"  # first scene of the film: continue dropped
    assert "Renamed `Seed` to `seed`" in s.why and "renamed `length` to `seconds`" in s.why
    assert "first scene" in s.why
    assert issues == [], issues


def test_continue_true_survives_when_an_earlier_episode_exists():
    text = f"# Two\n\n---\nseed: 7\nsecs: 8\ncontinue: yes\n---\n{_PROSE}\n"
    earlier = f"# One\n\n---\nseed: 1\nseconds: 8\n---\n{_PROSE}\n"
    report, healed, issues = _heal("0020-two.md", text, {"0010-one.md": earlier})
    assert report.suggestions[0].replacement == "seed: 7\nseconds: 8\ncontinue: true"
    assert issues == []


def test_header_missing_entirely_is_inserted_before_the_prose():
    text = f"# The Arrival\n\n{_PROSE}\n"
    report, healed, issues = _heal("0010-the-arrival.md", text)
    assert len(report.suggestions) == 1
    assert healed.split("\n")[2] == "---"
    assert issues == [], issues
    # the seed is drawn from the words, so a second run agrees with the first
    again, _, _ = _heal("0010-the-arrival.md", text)
    assert again.suggestions[0].replacement == report.suggestions[0].replacement


def test_seed_missing_is_added_and_a_quoted_seed_is_unquoted():
    text = f"# T\n\n---\nseconds: 8\n---\n{_PROSE}\n\n---\nseed: \"12\"\nseconds: 8\n---\n{_PROSE}\n"
    report, healed, issues = _heal("0010-t.md", text)
    assert issues == [], issues
    assert "seed: 12" in healed
    assert any("Added a `seed`" in s.why for s in report.suggestions)


def test_over_long_prompt_is_cut_at_a_sentence_and_the_tail_is_quoted():
    text = f"# T\n\n---\nseed: 1\nseconds: 8\n---\n{_LONG}\n"
    report, healed, issues = _heal("0010-t.md", text)
    assert issues == [], issues
    (s,) = report.suggestions
    kept = " ".join(s.replacement.split())
    assert MIN_PROMPT_CHARS <= len(kept) <= MAX_PROMPT_CHARS
    assert kept.endswith(".")
    assert "dropping: “" in s.why
    assert all(len(line) <= 80 for line in s.replacement.split("\n"))


def test_truncate_prompt_falls_back_to_a_word_boundary():
    one_sentence = ("word " * 300).strip()  # no sentence end before the cap
    kept, dropped = truncate_prompt(one_sentence)
    assert len(kept) <= MAX_PROMPT_CHARS and kept.endswith(".") and dropped.startswith("word")


def test_too_short_prompt_is_a_note_not_a_suggestion():
    text = "# T\n\n---\nseed: 1\nseconds: 8\n---\nA man walks in.\n"
    report, _, _ = _heal("0010-t.md", text)
    assert report.suggestions == []
    assert len(report.notes) == 1 and "at least" in report.notes[0].body


def test_a_dash_row_inside_the_prose_is_removed():
    text = f"# T\n\n---\nseed: 1\nseconds: 8\n---\n{_PROSE}\n---\nThe bell keeps ringing.\n"
    report, healed, issues = _heal("0010-t.md", text)
    assert issues == [], issues
    assert any(s.replacement == "" for s in report.suggestions)
    assert "The bell keeps ringing." in healed


def test_suggestions_never_overlap():
    # A long prose with a dash row inside: the cut rewrites the range, so no
    # separate delete may sit on a line the cut already covers.
    text = f"# T\n\n---\nseed: 1\nseconds: 8\n---\n{_LONG}\n---\nA short tail.\n"
    report, healed, issues = _heal("0010-t.md", text)
    assert issues == [], issues
    spans = sorted((s.start_line, s.end_line) for s in report.suggestions)
    for (a_start, a_end), (b_start, _b_end) in zip(spans, spans[1:]):
        assert a_end < b_start, spans


def test_a_second_prose_block_after_a_fence_gets_its_own_header():
    text = f"# T\n\n---\nseed: 1\nseconds: 8\n---\n{_PROSE}\n---\n{_PROSE}\n"
    report, healed, issues = _heal("0010-t.md", text)
    assert issues == [], issues
    episode, _ = validate.parse_episode("0010-t.md", healed)
    assert episode is not None and len(episode.scenes) == 2


def test_hash_lines_in_the_prose_lose_their_hash():
    text = f"# T\n\n---\nseed: 1\nseconds: 8\n---\n## Scene one\n{_PROSE}\n"
    report, healed, issues = _heal("0010-t.md", text)
    assert issues == [], issues
    assert "## Scene one" not in healed and "Scene one" in healed


def test_title_without_a_hash_and_a_four_dash_fence_are_fixed():
    text = f"The Arrival\n\n----\nseed: 1\nseconds: 8\n----\n{_PROSE}\n"
    report, healed, issues = _heal("0010-the-arrival.md", text)
    assert issues == [], issues
    assert healed.startswith("# The Arrival\n")


def test_missing_title_is_derived_from_the_filename():
    text = f"---\nseed: 1\nseconds: 8\n---\n{_PROSE}\n"
    report, healed, issues = _heal("0010-the-arrival.md", text)
    assert issues == [], issues
    assert healed.startswith("# The Arrival\n\n---")


def test_bad_filename_becomes_a_rename_note():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        assert fixed_name(root, "7774-Tung Tung Tung Sahur.md") == "7774-tung-tung-tung-sahur.md"
        (root / "0030-x.md").write_text("", encoding="utf-8")
        assert fixed_name(root, "My Scene.md") == "0040-my-scene.md"
        assert fixed_name(root, "0010-fine.md") is None
        assert fixed_name(root, "0010-....md") is None
    text = f"# T\n\n---\nseed: 1\nseconds: 8\n---\n{_PROSE}\n"
    report, _, _ = _heal("0050-Bad Name.md", text)
    assert report.suggestions == []
    assert len(report.notes) == 1 and "`0050-bad-name.md`" in report.notes[0].body


def test_diagnose_skips_removed_and_allowlisted_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "README.md").write_text("no header here", encoding="utf-8")
        (root / "0010-a.md").write_text(f"# A\n\n---\nseconds: 8\n---\n{_PROSE}\n", encoding="utf-8")
        reports = diagnose(
            root,
            [Change("README.md"), Change("0010-a.md", "added"), Change("0005-gone.md", "removed")],
        )
        assert [r.path for r in reports] == ["0010-a.md"]
        assert reports[0].remaining == []


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
