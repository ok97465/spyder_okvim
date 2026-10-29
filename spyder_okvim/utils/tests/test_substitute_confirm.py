"""Confirmation choices, document ownership and undo grouping."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, QObject, Signal
from qtpy.QtGui import QTextCursor, QTextDocument
from qtpy.QtWidgets import QPlainTextDocumentLayout, QPlainTextEdit

from spyder_okvim.executor.tests.test_substitute import substitute_bot as substitute_bot
from spyder_okvim.utils.substitute_confirm import SubstituteConfirm


@pytest.fixture
def confirmation_bot(request):
    bot = request.getfixturevalue("substitute_bot")
    editor, status, _, _ = bot
    editor.set_text("foo foo\n  foo")
    yield bot
    session = getattr(status, "substitute_confirm", None)
    if session is not None:
        session.cancel()


def start_session(bot, targets=None):
    editor, status, _, _ = bot
    callback = Mock()
    if targets is None:
        targets = ((0, 3, "longer"), (4, 7, "longer"), (10, 13, "longer"))
    session = SubstituteConfirm(status, editor, targets, callback)
    status.substitute_confirm = status.sub_mode = session
    session.start()
    return session, callback


@pytest.mark.parametrize(
    "keys, expected, count, lines",
    [
        ("yny", "longer foo\n  longer", 2, 2),
        ("a", "longer longer\n  longer", 3, 2),
        ("l", "longer foo\n  foo", 1, 1),
        ("nl", "foo longer\n  foo", 1, 1),
        ("nnn", "foo foo\n  foo", 0, 0),
    ],
)
def test_confirmation_choices_and_one_undo(
    confirmation_bot, keys, expected, count, lines
):
    editor, status, _, _ = confirmation_bot
    original = editor.toPlainText()
    session, callback = start_session(confirmation_bot)
    for key in keys:
        assert session(key) is True
    assert editor.toPlainText() == expected
    assert not session.active
    assert not session.cancelled
    assert session.replacement_count == count
    assert session.line_count == lines
    assert status.sub_mode is None
    assert status.substitute_confirm is None
    assert not editor.get_extra_selections("vim_substitute")
    callback.assert_called_once_with(session)
    if count:
        editor.undo()
        assert editor.toPlainText() == original
        assert not editor.document().isUndoAvailable()
        editor.redo()
        assert editor.toPlainText() == expected
    else:
        assert not editor.document().isUndoAvailable()


@pytest.mark.parametrize(
    "cancel", [lambda session: session("q"), lambda session: session.on_escape()]
)
def test_partial_cancel_keeps_one_undo(confirmation_bot, cancel):
    editor, status, _, _ = confirmation_bot
    original = editor.toPlainText()
    session, callback = start_session(confirmation_bot)
    session("y")
    cancel(session)
    session.cancel()
    assert editor.toPlainText() == "longer foo\n  foo"
    assert not session.active
    assert session.cancelled
    assert status.sub_mode is None
    assert not editor.get_extra_selections("vim_substitute")
    callback.assert_called_once_with(session)
    editor.undo()
    assert editor.toPlainText() == original


def test_highlight_follows_utf16_length_changes(confirmation_bot):
    editor, _, _, _ = confirmation_bot
    editor.set_text("😀a a")
    session, _ = start_session(confirmation_bot, ((2, 3, "한글"), (4, 5, "끝")))
    selection = editor.get_extra_selections("vim_substitute")[0]
    assert (selection.cursor.selectionStart(), selection.cursor.selectionEnd()) == (
        2,
        3,
    )
    session("y")
    selection = editor.get_extra_selections("vim_substitute")[0]
    assert (selection.cursor.selectionStart(), selection.cursor.selectionEnd()) == (
        5,
        6,
    )
    session("y")
    assert editor.toPlainText() == "😀한글 끝"


def test_external_edit_cancels_and_remains_separate_undo(confirmation_bot):
    editor, _, _, _ = confirmation_bot
    original = editor.toPlainText()
    session, callback = start_session(confirmation_bot)
    session("y")
    approved = editor.toPlainText()
    cursor = QTextCursor(editor.document())
    cursor.beginEditBlock()
    cursor.insertText("external ")
    cursor.endEditBlock()
    assert not session.active
    assert session.cancelled
    assert not session.valid()
    callback.assert_called_once_with(session)
    session("a")
    assert editor.toPlainText() == "external " + approved
    editor.undo()
    assert editor.toPlainText() == approved
    editor.undo()
    assert editor.toPlainText() == original


def test_unchanged_approvals_do_not_add_undo(confirmation_bot):
    editor, _, _, _ = confirmation_bot
    session, _ = start_session(confirmation_bot, ((0, 3, "foo"), (4, 7, "foo")))
    session("a")
    assert session.replacement_count == 2
    assert session.changed == 0
    assert not editor.document().isUndoAvailable()


def test_cancellation_signal_disconnects_session(confirmation_bot):
    editor, status, commandline, _ = confirmation_bot
    session, callback = start_session(confirmation_bot)
    commandline.vim_widget.sig_command_cancelled.emit()
    assert not session.active
    assert status.substitute_confirm is None
    assert not editor.get_extra_selections("vim_substitute")
    commandline.vim_widget.sig_command_cancelled.emit()
    callback.assert_called_once_with(session)


def test_invalid_confirmation_key_is_consumed(confirmation_bot):
    editor, _, _, _ = confirmation_bot
    session, _ = start_session(confirmation_bot)
    assert session("x") is True
    assert session.active
    assert editor.toPlainText() == "foo foo\n  foo"
    assert not editor.document().isUndoAvailable()


def test_readonly_change_cancels_before_next_approval(confirmation_bot):
    editor, _, _, _ = confirmation_bot
    session, _ = start_session(confirmation_bot)
    editor.setReadOnly(True)
    session("y")
    assert session.cancelled
    assert editor.toPlainText() == "foo foo\n  foo"


def test_strip_setting_restored_after_approval(confirmation_bot):
    editor, _, _, _ = confirmation_bot
    editor.skip_rstrip = False
    session, _ = start_session(confirmation_bot)
    session("l")
    assert editor.skip_rstrip is False


def test_edit_exception_cleans_up_session(confirmation_bot, monkeypatch):
    editor, status, _, _ = confirmation_bot
    editor.skip_rstrip = False
    session, callback = start_session(confirmation_bot)
    monkeypatch.setattr(
        editor, "document_did_change", Mock(side_effect=RuntimeError("notification"))
    )
    with pytest.raises(RuntimeError, match="notification"):
        session("y")
    assert not session.active
    assert status.sub_mode is None
    assert status.substitute_confirm is None
    assert editor.skip_rstrip is False
    assert not editor.get_extra_selections("vim_substitute")
    assert editor.toPlainText() == "longer foo\n  foo"
    callback.assert_called_once_with(session)
    editor.undo()
    assert editor.toPlainText() == "foo foo\n  foo"


@pytest.mark.parametrize("destroy", ["editor", "document"])
def test_destroyed_context_disconnects_confirmation(qtbot, destroy):
    class CommandWidget(QObject):
        sig_command_cancelled = Signal()

    class Editor(QPlainTextEdit):
        skip_rstrip = False
        highlighted = False

        def set_extra_selections(self, name, selections):
            self.highlighted = True

        def clear_extra_selections(self, name):
            self.highlighted = False

    editor = Editor()
    if destroy == "document":
        qtbot.addWidget(editor)
    editor.setPlainText("foo")
    widget = CommandWidget()
    status = SimpleNamespace(
        get_editor=lambda: editor,
        cursor=Mock(),
        set_message=Mock(),
        cmd_line=SimpleNamespace(vim_widget=widget, sync_input_method=Mock()),
    )
    callback = Mock()
    session = SubstituteConfirm(status, editor, ((0, 3, "x"),), callback)
    status.sub_mode = status.substitute_confirm = session
    session.start()
    if destroy == "editor":
        editor.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    else:
        document = QTextDocument(editor)
        document.setDocumentLayout(QPlainTextDocumentLayout(document))
        editor.setDocument(document)
    assert not session.active
    assert session.cancelled
    assert not session.valid()
    assert status.sub_mode is None
    assert status.substitute_confirm is None
    if destroy == "document":
        assert not editor.highlighted
    callback.assert_called_once_with(session)
    widget.sig_command_cancelled.emit()
    callback.assert_called_once_with(session)
