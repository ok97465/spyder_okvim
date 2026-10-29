"""Stable command observations survive recursive input and dispatch failures."""

# Standard Libraries
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QInputMethodEvent, QTextCursor
from qtpy.QtWidgets import QApplication

# Project Libraries
from spyder_okvim.vim import VimState


@pytest.fixture
def ex_input_bot(vim_bot):
    """Isolate Ex input from the session editor and previous pending commands."""
    _, stack, _, vim, qtbot = vim_bot
    widget = vim.vim_cmd
    status = widget.vim_status
    commandline = widget.commandline
    previous_index = stack.get_stack_index()
    commandline.setFocus()
    QCoreApplication.processEvents()
    commandline.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    status.reset_for_test()
    editor = stack.get_current_editor()
    original = editor.toPlainText()
    editor.set_text("aa\nbb\ncc\n")
    status.cursor.set_cursor_pos(0)
    commandline.histories["ex"].clear()
    try:
        yield editor, status, commandline, qtbot, widget, stack
    finally:
        widget.cancel_macro()
        commandline.setFocus()
        QCoreApplication.processEvents()
        commandline.esc_pressed()
        status.disconnect_from_editor()
        stack.set_stack_index(0)
        status.reset_for_test()
        editor.set_text(original)
        commandline.histories["ex"].clear()
        stack.set_stack_index(previous_index)


@pytest.mark.parametrize(
    "command, expected",
    [
        ("v", ":1,1"),
        ("V", ":1,1"),
        ("v2j", ":1,3"),
        ("2jv2k", ":1,3"),
        ("V2j", ":1,3"),
        ("2jV2k", ":1,3"),
        ("GV", ":4,4"),
        ("Gv", ":4,4"),
        ("VG", ":1,4"),
    ],
)
def test_visual_colon_fixes_range_before_normal_input(ex_input_bot, command, expected):
    """Reverse and EOF selections install one Normal Ex prompt without reentry."""
    editor, status, commandline, qtbot, widget, _ = ex_input_bot
    original = editor.toPlainText()
    changes = []

    def finished():
        changes.append(commandline.text())

    widget.sig_input_finished.connect(finished)
    qtbot.keyClicks(commandline, command)
    changes.clear()
    try:
        qtbot.keyClicks(commandline, ":")

        assert commandline.text() == expected
        assert changes == [expected]
        assert status.is_normal()
        assert not status.is_visual_mode
        assert status.sub_mode.history_kind == "ex"
        assert status.sub_mode.pending_range_text is None
        assert not editor.get_extra_selections("vim_selection")
        assert editor.toPlainText() == original
        qtbot.keyPress(commandline, Qt.Key_Escape)
        assert status.is_normal()
        assert status.sub_mode is None
        assert commandline.histories["ex"] == []
    finally:
        widget.sig_input_finished.disconnect(finished)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("mode, expected", [("v", ":1,1"), ("V", ":1,2")])
def test_visual_colon_uses_extra_selection_at_block_boundary(
    ex_input_bot, reverse, mode, expected
):
    """A character endpoint excludes the next row while VLINE keeps an empty row."""
    editor, status, commandline, qtbot, _, _ = ex_input_bot
    editor.set_text("aa\n\ncc")
    qtbot.keyClicks(commandline, mode)
    start, end = (3, 0) if reverse else (0, 3)
    status.cursor.create_selection(start, end)
    unrelated = editor.textCursor()
    unrelated.setPosition(4)
    unrelated.setPosition(6, QTextCursor.KeepAnchor)
    editor.setTextCursor(unrelated)

    qtbot.keyClicks(commandline, ":")

    assert commandline.text() == expected
    assert status.is_normal()


@pytest.mark.parametrize("mode", ["v", "V"])
def test_visual_colon_accepts_empty_document(ex_input_bot, mode):
    editor, status, commandline, qtbot, _, _ = ex_input_bot
    editor.set_text("")
    status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(commandline, mode + ":")
    assert commandline.text() == ":1,1"
    assert status.is_normal()


@pytest.mark.parametrize("key", [Qt.Key_Return, Qt.Key_Enter])
def test_substitute_ime_final_syllable_executes_once(ex_input_bot, monkeypatch, key):
    """Return flushes the final Korean replacement into one Ex execution."""
    editor, status, commandline, qtbot, _, _ = ex_input_bot
    editor.set_text("aa aa")
    status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(commandline, ":s/aa/")
    QCoreApplication.sendEvent(commandline, QInputMethodEvent("한글", []))
    executor = status.sub_mode
    substitute = Mock(wraps=executor.substitute)
    monkeypatch.setattr(executor, "substitute", substitute)

    def commit():
        event = QInputMethodEvent()
        event.setCommitString("한글")
        QCoreApplication.sendEvent(commandline, event)

    monkeypatch.setattr(QApplication.inputMethod(), "commit", commit)
    qtbot.keyPress(commandline, key)

    substitute.assert_called_once()
    assert editor.toPlainText() == "한글 aa"
    assert commandline.histories["ex"] == ["s/aa/한글"]
    assert commandline.text() == ""
    assert status.is_normal()
    assert status.sub_mode is None
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)


