"""Regression tests for IME input in search and Ex command lines."""

# Standard Libraries
import sys

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QInputMethodEvent, QInputMethodQueryEvent, QKeyEvent
from qtpy.QtWidgets import QApplication

# Project Libraries
from spyder_okvim.vim import VimState
from tests.qt_support import reset_vim_state


@pytest.fixture
def commandline_bot(vim_bot):
    """Isolate the shared command line, current editor and focus."""
    _, stack, _, vim, qtbot = vim_bot
    previous_index = stack.get_stack_index()
    commandline = vim.vim_cmd.commandline
    status = vim.vim_cmd.vim_status
    commandline.setFocus()
    QCoreApplication.processEvents()
    commandline.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    reset_vim_state(status)
    editor = stack.get_current_editor()
    editor.set_text("start 한글 target 한글")
    status.cursor.set_cursor_pos(0)
    commandline.clear()
    commandline.setFocus()
    QCoreApplication.processEvents()
    try:
        yield editor, status, commandline, qtbot
    finally:
        commandline.setFocus()
        QCoreApplication.processEvents()
        commandline.esc_pressed()
        status.disconnect_from_editor()
        stack.set_stack_index(previous_index)


def send_input_method(widget, preedit="", commit="", start=0, length=0):
    """Deliver composition updates through the same Qt path as an IME."""
    event = QInputMethodEvent(preedit, [])
    event.setCommitString(commit, start, length)
    QCoreApplication.sendEvent(widget, event)


@pytest.fixture(params=["latin", "hangul", "ime_char_qt5", "ime_char_qt6"])
def windows_key_event(request):
    """Cover key-down and standalone IME character paths in Windows Qt."""

    def create(text, scan_code):
        hangul = {"h": "ㅗ", "j": "ㅓ", "k": "ㅏ", "l": "ㅣ", "a": "ㅁ", "i": "ㅑ"}[
            text
        ]
        key, virtual_key, event_text = {
            "latin": (ord(text.upper()), ord(text.upper()), text),
            "hangul": (ord(text.upper()), ord(text.upper()), hangul),
            "ime_char_qt5": (0, ord(hangul), hangul),
            "ime_char_qt6": (0, 0, hangul),
        }[request.param]
        return QKeyEvent(
            QEvent.KeyPress, key, Qt.NoModifier, scan_code, virtual_key, 0, event_text
        )

    return create


@pytest.mark.parametrize("command", ["/", ":", "v/", "V/", "v:", "V:", "d/"])
def test_ime_enabled_only_while_entering_text(commandline_bot, command):
    """Search and Ex accept composition in each existing calling mode."""
    _, status, commandline, qtbot = commandline_bot
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)

    qtbot.keyClicks(commandline, command)

    assert commandline.testAttribute(Qt.WA_InputMethodEnabled)
    qtbot.keyPress(commandline, Qt.Key_Escape)
    assert status.sub_mode is None
    assert commandline.text() == ""
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)


@pytest.mark.parametrize("command", ["f", "r", "g", "d"])
def test_command_submodes_do_not_accept_ime(commandline_bot, command):
    """Single-key arguments and pending operators keep Normal key handling."""
    editor, _, commandline, qtbot = commandline_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, command)
    pending = commandline.text()

    send_input_method(commandline, preedit="ㅎ", commit="한")

    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)
    assert commandline.text() == pending
    assert editor.toPlainText() == original


@pytest.mark.parametrize("prefix", ["/", ":"])
def test_native_input_method_queries_follow_command_mode(commandline_bot, prefix):
    """Qt's native context must see ImEnabled=False outside text entry."""
    _, _, commandline, qtbot = commandline_bot

    def query_input_method():
        event = QInputMethodQueryEvent(
            Qt.ImEnabled | Qt.ImSurroundingText | Qt.ImCursorPosition
        )
        QCoreApplication.sendEvent(commandline, event)
        return event

    assert not query_input_method().value(Qt.ImEnabled)
    qtbot.keyClicks(commandline, prefix)
    send_input_method(commandline, commit="한글")

    query = query_input_method()
    assert query.value(Qt.ImEnabled)
    assert query.value(Qt.ImSurroundingText) == prefix + "한글"
    assert query.value(Qt.ImCursorPosition) == len(prefix + "한글")

    qtbot.keyPress(commandline, Qt.Key_Escape)
    assert not query_input_method().value(Qt.ImEnabled)


