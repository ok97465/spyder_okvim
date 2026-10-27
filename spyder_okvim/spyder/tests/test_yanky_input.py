"""Cycle keys share the command line without changing its existing fallbacks."""

from unittest.mock import Mock

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QKeyEvent
from spyder.config.manager import CONF

from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.vim.state import VimState


@pytest.fixture
def yank_input(vim_bot, monkeypatch):
    _, stack, _, vim, bot = vim_bot
    widget = vim.vim_cmd
    widget.cancel_yank_picker()
    stack.set_stack_index(0)
    vim._use_stack(stack)
    line = widget.commandline
    line.setFocus()
    QCoreApplication.processEvents()
    line.esc_pressed()
    status = widget.vim_status
    status.disconnect_from_editor()
    status.reset_for_test()
    editor = status.get_editor()
    editor.set_text("xy")
    status.cursor.set_cursor_pos(0)
    status.yank_history.record("A", "charwise")
    status.yank_history.record("B", "charwise")
    status.set_register('"', "B", VimState.NORMAL)
    search = Mock()
    monkeypatch.setitem(line.dispatcher, Qt.Key_P, search)
    yield widget, editor, status, line, bot, search
    widget.cancel_yank_picker()
    widget.put_controller.cancel()
    widget._macro_generation = -1
    widget._macro_editor = None
    line.esc_pressed()


def test_cycle_keys_consume_boundaries_and_clear_counts(yank_input):
    widget, editor, status, line, bot, search = yank_input
    bot.keyClicks(line, "p3")
    assert widget.put_controller.can_cycle()
    bot.keyPress(line, Qt.Key_P, Qt.ControlModifier)
    assert editor.toPlainText() == "xAy"
    assert line.text() == ""
    assert status.input_cmd.cmd == ""
    bot.keyPress(line, Qt.Key_P, Qt.ControlModifier)
    assert editor.toPlainText() == "xAy"
    bot.keyClicks(line, "2")
    bot.keyPress(line, Qt.Key_N, Qt.ControlModifier)
    assert editor.toPlainText() == "xBy"
    bot.keyPress(line, Qt.Key_N, Qt.ControlModifier)
    search.assert_not_called()
    bot.keyClicks(line, "u")
    assert editor.toPlainText() == "xy"
    bot.keyPress(line, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == "xBy"


def test_single_candidate_reserves_shortcut_without_editing(yank_input):
    widget, editor, status, line, bot, search = yank_input
    status.yank_history.clear()
    bot.keyClicks(line, "p")
    revision = editor.document().revision()
    event = QKeyEvent(QEvent.ShortcutOverride, Qt.Key_P, Qt.ControlModifier)
    event.ignore()
    QCoreApplication.sendEvent(line, event)
    assert event.isAccepted()
    assert editor.document().revision() == revision
    assert widget.put_controller.session.index == 0
    bot.keyPress(line, Qt.Key_P, Qt.ControlModifier)
    assert editor.document().revision() == revision
    search.assert_not_called()


@pytest.mark.parametrize("command", ["h", "0", "z", "d", ":", "/", "v", "i"])
def test_other_input_ends_session(yank_input, command):
    widget, _, _, line, bot, _ = yank_input
    bot.keyClicks(line, "p" + command)
    assert not widget.put_controller.can_cycle()


def test_escape_and_manual_search_keep_original_fallback(yank_input):
    widget, _, _, line, bot, search = yank_input
    bot.keyClicks(line, "p")
    bot.keyPress(line, Qt.Key_Escape)
    assert not widget.put_controller.can_cycle()
    bot.keyPress(line, Qt.Key_P, Qt.ControlModifier)
    search.assert_called_once_with()


def test_macro_without_local_put_never_opens_search(yank_input):
    widget, editor, _, line, bot, search = yank_input
    widget._macro_generation = 1
    bot.keyPress(line, Qt.Key_P, Qt.ControlModifier)
    bot.keyPress(line, Qt.Key_N, Qt.ControlModifier)
    assert editor.toPlainText() == "xy"
    search.assert_not_called()


def test_macro_operator_cycle_key_never_opens_search(yank_input):
    widget, editor, status, line, bot, search = yank_input
    bot.keyClicks(line, "d")
    operator = status.sub_mode
    widget._macro_generation = 1
    bot.keyPress(line, Qt.Key_P, Qt.ControlModifier)
    assert editor.toPlainText() == "xy"
    assert status.sub_mode is operator
    search.assert_not_called()


def test_macro_boundaries_expire_puts(yank_input):
    widget, _, _, line, bot, _ = yank_input
    bot.keyClicks(line, "p")
    widget.cancel_macro()
    assert not widget.put_controller.can_cycle()


def test_settings_disable_and_resize_cancel_sessions(yank_input):
    widget, editor, status, line, bot, _ = yank_input
    previous_enabled = CONF.get(CONF_SECTION, "yanky_enabled")
    previous_length = CONF.get(CONF_SECTION, "yank_history_length")
    try:
        bot.keyClicks(line, "p")
        CONF.set(CONF_SECTION, "yank_history_length", 1)
        widget.apply_settings()
        assert not widget.put_controller.can_cycle()
        assert len(status.yank_history) == 1
        bot.keyClicks(line, "p")
        CONF.set(CONF_SECTION, "yanky_enabled", False)
        widget.apply_settings()
        assert not widget.put_controller.can_cycle()
        old_history = status.yank_history.snapshot()
        bot.keyClicks(line, "yy")
        assert status.yank_history.snapshot() == old_history
        bot.keyClicks(line, "p")
        assert not widget.put_controller.can_cycle()
        assert editor.toPlainText() != "xy"
        widget.clear_yank_history()
        assert len(status.yank_history) == 0
    finally:
        CONF.set(CONF_SECTION, "yanky_enabled", previous_enabled)
        CONF.set(CONF_SECTION, "yank_history_length", previous_length)
        widget.apply_settings()
