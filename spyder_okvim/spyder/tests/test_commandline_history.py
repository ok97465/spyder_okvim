"""Regression tests for separate Ex and search command-line histories."""

import json
from unittest.mock import Mock

import pytest
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QInputMethodEvent
from spyder.config.manager import CONF

from spyder_okvim.executor.executor_colon import ExecutorColon
from spyder_okvim.spyder.vim_widgets import VimWidget
from spyder_okvim.utils.commandline_history import load_history, save_history
from spyder_okvim.vim import VimState


@pytest.fixture
def history_bot(vim_bot, tmp_path, monkeypatch):
    """Isolate command history, editor contents, current tab, and focus."""
    _, stack, _, vim, qtbot = vim_bot
    previous_index = stack.get_stack_index()
    commandline = vim.vim_cmd.commandline
    monkeypatch.setattr(
        commandline, "_history_file", tmp_path / "commandline_history.json"
    )
    monkeypatch.setattr(commandline, "_history_dirty", False)
    status = vim.vim_cmd.vim_status
    commandline.setFocus()
    QCoreApplication.processEvents()
    commandline.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    status.reset_for_test()
    editor = stack.get_current_editor()
    original_text = editor.toPlainText()
    editor.set_text("foo x foo x foo")
    status.cursor.set_cursor_pos(0)
    for history in commandline.histories.values():
        history.clear()
    try:
        yield editor, status, commandline, qtbot
    finally:
        commandline.setFocus()
        QCoreApplication.processEvents()
        commandline.esc_pressed()
        status.disconnect_from_editor()
        status.reset_for_test()
        editor.set_text(original_text)
        for history in commandline.histories.values():
            history.clear()
        stack.set_stack_index(previous_index)


def submit(commandline, qtbot, text):
    """Confirm a command through the real line-edit key handling."""
    qtbot.keyClicks(commandline, text)
    qtbot.keyPress(commandline, Qt.Key_Return)


def test_ex_and_search_histories_are_separate(history_bot):
    """Both search directions share words while Ex keeps its own commands."""
    _, _, commandline, qtbot = history_bot
    for text in (":01", "/foo", ":02", "?x"):
        submit(commandline, qtbot, text)

    assert commandline.histories == {"ex": ["01", "02"], "search": ["foo", "x"]}

    qtbot.keyClicks(commandline, "?")
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == "?x"
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == "?foo"
    qtbot.keyPress(commandline, Qt.Key_Escape)

    qtbot.keyClicks(commandline, ":")
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == ":02"


@pytest.mark.parametrize(
    "command, prompt, kind",
    [
        (":", ":", "ex"),
        ("/", "/", "search"),
        ("?", "?", "search"),
        ("2/", "2/", "search"),
        ("d/", "/", "search"),
        ("v/", "/", "search"),
        ("V/", "/", "search"),
    ],
)
def test_history_round_trip_restores_draft_and_cursor(
    history_bot, command, prompt, kind
):
    """Up/Down preserve the active prompt and restore a partially edited draft."""
    _, _, commandline, qtbot = history_bot
    commandline.histories[kind].extend(["old", "new"])
    qtbot.keyClicks(commandline, command + "draft text")
    draft = prompt + "draft text"
    cursor_position = len(prompt) + 3
    commandline.setCursorPosition(cursor_position)

    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == prompt + "new"
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == prompt + "old"
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == prompt + "old"
    qtbot.keyPress(commandline, Qt.Key_Down)
    assert commandline.text() == prompt + "new"
    qtbot.keyPress(commandline, Qt.Key_Down)
    assert commandline.text() == draft
    assert commandline.cursorPosition() == cursor_position
    qtbot.keyPress(commandline, Qt.Key_Down)
    assert commandline.text() == draft
    assert commandline.cursorPosition() == cursor_position