@pytest.mark.parametrize("prefix", ["/", ":"])
def test_preedit_and_committed_replacement(commandline_bot, prefix):
    """Preedit stays out of commands and committed Korean text is editable."""
    editor, status, commandline, qtbot = commandline_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, prefix)

    send_input_method(commandline, preedit="ㅎ")
    send_input_method(commandline, preedit="한")
    assert commandline.text() == prefix
    assert status.search.txt_searched == ""

    send_input_method(commandline, commit="한글")
    assert commandline.text() == prefix + "한글"
    send_input_method(commandline, commit="국", start=-1, length=1)
    assert commandline.text() == prefix + "한국"
    assert editor.toPlainText() == original


@pytest.mark.parametrize("key", [Qt.Key_Return, Qt.Key_Enter])
def test_enter_commits_final_search_syllable(commandline_bot, monkeypatch, key):
    """Enter includes a pending syllable before executing the search."""
    editor, status, commandline, qtbot = commandline_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, "/")
    send_input_method(commandline, preedit="한글")
    commits = []

    def commit():
        commits.append(True)
        send_input_method(commandline, commit="한글")

    monkeypatch.setattr(QApplication.inputMethod(), "commit", commit)
    qtbot.keyPress(commandline, key)

    assert commits == [True]
    assert status.search.txt_searched == "한글"
    assert editor.textCursor().position() == original.index("한글")
    assert status.sub_mode is None
    assert status.is_normal()
    assert commandline.text() == ""
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)

    send_input_method(commandline, commit="x")
    qtbot.keyClicks(commandline, "h")
    assert editor.textCursor().position() == original.index("한글") - 1
    assert editor.toPlainText() == original


def test_enter_commits_korean_ex_argument(commandline_bot, monkeypatch):
    """A Korean command argument reaches its Ex command in full."""
    _, status, commandline, qtbot = commandline_bot
    qtbot.keyClicks(commandline, ":w ")
    send_input_method(commandline, preedit="한글.py")
    arguments = []
    monkeypatch.setattr(status.sub_mode, "w", arguments.append)
    monkeypatch.setattr(
        QApplication.inputMethod(),
        "commit",
        lambda: send_input_method(commandline, commit="한글.py"),
    )

    qtbot.keyPress(commandline, Qt.Key_Return)

    assert arguments == ["한글.py"]
    assert status.sub_mode is None
    assert commandline.text() == ""
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)


@pytest.mark.parametrize("prefix", ["/", ":"])
def test_escape_discards_composition_and_late_commit(
    commandline_bot, monkeypatch, prefix
):
    """Canceling composition cannot leak a later commit into Normal commands."""
    editor, status, commandline, qtbot = commandline_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, prefix)
    send_input_method(commandline, preedit="한")
    resets = []

    def reset():
        resets.append(True)
        send_input_method(commandline, commit="x")

    monkeypatch.setattr(QApplication.inputMethod(), "reset", reset)
    qtbot.keyPress(commandline, Qt.Key_Escape)
    assert resets

    send_input_method(commandline, commit="x")
    qtbot.keyClicks(commandline, "l")

    assert status.sub_mode is None
    assert status.is_normal()
    assert commandline.text() == ""
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)
    assert editor.textCursor().position() == 1
    assert editor.toPlainText() == original


