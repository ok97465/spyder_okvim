"""Tests for the executor_surround."""

# Third Party Libraries
import pytest

# Project Libraries
from spyder_okvim.vim import VimState


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ["v", "S", "'"], "''", 0),
        ("", ["v", "S", "i"], "", 0),
        ("abde", ["l", "v", "S", "'"], "a'b'de", 1),
        ("abde", ["l", "v", "l" "S", '"'], 'a"bd"e', 1),
        ("abde", ["l", "v", "l" "S", "["], "a[ bd ]e", 1),
        ("abde", ["l", "v", "l" "S", "{"], "a{ bd }e", 1),
        ("abde", ["l", "v", "l" "S", "("], "a( bd )e", 1),
        ("abde", ["l", "v", "l" "S", "]"], "a[bd]e", 1),
        ("abde", ["l", "v", "l" "S", "}"], "a{bd}e", 1),
        ("abde", ["l", "v", "l" "S", ")"], "a(bd)e", 1),
        ("abde", ["l", "v", "l" "S", "B"], "a{bd}e", 1),
        ("abde", ["l", "v", "l" "S", "b"], "a(bd)e", 1),
        ("abde abcd", ["l", "v", "l" "S", ")", "6l", "."], "a(bd)e (ab)cd", 7),
        ("abde\ndd", ["l", "v", "j" "S", ")"], "a(bde\ndd)", 1),
    ],
)
def test_add_surround_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test to add surround command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")

    assert sel == []
    assert cmd_line.text() == ""
    assert vim.vim_cmd.vim_status.vim_state == VimState.NORMAL
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected",
    [
        ("a", ["y", "s", "l", "("], 0, "( a )"),
        ("abcd", ["$", "y", "s", "2h", ")"], 1, "a(bc)d"),
        ("abcd", ["$", "y", "s", "2h", "b"], 1, "a(bc)d"),
        ("abcd", ["y", "s", "$", '"'], 0, '"abcd"'),
        ("abcd", ["$", "ys", "^", "'"], 0, "'abc'd"),
        ("a b", ["ys", "w", "}"], 0, "{a} b"),
        ("a b", ["ys", "w", "B"], 0, "{a} b"),
        ("a b", ["ys", "w", "}", "4l", "."], 4, "{a} {b}"),
        ("a b", ["l", "ys", "w", "("], 1, "a(   )b"),
        ("a b c ", ["ys", "2w", "]"], 0, "[a b] c "),
        ("a.dk b", ["ys", "W", "["], 0, "[ a.dk ] b"),
        ("a.dk b dd", ["ys", "2W", '"'], 0, '"a.dk b" dd'),
        ("a.dk\nb", ["ys", "e", ")"], 0, "(a.)dk\nb"),
        ("a.dk\nb", ["ys", "2e", "("], 0, "( a.dk )\nb"),
        ("abcd", ["$", "ys", "b", "]"], 0, "[abc]d"),
        ("ab.cd", ["$", "ys", "b", "'"], 3, "ab.'c'd"),
        ("ab.cd", ["$", "ys", "B", "{"], 0, "{ ab.c }d"),
        ("  abcd \n b", ["3l", "ys", "i", "w", '"'], 2, '  "abcd" \n b'),
        ("  abcd \n b", ["3l", "ys", "a", "w", '"'], 2, '  "abcd "\n b'),
        ("AB(CD)", ["l", "ys", "%", '"'], 1, 'A"B(CD)"'),
        ("AB(CD)", ["$", "ys", "%", '"'], 2, 'AB"(CD)"'),
        ("ABCD", ["ys", "f", "D", '"'], 0, '"ABCD"'),
        ("ABCD", ["c", "f", "F"], 0, "ABCD"),
        ("ABCD", ["ys", "t", "D", '"'], 0, '"ABC"D'),
        ("ABCD", ["$", "ys", "F", "A", '"'], 0, '"ABC"D'),
        ("ABCD", ["$", "ys", "T", "A", '"'], 1, 'A"BC"D'),
        ("AAAA", ["ys", "2f", "A", '"'], 0, '"AAA"A'),
        (' "AAA"', ["ys", "i", '"', ")"], 2, ' "(AAA)"'),
        (' "AAA"', ["ys", "a", '"', ")"], 0, '( "AAA")'),
        ("(AAA)", ["ys", "i", "(", '"'], 1, '("AAA")'),
        ("(AAA)", ["ys", "a", "(", '"'], 0, '"(AAA)"'),
        ("(AAA)", ["%", "ys", "a", ")", '"'], 0, '"(AAA)"'),
        ("(AAA)", ["ys", "s", "}"], 0, "{(AAA)}"),
    ],
)
def test_add_surround_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected):
    """Test to add surround in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert vim.vim_cmd.vim_status.vim_state == VimState.NORMAL
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected",
    [
        ("(a)", ["ds", ")"], 0, "a"),
        ("( a )", ["ds", "b"], 0, " a "),
        ("( a ) ( a )", ["ds", "("], 0, "a ( a )"),
        ("( a ) ( a )", ["ds", "(", "."], 2, "a a"),
        ("{a}", ["ds", "}"], 0, "a"),
        ("{ a }", ["ds", "B"], 0, " a "),
        ("{ a }", ["ds", "{"], 0, "a"),
        ("[ a ]", ["ds", "]"], 0, " a "),
        ("[ a ]", ["ds", "["], 0, "a"),
        ('"a" "a"', ["ds", '"'], 0, 'a "a"'),
        ('"a" "a"', ["ds", '"', "."], 2, "a a"),
        ("'a'", ["ds", "'"], 0, "a"),
        ("  (a)", ["ds", ")"], 2, "  a"),
        ("  'a'", ["ds", "'"], 2, "  a"),
        ("(a)  ", ["$", "ds", ")"], 4, "(a)  "),
        ("(a)  ", ["$", "ds", "'"], 4, "(a)  "),
        ("'a'  ", ["$", "ds", "'"], 4, "'a'  "),
        ("a  ", ["ds", ")"], 0, "a  "),
        ("a  ", ["ds", "'"], 0, "a  "),
    ],
)
def test_delete_surround_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected):
    """Test to delete surround in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert vim.vim_cmd.vim_status.vim_state == VimState.NORMAL
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected",
    [
        ("(a) (a)", ["cs", "b", "B"], 0, "{a} (a)"),
        ("(a) (a)", ["cs", "b", "B", "."], 4, "{a} {a}"),
        ("( a )", ["cs", "b", "'"], 0, "' a '"),
        ("( a )", ["cs", "(", "'"], 0, "'a'"),
        ("{ a }", ["cs", "B", '"'], 0, '" a "'),
        ("{ a }", ["cs", "{", "["], 0, "[ a ]"),
        ("[ a ]", ["cs", "[", "]"], 0, "[a]"),
        ("' a '", ["cs", "'", '"'], 0, '" a "'),
    ],
)
def test_change_surround_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected):
    """Test to change surround in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert vim.vim_cmd.vim_status.vim_state == VimState.NORMAL
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.fixture
def surround_bot(vim_bot):
    """Give each preview test an idle editor and cancel its pending input."""
    from tests.qt_support import reset_vim_state

    _, stack, editor, vim, qtbot = vim_bot
    stack.set_stack_index(0)
    widget = vim.vim_cmd
    reset_vim_state(widget.vim_status)
    editor.set_text('one "two" (three)')
    widget.vim_status.cursor.set_cursor_pos(0)
    widget.commandline.clear()
    yield editor, widget.vim_status, widget.commandline, qtbot
    widget.commandline.esc_pressed()


def test_add_surround_preview_matches_edit_and_undo(surround_bot):
    """ysiw previews exactly the eventual range and leaves one undoable edit."""
    editor, status, commandline, qtbot = surround_bot
    before = editor.toPlainText()
    qtbot.keyClicks(commandline, "ysiw")
    preview = editor.get_extra_selections("vim_surround_preview")
    assert len(preview) == 1
    assert preview[0].cursor.selectedText() == "one"
    assert editor.toPlainText() == before
    assert "new delimiter" in status.msg_label.text()
    assert "( text )" in status.msg_label.text()
    qtbot.keyClicks(commandline, ")")
    assert editor.toPlainText() == '(one) "two" (three)'
    assert editor.get_extra_selections("vim_surround_preview") == []
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == before


def test_change_surround_previews_pair_then_cleans_on_cancel(surround_bot):
    """Choosing the old quote displays both endpoints without changing text."""
    from qtpy.QtCore import Qt

    editor, status, commandline, qtbot = surround_bot
    status.cursor.set_cursor_pos(6)
    before = editor.toPlainText()
    qtbot.keyClicks(commandline, 'cs"')
    preview = editor.get_extra_selections("vim_surround_preview")
    assert [
        (item.cursor.selectionStart(), item.cursor.selectionEnd()) for item in preview
    ] == [(4, 5), (8, 9)]
    assert editor.toPlainText() == before
    assert "change" in status.msg_label.text()
    qtbot.keyPress(commandline, Qt.Key_Escape)
    assert editor.get_extra_selections("vim_surround_preview") == []
    assert editor.toPlainText() == before


def test_surround_distinguishes_missing_and_unsupported_targets(surround_bot):
    editor, status, commandline, qtbot = surround_bot
    editor.set_text("plain")
    qtbot.keyClicks(commandline, "ds)")
    assert "no target" in status.msg_label.text()
    qtbot.keyClicks(commandline, "dsx")
    assert "unsupported delimiter" in status.msg_label.text()
    assert editor.get_extra_selections("vim_surround_preview") == []
    assert editor.toPlainText() == "plain"


def test_surround_preview_is_cancelled_by_document_change(surround_bot):
    editor, status, commandline, qtbot = surround_bot
    qtbot.keyClicks(commandline, "ysiw")
    assert editor.get_extra_selections("vim_surround_preview")
    editor.set_text("replacement document")
    assert editor.get_extra_selections("vim_surround_preview") == []
    assert status.sub_mode is None
    assert "document changed" in status.msg_label.text()


def test_leap_motion_keeps_pending_surround(surround_bot):
    """A unique Leap target must preserve the following delimiter prompt."""
    from spyder.config.manager import CONF

    from spyder_okvim.spyder.config import CONF_SECTION

    editor, status, commandline, qtbot = surround_bot
    CONF.set(CONF_SECTION, "use_leap", True)
    status.refresh_settings()
    editor.set_text("one word")
    status.cursor.set_cursor_pos(0)

    qtbot.keyClicks(commandline, "yszwo")

    assert status.sub_mode is not None
    assert "new delimiter" in status.msg_label.text()
    preview = editor.get_extra_selections("vim_surround_preview")
    assert len(preview) == 1
    assert preview[0].cursor.selectedText() == "one "

    qtbot.keyClicks(commandline, ")")

    assert editor.toPlainText() == "(one )word"
    assert status.sub_mode is None
    assert editor.get_extra_selections("vim_surround_preview") == []


@pytest.mark.parametrize("command", ["yszxx", "czxx"])
def test_failed_leap_does_not_run_pending_edit(surround_bot, command):
    """A missing target cancels without opening a delimiter or insert prompt."""
    from spyder.config.manager import CONF

    from spyder_okvim.spyder.config import CONF_SECTION

    editor, status, commandline, qtbot = surround_bot
    CONF.set(CONF_SECTION, "use_leap", True)
    status.refresh_settings()
    before = editor.toPlainText()

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == before
    assert status.sub_mode is None
    assert status.vim_state == VimState.NORMAL
    assert editor.get_extra_selections("vim_surround_preview") == []
    assert "no matching target" in status.msg_label.text()


def test_visual_surround_escape_preserves_selection(surround_bot):
    """The first Escape cancels pending S while keeping its Visual selection."""
    from qtpy.QtCore import Qt

    editor, status, commandline, qtbot = surround_bot
    qtbot.keyClicks(commandline, "vlS")
    original = editor.get_extra_selections("vim_selection")[0].cursor
    qtbot.keyPress(commandline, Qt.Key_Escape)
    assert status.vim_state == VimState.VISUAL
    assert editor.get_extra_selections("vim_surround_preview") == []
    current = editor.get_extra_selections("vim_selection")[0].cursor
    assert (current.selectionStart(), current.selectionEnd()) == (
        original.selectionStart(),
        original.selectionEnd(),
    )