@pytest.mark.parametrize("prefix", [":", "/", "?"])
def test_navigation_without_history_preserves_input(history_bot, prefix):
    """An empty history does not erase text or move its insertion point."""
    _, _, commandline, qtbot = history_bot
    qtbot.keyClicks(commandline, prefix + "draft")
    commandline.setCursorPosition(3)

    qtbot.keyPress(commandline, Qt.Key_Up)
    qtbot.keyPress(commandline, Qt.Key_Down)

    assert commandline.text() == prefix + "draft"
    assert commandline.cursorPosition() == 3


def test_recalled_search_keeps_its_count(history_bot):
    """A history word is searched with the count entered for this command."""
    editor, _, commandline, qtbot = history_bot
    commandline.histories["search"].append("foo")
    qtbot.keyClicks(commandline, "2/")
    qtbot.keyPress(commandline, Qt.Key_Up)
    qtbot.keyPress(commandline, Qt.Key_Return)

    assert editor.textCursor().position() == 12
    assert commandline.histories["search"] == ["foo"]
    assert commandline.text() == ""


def test_recalled_search_executes_pending_delete(history_bot):
    """History navigation previews text without executing an operator early."""
    editor, status, commandline, qtbot = history_bot
    original = editor.toPlainText()
    commandline.histories["search"].append("foo")
    qtbot.keyClicks(commandline, "d/")
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert editor.toPlainText() == original

    qtbot.keyPress(commandline, Qt.Key_Return)

    assert editor.toPlainText() == "foo x foo"
    assert status.register_dict['"'].content == "foo x "
    assert commandline.histories["search"] == ["foo"]


@pytest.mark.parametrize("mode, state", [("v", VimState.VISUAL), ("V", VimState.VLINE)])
def test_recalled_search_extends_visual_selection(history_bot, mode, state):
    """A history selection retains the Visual mode that started the search."""
    editor, status, commandline, qtbot = history_bot
    commandline.histories["search"].append("foo")
    qtbot.keyClicks(commandline, mode + "/")
    qtbot.keyPress(commandline, Qt.Key_Up)
    qtbot.keyPress(commandline, Qt.Key_Return)

    assert status.vim_state == state
    assert status.is_visual_mode
    assert editor.textCursor().position() == 6
    selections = editor.get_extra_selections("vim_selection")
    assert len(selections) == 1
    assert selections[0].cursor.selectionStart() == 0
    assert selections[0].cursor.selectionEnd() > 6


@pytest.mark.parametrize("prefix, kind", [(":", "ex"), ("/", "search")])
@pytest.mark.parametrize("cancel", ["escape", "focus_loss"])
def test_new_session_does_not_restore_a_cancelled_draft(
    history_bot, prefix, kind, cancel
):
    """Cancellation drops navigation state without adding the unfinished input."""
    editor, status, commandline, qtbot = history_bot
    commandline.histories[kind].append("old")
    qtbot.keyClicks(commandline, prefix + "cancelled draft")
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == prefix + "old"
    if cancel == "escape":
        qtbot.keyPress(commandline, Qt.Key_Escape)
    else:
        editor.setFocus()
        QCoreApplication.processEvents()
        assert status.sub_mode is None
        commandline.setFocus()
        QCoreApplication.processEvents()

    assert commandline.text() == ""
    assert commandline.histories[kind] == ["old"]
    assert not commandline._history_file.exists()
    qtbot.keyClicks(commandline, prefix + "fresh draft")
    qtbot.keyPress(commandline, Qt.Key_Down)
    assert commandline.text() == prefix + "fresh draft"
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == prefix + "old"
    qtbot.keyPress(commandline, Qt.Key_Down)
    assert commandline.text() == prefix + "fresh draft"


@pytest.mark.parametrize(
    "commands, kind, expected",
    [
        ([":01", ":01", ":02", ":01"], "ex", ["01", "02", "01"]),
        (["/foo", "?foo", "/x", "/foo"], "search", ["foo", "x", "foo"]),
    ],
)
def test_only_adjacent_duplicate_entries_are_removed(
    history_bot, commands, kind, expected
):
    """Repeating one entry is quiet while later reuses remain in sequence."""
    _, _, commandline, qtbot = history_bot
    for command in commands:
        submit(commandline, qtbot, command)

    assert commandline.histories[kind] == expected
    assert load_history(commandline._history_file) == commandline.histories