@pytest.mark.parametrize("prefix", ["/", ":"])
def test_native_editing_uses_commandline_cursor(commandline_bot, prefix):
    """Spaces, deletion and selection replacement respect the edit position."""
    _, _, commandline, qtbot = commandline_bot
    qtbot.keyClicks(commandline, prefix)
    send_input_method(commandline, commit="한글")
    qtbot.keyPress(commandline, Qt.Key_Left)
    qtbot.keyPress(commandline, Qt.Key_Space)
    assert commandline.text() == prefix + "한 글"

    qtbot.keyPress(commandline, Qt.Key_Backspace)
    assert commandline.text() == prefix + "한글"
    qtbot.keyPress(commandline, Qt.Key_Delete)
    assert commandline.text() == prefix + "한"

    commandline.setSelection(1, 1)
    send_input_method(commandline, commit="한국어")
    assert commandline.text() == prefix + "한국어"


@pytest.mark.parametrize("prefix", ["/", ":"])
def test_backspace_empty_command_exits_input_mode(commandline_bot, prefix):
    """Deleting the initial prompt restores Normal input handling."""
    _, status, commandline, qtbot = commandline_bot
    qtbot.keyClicks(commandline, prefix)

    qtbot.keyPress(commandline, Qt.Key_Backspace)

    assert commandline.text() == ""
    assert status.sub_mode is None
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)


def test_insert_editor_still_accepts_composition(commandline_bot):
    """Command-line IME handling leaves the editor's Insert path intact."""
    editor, status, commandline, qtbot = commandline_bot
    editor.set_text("target")
    status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(commandline, "i")
    assert QApplication.focusWidget() is editor

    send_input_method(editor, preedit="ㅎ")
    send_input_method(editor, preedit="한")
    assert editor.toPlainText() == "target"
    send_input_method(editor, commit="한글")
    assert editor.toPlainText() == "한글target"

    commandline.setFocus()
    QCoreApplication.processEvents()

    assert status.is_normal()
    assert commandline.text() == ""
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)
    qtbot.keyClicks(commandline, "l")
    assert editor.toPlainText() == "한글target"


@pytest.mark.parametrize(
    "command, expected_state", [("v", VimState.VISUAL), ("V", VimState.VLINE)]
)
def test_korean_search_preserves_visual_selection(
    commandline_bot, command, expected_state
):
    """Completing an IME search extends the existing Visual selection."""
    editor, status, commandline, qtbot = commandline_bot
    text = "start\n한글 target\nend"
    editor.set_text(text)
    status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(commandline, command + "/")
    send_input_method(commandline, preedit="ㅎ")
    send_input_method(commandline, commit="한글")

    qtbot.keyPress(commandline, Qt.Key_Return)

    assert status.vim_state == expected_state
    assert status.is_visual_mode
    assert status.sub_mode is None
    assert commandline.text() == ""
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)
    assert editor.textCursor().position() == text.index("한글")
    selections = editor.get_extra_selections("vim_selection")
    assert len(selections) == 1
    selection = selections[0].cursor
    assert selection.selectionStart() == 0
    expected_end = text.index("한글") + 1 if command == "v" else text.index("\nend")
    assert selection.selectionEnd() == expected_end


@pytest.mark.parametrize("prefix", ["/", ":"])
@pytest.mark.parametrize("key", [Qt.Key_A, Qt.Key_X])
def test_number_shortcuts_cancel_commandline_input(commandline_bot, prefix, key):
    """The existing number shortcuts cancel pending text before Normal input."""
    editor, status, commandline, qtbot = commandline_bot
    editor.set_text(" -2a")
    status.cursor.set_cursor_pos(1)
    qtbot.keyClicks(commandline, prefix)
    send_input_method(commandline, preedit="한")

    qtbot.keyPress(commandline, key, Qt.ControlModifier)

    assert status.sub_mode is None
    assert status.is_normal()
    assert commandline.text() == ""
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)
    assert editor.toPlainText() == " -2a"
    assert editor.textCursor().position() == 1
    qtbot.keyClicks(commandline, "l")
    assert editor.textCursor().position() == 2
    assert editor.toPlainText() == " -2a"


