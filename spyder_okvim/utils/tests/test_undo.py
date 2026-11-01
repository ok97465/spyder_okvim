"""Verify Vim undo boundaries with Qt and Spyder 6.2 editor histories."""

# Third Party Libraries
import pytest
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QPlainTextEdit
from spyder.plugins.editor.widgets.codeeditor import CodeEditor

# Project Libraries
from spyder_okvim.utils.undo import (
    UndoGroup,
    editor_redo,
    editor_undo,
    undo_available,
    undo_block,
    undo_owner,
)


@pytest.fixture(params=[QPlainTextEdit, CodeEditor], ids=["qt", "spyder"])
def undo_editor(request, qtbot):
    editor = request.param(None)
    qtbot.addWidget(editor)
    return editor


def test_separate_changes_keep_separate_undo_steps(undo_editor):
    editor = undo_editor
    with undo_block(editor):
        editor.insertPlainText("first")
    with undo_block(editor):
        editor.insertPlainText("second")
    assert undo_available(editor)

    editor.undo()
    assert editor.toPlainText() == "first"
    editor.undo()
    assert editor.toPlainText() == ""
    editor.redo()
    assert editor.toPlainText() == "first"
    editor.redo()
    assert editor.toPlainText() == "firstsecond"


def test_session_groups_events_across_cursor_moves(undo_editor):
    editor = undo_editor
    with undo_block(editor):
        editor.insertPlainText("before")

    group = UndoGroup(editor)
    group.start()
    with group.edit_block():
        editor.insertPlainText("\n")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.Start)
    editor.setTextCursor(cursor)
    with group.edit_block():
        editor.insertPlainText("first")
    with group.edit_block():
        editor.insertPlainText("second")
    group.finish()
    changed = editor.toPlainText()
    assert changed == "firstsecondbefore\n"

    editor.undo()
    assert editor.toPlainText() == "before"
    editor.redo()
    assert editor.toPlainText() == changed


def test_join_previous_retains_earlier_change(undo_editor):
    editor = undo_editor
    with undo_block(editor):
        editor.insertPlainText("before")
    with undo_block(editor):
        editor.insertPlainText("first")
    with undo_block(editor, join_previous=True):
        editor.insertPlainText("second")

    editor.undo()
    assert editor.toPlainText() == "before"
    editor.redo()
    assert editor.toPlainText() == "beforefirstsecond"


def test_cloned_spyder_view_uses_shared_document_history(qtbot):
    """A clone records edits through its document's original editor."""
    original = CodeEditor(None)
    clone = CodeEditor(None)
    qtbot.addWidget(original)
    qtbot.addWidget(clone)
    original.setup_editor(language="Python")
    clone.setup_editor(language="Python")
    original.set_text("abcd")
    original._commit_pending_edit()
    original.clear_undo_stack()
    clone.set_as_clone(original)
    cursor = clone.textCursor()
    cursor.setPosition(1)
    clone.setTextCursor(cursor)
    assert undo_owner(clone) is original
    assert not clone.document().isUndoRedoEnabled()
    with undo_block(clone):
        clone.insertPlainText("X")
    with undo_block(clone, join_previous=True):
        clone.insertPlainText("Y")
    assert undo_available(clone)
    assert not clone.undo_stack.can_undo()
    assert clone.toPlainText() == "aXYbcd"

    editor_undo(clone)
    assert clone.toPlainText() == original.toPlainText() == "abcd"
    assert clone.textCursor().position() == 1
    editor_redo(clone)
    assert clone.toPlainText() == original.toPlainText() == "aXYbcd"
    assert clone.textCursor().position() == 3
