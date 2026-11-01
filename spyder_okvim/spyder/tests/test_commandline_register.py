"""Register insertion edits a prompt without invoking document shortcuts."""

# Standard Libraries
import sys
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QFocusEvent, QInputMethodEvent, QKeyEvent
from qtpy.QtWidgets import QApplication

# Project Libraries
from spyder_okvim.utils.qtcompat import qt_cursor_position
from spyder_okvim.vim.state import VimState
from tests.commandline_support import history_popup  # noqa: F401


def select_register(state, name="a"):
    state.qtbot.keyPress(state.line, Qt.Key_R, Qt.ControlModifier)
    state.qtbot.keyClicks(state.line, name)


@pytest.mark.parametrize("prefix", ["/", "?", ":", "d/", "v/", "V:"])
def test_insert_register_at_unicode_prompt_cursor(history_popup, monkeypatch, prefix):
    state = history_popup
    redo = Mock()
    monkeypatch.setitem(state.line.dispatcher, Qt.Key_R, redo)
    state.status.set_register("a", "한😀", VimState.NORMAL)
    state.qtbot.keyClicks(state.line, prefix)
    prompt = state.line.text()
    state.line.setText(prompt + "ab😀cd")
    state.line.setCursorPosition(qt_cursor_position(state.line.text(), len(prompt) + 2))
    original = state.editor.toPlainText()
    session = state.status.sub_mode

    select_register(state)

    assert state.line.text() == prompt + "ab한😀😀cd"
    assert state.line.snapshot().cursor == len(prompt) + 4
    assert state.status.sub_mode is session
    assert state.line.testAttribute(Qt.WA_InputMethodEnabled)
    assert state.editor.toPlainText() == original
    redo.assert_not_called()


def test_register_insertion_replaces_selection_and_resets_navigation(history_popup):
    state = history_popup
    state.status.set_register("a", "XYZ", VimState.NORMAL)
    state.qtbot.keyClicks(state.line, ":")
    state.line.setText(":e abc.txt")
    state.line.setSelection(3, 3)
    state.line._history_index = 1
    state.line._history_draft = (":e previous", 4)

    select_register(state)

    assert state.line.text() == ":e XYZ.txt"
    assert state.line.cursorPosition() == 6
    assert state.line._history_index is None
    assert state.line._history_draft is None
    assert state.line.completion_result is None


@pytest.mark.parametrize("name", ['"', "0", "-", "A", "+", "_"])
def test_insert_supported_registers(history_popup, name):
    state = history_popup
    value = "" if name == "_" else "value"
    if name == "+":
        QApplication.clipboard().setText(value)
    elif name != "_":
        state.status.set_register(name.lower(), value, VimState.NORMAL)
    state.qtbot.keyClicks(state.line, ":")
    state.line.setText(":e ")

    select_register(state, name)

    assert state.line.text() == ":e " + value
    assert state.line.testAttribute(Qt.WA_InputMethodEnabled)


def test_empty_and_invalid_register_do_not_insert_or_submit(history_popup):
    state = history_popup
    state.qtbot.keyClicks(state.line, ":")
    state.line.setText(":e draft")
    session = state.status.sub_mode

    select_register(state, "z")
    assert state.line.text() == ":e draft"
    select_register(state, "!")
    assert state.line.text() == ":e draft"
    assert "Invalid register" in state.status.msg_label.text()
    assert state.status.sub_mode is session


@pytest.mark.parametrize("content", ["first\nsecond\n", "first\r\nsecond\r"])
def test_multiline_clipboard_is_text_not_prompt_submission(history_popup, content):
    state = history_popup
    QApplication.clipboard().setText(content)
    state.qtbot.keyClicks(state.line, ":")
    state.line.setText(":e ")
    session = state.status.sub_mode
    original = state.editor.toPlainText()

    select_register(state, "+")

    assert state.line.text() == ":e first\nsecond\n"
    assert state.status.sub_mode is session
    assert state.editor.toPlainText() == original


@pytest.mark.parametrize(
    "key, modifiers", [(Qt.Key_Escape, Qt.NoModifier), (Qt.Key_C, Qt.ControlModifier)]
)
def test_cancelling_pending_register_does_not_leak_to_next_prompt(
    history_popup, key, modifiers
):
    state = history_popup
    state.qtbot.keyClicks(state.line, "/")
    state.qtbot.keyPress(state.line, Qt.Key_R, Qt.ControlModifier)
    state.qtbot.keyPress(state.line, key, modifiers)
    assert state.status.sub_mode is None

    state.qtbot.keyClicks(state.line, "/a")

    assert state.line.text() == "/a"
    assert state.line.testAttribute(Qt.WA_InputMethodEnabled)


def test_pending_selector_bypasses_popup_and_global_shortcuts(history_popup):
    state = history_popup
    state.line.histories["ex"][:] = ["e first", "e second"]
    state.qtbot.keyClicks(state.line, ":")
    state.qtbot.keyPress(state.line, Qt.Key_N, Qt.ControlModifier)
    state.qtbot.keyPress(state.line, Qt.Key_R, Qt.ControlModifier)
    original = state.line.text()
    session = state.status.sub_mode
    event = QKeyEvent(QEvent.ShortcutOverride, Qt.Key_Return, Qt.NoModifier)

    assert state.line.event(event)
    assert event.isAccepted()
    state.qtbot.keyPress(state.line, Qt.Key_Return)

    assert state.line.text() == original
    assert state.status.sub_mode is session
    assert state.line.testAttribute(Qt.WA_InputMethodEnabled)


