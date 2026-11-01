"""Macro repeat uses the last executed register and the current command count."""

# Standard Libraries
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication

# Project Libraries
from tests.qt_support import reset_vim_state


@pytest.fixture
def macro_bot(vim_bot):
    """Keep recorded keys and asynchronous playback local to each test."""
    _, stack, _, vim, qtbot = vim_bot
    widget = vim.vim_cmd
    status = widget.vim_status
    line = widget.commandline
    previous_index = stack.get_stack_index()
    widget.cancel_macro()
    if widget.worker_macro.isRunning():
        widget.worker_macro.wait()
    line.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    vim._use_stack(stack)
    reset_vim_state(status)
    editor = stack.get_current_editor()
    original = editor.toPlainText()
    editor.set_text("abcdefghijklmnopqrstuvwxyz")
    status.cursor.set_cursor_pos(0)
    line.clear()
    line.setFocus()
    state = SimpleNamespace(
        editor=editor, status=status, line=line, widget=widget, qtbot=qtbot
    )
    try:
        yield state
    finally:
        widget.cancel_macro()
        if widget.worker_macro.isRunning():
            widget.worker_macro.wait()
        if status.is_recording_macro():
            status.stop_recording_macro()
        line.esc_pressed()
        status.disconnect_from_editor()
        reset_vim_state(status)
        editor.set_text(original)
        stack.set_stack_index(previous_index)
        vim._use_stack(stack)
        QCoreApplication.processEvents()


def record(state, register, keys):
    """Record a normal-mode macro through actual command-line key events."""
    state.qtbot.keyClicks(state.line, "q" + register + keys + "q")
    assert not state.status.is_recording_macro()
    assert (
        "".join(key.text for key in state.status.manager_macro.registers[register])
        == keys
    )


def execute(state, command):
    """Wait through queued key delivery before observing a macro's result."""
    state.qtbot.keyClicks(state.line, command)
    state.qtbot.waitUntil(lambda: not state.widget.is_playing_macro, timeout=5000)
    assert state.line.text() == ""
    assert state.status.sub_mode is None


def test_repeat_macro_and_count(macro_bot):
    """@@ repeats one execution, and 3@@ applies its own count."""
    state = macro_bot
    record(state, "a", "x")
    assert state.editor.toPlainText() == "bcdefghijklmnopqrstuvwxyz"

    for command, expected in [
        ("@a", "cdefghijklmnopqrstuvwxyz"),
        ("@@", "defghijklmnopqrstuvwxyz"),
        ("3@@", "ghijklmnopqrstuvwxyz"),
        ("@@", "hijklmnopqrstuvwxyz"),
    ]:
        execute(state, command)
        assert state.editor.toPlainText() == expected


def test_repeat_uses_latest_executed_register(macro_bot):
    """Executing another register changes the target of the next @@."""
    state = macro_bot
    record(state, "a", "l")
    record(state, "b", "2l")
    state.status.cursor.set_cursor_pos(0)

    for command, position in [("@a", 1), ("@b", 3), ("@@", 5)]:
        execute(state, command)
        assert state.editor.textCursor().position() == position


def test_recording_does_not_change_last_executed_register(macro_bot):
    """A new recording leaves @@ pointing at the preceding execution."""
    state = macro_bot
    record(state, "a", "x")
    execute(state, "@a")
    record(state, "b", "2x")

    execute(state, "@@")

    assert state.editor.toPlainText() == "fghijklmnopqrstuvwxyz"


def test_repeat_without_previous_macro_does_not_start_playback(macro_bot, monkeypatch):
    """An initial @@ ends cleanly and explains why it cannot execute."""
    state = macro_bot
    start = Mock()
    monkeypatch.setattr(state.widget.macro_playback, "start", start)

    execute(state, "@@")

    start.assert_not_called()
    assert not state.widget.worker_macro.isRunning()
    assert state.editor.toPlainText() == "abcdefghijklmnopqrstuvwxyz"
    assert "No previously used register" in state.status.msg_label.text()


@pytest.mark.parametrize("command", ["q@", "m@"])
def test_repeat_register_is_only_accepted_for_execution(
    macro_bot, monkeypatch, command
):
    """Allowing @@ does not admit @ as a recording register or mark name."""
    state = macro_bot
    callback = Mock()
    if command == "q@":
        monkeypatch.setattr(state.status, "start_recording_macro", callback)
    else:
        monkeypatch.setattr(state.status.bookmark_manager, "set_bookmark", callback)
    registers = dict(state.status.manager_macro.registers)
    bookmarks = list(state.status.bookmark_manager.list_bookmarks())

    state.qtbot.keyClicks(state.line, command)

    callback.assert_not_called()
    assert not state.status.is_recording_macro()
    assert dict(state.status.manager_macro.registers) == registers
    assert list(state.status.bookmark_manager.list_bookmarks()) == bookmarks
    assert state.line.text() == ""
    assert state.status.sub_mode is None
