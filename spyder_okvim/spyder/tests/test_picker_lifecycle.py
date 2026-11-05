"""Queued focus and accept callbacks belong to exactly one picker session."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QFocusEvent

from spyder_okvim.utils.qtcompat import widget_is_deleted
from tests.qt_support import reset_vim_state


@pytest.fixture
def picker_session(vim_bot):
    main, stack, _, vim, bot = vim_bot
    widget = vim.vim_cmd
    line = widget.commandline
    status = widget.vim_status
    previous_index = stack.get_stack_index()
    line.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    vim._use_stack(stack)
    reset_vim_state(status)
    editor = stack.get_current_editor()
    original = editor.toPlainText()
    editor.set_text("alpha\nsecond line\nthird line")
    status.cursor.set_cursor_pos(0)
    filename = stack.get_current_filename()
    status.jump_list.push(filename, 0)
    status.jump_list.push(filename, 7)
    main.show()
    main.activateWindow()
    line.setFocus()
    QCoreApplication.processEvents()
    state = SimpleNamespace(
        main=main,
        stack=stack,
        widget=widget,
        line=line,
        status=status,
        editor=editor,
        controller=widget.picker,
        bot=bot,
        dialogs=[],
    )
    yield state
    widget.picker.cancel()
    for dialog in state.dialogs:
        if not widget_is_deleted(dialog):
            dialog.close()
            dialog.deleteLater()
    line.esc_pressed()
    status.disconnect_from_editor()
    reset_vim_state(status)
    stack.set_stack_index(0)
    vim._use_stack(stack)
    editor.set_text(original)
    stack.set_stack_index(previous_index)
    vim._use_stack(stack)
    main.activateWindow()
    line.setFocus()
    QCoreApplication.processEvents()


def open_picker(state, source="jumps"):
    state.widget.open_picker(source)
    dialog = state.controller.dialog
    # These tests deliberately invoke callbacks after close; keep their Qt
    # objects alive until teardown while production dialogs delete on close.
    dialog.setAttribute(Qt.WA_DeleteOnClose, False)
    if dialog not in state.dialogs:
        state.dialogs.append(dialog)
    state.bot.waitUntil(lambda: state.controller.result_token is not None)
    return dialog


def post_focus_out(line):
    QCoreApplication.postEvent(line, QFocusEvent(QEvent.FocusOut, Qt.OtherFocusReason))


def test_queued_focus_out_preserves_active_and_finishing_command_state(picker_session):
    state = picker_session
    dialog = open_picker(state)
    previous = state.line.blockSignals(True)
    state.line.setText("draft preserved by focus owner")
    state.line.blockSignals(previous)
    mode = state.status.vim_state
    post_focus_out(state.line)
    QCoreApplication.processEvents()
    assert state.line.text() == "draft preserved by focus owner"
    assert state.status.vim_state == mode
    dialog.reject()
    assert state.controller.phase == "finishing"
    assert state.controller.owns_focus
    # Model an event queued while the disappearing popup relinquishes focus.
    post_focus_out(state.line)
    state.bot.waitUntil(lambda: state.controller.phase == "closed")
    assert state.line.text() == "draft preserved by focus owner"
    assert state.status.vim_state == mode
    assert not state.controller.owns_focus


def test_reopen_invalidates_accepted_action_before_queued_completion(
    picker_session, monkeypatch
):
    state = picker_session
    first = open_picker(state)
    entry = first.selected_entry()
    execute = Mock(return_value=True)
    monkeypatch.setattr(state.controller.providers["jumps"], "execute", execute)
    old_session = state.controller.session
    state.controller._accept(entry)
    assert state.controller.phase == "finishing"
    state.widget.open_picker("marks")
    replacement = state.controller.dialog
    replacement.setAttribute(Qt.WA_DeleteOnClose, False)
    state.dialogs.append(replacement)
    assert replacement is not first
    assert state.controller.session != old_session
    state.controller._complete(old_session)
    QCoreApplication.processEvents()
    execute.assert_not_called()
    assert state.controller.phase == "active"
    assert state.controller.dialog is replacement
    assert state.controller.source == "marks"
    assert replacement.isVisible()


def test_duplicate_enter_and_finished_callbacks_execute_once(
    picker_session, monkeypatch
):
    state = picker_session
    dialog = open_picker(state)
    entry = dialog.selected_entry()
    execute = Mock(return_value=True)
    monkeypatch.setattr(state.controller.providers["jumps"], "execute", execute)
    state.controller._accept(entry)
    state.controller._accept(entry)
    state.controller._finished(1)
    state.bot.waitUntil(lambda: state.controller.phase == "closed")
    execute.assert_called_once_with(entry)


def test_context_loss_after_close_discards_pending_action(picker_session, monkeypatch):
    state = picker_session
    dialog = open_picker(state)
    execute = Mock(return_value=True)
    monkeypatch.setattr(state.controller.providers["jumps"], "execute", execute)
    state.controller._accept(dialog.selected_entry())
    monkeypatch.setattr(state.controller, "_context_valid", lambda: False)
    state.bot.waitUntil(lambda: state.controller.phase == "closed")
    execute.assert_not_called()


def test_same_source_reuses_dialog_and_query(picker_session):
    state = picker_session
    first = open_picker(state)
    first.set_query("second")
    state.controller._query_changed("second")
    state.widget.open_picker("jumps")
    assert state.controller.dialog is first
    assert first.query() == "second"


def test_failed_action_releases_finishing_focus_owner(picker_session, monkeypatch):
    state = picker_session
    dialog = open_picker(state)

    def failed(entry):
        raise RuntimeError("Host rejected navigation")

    monkeypatch.setattr(state.controller.providers["jumps"], "execute", failed)
    state.bot.keyClick(dialog.prompt, Qt.Key_Return)
    state.bot.waitUntil(lambda: state.controller.phase == "closed")
    assert not state.controller.owns_focus
    assert not state.controller.navigating
    assert "could not be opened" in state.widget.msg_label.text()
