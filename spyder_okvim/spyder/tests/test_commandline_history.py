"""Regression tests for separate Ex and search command-line histories."""

import pytest
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QInputMethodEvent

from spyder_okvim.vim import VimState


@pytest.fixture
def history_bot(vim_bot):
    """Isolate command history, editor contents, current tab, and focus."""
    _, stack, _, vim, qtbot = vim_bot
    previous_index = stack.get_stack_index()
    commandline = vim.vim_cmd.commandline
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
    for text in (":1", "/foo", ":2", "?x"):
        submit(commandline, qtbot, text)

    assert commandline.histories == {"ex": ["1", "2"], "search": ["foo", "x"]}

    qtbot.keyClicks(commandline, "?")
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == "?x"
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == "?foo"
    qtbot.keyPress(commandline, Qt.Key_Escape)

    qtbot.keyClicks(commandline, ":")
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == ":2"


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
        ([":1", ":1", ":2", ":1"], "ex", ["1", "2", "1"]),
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


@pytest.mark.parametrize("command", [":", ":   ", "/", "?"])
def test_empty_commands_do_not_create_history(history_bot, command):
    """Blank Ex input and searches without a pattern exit without history."""
    _, status, commandline, qtbot = history_bot
    submit(commandline, qtbot, command)

    assert commandline.histories == {"ex": [], "search": []}
    assert status.sub_mode is None
    assert commandline.text() == ""


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