def test_register_selector_hides_popup_until_prompt_edit_resumes(history_popup):
    state = history_popup
    state.line.histories["ex"][:] = ["e first", "e second"]
    state.qtbot.keyClicks(state.line, ":")
    assert state.controller.popup.isVisible()

    state.qtbot.keyPress(state.line, Qt.Key_R, Qt.ControlModifier)

    assert state.line.snapshot() is None
    assert not state.controller.popup.isVisible()
    state.qtbot.keyClicks(state.line, "z")
    assert state.line.snapshot() is not None


def test_cancelled_selector_key_cannot_become_normal_edit(history_popup):
    state = history_popup
    state.qtbot.keyClicks(state.line, "/")
    state.qtbot.keyPress(state.line, Qt.Key_R, Qt.ControlModifier)
    original = state.editor.toPlainText()

    def cancel():
        state.line.esc_pressed()

    state.widget.sig_input_started.connect(cancel)
    try:
        state.qtbot.keyClicks(state.line, "x")
    finally:
        state.widget.sig_input_started.disconnect(cancel)

    assert state.editor.toPlainText() == original
    assert state.status.sub_mode is None
    assert state.line.text() == ""


def test_cancelled_prompt_ctrl_r_cannot_become_document_redo(
    history_popup, monkeypatch
):
    state = history_popup
    redo = Mock()
    monkeypatch.setitem(state.line.dispatcher, Qt.Key_R, redo)
    state.qtbot.keyClicks(state.line, "/")

    def cancel():
        state.line.esc_pressed()

    state.widget.sig_input_started.connect(cancel)
    try:
        # Send only the semantic key so a modifier-only event cannot cancel first.
        event = QKeyEvent(QEvent.KeyPress, Qt.Key_R, Qt.ControlModifier, "\x12")
        state.line.keyPressEvent(event)
    finally:
        state.widget.sig_input_started.disconnect(cancel)

    redo.assert_not_called()
    assert state.status.sub_mode is None


@pytest.mark.skipif(sys.platform != "darwin", reason="Cocoa native virtual keys")
def test_register_selector_uses_latin_key_with_hangul_input_source(history_popup):
    state = history_popup
    state.status.set_register("a", "값", VimState.NORMAL)
    state.qtbot.keyClicks(state.line, "/")
    state.qtbot.keyPress(state.line, Qt.Key_R, Qt.ControlModifier)
    event = QKeyEvent(QEvent.KeyPress, ord("ㅁ"), Qt.NoModifier, 1, 0x00, 0, "ㅁ")

    state.line.keyPressEvent(event)

    assert state.line.text() == "/값"
    assert state.line.testAttribute(Qt.WA_InputMethodEnabled)


def test_ime_commit_precedes_selector_and_late_commit_is_ignored(
    history_popup, monkeypatch
):
    state = history_popup
    state.status.set_register("a", "값", VimState.NORMAL)
    state.qtbot.keyClicks(state.line, "/")

    def commit():
        event = QInputMethodEvent()
        event.setCommitString("한")
        QCoreApplication.sendEvent(state.line, event)

    monkeypatch.setattr(QApplication.inputMethod(), "commit", commit)
    state.qtbot.keyPress(state.line, Qt.Key_R, Qt.ControlModifier)
    assert state.line.text() == "/한"
    assert not state.line.testAttribute(Qt.WA_InputMethodEnabled)
    late = QInputMethodEvent()
    late.setCommitString("누출")
    QCoreApplication.sendEvent(state.line, late)
    state.qtbot.keyClicks(state.line, "a")

    assert state.line.text() == "/한값"
    assert state.line.testAttribute(Qt.WA_InputMethodEnabled)


def test_focus_loss_cancels_selector_but_preserves_ex_draft(history_popup):
    state = history_popup
    state.qtbot.keyClicks(state.line, ":")
    state.line.setText(":e ")
    state.qtbot.keyPress(state.line, Qt.Key_R, Qt.ControlModifier)

    state.line.focusOutEvent(QFocusEvent(QEvent.FocusOut, Qt.ActiveWindowFocusReason))
    state.qtbot.keyClicks(state.line, "a")

    assert state.line.text() == ":e a"
    assert state.line.testAttribute(Qt.WA_InputMethodEnabled)


def test_macro_records_selector_and_replays_current_register(history_popup):
    state = history_popup
    state.status.set_register("a", "alpha", VimState.NORMAL)
    state.qtbot.keyClicks(state.line, "qb/")
    select_register(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    state.qtbot.keyClicks(state.line, "q")
    keys = state.status.manager_macro.registers["b"]
    assert [key.key_code for key in keys] == [
        Qt.Key_Slash,
        Qt.Key_R,
        Qt.Key_A,
        Qt.Key_Return,
    ]
    assert keys[1].modifiers == Qt.ControlModifier
    assert state.status.search.txt_searched == "alpha"
    state.status.set_register("a", "beta", VimState.NORMAL)

    state.qtbot.keyClicks(state.line, "@b")
    state.qtbot.waitUntil(lambda: not state.widget.is_playing_macro)

    assert state.status.search.txt_searched == "beta"
    assert state.line.text() == ""


def test_normal_ctrl_r_still_redoes_document(history_popup):
    state = history_popup
    original = state.editor.toPlainText()
    state.qtbot.keyClicks(state.line, "x")
    deleted = state.editor.toPlainText()
    state.qtbot.keyClicks(state.line, "u")
    assert state.editor.toPlainText() == original

    state.qtbot.keyPress(state.line, Qt.Key_R, Qt.ControlModifier)

    assert state.editor.toPlainText() == deleted