def test_visual_substitute_history_retains_numeric_range(ex_input_bot):
    """History records the visible numeric addresses and replays the same rows."""
    editor, status, commandline, qtbot, _, _ = ex_input_bot
    qtbot.keyClicks(commandline, "Vj:s/a/long/g")
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert editor.toPlainText() == "longlong\nbb\ncc\n"
    assert commandline.histories["ex"] == ["1,2s/a/long/g"]
    qtbot.keyClicks(commandline, ":")
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == ":1,2s/a/long/g"
    qtbot.keyPress(commandline, Qt.Key_Escape)
    assert status.is_normal()
    assert commandline.histories["ex"] == ["1,2s/a/long/g"]


def test_substitute_records_and_replays_noninteractive_macro(ex_input_bot):
    """Ex keys retain their normal macro recording and asynchronous playback."""
    editor, status, commandline, qtbot, widget, _ = ex_input_bot
    qtbot.keyClicks(commandline, "qa:%s/a/long/g")
    qtbot.keyPress(commandline, Qt.Key_Return)
    qtbot.keyClicks(commandline, "q")
    assert not status.is_recording_macro()
    assert editor.toPlainText() == "longlong\nbb\ncc\n"
    assert "".join(key.text for key in status.manager_macro.registers["a"]) == (
        ":%s/a/long/g\r"
    )
    editor.set_text("a a")
    status.cursor.set_cursor_pos(0)

    qtbot.keyClicks(commandline, "@a")
    qtbot.waitUntil(lambda: not widget.is_playing_macro)

    assert editor.toPlainText() == "long long"
    assert commandline.text() == ""
    assert status.sub_mode is None


def test_file_switch_cancels_pending_substitute_and_ime(ex_input_bot, vim_bot):
    """An unfinished Ex command and a late IME commit cannot cross documents."""
    editor, status, commandline, qtbot, _, stack = ex_input_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, "Vj:s/a/long/g")
    executor = status.sub_mode
    stack.set_stack_index(1)
    vim_bot[3]._on_editor_focus_changed()
    other = stack.get_current_editor()
    other_original = other.toPlainText()
    event = QInputMethodEvent()
    event.setCommitString("x")
    QCoreApplication.sendEvent(commandline, event)

    assert commandline.text() == ""
    assert status.sub_mode is None
    assert executor.pending_range_text is None
    assert status.is_normal()
    assert editor.toPlainText() == original
    assert other.toPlainText() == other_original
    assert commandline.histories["ex"] == []


@pytest.fixture
def pending_command(vim_bot, monkeypatch):
    widget = vim_bot[3].vim_cmd
    executor = SimpleNamespace(
        hint_prefix="x",
        get_hint_candidates=Mock(side_effect=AssertionError("read before display")),
    )
    monkeypatch.setattr(widget.vim_status, "sub_mode", executor)
    monkeypatch.setattr(widget.vim_status, "vim_state", VimState.NORMAL)
    monkeypatch.setattr(widget.vim_status, "running_dot_cmd", False)
    monkeypatch.setattr(widget, "_macro_generation", -1)
    monkeypatch.setattr(widget.which_key, "enabled", False)
    widget.which_key.cancel()
    return widget, executor


def test_pending_hint_is_an_executor_independent_snapshot(pending_command):
    widget, executor = pending_command
    pending = widget.pending_hint()
    assert pending.executor is executor
    assert pending.editor() is widget.vim_status.get_editor()
    assert pending.mode == VimState.NORMAL
    assert pending.prefix == "x"

    # A configurable executor can change its prefix without changing identity.
    executor.hint_prefix = "y"
    updated = widget.pending_hint()
    assert updated != pending
    assert updated.prefix == "y"
    assert pending.prefix == "x"
    executor.get_hint_candidates.assert_not_called()


def test_nested_input_exception_releases_the_outer_boundary(pending_command):
    widget, _ = pending_command
    observations = []

    def started():
        observations.append(
            ("start", widget.is_processing_input, widget.pending_hint())
        )

    def finished():
        observations.append(
            ("finish", widget.is_processing_input, widget.pending_hint())
        )

    widget.sig_input_started.connect(started)
    widget.sig_input_finished.connect(finished)
    try:
        with pytest.raises(ValueError, match="dispatch failed"):
            with widget.input_processing():
                with widget.input_processing():
                    raise ValueError("dispatch failed")
        assert [entry[0] for entry in observations] == ["start", "finish"]
        assert observations[0][1:] == (True, None)
        assert observations[1][1] is False
        assert observations[1][2] == widget.pending_hint()

        # A failed command must not suppress the next input's observations.
        observations.clear()
        with widget.input_processing():
            assert widget.pending_hint() is None
        assert [entry[0] for entry in observations] == ["start", "finish"]
        assert not widget.is_processing_input
    finally:
        widget.sig_input_started.disconnect(started)
        widget.sig_input_finished.disconnect(finished)