@pytest.mark.skipif(sys.platform != "darwin", reason="Cocoa native virtual keys")
@pytest.mark.parametrize(
    "text, virtual_key, expected_position", [("ㅗ", 0x04, 0), ("ㅓ", 0x26, 6)]
)
def test_korean_native_keys_execute_normal_motions(
    commandline_bot, text, virtual_key, expected_position
):
    """Korean input remains active while physical h/j run Normal motions."""
    editor, status, commandline, _ = commandline_bot
    original = "abcd\nefgh\nijkl"
    editor.set_text(original)
    status.cursor.set_cursor_pos(1)
    event = QKeyEvent(
        QEvent.KeyPress, ord(text), Qt.NoModifier, 1, virtual_key, 0, text
    )

    commandline.keyPressEvent(event)

    assert editor.textCursor().position() == expected_position
    assert editor.toPlainText() == original
    assert commandline.text() == ""
    assert status.is_normal()


@pytest.mark.skipif(sys.platform != "darwin", reason="Cocoa native virtual keys")
@pytest.mark.parametrize(
    "text, virtual_key, command, position",
    [("ㅁ", 0x00, "a", 2), ("ㅑ", 0x22, "i", 1)],
)
def test_korean_native_keys_can_enter_insert(
    commandline_bot, text, virtual_key, command, position
):
    """Native virtual key zero is A, and mapped Insert keeps editor IME."""
    editor, status, commandline, _ = commandline_bot
    editor.set_text("abcd")
    status.cursor.set_cursor_pos(1)
    event = QKeyEvent(
        QEvent.KeyPress, ord(text), Qt.NoModifier, 1, virtual_key, 0, text
    )

    commandline.keyPressEvent(event)

    assert QApplication.focusWidget() is editor
    assert status.insert_cmd.command == command
    assert editor.textCursor().position() == position
    send_input_method(editor, preedit="ㅎ")
    send_input_method(editor, commit="한")
    assert editor.toPlainText() == "abcd"[:position] + "한" + "abcd"[position:]


@pytest.mark.skipif(sys.platform != "darwin", reason="Cocoa native virtual keys")
@pytest.mark.parametrize("prefix", ["/", ":"])
def test_korean_native_keys_stay_text_in_commandline(commandline_bot, prefix):
    """Search/Ex typing and subsequent preedit bypass Normal key mapping."""
    _, _, commandline, qtbot = commandline_bot
    qtbot.keyClicks(commandline, prefix)
    event = QKeyEvent(QEvent.KeyPress, ord("ㅗ"), Qt.NoModifier, 1, 0x04, 0, "ㅗ")

    commandline.keyPressEvent(event)
    send_input_method(commandline, preedit="한")
    assert commandline.text() == prefix + "ㅗ"
    send_input_method(commandline, commit="글")
    assert commandline.text() == prefix + "ㅗ글"


@pytest.mark.skipif(sys.platform != "darwin", reason="Cocoa native virtual keys")
@pytest.mark.parametrize(
    "modifiers, expected_text", [(Qt.NoModifier, "h"), (Qt.ShiftModifier, "H")]
)
def test_macro_records_mapped_korean_native_keys(
    commandline_bot, modifiers, expected_text
):
    """Record the translated key so playback needs no native key metadata."""
    editor, status, commandline, _ = commandline_bot
    editor.set_text("abcd")
    status.cursor.set_cursor_pos(2)
    manager = status.manager_macro
    manager.start_record("a")
    event = QKeyEvent(QEvent.KeyPress, ord("ㅗ"), modifiers, 1, 0x04, 0, "ㅗ")

    commandline.keyPressEvent(event)

    recorded = manager.registers["a"]
    assert len(recorded) == 1
    assert recorded[0].key_code == Qt.Key_H
    assert recorded[0].text == expected_text
    assert recorded[0].modifiers == modifiers
    manager.stop_record()
    if expected_text == "h":
        assert editor.textCursor().position() == 1
        commandline.keyPressEvent(recorded[0].to_event())
        assert editor.textCursor().position() == 0


