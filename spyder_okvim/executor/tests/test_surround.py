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
