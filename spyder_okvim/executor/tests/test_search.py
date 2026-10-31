"""Search direction, incremental previews, and cancellation regressions."""

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QInputMethodEvent, QTextCursor
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.vim import VimState
from tests.qt_support import reset_vim_state


@pytest.fixture
def search_bot(vim_bot):
    """Isolate the editor and command line shared by the GUI test session."""
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
    original_text = editor.toPlainText()
    editor.set_text("foo x foo x foo")
    status.cursor.set_cursor_pos(0)
    options = {
        name: CONF.get(CONF_SECTION, name) for name in ("ignorecase", "smartcase")
    }
    CONF.set(CONF_SECTION, "ignorecase", True)
    CONF.set(CONF_SECTION, "smartcase", True)
    try:
        yield editor, status, commandline, qtbot
    finally:
        commandline.esc_pressed()
        status.disconnect_from_editor()
        reset_vim_state(status)
        editor.set_text(original_text)
        stack.set_stack_index(previous_index)
        for name, value in options.items():
            CONF.set(CONF_SECTION, name, value)


def _selection(editor):
    return [
        (sel.cursor.anchor(), sel.cursor.position())
        for sel in editor.get_extra_selections("vim_selection")
    ]


def _highlights(editor):
    return [
        (sel.cursor.selectionStart(), sel.cursor.selectionEnd())
        for sel in editor.get_extra_selections("vim_search")
    ]


@pytest.mark.parametrize(
    "command, start, expected, forward",
    [
        ("/foo", 0, 6, True),
        ("?foo", 12, 6, False),
        ("2/foo", 0, 12, True),
        ("2?foo", 0, 6, False),
    ],
)
def test_confirm_and_repeat_follow_search_direction(
    search_bot, command, start, expected, forward
):
    """Enter bypasses the debounce and n/N do not overwrite the saved direction."""
    editor, status, commandline, qtbot = search_bot
    status.cursor.set_cursor_pos(start)
    qtbot.keyClicks(commandline, command)
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert editor.textCursor().position() == expected
    assert status.search.forward is forward
    assert commandline.text() == ""

    qtbot.keyClicks(commandline, "n")
    assert editor.textCursor().position() == (expected + (6 if forward else -6)) % 18
    qtbot.keyClicks(commandline, "N")
    assert editor.textCursor().position() == expected
    qtbot.keyClicks(commandline, "2N")
    assert editor.textCursor().position() == (expected + (-12 if forward else 12)) % 18
    assert status.search.forward is forward


@pytest.mark.parametrize("prompt, start, expected", [("/", 0, 6), ("?", 12, 6)])
def test_preview_is_debounced_and_enter_keeps_the_preview_match(
    search_bot, monkeypatch, prompt, start, expected
):
    editor, status, commandline, qtbot = search_bot
    status.cursor.set_cursor_pos(start)
    searches = []
    search = status.search.search

    def record(*args, **kwargs):
        searches.append(args[0])
        return search(*args, **kwargs)

    monkeypatch.setattr(status.search, "search", record)
    qtbot.keyClicks(commandline, prompt + "foo")
    assert searches == []
    assert editor.textCursor().position() == start
    qtbot.waitUntil(lambda: editor.textCursor().position() == expected)
    assert searches == ["foo"]
    assert status.jump_list.jumps == []

    qtbot.keyPress(commandline, Qt.Key_Return)
    assert editor.textCursor().position() == expected
    assert [jump.pos for jump in status.jump_list.jumps] == [start, expected]


def test_preview_refinement_and_backspace_always_use_the_origin(search_bot):
    editor, status, commandline, qtbot = search_bot
    editor.set_text("x ab a ab")
    status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(commandline, "/a")
    qtbot.waitUntil(lambda: editor.textCursor().position() == 2)
    qtbot.keyClicks(commandline, "b")
    qtbot.waitUntil(lambda: status.search.txt_searched == "ab")
    assert editor.textCursor().position() == 2
    qtbot.keyPress(commandline, Qt.Key_Backspace)
    qtbot.waitUntil(lambda: status.search.txt_searched == "a")
    assert editor.textCursor().position() == 2
    qtbot.keyPress(commandline, Qt.Key_Backspace)
    qtbot.waitUntil(lambda: editor.textCursor().position() == 0)
    assert commandline.text() == "/"
    assert status.search.txt_searched == ""
    assert _highlights(editor) == []


@pytest.mark.parametrize("invalid", ["missing", "["])
def test_unmatched_preview_returns_to_start(search_bot, invalid):
    editor, status, commandline, qtbot = search_bot
    qtbot.keyClicks(commandline, "/foo")
    qtbot.waitUntil(lambda: editor.textCursor().position() == 6)
    commandline.setText("/" + invalid)
    qtbot.waitUntil(lambda: status.search.txt_searched == invalid)
    assert editor.textCursor().position() == 0
    assert _highlights(editor) == []
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert editor.textCursor().position() == 0