@pytest.mark.skipif(sys.platform != "darwin", reason="Cocoa native virtual keys")
def test_synthetic_korean_keys_keep_their_original_text(commandline_bot):
    """Events without native scan information cannot be assumed to be QWERTY."""
    _, status, commandline, _ = commandline_bot
    manager = status.manager_macro
    manager.start_record("a")
    event = QKeyEvent(QEvent.KeyPress, ord("ㅗ"), Qt.NoModifier, 0, 0x04, 0, "ㅗ")

    commandline.keyPressEvent(event)

    assert manager.registers["a"][0].text == "ㅗ"
    manager.stop_record()


@pytest.mark.parametrize("prefix", ["/", ":w "])
def test_commit_and_next_preedit_in_one_event(commandline_bot, monkeypatch, prefix):
    """Windows composition rollover exposes each committed syllable once."""
    editor, status, commandline, qtbot = commandline_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, prefix)

    send_input_method(commandline, preedit="ㅎ")
    send_input_method(commandline, commit="한", preedit="ㄱ")
    assert commandline.text() == prefix + "한"
    send_input_method(commandline, preedit="글")
    assert commandline.text() == prefix + "한"
    assert status.search.txt_searched == ""
    send_input_method(commandline, commit="글")
    assert commandline.text() == prefix + "한글"

    arguments = []
    if prefix == ":w ":
        monkeypatch.setattr(status.sub_mode, "w", arguments.append)
    qtbot.keyPress(commandline, Qt.Key_Return)

    if prefix == "/":
        assert status.search.txt_searched == "한글"
        assert editor.textCursor().position() == original.index("한글")
    else:
        assert arguments == ["한글"]
    assert status.sub_mode is None
    assert commandline.text() == ""
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)
    assert editor.toPlainText() == original


@pytest.mark.parametrize("prefix", ["/", ":"])
def test_focus_loss_cancels_composition(commandline_bot, prefix):
    """A late commit after focus returns cannot become a Normal command."""
    editor, status, commandline, qtbot = commandline_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, prefix)
    send_input_method(commandline, preedit="한")

    editor.setFocus()
    QCoreApplication.processEvents()
    assert QApplication.focusWidget() is editor
    assert status.sub_mode is None
    assert commandline.text() == ""
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)

    commandline.setFocus()
    QCoreApplication.processEvents()
    send_input_method(commandline, commit="x")
    qtbot.keyClicks(commandline, "l")

    assert status.is_normal()
    assert editor.textCursor().position() == 1
    assert editor.toPlainText() == original
    assert commandline.text() == ""


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native virtual keys")
@pytest.mark.parametrize(
    "text, scan_code, expected_position",
    [("h", 0x23, 5), ("j", 0x24, 11), ("k", 0x25, 1), ("l", 0x26, 7)],
)
def test_windows_native_keys_execute_normal_motions(
    commandline_bot, windows_key_event, text, scan_code, expected_position
):
    """Windows Hangul character events still execute physical Vim motions."""
    editor, status, commandline, _ = commandline_bot
    original = "abcd\nefgh\nijkl"
    editor.set_text(original)
    status.cursor.set_cursor_pos(6)
    event = windows_key_event(text, scan_code)

    QCoreApplication.sendEvent(commandline, event)

    assert editor.textCursor().position() == expected_position
    assert editor.toPlainText() == original
    assert commandline.text() == ""
    assert status.is_normal()
    assert not commandline.testAttribute(Qt.WA_InputMethodEnabled)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native virtual keys")
