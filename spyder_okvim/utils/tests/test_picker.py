"""Search contracts shared by all picker sources."""

from dataclasses import replace

import pytest

from spyder_okvim.utils.picker import (
    CandidateSnapshot,
    MAX_DISPLAY_RESULTS,
    PickerEntry,
    PickerTarget,
    search,
)


def snapshot(*labels):
    return CandidateSnapshot(
        "files",
        "/project",
        1,
        tuple(
            PickerEntry(
                str(i),
                "files",
                label,
                ordinal=i,
                target=PickerTarget(f"/project/{label}"),
            )
            for i, label in enumerate(labels)
        ),
    )


def test_best_match_is_at_prompt_and_empty_order_is_stable():
    data = snapshot("ab-long-c.py", "abc.py", "other-ABC.py")
    assert [match.entry.id for match in search(data, "").matches] == ["2", "1", "0"]
    matches = search(data, "a B c").matches
    assert matches[-1].entry.label == "abc.py"
    assert matches[-1].label_matches == (0, 1, 2)
    assert matches[-1].entry.target.path == "/project/abc.py"


def test_smallest_window_beats_first_subsequence():
    data = snapshot("a---b---c---abc", "a-b-c")
    assert search(data, "abc").matches[-1].entry.label == "a---b---c---abc"
    assert search(data, "abc").matches[-1].label_matches == (12, 13, 14)


def test_top_n_is_never_used_as_candidate_set_for_next_query():
    data = snapshot(*(f"file-{i}.py" for i in range(MAX_DISPLAY_RESULTS + 25)))
    initial = search(data, "")
    assert initial.total_matches == MAX_DISPLAY_RESULTS + 25
    assert initial.truncated
    assert len(initial.matches) == MAX_DISPLAY_RESULTS
    assert search(data, "file-1024").matches[-1].entry.id == "1024"
    assert search(data, "no-such-file").matches == ()
    assert search(data, "").total_matches == MAX_DISPLAY_RESULTS + 25


@pytest.mark.parametrize("query", ["", "same"])
def test_limited_results_preserve_stable_ties_and_total_count(query):
    data = snapshot(*(["same.py"] * 6))
    data = replace(
        data, entries=tuple(replace(entry, ordinal=0) for entry in data.entries)
    )
    complete = search(data, query)
    for limit in (0, 1, 3):
        result = search(data, query, limit=limit)
        assert result.matches == (complete.matches[-limit:] if limit else ())
        assert result.total_matches == len(data.entries)
        assert result.truncated


def test_unicode_casefold_highlight_uses_original_characters():
    data = snapshot("Straße.py")
    found = search(data, "STRASSE").matches[-1]
    assert found.label_matches == (0, 1, 2, 3, 4, 5)


def test_metadata_search_preserves_id_and_target():
    data = snapshot("alpha.py")
    entry = replace(data.entries[0], search_text="alpha.py print(marker)")
    enriched = replace(data, dataset_version=2, entries=(entry,))
    match = search(enriched, "marker").matches[-1]
    assert match.entry.id == data.entries[0].id
    assert match.entry.target == data.entries[0].target


def test_cancel_returns_no_selectable_partial_result():
    data = snapshot(*(f"file-{i}.py" for i in range(300)))
    calls = 0

    def cancelled():
        nonlocal calls
        calls += 1
        return calls > 1

    result = search(data, "file", cancelled)
    assert result.cancelled
    assert result.matches == ()


def test_repeating_query_is_bounded_and_literal():
    data = snapshot("a" * 8000 + "[x]")
    assert search(data, "a" * 256).total_matches == 1
    assert search(data, "[x]").matches[-1].label_matches == (8000, 8001, 8002)


def test_adversarial_single_match_is_cancellable_inside_the_window_search():
    data = snapshot("a_b_" * 2048)
    calls = 0

    def cancelled():
        nonlocal calls
        calls += 1
        return calls >= 3

    result = search(data, "ab" * 128, cancelled)
    assert result.cancelled
    assert result.matches == ()
    assert calls <= 6


def test_long_fields_keep_exact_match_existence_with_bounded_window_ranking():
    # The first backward-shrunk window spans a_b_c (5 characters); a later
    # a_bc window is shorter, but long-field refinement intentionally stops.
    text = "a_b_" * 600 + "c" + "a_bc"
    result = search(snapshot(text), "abc")
    assert result.total_matches == 1
    assert result.matches[-1].score[0] == 5
    assert search(snapshot(text), "z").total_matches == 0