@pytest.mark.parametrize("mode", ["", "vll", "vllo", "Vj", "Vjo"])
@pytest.mark.parametrize("prompt", ["/", "?"])
def test_escape_restores_cursor_visual_selection_and_previous_search(
    search_bot, mode, prompt
):
    editor, status, commandline, qtbot = search_bot
    editor.set_text("foo xx\nfoo xx\nfoo xx\nfoo")
    status.search.search("xx", forward=False)
    status.search.clear_highlights()
    snapshot = status.search.snapshot()
    status.cursor.set_cursor_pos(7)
    qtbot.keyClicks(commandline, mode)
    cursor = editor.textCursor()
    selections = _selection(editor)
    state = status.vim_state
    qtbot.keyClicks(commandline, prompt + "foo")
    qtbot.waitUntil(lambda: status.search.txt_searched == "foo")
    assert editor.textCursor().position() != cursor.position()
    qtbot.keyPress(commandline, Qt.Key_Escape)

    assert editor.textCursor().position() == cursor.position()
    assert editor.textCursor().anchor() == cursor.anchor()
    assert _selection(editor) == selections
    assert status.vim_state == state
    assert status.search.snapshot() == snapshot
    assert _highlights(editor) == []
    assert status.msg_label.text() == ""
    assert status.sub_mode is None
    assert status.jump_list.jumps == []


@pytest.mark.parametrize("cancel", ["escape", "backspace", "clear"])
def test_cancel_stops_pending_preview(search_bot, cancel):
    editor, status, commandline, qtbot = search_bot
    qtbot.keyClicks(commandline, "?foo")
    if cancel == "escape":
        qtbot.keyPress(commandline, Qt.Key_Escape)
    elif cancel == "backspace":
        for _ in range(4):
            qtbot.keyPress(commandline, Qt.Key_Backspace)
    else:
        commandline.clear()
    qtbot.wait(250)
    assert editor.textCursor().position() == 0
    assert status.search.txt_searched == ""
    assert status.search.forward is True
    assert _highlights(editor) == []
    assert status.sub_mode is None


@pytest.mark.parametrize("prompt, expected", [("/", 12), ("?", 0)])
def test_empty_search_reuses_confirmed_pattern_after_erasing_preview(
    search_bot, prompt, expected
):
    editor, status, commandline, qtbot = search_bot
    status.search.search("foo")
    status.cursor.set_cursor_pos(6)
    qtbot.keyClicks(commandline, prompt + "x")
    qtbot.waitUntil(lambda: status.search.txt_searched == "x")
    qtbot.keyPress(commandline, Qt.Key_Backspace)
    # Confirm before the empty-input debounce fires.
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert status.search.txt_searched == "foo"
    assert status.search.forward is (prompt == "/")
    assert editor.textCursor().position() == expected


@pytest.mark.parametrize("prompt", ["/", "?"])
def test_empty_search_without_history_is_a_noop(search_bot, prompt):
    editor, status, commandline, qtbot = search_bot
    qtbot.keyClicks(commandline, prompt)
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert editor.textCursor().position() == 0
    assert status.sub_mode is None
    assert commandline.text() == ""
    assert status.jump_list.jumps == []


@pytest.mark.parametrize("operator", ["d", "y", "c"])
@pytest.mark.parametrize("prompt, start, expected", [("/", 0, 6), ("?", 12, 6)])
def test_operator_preview_defers_edits_and_enter_uses_original_range(
    search_bot, operator, prompt, start, expected
):
    editor, status, commandline, qtbot = search_bot
    original = editor.toPlainText()
    status.cursor.set_cursor_pos(start)
    qtbot.keyClicks(commandline, operator + prompt + "foo")
    qtbot.waitUntil(lambda: editor.textCursor().position() == expected)
    assert editor.toPlainText() == original
    assert not status.register_dict
    assert status.jump_list.jumps == []
    qtbot.keyPress(commandline, Qt.Key_Return)

    low, high = sorted([start, expected])
    assert status.register_dict['"'].content == original[low:high]
    if operator == "y":
        assert editor.toPlainText() == original
    else:
        assert editor.toPlainText() == original[:low] + original[high:]
        editor.undo()
        assert editor.toPlainText() == original


def test_counted_operator_search_and_dot_replay(search_bot):
    editor, status, commandline, qtbot = search_bot
    qtbot.keyClicks(commandline, "d2/foo")
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert editor.toPlainText() == "foo"
    assert status.register_dict['"'].content == "foo x foo x "
    editor.undo()
    status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(commandline, ".")
    assert editor.toPlainText() == "foo"


