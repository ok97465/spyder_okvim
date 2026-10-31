"""Mark storage contracts without Qt, Spyder or a user configuration directory."""

# Standard Libraries
from copy import deepcopy
from types import SimpleNamespace

# Project Libraries
from spyder_okvim.utils.bookmark_manager import (
    BookmarkManager,
    load_bookmarks,
    save_bookmarks,
)


def test_mark_rules_can_use_an_in_memory_store():
    stored = {"A": {"file": "previous.py", "line": 0, "col": 1}}
    writes = []
    cursor = SimpleNamespace(
        blockNumber=lambda: 2,
        position=lambda: 13,
        block=lambda: SimpleNamespace(position=lambda: 10),
    )
    editor = SimpleNamespace(textCursor=lambda: cursor)
    stack = SimpleNamespace(get_current_filename=lambda: "current.py")
    manager = BookmarkManager(
        "memory://marks",
        lambda path: None,
        lambda: stack,
        lambda: editor,
        lambda position: None,
        load=lambda path: deepcopy(stored),
        persist=lambda path, values: writes.append((path, deepcopy(values))),
    )

    assert manager.get_bookmark("A") == stored["A"]
    manager.set_bookmark("a")
    assert manager.get_bookmark("a") == {"file": "current.py", "line": 2, "col": 3}
    assert writes == []

    manager.set_bookmark("B")
    assert writes == [
        (
            "memory://marks",
            {**stored, "B": {"file": "current.py", "line": 2, "col": 3}},
        )
    ]
    manager.clear()
    assert manager.list_bookmarks() == []
    assert writes[-1] == ("memory://marks", {})


def test_bookmark_storage_preserves_existing_json_format(tmp_path):
    path = tmp_path / "config" / "bookmarks.json"
    marks = {"Z": {"file": "한글.py", "line": 4, "col": 2}}
    save_bookmarks(str(path), marks)
    assert load_bookmarks(str(path)) == marks


def test_missing_and_damaged_bookmark_storage_remains_empty(tmp_path):
    path = tmp_path / "bookmarks.json"
    assert load_bookmarks(str(path)) == {}
    path.write_text("invalid json", encoding="utf-8")
    assert load_bookmarks(str(path)) == {}
