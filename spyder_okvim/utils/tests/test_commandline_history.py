"""Persistent command-line histories tolerate damaged data and failed writes."""

# Standard Libraries
import json

# Third Party Libraries
import pytest

# Project Libraries
from spyder_okvim.utils.commandline_history import (
    HISTORY_LIMIT,
    load_history,
    save_history,
)


def test_history_round_trip_preserves_literal_unicode_and_order(tmp_path):
    """Ex commands and shared search words survive a new read unchanged."""
    path = tmp_path / "commandline_history.json"
    histories = {
        "ex": ["w 한글 파일.py", r"%s/old/new\\value/g", "w 한글 파일.py"],
        "search": ["한글😀", "  ", r"a.*b\\c", "한글😀"],
    }

    assert save_history(path, histories) is True
    assert load_history(path) == histories
    assert "한글😀" in path.read_text(encoding="utf-8")

    restored = load_history(path)
    restored["ex"].clear()
    assert load_history(path) == histories
    assert histories["ex"]


def test_missing_history_returns_independent_empty_lists(tmp_path):
    """A first run needs no history file and shares no mutable defaults."""
    path = tmp_path / "missing.json"
    histories = load_history(path)
    assert histories == {"ex": [], "search": []}

    histories["ex"].append("w")
    assert load_history(path) == {"ex": [], "search": []}
    assert not path.exists()


@pytest.mark.parametrize(
    "contents",
    [
        b"",
        b"{broken json",
        b"\xff\xfe",
        b"null",
        b"[]",
        b'"history"',
        b"42",
        pytest.param(b"[" * 50000 + b"]" * 50000, id="deeply-nested-json"),
    ],
)
def test_corrupt_or_invalid_root_starts_with_empty_histories(tmp_path, contents):
    path = tmp_path / "commandline_history.json"
    path.write_bytes(contents)

    assert load_history(path) == {"ex": [], "search": []}
    assert path.read_bytes() == contents


@pytest.mark.parametrize(
    "stored, expected",
    [
        ({}, {"ex": [], "search": []}),
        ({"ex": ["w"]}, {"ex": ["w"], "search": []}),
        ({"search": ["한글"]}, {"ex": [], "search": ["한글"]}),
        (
            {"ex": "w", "search": {"pattern": "foo"}},
            {"ex": [], "search": []},
        ),
        (
            {"ex": None, "search": 42, "unknown": ["ignored"]},
            {"ex": [], "search": []},
        ),
        (
            {
                "ex": ["", "  \t", None, 3, False, [], {}, " w file.py "],
                "search": ["", None, 3, False, [], {}, "  \t", "한글😀"],
            },
            {"ex": [" w file.py "], "search": ["  \t", "한글😀"]},
        ),
        (
            {
                "ex": ["w\r", "q\n", "w\ud800", "\udfff", "w valid.py"],
                "search": ["foo\rbar", "foo\nbar", "\ud800", "foo\udfff", "한글😀"],
            },
            {"ex": ["w valid.py"], "search": ["한글😀"]},
        ),
    ],
)
def test_load_validates_each_history_without_losing_valid_entries(
    tmp_path, stored, expected
):
    path = tmp_path / "commandline_history.json"
    path.write_text(json.dumps(stored), encoding="utf-8")

    assert load_history(path) == expected


def test_load_keeps_the_latest_entries_in_each_history(tmp_path):
    path = tmp_path / "commandline_history.json"
    entries = [f"entry {index}" for index in range(HISTORY_LIMIT + 7)]
    path.write_text(json.dumps({"ex": entries, "search": entries}), encoding="utf-8")

    assert HISTORY_LIMIT == 100
    assert load_history(path) == {
        "ex": entries[-HISTORY_LIMIT:],
        "search": entries[-HISTORY_LIMIT:],
    }


def test_failed_atomic_replacement_preserves_previous_history(tmp_path, monkeypatch):
    """An interrupted write leaves the old file intact and removes its staging file."""
    path = tmp_path / "commandline_history.json"
    original = {"ex": ["w"], "search": ["한글"]}
    assert save_history(path, original) is True
    previous_bytes = path.read_bytes()

    def fail_replace(source, target):
        raise OSError("history directory is not writable")

    monkeypatch.setattr(
        "spyder_okvim.utils.commandline_history.os.replace", fail_replace
    )

    assert save_history(path, {"ex": ["q"], "search": ["new"]}) is False
    assert path.read_bytes() == previous_bytes
    assert load_history(path) == original
    assert set(tmp_path.iterdir()) == {path}


def test_failed_encoding_preserves_previous_history(tmp_path):
    """A failed write keeps the old file and removes the partial staging file."""
    path = tmp_path / "commandline_history.json"
    original = {"ex": ["w"], "search": ["한글"]}
    assert save_history(path, original) is True
    previous_bytes = path.read_bytes()

    assert save_history(path, {"ex": ["q"], "search": ["\ud800"]}) is False
    assert path.read_bytes() == previous_bytes
    assert load_history(path) == original
    assert set(tmp_path.iterdir()) == {path}