@pytest.mark.parametrize(
    "command, scan_code, position", [("a", 0x1E, 2), ("i", 0x17, 1)]
)
def test_windows_native_insert_keys_preserve_editor_ime(
    commandline_bot, windows_key_event, command, scan_code, position
):
    """Native a/i switches to the editor, which still accepts Hangul."""
    editor, status, commandline, _ = commandline_bot
    editor.set_text("abcd")
    status.cursor.set_cursor_pos(1)
    event = windows_key_event(command, scan_code)

    QCoreApplication.sendEvent(commandline, event)

    assert QApplication.focusWidget() is editor
    assert status.insert_cmd.command == command
    assert editor.textCursor().position() == position
    send_input_method(editor, preedit="ㅎ")
    send_input_method(editor, commit="한", preedit="ㄱ")
    send_input_method(editor, commit="글")
    assert editor.toPlainText() == "abcd"[:position] + "한글" + "abcd"[position:]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native virtual keys")
def test_windows_native_keys_record_and_replay(commandline_bot, windows_key_event):
    """A Windows key recording works without native metadata on replay."""
    editor, status, commandline, _ = commandline_bot
    editor.set_text("abcd")
    status.cursor.set_cursor_pos(2)
    manager = status.manager_macro
    manager.start_record("a")
    event = windows_key_event("h", 0x23)

    QCoreApplication.sendEvent(commandline, event)

    assert editor.textCursor().position() == 1
    recorded = manager.registers["a"]
    assert len(recorded) == 1
    assert recorded[0].key_code == Qt.Key_H
    assert recorded[0].text == "h"
    manager.stop_record()
    QCoreApplication.sendEvent(commandline, recorded[0].to_event())
    assert editor.textCursor().position() == 0
    assert editor.toPlainText() == "abcd"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native virtual keys")
@pytest.mark.parametrize("prefix", ["/", ":"])
def test_windows_native_keys_stay_text_in_commandline(
    commandline_bot, windows_key_event, prefix
):
    """Physical-key recovery never changes text entered in search or Ex."""
    editor, _, commandline, qtbot = commandline_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, prefix)
    event = windows_key_event("h", 0x23)

    QCoreApplication.sendEvent(commandline, event)

    assert commandline.text() == prefix + event.text()
    assert commandline.testAttribute(Qt.WA_InputMethodEnabled)
    assert editor.toPlainText() == original


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native IME context")
@pytest.mark.parametrize("prefix", ["/", ":"])
@pytest.mark.parametrize("exit_key", [Qt.Key_Escape, Qt.Key_Return, Qt.Key_Backspace])
def test_windows_native_ime_context_follows_command_mode(
    commandline_bot, prefix, exit_key
):
    """The Windows backend associates an IME context only in text modes."""
    if QApplication.platformName() != "windows":
        pytest.skip("Requires QT_QPA_PLATFORM=windows instead of offscreen")

    # Import Windows APIs only on their platform; inspect the top-level HWND
    # used by Qt rather than creating a native child window for the line edit.
    # Standard Libraries
    import ctypes
    from ctypes import wintypes

    _, status, commandline, qtbot = commandline_bot
    window = commandline.window()
    window.raise_()
    window.activateWindow()
    commandline.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusObject() is commandline)
    qtbot.waitUntil(lambda: QApplication.focusWindow() is window.windowHandle())
    imm32 = ctypes.WinDLL("imm32", use_last_error=True)
    imm32.ImmGetContext.argtypes = [wintypes.HWND]
    imm32.ImmGetContext.restype = wintypes.HANDLE
    imm32.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
    imm32.ImmReleaseContext.restype = wintypes.BOOL
    hwnd = int(window.winId())

    def has_ime_context():
        context = imm32.ImmGetContext(hwnd)
        if context:
            imm32.ImmReleaseContext(hwnd, context)
        return bool(context)

    assert not has_ime_context()
    qtbot.keyClicks(commandline, prefix)
    qtbot.waitUntil(has_ime_context)

    qtbot.keyPress(commandline, exit_key)
    qtbot.waitUntil(lambda: not has_ime_context())
    assert status.sub_mode is None
    assert status.is_normal()
    assert commandline.text() == ""