@pytest.mark.parametrize(
    "text, method", [(":02", None), (":marks", "marks"), ("/foo", None)]
)
def test_saved_duplicate_does_not_write_again(history_bot, monkeypatch, text, method):
    """Repeated confirmed input does not rewrite an unchanged history file."""
    _, _, commandline, qtbot = history_bot
    save = Mock(wraps=save_history)
    monkeypatch.setattr("spyder_okvim.spyder.vim_widgets.save_history", save)
    if method is not None:
        monkeypatch.setattr(ExecutorColon, method, Mock())

    submit(commandline, qtbot, text)
    submit(commandline, qtbot, text)

    save.assert_called_once()
    kind = "ex" if text.startswith(":") else "search"
    assert commandline.histories[kind] == [text[1:]]
    assert load_history(commandline._history_file) == commandline.histories


@pytest.mark.parametrize("entry", ["02\r", "02\n"])
def test_damaged_history_cannot_execute_on_recall(history_bot, entry):
    """Restored single-line entries wait for Enter before executing."""
    editor, status, commandline, qtbot = history_bot
    editor.set_text("one\ntwo")
    status.cursor.set_cursor_pos(0)
    commandline._history_file.write_text(
        json.dumps({"ex": ["01", entry]}), encoding="utf-8"
    )
    commandline.histories = load_history(commandline._history_file)

    qtbot.keyClicks(commandline, ":")
    qtbot.keyPress(commandline, Qt.Key_Up)

    assert commandline.text() == ":01"
    assert editor.textCursor().position() == 0
    assert status.sub_mode is not None


@pytest.mark.parametrize("command", [":", ":   ", "/", "?"])
def test_empty_commands_do_not_create_history(history_bot, command):
    """Blank Ex input and searches without a pattern exit without history."""
    _, status, commandline, qtbot = history_bot
    submit(commandline, qtbot, command)

    assert commandline.histories == {"ex": [], "search": []}
    assert status.sub_mode is None
    assert commandline.text() == ""
    assert not commandline._history_file.exists()


@pytest.mark.parametrize(
    "body",
    ["w", "q", "e", "s", "&", "~", "2", "한", "😀", "  w", "w  ", " \tw\t "],
)
def test_one_character_ex_inputs_do_not_change_or_save_history(
    history_bot, monkeypatch, body
):
    """A one-character body leaves existing memory and saved history intact."""
    _, _, commandline, qtbot = history_bot
    commandline.histories = {"ex": ["e notes.py"], "search": ["foo"]}
    assert save_history(commandline._history_file, commandline.histories)
    original = commandline._history_file.read_bytes()
    save = Mock(
        side_effect=AssertionError("one-character command attempted a history save")
    )
    monkeypatch.setattr("spyder_okvim.spyder.vim_widgets.save_history", save)
    qtbot.keyClicks(commandline, ":")

    commandline.remember_command(":" + body)

    assert commandline.histories == {"ex": ["e notes.py"], "search": ["foo"]}
    assert commandline._history_file.read_bytes() == original
    assert not commandline._history_dirty
    save.assert_not_called()


@pytest.mark.parametrize(
    "command, method",
    [
        (":w", "w"),
        (":q", "q"),
        (":e", "e"),
    ],
)
def test_one_character_ex_commands_still_execute_without_creating_history(
    history_bot, monkeypatch, command, method
):
    """Skipping persistence does not prevent the confirmed command dispatch."""
    _, status, commandline, qtbot = history_bot
    execute = Mock()
    monkeypatch.setattr(ExecutorColon, method, execute)
    save = Mock(
        side_effect=AssertionError("one-character command attempted a history save")
    )
    monkeypatch.setattr("spyder_okvim.spyder.vim_widgets.save_history", save)

    submit(commandline, qtbot, command)

    execute.assert_called_once_with("")
    assert commandline.histories == {"ex": [], "search": []}
    assert not commandline._history_file.exists()
    assert not commandline._history_dirty
    assert commandline.text() == ""
    assert status.sub_mode is None
    save.assert_not_called()


