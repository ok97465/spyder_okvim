"""Confirmation responses stay inside their input and document context."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QFocusEvent, QInputMethodEvent, QKeyEvent

from spyder_okvim.spyder.vim_widgets import VimWidget
from spyder_okvim.vim import KeyInfo


@pytest.fixture
def confirming(vim_bot):
    """Start each test with a focused command line and an isolated document."""
    main, stack, _, vim, bot = vim_bot
    widget = vim.vim_cmd
    status = widget.vim_status
    line = widget.commandline
    previous_index = stack.get_stack_index()
    widget.cancel_macro()
    line.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    vim._use_stack(stack)
    status.reset_for_test()
    editor = stack.get_current_editor()
    original = editor.toPlainText()
    editor.set_text("foo foo\n  foo foo")
    status.cursor.set_cursor_pos(0)
    line.histories["ex"].clear()
    main.activateWindow()
    line.setFocus()
    QCoreApplication.processEvents()
    state = SimpleNamespace(
        main=main,
        stack=stack,
        vim=vim,
        widget=widget,
        status=status,
        line=line,
        editor=editor,
        bot=bot,
    )
    try:
        yield state
    finally:
        widget.cancel_substitute()
        widget.cancel_macro()
        if status.is_recording_macro():
            status.stop_recording_macro()
        line.esc_pressed()
        status.disconnect_from_editor()
        stack.set_stack_index(0)
        vim._use_stack(stack)
        status.reset_for_test()
        editor.set_text(original)
        line.histories["ex"].clear()
        stack.set_stack_index(previous_index)
        vim._use_stack(stack)


def start_confirmation(state):
    state.bot.keyClicks(state.line, ":%s/foo/long/gc")
    state.bot.keyPress(state.line, Qt.Key_Return)
    session = state.status.substitute_confirm
    assert session is not None
    assert session.active
    assert state.status.sub_mode is session
    assert state.line.text() == ""
    return session


def test_confirmation_disables_ime_and_ignores_late_commit(confirming):
    state = confirming
    session = start_confirmation(state)
    original = state.editor.toPlainText()
    assert not state.line.testAttribute(Qt.WA_InputMethodEnabled)

    event = QInputMethodEvent("한글", [])
    event.setCommitString("a")
    QCoreApplication.sendEvent(state.line, event)

    assert state.status.substitute_confirm is session
    assert state.editor.toPlainText() == original
    assert state.line.text() == ""
    state.bot.keyClicks(state.line, "y")
    assert state.editor.toPlainText() == "long foo\n  foo foo"


def test_responses_do_not_enter_history_or_macro_recording(confirming):
    state = confirming
    state.status.manager_macro.start_record("a")
    start_confirmation(state)
    command = list(state.status.manager_macro.registers["a"])
    input_command = state.status.input_cmd.cmd
    state.bot.keyClicks(state.line, "ynq")
    assert state.status.substitute_confirm is None
    assert state.status.is_recording_macro()
    assert state.status.manager_macro.registers["a"] == command
    assert state.status.input_cmd.cmd == input_command
    assert state.line.histories["ex"] == ["%s/foo/long/gc"]
    assert state.line.text() == ""
    state.bot.keyClicks(state.line, "q")
    assert not state.status.is_recording_macro()


@pytest.mark.parametrize(
    "key, modifiers",
    [
        (Qt.Key_X, Qt.NoModifier),
        (Qt.Key_Tab, Qt.NoModifier),
        (Qt.Key_R, Qt.ControlModifier),
    ],
)
def test_non_response_keys_and_shortcuts_are_consumed(
    confirming, monkeypatch, key, modifiers
):
    state = confirming
    session = start_confirmation(state)
    redo = Mock()
    monkeypatch.setitem(state.line.dispatcher, Qt.Key_R, redo)
    original = state.editor.toPlainText()
    state.bot.keyPress(state.line, key, modifiers)
    assert state.status.substitute_confirm is session
    assert state.editor.toPlainText() == original
    assert state.line.text() == ""
    redo.assert_not_called()
    override = QKeyEvent(QEvent.ShortcutOverride, key, modifiers)
    QCoreApplication.sendEvent(state.line, override)
    assert override.isAccepted()


@pytest.mark.parametrize(
    "key, modifiers", [(Qt.Key_Escape, Qt.NoModifier), (Qt.Key_C, Qt.ControlModifier)]
)
def test_escape_and_control_c_keep_accepted_changes(
    confirming, monkeypatch, key, modifiers
):
    state = confirming
    session = start_confirmation(state)
    state.bot.keyClicks(state.line, "y")
    clear_search = Mock()
    monkeypatch.setitem(state.line.dispatcher, Qt.Key_C, clear_search)
    state.bot.keyPress(state.line, key, modifiers)
    assert state.editor.toPlainText() == "long foo\n  foo foo"
    assert state.status.substitute_confirm is None
    assert state.status.sub_mode is None
    assert not session.active
    assert not state.editor.get_extra_selections("vim_substitute")
    clear_search.assert_not_called()
    state.bot.keyClicks(state.line, "u")
    assert state.editor.toPlainText() == "foo foo\n  foo foo"


def test_focus_loss_cancels_even_with_ime_disabled(confirming):
    state = confirming
    session = start_confirmation(state)
    state.bot.keyClicks(state.line, "y")
    state.line.focusOutEvent(QFocusEvent(QEvent.FocusOut))
    assert state.status.substitute_confirm is None
    assert not session.active
    session("a")
    assert state.editor.toPlainText() == "long foo\n  foo foo"
    assert not state.editor.get_extra_selections("vim_substitute")


def test_file_switch_cancels_before_responses_cross_documents(confirming):
    state = confirming
    session = start_confirmation(state)
    state.bot.keyClicks(state.line, "y")
    state.stack.set_stack_index(1)
    state.vim._on_editor_focus_changed()
    other = state.stack.get_current_editor()
    other_original = other.toPlainText()
    assert state.status.substitute_confirm is None
    assert state.status.sub_mode is None
    assert not session.active
    session("a")
    assert state.editor.toPlainText() == "long foo\n  foo foo"
    assert other.toPlainText() == other_original


def test_test_reset_cancels_confirmation(confirming):
    state = confirming
    session = start_confirmation(state)
    state.status.reset_for_test()
    assert state.status.substitute_confirm is None
    assert not session.active
    assert not state.editor.get_extra_selections("vim_substitute")


def test_cleanup_cancels_before_queued_responses(confirming):
    state = confirming
    widget = VimWidget(state.main.editor, state.main)
    state.bot.addWidget(widget)
    widget.commandline.setFocus()
    state.bot.keyClicks(widget.commandline, ":%s/foo/long/gc")
    state.bot.keyPress(widget.commandline, Qt.Key_Return)
    session = widget.vim_status.substitute_confirm
    assert session is not None
    widget.cleanup()
    assert widget.vim_status.substitute_confirm is None
    assert not session.active
    session("a")
    assert state.editor.toPlainText() == "foo foo\n  foo foo"


def test_programmatic_response_uses_only_confirmation_dispatch(confirming):
    state = confirming
    start_confirmation(state)
    state.line.setText("y")
    assert state.editor.toPlainText() == "long foo\n  foo foo"
    assert state.line.text() == ""
    assert state.line.histories["ex"] == ["%s/foo/long/gc"]


def test_macro_confirmation_aborts_queued_normal_commands(confirming):
    state = confirming
    state.status.manager_macro.start_record("a")
    start_confirmation(state)
    state.bot.keyClicks(state.line, "qq")
    assert not state.status.is_recording_macro()
    state.status.manager_macro.registers["a"].extend(
        KeyInfo(ord(char.upper()), char, Qt.NoModifier, 0) for char in "xya"
    )
    original = state.editor.toPlainText()

    state.bot.keyClicks(state.line, "@a")
    state.bot.waitUntil(lambda: not state.widget.is_playing_macro)
    QCoreApplication.processEvents()

    assert state.editor.toPlainText() == original
    assert state.status.substitute_confirm is None
    assert state.status.sub_mode is None
    assert state.status.is_normal()
    assert state.line.text() == ""
    assert "macro" in state.status.msg_label.text().lower()


@pytest.mark.parametrize("command", ["s/[foo/x/c", "99s/foo/x/c", "s/foo/x/cx"])
def test_invalid_macro_confirmation_does_not_leak_response_keys(confirming, command):
    state = confirming
    state.status.manager_macro.start_record("a")
    state.bot.keyClicks(state.line, ":" + command)
    state.bot.keyPress(state.line, Qt.Key_Return)
    state.status.manager_macro.stop_record()
    state.status.manager_macro.registers["a"].extend(
        KeyInfo(ord(char.upper()), char, Qt.NoModifier, 0) for char in "xya"
    )
    original = state.editor.toPlainText()
    previous = state.status.last_substitute
    state.bot.keyClicks(state.line, "@a")
    state.bot.waitUntil(lambda: not state.widget.is_playing_macro)
    QCoreApplication.processEvents()
    assert state.editor.toPlainText() == original
    assert state.status.substitute_confirm is None
    assert state.status.last_substitute == previous
    assert state.status.is_normal()


@pytest.mark.parametrize(
    "flags, expected",
    [("", "foo foo\n  foo foo"), ("e", "oo foo\n  foo foo")],
)
def test_no_match_stops_macro_unless_error_is_suppressed(confirming, flags, expected):
    state = confirming
    state.status.manager_macro.start_record("a")
    state.bot.keyClicks(state.line, ":s/absent/x/" + flags)
    state.bot.keyPress(state.line, Qt.Key_Return)
    state.status.manager_macro.stop_record()
    state.status.manager_macro.registers["a"].append(
        KeyInfo(Qt.Key_X, "x", Qt.NoModifier, 0)
    )

    state.bot.keyClicks(state.line, "@a")
    state.bot.waitUntil(lambda: not state.widget.is_playing_macro)
    QCoreApplication.processEvents()

    assert state.editor.toPlainText() == expected
    assert state.status.is_normal()
    assert state.line.text() == ""
