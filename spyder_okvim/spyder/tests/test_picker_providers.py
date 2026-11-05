"""Navigation providers must confirm a destination before applying its position."""

from types import SimpleNamespace

import pytest
from qtpy.QtGui import QTextDocument
from qtpy.QtWidgets import QPlainTextDocumentLayout, QPlainTextEdit

from spyder_okvim.spyder import picker_providers as providers_module
from spyder_okvim.spyder.picker_preview import from_text
from spyder_okvim.spyder.picker_providers import (
    JumpsProvider,
    MAX_METADATA_CHARS,
    MarksProvider,
    PickerHost,
    enrich_entries,
)
from spyder_okvim.utils.jump_list import JumpList
from spyder_okvim.utils.picker import PickerEntry, PickerTarget


@pytest.fixture
def provider_host(vim_bot, monkeypatch):
    _, stack, _, vim, _ = vim_bot
    status = vim.vim_cmd.vim_status
    position = status.cursor.get_cursor().position()
    host = PickerHost(vim.vim_cmd)
    monkeypatch.setattr(status, "jump_list", JumpList())
    monkeypatch.setattr(status.host, "open_file", lambda path: None)
    status.cursor.set_cursor_pos(2)
    yield SimpleNamespace(host=host, status=status, stack=stack)
    status.cursor.set_cursor_pos(position)


@pytest.mark.parametrize("exists", [False, True], ids=["missing", "open-rejected"])
def test_failed_jump_keeps_original_cursor_and_history(provider_host, tmp_path, exists):
    state = provider_host
    path = tmp_path / "jump.py"
    if exists:
        path.write_text("destination\n")
    origin = state.status.get_current_location()
    history = state.status.jump_list
    history.push(str(path), 7)
    history.push(*origin)
    provider = JumpsProvider(state.host)
    entry = provider.snapshot(1).entries[0]

    assert not provider.execute(entry)
    assert state.status.get_current_location() == origin
    assert history.index == 2


@pytest.mark.parametrize("line", [0, 100_000], ids=["valid-block", "missing-block"])
def test_failed_mark_open_does_not_move_cursor_or_remove_mark(
    provider_host, monkeypatch, tmp_path, line
):
    state = provider_host
    path = tmp_path / "mark.py"
    path.write_text("destination\n")
    manager = state.status.bookmark_manager
    mark = {"file": str(path), "line": line, "col": 0}
    monkeypatch.setattr(manager, "bookmarks_global", {"A": mark})
    monkeypatch.setattr(manager, "save", lambda: None)
    origin = state.status.get_current_location()
    provider = MarksProvider(state.host)
    entry = next(entry for entry in provider.snapshot(1).entries if entry.label == "A")

    assert not provider.execute(entry)
    assert state.status.get_current_location() == origin
    assert manager.get_bookmark("A") == mark
    assert not state.status.jump_list.jumps


def test_open_document_snapshot_is_reused_until_revision_changes(qtbot, monkeypatch):
    editor = QPlainTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("unsaved first\nsecond")
    stack = SimpleNamespace(data=[SimpleNamespace(filename="live.py", editor=editor)])
    host = PickerHost(
        SimpleNamespace(vim_status=SimpleNamespace(get_editorstack=lambda: stack))
    )
    captures = []

    def capture(*args, **kwargs):
        captures.append(args[0])
        return from_text(*args, **kwargs)

    monkeypatch.setattr(providers_module, "from_text", capture)
    document = editor.document()
    identity = host.content_identity("live.py")
    del document
    assert host.content_identity("live.py") == identity
    first = host.open_content("live.py")
    assert first.identity == identity
    assert host.open_content("live.py") is first
    assert captures == ["unsaved first\nsecond"]

    editor.setPlainText("changed\nsecond")
    second = host.open_content("live.py")
    assert second is not first
    assert second.text == "changed\nsecond"
    assert len(captures) == 2

    replacement = QTextDocument(editor)
    replacement.setDocumentLayout(QPlainTextDocumentLayout(replacement))
    replacement.setPlainText("replacement")
    editor.setDocument(replacement)
    third = host.open_content("live.py")
    assert third is not second
    assert third.identity != second.identity
    assert third.text == "replacement"
    assert len(captures) == 3


@pytest.mark.parametrize("capture", [False, True], ids=["identity", "snapshot"])
def test_document_identity_survives_other_document_lookups(qtbot, capture):
    first, other = QPlainTextEdit(), QPlainTextEdit()
    qtbot.addWidget(first)
    qtbot.addWidget(other)
    first.setPlainText("first unsaved document")
    other.setPlainText("other unsaved document")
    stack = SimpleNamespace(
        data=[
            SimpleNamespace(filename="first.py", editor=first),
            SimpleNamespace(filename="other.py", editor=other),
        ]
    )
    host = PickerHost(
        SimpleNamespace(vim_status=SimpleNamespace(get_editorstack=lambda: stack))
    )
    snapshot = host.open_content("first.py") if capture else None
    identity = snapshot.identity if capture else host.content_identity("first.py")
    other_identity = host.content_identity("other.py")
    # A temporary wrapper can otherwise immediately reuse the released first
    # wrapper's address, hiding an identity based on Python id() by coincidence.
    intervening = QTextDocument()

    assert host.content_identity("first.py") == identity
    assert other_identity != identity
    if capture:
        assert host.open_content("first.py") is snapshot
    del intervening


def test_metadata_snippets_are_bounded_without_changing_navigation_target():
    content = from_text("x" * (MAX_METADATA_CHARS * 20))
    target = PickerTarget("long.py", block_number=0, column_utf16=10_000)
    entry = PickerEntry("a", "marks", "a", target=target)

    (enriched,), limited = enrich_entries((entry,), content)

    assert limited
    assert len(enriched.detail) < MAX_METADATA_CHARS + 100
    assert "1:10001" in enriched.detail
    assert enriched.detail.endswith("…")
    assert enriched.target is target


def test_invalid_metadata_column_has_readable_coordinates():
    target = PickerTarget("short.py", block_number=0, column_utf16=100)
    entry = PickerEntry("a", "marks", "a", target=target)

    (enriched,), limited = enrich_entries((entry,), from_text("short"))

    assert limited
    assert "1:?" in enriched.detail
    assert "None" not in enriched.detail