def test_one_character_line_address_executes_without_history(history_bot):
    """Numeric addresses follow the same length rule without losing motion."""
    editor, status, commandline, qtbot = history_bot
    editor.set_text("one\ntwo")
    status.cursor.set_cursor_pos(0)

    submit(commandline, qtbot, ":2")

    assert editor.textCursor().position() == 4
    assert commandline.histories == {"ex": [], "search": []}
    assert not commandline._history_file.exists()
    assert status.sub_mode is None


@pytest.mark.parametrize(
    "command, method", [(":q!", "qexclamation"), (":wq", "wq"), (":marks", "marks")]
)
def test_multiple_character_commands_execute_and_are_saved(
    history_bot, monkeypatch, command, method
):
    """Argument-free commands with multiple characters still enter history."""
    _, status, commandline, qtbot = history_bot
    execute = Mock()
    monkeypatch.setattr(ExecutorColon, method, execute)

    submit(commandline, qtbot, command)

    execute.assert_called_once_with("")
    assert commandline.histories == {"ex": [command[1:]], "search": []}
    assert load_history(commandline._history_file) == commandline.histories
    assert status.sub_mode is None


def test_duplicate_filter_compares_the_exact_previous_input(history_bot, monkeypatch):
    """Whitespace is preserved for accepted entries and exact repeats are quiet."""
    _, _, commandline, qtbot = history_bot
    qtbot.keyClicks(commandline, ":")
    save = Mock(wraps=save_history)
    monkeypatch.setattr("spyder_okvim.spyder.vim_widgets.save_history", save)

    for body in ("marks", " marks", " marks"):
        commandline.remember_command(":" + body)

    assert commandline.histories == {"ex": ["marks", " marks"], "search": []}
    assert save.call_count == 2
    assert load_history(commandline._history_file) == commandline.histories


@pytest.mark.parametrize(
    "body",
    [
        "e docs/guide.py",
        'w "notes file.py"',
        "s/foo/bar/g",
        "%s/foo/bar/g",
        "1,2s",
        "%&",
        "02",
        "q!",
        "wq",
        "marks",
        "&&",
        "한글",
        "😀😀",
    ],
)
def test_multiple_character_ex_inputs_remain_in_history(history_bot, body):
    """Length, rather than argument or token count, determines eligibility."""
    _, _, commandline, qtbot = history_bot
    qtbot.keyClicks(commandline, ":")

    commandline.remember_command(":" + body)

    assert commandline.histories == {"ex": [body], "search": []}
    assert load_history(commandline._history_file) == commandline.histories


@pytest.mark.parametrize("prompt, body", [("/", "w"), ("?", "q"), ("2/", "foo")])
def test_single_word_searches_remain_in_history(history_bot, prompt, body):
    """Single-word patterns remain useful even when they spell an Ex command."""
    _, _, commandline, qtbot = history_bot
    qtbot.keyClicks(commandline, prompt)

    commandline.remember_command(prompt + body)

    assert commandline.histories == {"ex": [], "search": [body]}
    assert load_history(commandline._history_file) == commandline.histories


def test_repeated_empty_search_does_not_store_an_empty_entry(history_bot):
    """Enter can reuse a confirmed word without adding an empty history item."""
    _, status, commandline, qtbot = history_bot
    submit(commandline, qtbot, "/foo")
    submit(commandline, qtbot, "?")

    assert status.search.txt_searched == "foo"
    assert status.search.forward is False
    assert commandline.histories["search"] == ["foo"]