@pytest.mark.parametrize("command, forward", [("*", True), ("#", False)])
def test_word_search_sets_repeat_direction(search_bot, command, forward):
    editor, status, commandline, qtbot = search_bot
    status.search.search("x", forward=not forward)
    status.cursor.set_cursor_pos(6)
    qtbot.keyClicks(commandline, command)
    first = 12 if forward else 0
    assert editor.textCursor().position() == first
    qtbot.keyClicks(commandline, "n")
    assert editor.textCursor().position() == (first + (6 if forward else -6)) % 18
    assert status.search.forward is forward


def test_ime_committed_text_is_previewed_in_reverse(search_bot):
    editor, status, commandline, qtbot = search_bot
    editor.set_text("한글 xx 한글")
    status.cursor.set_cursor_pos(6)
    qtbot.keyClicks(commandline, "?")
    event = QInputMethodEvent("", [])
    event.setCommitString("한글")
    QCoreApplication.sendEvent(commandline, event)
    qtbot.waitUntil(lambda: editor.textCursor().position() == 0)
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert editor.textCursor().position() == 0
    assert status.search.txt_searched == "한글"
    assert status.search.forward is False


@pytest.mark.parametrize("mode, state", [("v", VimState.VISUAL), ("V", VimState.VLINE)])
def test_visual_confirm_and_repeats_extend_selection(search_bot, mode, state):
    editor, status, commandline, qtbot = search_bot
    editor.set_text("foo\nfoo\nfoo")
    status.cursor.set_cursor_pos(8)
    qtbot.keyClicks(commandline, mode + "?foo")
    qtbot.waitUntil(lambda: editor.textCursor().position() == 4)
    preview = _selection(editor)
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert _selection(editor) == preview
    assert status.vim_state == state
    qtbot.keyClicks(commandline, "n")
    assert editor.textCursor().position() == 0
    qtbot.keyClicks(commandline, "N")
    assert editor.textCursor().position() == 4


@pytest.mark.parametrize("mode", ["vll", "Vj"])
def test_unmatched_visual_preview_restores_the_original_selection(search_bot, mode):
    editor, status, commandline, qtbot = search_bot
    editor.set_text("foo xx\nfoo xx\nfoo xx")
    status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(commandline, mode)
    original = _selection(editor)
    position = editor.textCursor().position()
    qtbot.keyClicks(commandline, "/foo")
    qtbot.waitUntil(lambda: status.search.txt_searched == "foo")
    assert _selection(editor) != original
    commandline.setText("/missing")
    qtbot.waitUntil(lambda: status.search.txt_searched == "missing")
    assert _selection(editor) == original
    assert editor.textCursor().position() == position


def test_escape_restores_a_native_text_selection(search_bot):
    editor, status, commandline, qtbot = search_bot
    cursor = editor.textCursor()
    cursor.setPosition(2)
    cursor.setPosition(0, QTextCursor.KeepAnchor)
    editor.setTextCursor(cursor)
    qtbot.keyClicks(commandline, "/foo")
    qtbot.waitUntil(lambda: editor.textCursor().position() == 6)
    qtbot.keyPress(commandline, Qt.Key_Escape)
    assert editor.textCursor().position() == 0
    assert editor.textCursor().anchor() == 2


@pytest.mark.parametrize("close", [False, True])
def test_reset_and_close_stop_pending_previews(search_bot, close):
    editor, status, commandline, qtbot = search_bot
    qtbot.keyClicks(commandline, "/foo")
    search = status.search
    if close:
        search.close()
        search.close()  # Shutdown can reach the same state twice.
    else:
        reset_vim_state(status)
    qtbot.wait(250)
    assert search.txt_searched == ""
    assert status.search.txt_searched == ""
    assert _highlights(editor) == []
    assert editor.textCursor().position() == 0
    assert status.sub_mode is None


@pytest.mark.parametrize("prompt", ["/", "?"])
def test_search_without_an_open_editor_is_a_noop(
    search_bot, vim_bot, monkeypatch, prompt
):
    _, status, commandline, qtbot = search_bot
    _, stack, _, _, _ = vim_bot
    with monkeypatch.context() as context:
        context.setattr(stack, "get_current_editor", lambda: None)
        qtbot.keyClicks(commandline, prompt)
        assert status.sub_mode is None
        assert commandline.text() == ""