def test_ime_committed_search_word_round_trips_through_history(history_bot):
    """Committed Korean text survives history and the unfinished draft."""
    editor, _, commandline, qtbot = history_bot
    editor.set_text("start 한글 target")
    qtbot.keyClicks(commandline, "/")
    event = QInputMethodEvent()
    event.setCommitString("한글")
    QCoreApplication.sendEvent(commandline, event)
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert commandline.histories["search"] == ["한글"]

    qtbot.keyClicks(commandline, "?")
    event = QInputMethodEvent()
    event.setCommitString("초안")
    QCoreApplication.sendEvent(commandline, event)
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == "?한글"
    qtbot.keyPress(commandline, Qt.Key_Down)
    assert commandline.text() == "?초안"
    assert load_history(commandline._history_file)["search"] == ["한글"]


def test_new_widget_restores_saved_histories(history_bot, monkeypatch):
    """A new input widget loads confirmed entries and can recall both kinds."""
    _, _, commandline, qtbot = history_bot
    qtbot.keyClicks(commandline, ":02")
    assert not commandline._history_file.exists()
    qtbot.keyPress(commandline, Qt.Key_Return)
    submit(commandline, qtbot, "/foo")
    qtbot.keyClicks(commandline, "?")
    commandline.insert("한글😀")
    qtbot.keyPress(commandline, Qt.Key_Return)
    expected = {"ex": ["02"], "search": ["foo", "한글😀"]}
    assert load_history(commandline._history_file) == expected

    monkeypatch.setattr(
        CONF, "get_plugin_config_path", lambda _: str(commandline._history_file.parent)
    )
    original = commandline.vim_widget
    restored = VimWidget(original.editor_widget, original.main)
    qtbot.addWidget(restored)
    try:
        assert restored.commandline.histories == expected
        restored.commandline.setFocus()
        QCoreApplication.processEvents()
        qtbot.keyClicks(restored.commandline, ":")
        qtbot.keyPress(restored.commandline, Qt.Key_Up)
        assert restored.commandline.text() == ":02"
        qtbot.keyPress(restored.commandline, Qt.Key_Escape)
        qtbot.keyClicks(restored.commandline, "/")
        qtbot.keyPress(restored.commandline, Qt.Key_Up)
        assert restored.commandline.text() == "/한글😀"
    finally:
        restored.cleanup()


def test_saved_history_keeps_latest_100_entries(history_bot):
    """Appending past the limit truncates the same oldest entry on disk."""
    _, _, commandline, qtbot = history_bot
    commandline.histories["ex"][:] = [str(index) for index in range(100)]
    commandline.histories["search"][:] = ["foo"]

    submit(commandline, qtbot, ":100")

    expected = {
        "ex": [str(index) for index in range(1, 101)],
        "search": ["foo"],
    }
    assert commandline.histories == expected
    assert load_history(commandline._history_file) == expected


@pytest.mark.parametrize(
    "text, kind, body", [(":02", "ex", "02"), ("/two", "search", "two")]
)
def test_save_failure_does_not_interrupt_execution(
    history_bot, monkeypatch, caplog, text, kind, body
):
    """A full or unwritable disk must not stop an Ex command or search."""
    editor, status, commandline, qtbot = history_bot
    editor.set_text("one\ntwo")
    status.cursor.set_cursor_pos(0)

    def fail_replace(source, target):
        raise OSError("disk is full")

    with monkeypatch.context() as patch:
        patch.setattr("spyder_okvim.utils.commandline_history.os.replace", fail_replace)
        submit(commandline, qtbot, text)

    assert editor.textCursor().position() == 4
    assert commandline.histories[kind] == [body]
    assert commandline.text() == ""
    assert status.sub_mode is None
    assert not commandline._history_file.exists()
    assert "Unable to save command-line history" in caplog.text

    submit(commandline, qtbot, text)

    assert commandline.histories[kind] == [body]
    assert load_history(commandline._history_file) == commandline.histories