@pytest.mark.parametrize("prompt, expected", [("/", 4), ("?", 0)])
def test_zero_width_incremental_search_terminates(search_bot, prompt, expected):
    editor, status, commandline, qtbot = search_bot
    editor.set_text("foo\n\nfoo")
    status.cursor.set_cursor_pos(1)
    qtbot.keyClicks(commandline, prompt + "^")
    qtbot.waitUntil(lambda: status.search.txt_searched == "^")
    assert editor.textCursor().position() == expected
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert editor.textCursor().position() == expected


def test_search_feedback_distinguishes_invalid_patterns_and_missing_results(search_bot):
    editor, status, commandline, qtbot = search_bot
    qtbot.keyClicks(commandline, "/[")
    qtbot.waitUntil(lambda: "Regex error at" in status.msg_label.text())
    assert "No results" not in status.msg_label.text()
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert "Regex error at" in status.msg_label.text()
    assert editor.textCursor().position() == 0

    qtbot.keyClicks(commandline, "/missing")
    qtbot.waitUntil(lambda: "No results" in status.msg_label.text())
    assert "Regex error" not in status.msg_label.text()
    qtbot.keyPress(commandline, Qt.Key_Return)
    qtbot.keyClicks(commandline, "n")
    assert "No results" in status.msg_label.text()
    assert editor.textCursor().position() == 0


def test_counted_search_reports_target_index_and_wrap_direction(search_bot):
    editor, status, commandline, qtbot = search_bot
    qtbot.keyClicks(commandline, "2/foo")
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert editor.textCursor().position() == 12
    assert status.msg_label.text().startswith("3/3")
    assert "Wrapped" not in status.msg_label.text()

    qtbot.keyClicks(commandline, "n")
    assert editor.textCursor().position() == 0
    assert status.msg_label.text().startswith("1/3")
    assert "Wrapped to top" in status.msg_label.text()
    qtbot.keyClicks(commandline, "N")
    assert editor.textCursor().position() == 12
    assert status.msg_label.text().startswith("3/3")
    assert "Wrapped to bottom" in status.msg_label.text()
    qtbot.keyClicks(commandline, "4n")
    assert editor.textCursor().position() == 0
    assert status.msg_label.text().startswith("1/3")
    assert "Wrapped to top" in status.msg_label.text()


@pytest.mark.parametrize("pattern, count", [("foo", 3), ("Foo", 1)])
def test_search_count_reflects_smartcase_policy(search_bot, pattern, count):
    editor, status, commandline, qtbot = search_bot
    editor.set_text("foo Foo FOO")
    qtbot.keyClicks(commandline, "/" + pattern)
    qtbot.keyPress(commandline, Qt.Key_Return)
    assert f"/{count} · /{pattern}" in status.msg_label.text()


def test_search_guide_examples_toggle_without_changing_input_or_focus(
    search_bot, vim_bot
):
    _, status, commandline, qtbot = search_bot
    _, _, _, vim, _ = vim_bot
    controller = vim.vim_cmd.commandline_popup
    qtbot.keyClicks(commandline, "/foo")
    qtbot.waitUntil(lambda: controller.guide_popup is not None)
    guide = controller.guide_popup
    assert guide.isVisible()
    assert "Qt regex" in guide.header.text()
    assert "Ignore case" in guide.header.text()
    assert guide.description.isHidden()
    qtbot.keyPress(commandline, Qt.Key_F1)
    assert not guide.description.isHidden()
    assert "whole word" in guide.description.text()
    assert commandline.text() == "/foo"
    assert commandline.hasFocus()
    qtbot.keyPress(commandline, Qt.Key_F1)
    assert guide.description.isHidden()

    commandline.setText("/Foo")
    assert "Match case" in guide.header.text()
    qtbot.keyPress(commandline, Qt.Key_Escape)
    assert not controller.host.isVisible()
    assert status.search.txt_searched == ""


def test_search_guide_follows_delayed_preview_and_editor_scroll(search_bot, vim_bot):
    editor, status, commandline, qtbot = search_bot
    _, _, _, vim, _ = vim_bot
    editor.set_text("\n".join(["filler"] * 120 + ["needle"] + ["filler"] * 20))
    status.cursor.set_cursor_pos(0)
    editor.verticalScrollBar().setValue(0)
    qtbot.keyClicks(commandline, "/needle")
    controller = vim.vim_cmd.commandline_popup
    initial_geometry = controller.host.geometry()
    qtbot.waitUntil(lambda: editor.textCursor().blockNumber() == 120)
    host = controller.host
    assert host.isVisible()
    assert host.geometry() != initial_geometry
    assert not host.geometry().intersects(editor.cursorRect())

    scrollbar = editor.verticalScrollBar()
    scrollbar.setValue(max(scrollbar.minimum(), scrollbar.value() - 3))
    assert not host.geometry().intersects(editor.cursorRect())
    assert commandline.hasFocus()
