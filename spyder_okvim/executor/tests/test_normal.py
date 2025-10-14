# -*- coding: utf-8 -*-
"""Tests for the executor_normal."""

# Standard Libraries
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent, QTextCursor
from qtpy.QtWidgets import QApplication
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.spyder.vim_widgets import enable_coverage_tracing


def test_unknown_cmd(vim_bot):
    """Test unknown cmd."""
    _, _, _, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "|")

    assert cmd_line.text() == ""


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("\ncdef\naslkdj\ndslkj", ["h"], 0),
        ("\ncdef\naslkdj\ndslkj", ["j", "4l", "h"], 3),
        ("\ncdef\naslkdj\ndslkj", ["j", "3l", "j", "3h"], 6),
        ("    ab\ncdef\n", ["5l", "10h"], 0),
        ("    ab\ncdef\n", ["2j", "5h"], 12),
    ],
)
def test_h_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test h command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("\ncdef\naslkdj\ndslkj", ["j"], 1),
        ("\ncdef\naslkdj\ndslkj", ["j", "4l", "j"], 9),
        ("\ncdef\naslkdj\ndslkj", ["j", "3l", "2j"], 16),
        ("\ncdef\naslkdj\ndslkj", ["j", "3l", "3j"], 16),
        ("    ab\ncdef\n", ["5l", "j"], 10),
        ("    ab\ncdef\n", ["5l", "2j", "j"], 12),
    ],
)
def test_j_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test j command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [("    ab\ncdef\n", ["2j", "2k"], 0), ("    ab\ncdef\n", ["5l", "2j", "k"], 7)],
)
def test_k_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test k command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("\ncdef\naslkdj\ndslkj", ["l"], 0),
        ("\ncdef\naslkdj\ndslkj", ["j", "4l"], 4),
        ("\ncdef\naslkdj\ndslkj", ["j", "3l", "j", "l"], 10),
        ("    ab\ncdef\n", ["5l"], 5),
        ("    ab\ncdef\n", ["2j", "5l"], 12),
    ],
)
def test_l_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test l command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


def test_HML(vim_bot):
    """Test HML."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "V")
    qtbot.keyClicks(cmd_line, "v")
    qtbot.keyClicks(cmd_line, "L")
    qtbot.keyClicks(cmd_line, "M")
    qtbot.keyClicks(cmd_line, "H")

    qtbot.keyClicks(cmd_line, "V")
    qtbot.keyClicks(cmd_line, "L")
    qtbot.keyClicks(cmd_line, "M")
    qtbot.keyClicks(cmd_line, "H")

    qtbot.keyPress(cmd_line, Qt.Key_Escape)
    qtbot.keyClicks(cmd_line, "L")
    qtbot.keyClicks(cmd_line, "M")
    qtbot.keyClicks(cmd_line, "H")

    qtbot.keyClicks(cmd_line, "y")
    qtbot.keyClicks(cmd_line, "L")

    qtbot.keyClicks(cmd_line, "y")
    qtbot.keyClicks(cmd_line, "M")

    qtbot.keyClicks(cmd_line, "y")
    qtbot.keyClicks(cmd_line, "H")

    assert cmd_line.text() == ""


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["0"], 0),
        ("cdef", ["l", "0"], 0),
        ("\ncdef\naslkdj\ndslkj", ["j", "4l", "0"], 1),
        ("c\n", ["j", "0"], 2),
    ],
)
def test_zero_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test 0 command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize("text, cmd_list, cursor_pos", [("", ["i"], 0)])
def test_i_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test i command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    # assert vim.vim_cmd.vim_status.vim_state == VimState.INSERT


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["I"], 0),
        ("  ", ["I"], 0),
        ("  a", ["I"], 2),
        ("  ab", ["5l", "I"], 2),
    ],
)
def test_I_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test I command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["a"], 0),
        ("0", ["a"], 1),
        ("\n1", ["j", "a"], 2),
        ("\n1\n", ["2j", "a"], 3),
    ],
)
def test_a_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test a command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["A"], 0),
        ("012", ["A"], 3),
        ("\n123", ["j", "A"], 4),
        ("\n1\n", ["2j", "A"], 3),
    ],
)
def test_A_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test A command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["^"], 0),
        ("   ", ["l", "^"], 1),
        (" cdef", ["5l", "^"], 1),
        ("\n cdef\naslkdj\ndslkj", ["j", "4l", "^"], 2),
        ("c\n", ["j", "^"], 2),
    ],
)
def test_caret_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test ^ command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["$"], 0),
        ("cdef", ["l", "$"], 3),
        ("\ncdef\naslkdj\ndslkj", ["j", "4l", "$"], 4),
        ("c\n", ["j", "$"], 2),
    ],
)
def test_dollar_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test $ command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize("text, cmd_list, cursor_pos", [("import re", ["7l", "K"], 7)])
def test_K_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test K command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [("", ["o"], "\n", 1), ("\na\n", ["3j", "o"], "\na\n\n", 4)],
)
def test_o_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test o command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [("", ["O"], "\n", 0), ("\na\n", ["3j", "O"], "\na\n\n", 3)],
)
def test_O_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test O command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected


def test_undo_redo(vim_bot):
    """Test undo redo command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    editor.moveCursor(QTextCursor.EndOfLine)
    qtbot.keyPress(editor, Qt.Key_Enter)
    qtbot.keyPress(editor, Qt.Key_1)

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "2u")

    assert editor.toPlainText() == "a"
    assert editor.textCursor().position() == 0

    qtbot.keyClicks(cmd_line, "g")
    qtbot.keyPress(cmd_line, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == "a"
    assert editor.textCursor().position() == 0

    qtbot.keyClicks(cmd_line, "v")
    qtbot.keyPress(cmd_line, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == "a"
    assert editor.textCursor().position() == 0

    qtbot.keyClicks(cmd_line, "/")
    qtbot.keyPress(cmd_line, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == "a"
    assert editor.textCursor().position() == 0

    qtbot.keyPress(cmd_line, Qt.Key_Escape)
    qtbot.keyClicks(cmd_line, "2")
    qtbot.keyPress(cmd_line, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == "a\n1"
    assert editor.textCursor().position() == 2


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ["J"], "", 0),
        ("\n\n", ["3j", "J"], "\n\n", 2),
        ("0\n23", ["J"], "0 23", 1),
        ("0\n23\n5", ["2J"], "0 23\n5", 1),
        ("0\n2\n  \n3", ["4J"], "0 2 3", 3),
        ("0\n23\n5", ["2J", "."], "0 23 5", 4),
    ],
)
def test_J_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test J command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("01 34", ["w"], 3),
        ("01 34", ["2w"], 4),
        ("01 34\na", ["3w"], 6),
        ("01 34\n  a", ["3w"], 8),
        ("01 34\n  a", ["2l", "w"], 3),
    ],
)
def test_w_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test w command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["W"], 0),
        ("029.d98@jl 34", ["W"], 11),
        ("029.d98@jl 34", ["2W"], 12),
        ("029.d98@jl 34\na", ["2W"], 14),
        ("029.d98@jl 34\n  a", ["2W"], 16),
        ("\na (", ["W"], 1),
        ("\n  a (", ["W"], 3),
    ],
)
def test_W_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test W command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("01 34", ["b"], 0),
        ("01 34", ["$", "b"], 3),
        ("0\n2\n4\n6", ["3j", "3b"], 0),
        ("0\n2\n\n 6\n8", ["4j", "3b"], 2),
        ("0\n2\n .6\n\n9", ["4j", "3b"], 5),
        ("0\n\n  \n  \n9", ["4j", "b"], 2),
    ],
)
def test_b_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test b command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("01 34", ["B"], 0),
        ("01.34", ["$", "B"], 0),
        ("0\n2()\n4.\n6", ["3j", "3B"], 0),
        ("0\n2\n .6\n\n9", ["4j", "3B"], 0),
        ("0\n\n  \n  \n9", ["4j", "B"], 2),
    ],
)
def test_B_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test B command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["e"], 0),
        ("01", ["e"], 1),
        ("01 ", ["e", "e"], 2),
        ("01 34", ["e", "e"], 4),
        ("01 34\n6 ", ["3e"], 6),
        ("01 34\n 7 ", ["3e"], 7),
        ("01 34\n67 ", ["3e"], 7),
        ("01 34\n\n   \n  ab", ["3e"], 14),
        ("01 34\n\n   \n  ab", ["e", "e", "e"], 14),
        (" 12 45", ["e"], 2),
    ],
)
def test_e_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test e command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


def test_gt_cmd(vim_bot):
    """Test gt, gT command."""
    _, editor_stack, editor, vim, qtbot = vim_bot

    assert 0 == editor_stack.get_stack_index()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "gt")
    assert 1 == editor_stack.get_stack_index()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "gt")
    assert 2 == editor_stack.get_stack_index()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "gt")
    assert 3 == editor_stack.get_stack_index()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "gT")
    assert 2 == editor_stack.get_stack_index()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "1gt")
    assert 0 == editor_stack.get_stack_index()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "2gt")
    assert 1 == editor_stack.get_stack_index()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "3gt")
    assert 2 == editor_stack.get_stack_index()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "gt")
    qtbot.keyClicks(cmd_line, "gT")
    assert 2 == editor_stack.get_stack_index()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "2gT")
    assert 0 == editor_stack.get_stack_index()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "gT")
    assert 3 == editor_stack.get_stack_index()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "gt")
    assert 0 == editor_stack.get_stack_index()


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("0\n2\n4\n", ["j", "10G"], 2),
        ("0\n2\n4\n", ["2G"], 2),
        ("0\n     \n8\n", ["2G"], 6),
        ("0\n2\n4\n", ["G"], 6),
        ("0\n2\n4\n     a", ["G"], 11),
    ],
)
def test_G_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test G command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("0\n2\n4\n", ["4j", "gg"], 0),
        ("0\n2\n4\n", ["2gg"], 2),
        ("0\n     \n8\n", ["2gg"], 6),
        ("0\n2\n4\n", ["gg"], 0),
        ("0\n2\n4\n     a", ["4gg"], 11),
        ("", ["gg"], 0),
        ("", ["2gg"], 0),
    ],
)
def test_gg_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test gg command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("0\n2\n4\n", ["4j", ":", "1", Qt.Key_Return], 0),
        ("0\n2\n4\n", [":", "2", Qt.Key_Return], 2),
        ("0\n     \n8\n", [":", "2", Qt.Key_Return], 6),
        ("0\n2\n4\n", [":", "1", Qt.Key_Return], 0),
        ("0\n2\n4\n     a", [":", "4", Qt.Key_Return], 11),
        ("", [":", "1", Qt.Key_Return], 0),
        ("", [":", "2", Qt.Key_Return], 0),
        (
            "aaa\nbbb\nccc\nddd\neee\n",
            ["j", ":", "4", Qt.Key_Return],
            12,
        ),
        (
            "aaa\nbbb\nccc\nddd\neee\n",
            ["j", "2l", ":", "5", Qt.Key_Return],
            16,
        ),
    ],
)
def test_colon_num_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test :num command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("abcde", ["~"], "Abcde", 1),
        ("abcde", ["2~"], "ABcde", 2),
        ("abcde", ["2~", "."], "ABCDe", 4),
        ("abcde", ["20~"], "ABCDE", 4),
        ("", ["10~"], "", 0),
    ],
)
def test_tilde_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test ~ command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ["^A"], "", 0),
        ("\n1\n", ["2j", "^A"], "\n1\n", 3),
        ("1", ["^A"], "2", 0),
        ("9", ["^A"], "10", 1),
        ("100", ["^A"], "101", 2),
        ("100", ["l", "^A"], "101", 2),
        (" 100a", ["l", "^A"], " 101a", 3),
        (" -1a", ["2l", "^A"], " 0a", 1),
        (" -2a", ["l", "^A"], " -1a", 2),
        (" -2a", ["l", "15", "^A"], " 13a", 2),
        (" -2a", ["l", "15", "^A", "."], " 28a", 2),
        (" -2a", ["l", "15", "^A", "2."], " 15a", 2),
        (" -2a", ["l", "c", "^A"], " -2a", 1),
        (" -2a", ["l", "/", "^A"], " -2a", 1),
    ],
)
def test_add_num_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test add_num."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if cmd != "^A":
            qtbot.keyClicks(cmd_line, cmd)
        else:
            event = QKeyEvent(QEvent.KeyPress, Qt.Key_A, Qt.ControlModifier)
            vim.vim_cmd.commandline.keyPressEvent(event)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ["^X"], "", 0),
        ("\n1\n", ["2j", "^X"], "\n1\n", 3),
        ("1", ["^X"], "0", 0),
        ("0", ["^X"], "-1", 1),
        ("100", ["^X"], "99", 1),
        ("100", ["l", "^X"], "99", 1),
        (" 100a", ["l", "^X"], " 99a", 2),
        (" -1a", ["2l", "^X"], " -2a", 2),
        (" -2a", ["l", "^X"], " -3a", 2),
        (" -2a", ["l", "15", "^X"], " -17a", 3),
        (" -2a", ["l", "15", "^X", "."], " -32a", 3),
        (" -2a", ["l", "15", "^X", "2."], " -19a", 3),
        (" -2a", ["l", "c", "^X"], " -2a", 1),
        (" -2a", ["l", "/", "^X"], " -2a", 1),
    ],
)
def test_subtract_num_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test subtract_num."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if cmd != "^X":
            qtbot.keyClicks(cmd_line, cmd)
        else:
            event = QKeyEvent(QEvent.KeyPress, Qt.Key_X, Qt.ControlModifier)
            vim.vim_cmd.commandline.keyPressEvent(event)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["%"], 0),
        ("\n", ["j", "%"], 1),
        ("()", ["%"], 1),
        ("()", ["$", "%"], 0),
        (" () ", ["$", "%"], 3),
        (" () ", ["2l", "%"], 1),
        (" (  \n) ", ["%"], 5),
        (" (  \n) ", ["%", "%"], 1),
        (" ({  \n}) ", ["%"], 7),
        (" ({  \n}) ", ["%", "%"], 1),
        (" ({  \n}) ", ["2l", "%"], 6),
        (" ({  \n}) ", ["2l", "%", "%"], 2),
    ],
)
def test_percent_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test % command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["f", "r"], 0),
        ("", [";"], 0),
        ("", [","], 0),
        ("\n", ["j", "f", "r"], 1),
        ("\n r", ["j", "f", "r"], 2),
        ("\n r", ["j", "2", "f", "r"], 1),
        ("\n rr", ["j", "2", "f", "r"], 3),
        ("\n rr", ["j", "3", "f", "r"], 1),
        ("\n rr", ["j", "l", "f", "r"], 3),
        ("\n rr", ["l", "f", "r"], 0),
        ("\n rr", ["j", "f", "r", ";"], 3),
        ("\n rr", ["j", "f", "r", ";", ","], 2),
        ("\n rrr", ["j", "f", "r", "2;"], 4),
        ("\n rrr", ["j", "f", "r", "2;", "2,"], 2),
        ("  ", ["f", Qt.Key_Space], 1),
    ],
)
def test_f_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test f command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.sub_mode is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["s", "aa"], 0),
        ("", [";"], 0),
        ("", [","], 0),
        ("\n", ["j", "s", "rr"], 1),
        ("d\ndhr Dhr dhr", ["sdh"], 2),
        ("d\ndhr Dhr dhr", ["sdh", ";"], 10),
        ("d\ndhr Dhr dhr", ["sdh", ";,"], 2),
        ("d\ndhr Dhr dhr", ["j$" "Sdh"], 10),
        ("d\ndhr Dhr dhr", ["j$" "Sdh", ";"], 2),
        ("d\ndhr Dhr dhr", ["j$" "Sdh", ";,"], 10),
    ],
)
def test_sneak_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test sneak command."""
    CONF.set(CONF_SECTION, "use_sneak", True)
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.sub_mode is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["F", "r"], 0),
        ("\n", ["j", "F", "r"], 1),
        ("\n r", ["j", "F", "r"], 1),
        ("\n r", ["j", "$", "F", "r"], 2),
        ("\n  r ", ["j", "$", "F", "r"], 3),
        ("\n  rr", ["j", "$", "F", "r"], 3),
        ("\n  rr", ["j", "$", "F", "r", ","], 4),
        ("\n  rr", ["j", "$", "F", "r", ",", ";"], 3),
        ("\n  rr", ["j", "$", "2F", "r"], 4),
    ],
)
def test_F_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test F command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.sub_mode is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["t", "r"], 0),
        ("\n", ["j", "t", "r"], 1),
        ("\n r", ["j", "t", "r"], 1),
        ("\n  r", ["j", "t", "r"], 2),
        ("\n  rr", ["j", "t", "r", ";"], 3),
        ("\n  rrr", ["j", "t", "r", "2;"], 3),
        ("\n  rrr", ["j", "t", "r", ";", ";"], 4),
        ("\n  rrr", ["j", "t", "r", ";", ";", ","], 4),
        ("\n  rrrr", ["j", "t", "r", "4;"], 5),
        ("\n  rrrr", ["j", "t", "r", "4;", ","], 4),
        ("\n  r\n", ["j", "t", "r"], 2),
        ("\n  rr\n", ["j", "t", "r", ";"], 3),
        ("\n  rr\n", ["j", "t", "r", ";", ","], 3),
        ("\n  rrr\n", ["j", "t", "r", "2;"], 3),
        ("\n  rrr\n", ["j", "t", "r", ";", ";"], 4),
        ("\n  rrr\n", ["j", "t", "r", ";", ";", ","], 4),
        ("\n  rrrr\n", ["j", "t", "r", "4;"], 5),
        ("\n  rrrr\n", ["j", "t", "r", "4;", ","], 4),
        ("\n  r r r r", ["j", "2t", "r"], 4),
        ("\n  r r r r", ["j", "2t", "r", "0"], 1),
        ("\n  r r r r", ["j", "2t", "r", "0", ";"], 2),
        ("\n  r r r r", ["j", "2t", "r", "0", "2;"], 4),
    ],
)
def test_t_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test t command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.sub_mode is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["T", "r"], 0),
        ("r\n", ["j", "T", "r"], 2),
        ("r ", ["T", "r"], 0),
        ("r ", ["T", "r", ";"], 0),
        ("r ", ["T", "r", ";", ","], 0),
        ("\n r ", ["j", "$", "T", "r"], 3),
        ("\n rr ", ["j", "$", "T", "r"], 4),
        ("\n rr ", ["j", "$", "2T", "r"], 3),
        ("\n rrr ", ["j", "$", "2T", "r", ";"], 3),
        ("\n rrr r", ["j", "$", "2T", "r", ";", ","], 5),
        ("\n r \n", ["j", "$", "T", "r"], 3),
        ("\n rr \n", ["j", "$", "T", "r"], 4),
        ("\n rr \n", ["j", "$", "2T", "r"], 3),
        ("\n rrr \n", ["j", "$", "2T", "r", ";"], 3),
        ("\n rrr r\n", ["j", "$", "2T", "r", ";", ","], 5),
    ],
)
def test_T_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test T command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.sub_mode is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ["r", "r"], "", 0),
        ("\n", ["j", "r", "r"], "\n", 1),
        ("\n\na", ["j", "r", "r"], "\n\na", 1),
        ("a", ["r", "r"], "r", 0),
        ("a", ["2r", "r"], "a", 0),
        ("aa", ["2r", "r"], "rr", 1),
        (" aa", ["3r", "r"], "rrr", 2),
        (" aaaa", ["2l", "2r", "r"], " arra", 3),
        (" aaaa", ["2l", "2r", "r", "."], " arrr", 4),
        (" aaaa", ["2l", "2r", "r", "3."], " arra", 3),
    ],
)
def test_r_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test r command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected


def test_ZZ_cmd(vim_bot):
    """Test ZZ command."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ZZ")
    main.editor.save.assert_called_once_with()
    main.editor.close_file.assert_called_once_with()
    main.editor.save.reset_mock()
    main.editor.close_file.reset_mock()


def test_ZQ_cmd(vim_bot):
    """Test ZQ command."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ZQ")
    main.editor.close_file.assert_called_once_with()
    main.editor.close_file.reset_mock()


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("ABcDE", ["2l", "g", "u", "u"], "abcde", 0),
        (" ABCDE\nA", ["l", "g", "u", "u"], " abcde\nA", 0),
        ("AB\nA\nA\nB\nC\nD\nE\n", ["l", "2g", "u", "3u"], "ab\na\na\nb\nc\nd\nE\n", 1),
        (
            "AB\nA\nA\nB\nC\nD\nE\n",
            ["l", "2g", "u", "3u", "j", "."],
            "ab\na\na\nb\nc\nd\ne\n",
            3,
        ),
        ("ABCDE", ["$", "g", "u", "0"], "abcdE", 0),
        ("ABCDE", ["g", "u", "l"], "aBCDE", 0),
        ("ABCDE", ["g", "u", "2l"], "abCDE", 0),
        ("ABCDE", ["2g", "u", "2l"], "abcdE", 0),
        ("ABCDE", ["2g", "u", "2l", "l", "."], "abcde", 1),
        ("AB\nC\nD\nE\nF\nG\n", ["l", "g", "u", "j"], "ab\nc\nD\nE\nF\nG\n", 1),
        ("AB\nC\nD\nE\nF\nG\n", ["l", "g", "u", "2j"], "ab\nc\nd\nE\nF\nG\n", 1),
        ("AB\nC\nD\nE\nF\nG\n", ["l", "2g", "u", "2j"], "ab\nc\nd\ne\nf\nG\n", 1),
        (
            "AB\nC\nD\nE\nF\nG\n",
            ["l", "2g", "u", "2j", "j", "."],
            "ab\nc\nd\ne\nf\ng\n",
            3,
        ),
        ("AB\nC\nD\nE\nF\nG\n", ["4j", "g", "u", "k"], "AB\nC\nD\ne\nf\nG\n", 7),
        ("AB\nC\nD\nE\nF\nG\n", ["4j", "g", "u", "2k"], "AB\nC\nd\ne\nf\nG\n", 5),
        ("AB\nC\nD\nE\nF\nG\n", ["4j", "2g", "u", "2k"], "ab\nc\nd\ne\nf\nG\n", 0),
        ("ABCDE", ["$", "g", "u", "h"], "ABCdE", 3),
        ("ABCDE", ["$", "g", "u", "2h"], "ABcdE", 2),
        ("ABCDE", ["$", "2g", "u", "2h"], "abcdE", 0),
        ("ABCDE", ["g", "u", "$"], "abcde", 0),
        (" ABCDE", ["$", "g", "u", "^"], " abcdE", 1),
        ("ABCDE", ["g", "u", "w"], "abcde", 0),
        ("A B C D E", ["g", "u", "w"], "a B C D E", 0),
        ("A B C D E", ["g", "u", "2w"], "a b C D E", 0),
        ("A B C D E", ["2g", "u", "2w"], "a b c d E", 0),
        ("AbC.DE", ["g", "u", "W"], "abc.de", 0),
        ("AbC.DE", ["g", "u", "e"], "abc.DE", 0),
        ("AbC.DE", ["g", "u", "2e"], "abc.DE", 0),
        ("AbC.DE", ["g", "u", "3e"], "abc.de", 0),
        ("A B C D E ", ["$", "g", "u", "b"], "A B C D e ", 8),
        ("A B C D E ", ["$", "g", "u", "2b"], "A B C d e ", 6),
        ("A B C D E ", ["$", "2g", "u", "2b"], "A b c d e ", 2),
        ("A.B.C D.E ", ["$", "g", "u", "B"], "A.B.C d.e ", 6),
        ("A.B.C D.E ", ["$", "2g", "u", "B"], "a.b.c d.e ", 0),
        ("AB\nC\nD\nE\nF\nG", ["l", "g", "u", "G"], "ab\nc\nd\ne\nf\ng", 1),
        ("AB\nC\nD\nE\nF\nG", ["l", "g", "u", "2G"], "ab\nc\nD\nE\nF\nG", 1),
        ("AB\nC\nD\nE\nF\nG", ["l", "2g", "u", "2G"], "ab\nc\nd\ne\nF\nG", 1),
        ("AB\nC\nD\nE\nF\nG", ["l", "g", "u", "g", "g"], "ab\nC\nD\nE\nF\nG", 0),
        ("AB\nC\nD\nE\nF\nG", ["l", "g", "u", "2g", "g"], "ab\nc\nD\nE\nF\nG", 1),
        ("AB\nC\nD\nE\nF\nG", ["l", "2g", "u", "2g", "g"], "ab\nc\nd\ne\nF\nG", 1),
        ("AB(CD)", ["l", "g", "u", "%"], "Ab(cd)", 1),
        ("ABCD ", ["g", "u", "f", "D"], "abcd ", 0),
        ("ABCD", ["g", "u", "f", "F"], "ABCD", 0),
        ("ABCD", ["g", "u", "t", "D"], "abcD", 0),
        ("ABCD", ["$", "g", "u", "F", "A"], "abcD", 0),
        ("ABCD", ["$", "g", "u", "T", "A"], "AbcD", 1),
        ("AAAA", ["g", "u", "2f", "A"], "aaaA", 0),
        ("AAAAAAA", ["2g", "u", "2f", "A"], "aaaaaAA", 0),
        ("AAAAAAA", ["2g", "u", "2f", "A", "4l", "g", "u", ";"], "aaaaaaA", 4),
        ("AAAAAAA", ["2g", "u", "2f", "A", "4l", "g", "u", ";"], "aaaaaaA", 4),
        ('"AaA" "AaA"', ["2l", "g", "u", "i", '"', "6l", "."], '"aaa" "aaa"', 7),
        ("'AaA' 'AaA'", ["2l", "g", "u", "a", "'", "7l", "."], "'aaa' 'aaa'", 5),
        ("'AaA' 'AaA'", ["2l", "g", "u", "i", "w", "7l", "."], "'aaa' 'aaa'", 7),
        ("[AaA] [AaA]", ["2l", "g", "u", "i", "[", "7l", "."], "[aaa] [aaa]", 7),
        ("[AaA] [AaA]", ["2l", "g", "u", "a", "[", "7l", "."], "[aaa] [aaa]", 6),
        ("(AaA) (AaA)", ["2l", "g", "u", "i", "b", "7l", "."], "(aaa) (aaa)", 7),
        ("(AaA) (AaA)", ["2l", "g", "u", "a", "b", "7l", "."], "(aaa) (aaa)", 6),
    ],
)
def test_gu_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gu command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("abCde", ["2l", "g", "U", "U"], "ABCDE", 0),
        (" abcde\na", ["l", "g", "U", "U"], " ABCDE\na", 0),
        ("ab\na\na\nb\nc\nd\ne\n", ["l", "2g", "U", "3U"], "AB\nA\nA\nB\nC\nD\ne\n", 1),
        (
            "ab\na\na\nb\nc\nd\ne\n",
            ["l", "2g", "U", "3U", "j", "."],
            "AB\nA\nA\nB\nC\nD\nE\n",
            3,
        ),
        ("abcde", ["$", "g", "U", "0"], "ABCDe", 0),
        ("abcde", ["g", "U", "l"], "Abcde", 0),
        ("abcde", ["g", "U", "2l"], "ABcde", 0),
        ("abcde", ["2g", "U", "2l"], "ABCDe", 0),
        ("abcde", ["2g", "U", "2l", "l", "."], "ABCDE", 1),
        ("ab\nc\nd\ne\nf\ng\n", ["l", "g", "U", "j"], "AB\nC\nd\ne\nf\ng\n", 1),
        ("ab\nc\nd\ne\nf\ng\n", ["l", "g", "U", "2j"], "AB\nC\nD\ne\nf\ng\n", 1),
        ("ab\nc\nd\ne\nf\ng\n", ["l", "2g", "U", "2j"], "AB\nC\nD\nE\nF\ng\n", 1),
        (
            "ab\nc\nd\ne\nf\ng\n",
            ["l", "2g", "U", "2j", "j", "."],
            "AB\nC\nD\nE\nF\nG\n",
            3,
        ),
        ("ab\nc\nd\ne\nf\ng\n", ["4j", "g", "U", "k"], "ab\nc\nd\nE\nF\ng\n", 7),
        ("ab\nc\nd\ne\nf\ng\n", ["4j", "g", "U", "2k"], "ab\nc\nD\nE\nF\ng\n", 5),
        ("ab\nc\nd\ne\nf\ng\n", ["4j", "2g", "U", "2k"], "AB\nC\nD\nE\nF\ng\n", 0),
        ("abcde", ["$", "g", "U", "h"], "abcDe", 3),
        ("abcde", ["$", "g", "U", "2h"], "abCDe", 2),
        ("abcde", ["$", "2g", "U", "2h"], "ABCDe", 0),
        ("abcde", ["g", "U", "$"], "ABCDE", 0),
        (" abcde", ["$", "g", "U", "^"], " ABCDe", 1),
        ("abcde", ["g", "U", "w"], "ABCDE", 0),
        ("a b c d e", ["g", "U", "w"], "A b c d e", 0),
        ("a b c d e", ["g", "U", "2w"], "A B c d e", 0),
        ("a b c d e", ["2g", "U", "2w"], "A B C D e", 0),
        ("aBc.de", ["g", "U", "W"], "ABC.DE", 0),
        ("a b c d e ", ["$", "g", "U", "b"], "a b c d E ", 8),
        ("a b c d e ", ["$", "g", "U", "2b"], "a b c D E ", 6),
        ("a b c d e ", ["$", "2g", "U", "2b"], "a B C D E ", 2),
        ("a.b.c d.e ", ["$", "g", "U", "B"], "a.b.c D.E ", 6),
        ("a.b.c d.e ", ["$", "g", "U", "2B"], "A.B.C D.E ", 0),
        ("ab\nc\nd\ne\nf\ng", ["l", "g", "U", "G"], "AB\nC\nD\nE\nF\nG", 1),
        ("ab\nc\nd\ne\nf\ng", ["l", "g", "U", "2G"], "AB\nC\nd\ne\nf\ng", 1),
        ("ab\nc\nd\ne\nf\ng", ["l", "2g", "U", "2G"], "AB\nC\nD\nE\nf\ng", 1),
        ("ab\nc\nd\ne\nf\ng", ["l", "g", "U", "g", "g"], "AB\nc\nd\ne\nf\ng", 0),
        ("ab\nc\nd\ne\nf\ng", ["l", "g", "U", "2g", "g"], "AB\nC\nd\ne\nf\ng", 1),
        ("ab\nc\nd\ne\nf\ng", ["l", "2g", "U", "2g", "g"], "AB\nC\nD\nE\nf\ng", 1),
        ("ab(cd)", ["l", "g", "U", "%"], "aB(CD)", 1),
        ("abcd ", ["g", "U", "f", "d"], "ABCD ", 0),
        ("abcd ", ["g", "U", "f", "D"], "abcd ", 0),
        ("abcd", ["g", "U", "t", "d"], "ABCd", 0),
        ("abcd", ["$", "g", "U", "F", "a"], "ABCd", 0),
        ("abcd", ["$", "g", "U", "T", "a"], "aBCd", 1),
        ("aaaa", ["g", "U", "2f", "a"], "AAAa", 0),
        ("aaaaaaa", ["2g", "U", "2f", "a"], "AAAAAaa", 0),
        ("aaaaaaa", ["2g", "U", "2f", "a", "4l", "g", "U", ";"], "AAAAAAa", 4),
        ("aaaaaaa", ["2g", "U", "2f", "a", "4l", "g", "U", ";"], "AAAAAAa", 4),
        ('"aAa" "aAa"', ["2l", "g", "U", "i", '"', "6l", "."], '"AAA" "AAA"', 7),
        ("'aAa' 'aAa'", ["2l", "g", "U", "a", "'", "7l", "."], "'AAA' 'AAA'", 5),
        ('"aAa" "aAa"', ["2l", "g", "U", "i", "w", "6l", "."], '"AAA" "AAA"', 7),
        ("{aAa} {aAa}", ["2l", "g", "U", "i", "{", "6l", "."], "{AAA} {AAA}", 7),
        ("{aAa} {aAa}", ["2l", "g", "U", "a", "{", "6l", "."], "{AAA} {AAA}", 6),
        ("{aAa} {aAa}", ["2l", "g", "U", "i", "B", "6l", "."], "{AAA} {AAA}", 7),
        ("{aAa} {aAa}", ["2l", "g", "U", "a", "B", "6l", "."], "{AAA} {AAA}", 6),
    ],
)
def test_gU_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gU command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("abCde", ["2l", "g", "~", "~"], "ABcDE", 0),
        (" abCde\na", ["l", "g", "~", "~"], " ABcDE\na", 0),
        ("ab\na\na\nb\nc\nd\ne\n", ["l", "2g", "~", "3~"], "AB\nA\nA\nB\nC\nD\ne\n", 1),
        (
            "ab\na\na\nb\nc\nd\ne\n",
            ["l", "2g", "~", "3~", "j", "."],
            "AB\na\na\nb\nc\nd\nE\n",
            3,
        ),
        ("abcde", ["$", "g", "~", "0"], "ABCDe", 0),
        ("abcde", ["g", "~", "l"], "Abcde", 0),
        ("abcde", ["g", "~", "2l"], "ABcde", 0),
        ("abcde", ["2g", "~", "2l"], "ABCDe", 0),
        ("abcde", ["2g", "~", "2l", "l", "."], "AbcdE", 1),
        ("ab\nc\nd\ne\nf\ng\n", ["l", "g", "~", "j"], "AB\nC\nd\ne\nf\ng\n", 1),
        ("ab\nc\nd\ne\nf\ng\n", ["l", "g", "~", "2j"], "AB\nC\nD\ne\nf\ng\n", 1),
        ("ab\nc\nd\ne\nf\ng\n", ["l", "2g", "~", "2j"], "AB\nC\nD\nE\nF\ng\n", 1),
        (
            "ab\nc\nd\ne\nf\ng\n",
            ["l", "2g", "~", "2j", "j", "."],
            "AB\nc\nd\ne\nf\nG\n",
            3,
        ),
        ("ab\nc\nd\ne\nf\ng\n", ["4j", "g", "~", "k"], "ab\nc\nd\nE\nF\ng\n", 7),
        ("ab\nc\nd\ne\nf\ng\n", ["4j", "g", "~", "2k"], "ab\nc\nD\nE\nF\ng\n", 5),
        ("ab\nc\nd\ne\nf\ng\n", ["4j", "2g", "~", "2k"], "AB\nC\nD\nE\nF\ng\n", 0),
        ("abcde", ["$", "g", "~", "h"], "abcDe", 3),
        ("abcde", ["$", "g", "~", "2h"], "abCDe", 2),
        ("abcde", ["$", "2g", "~", "2h"], "ABCDe", 0),
        ("abcde", ["g", "~", "$"], "ABCDE", 0),
        (" abcde", ["$", "g", "~", "^"], " ABCDe", 1),
        ("abcde", ["g", "~", "w"], "ABCDE", 0),
        ("aBc.de", ["g", "~", "W"], "AbC.DE", 0),
        ("a b c d e", ["g", "~", "w"], "A b c d e", 0),
        ("a b c d e", ["g", "~", "2w"], "A B c d e", 0),
        ("a b c d e", ["2g", "~", "2w"], "A B C D e", 0),
        ("a b c d e ", ["$", "g", "~", "b"], "a b c d E ", 8),
        ("a b c d e ", ["$", "g", "~", "2b"], "a b c D E ", 6),
        ("a b c d e ", ["$", "2g", "~", "2b"], "a B C D E ", 2),
        ("a b c d.e ", ["$", "g", "~", "B"], "a b c D.E ", 6),
        ("ab\nc\nd\ne\nf\ng", ["l", "g", "~", "G"], "AB\nC\nD\nE\nF\nG", 1),
        ("ab\nc\nd\ne\nf\ng", ["l", "g", "~", "2G"], "AB\nC\nd\ne\nf\ng", 1),
        ("ab\nc\nd\ne\nf\ng", ["l", "2g", "~", "2G"], "AB\nC\nD\nE\nf\ng", 1),
        ("ab\nc\nd\ne\nf\ng", ["l", "g", "~", "g", "g"], "AB\nc\nd\ne\nf\ng", 0),
        ("ab\nc\nd\ne\nf\ng", ["l", "g", "~", "2g", "g"], "AB\nC\nd\ne\nf\ng", 1),
        ("ab\nc\nd\ne\nf\ng", ["l", "2g", "~", "2g", "g"], "AB\nC\nD\nE\nf\ng", 1),
        ("ab(cd)", ["l", "g", "~", "%"], "aB(CD)", 1),
        ("abcd ", ["g", "~", "f", "d"], "ABCD ", 0),
        ("abcd ", ["g", "~", "f", "D"], "abcd ", 0),
        ("abcd", ["g", "~", "t", "d"], "ABCd", 0),
        ("abcd", ["$", "g", "~", "F", "a"], "ABCd", 0),
        ("abcd", ["$", "g", "~", "T", "a"], "aBCd", 1),
        ("aaaa", ["g", "~", "2f", "a"], "AAAa", 0),
        ("aaaaaaa", ["2g", "~", "2f", "a"], "AAAAAaa", 0),
        ("aaaaaaa", ["2g", "~", "2f", "a", "4l", "g", "~", ";"], "AAAAaAa", 4),
        ('"aAa" "aAa"', ["2l", "g", "~", "i", '"', "6l", "."], '"AaA" "AaA"', 7),
        ('"aAa" "aAa"', ["2l", "g", "~", "a", '"', "7l", "."], '"AaA" "AaA"', 5),
        ('"aAa" "aAa"', ["2l", "g", "~", "i", "w", "6l", "."], '"AaA" "AaA"', 7),
        ("(aAa) (aAa)", ["2l", "g", "~", "i", "(", "6l", "."], "(AaA) (AaA)", 7),
        ("(aAa) (aAa)", ["2l", "g", "~", "a", "(", "7l", "."], "(AaA) (AaA)", 6),
    ],
)
def test_gtilde_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test g~ command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", [">", ">"], "", 0),
        ("abcde", ["2l", ">", ">"], "    abcde", 4),
        ("abcde", ["2l", ">", "%"], "abcde", 2),
        (" abcde\na", ["l", ">", ">"], "     abcde\na", 5),
        ("a\n\na", ["l", "3>", ">"], "    a\n\n    a", 4),
        (
            "ab\na\na\nb\nc\nd\ne\n",
            ["l", "2>", "3>"],
            "    ab\n    a\n    a\n    b\n    c\n    d\ne\n",
            4,
        ),
        (
            "ab\na\na\nb\nc\nd\ne\n",
            ["l", "2>", "3>", "j", "."],
            "    ab\n        a\n        a\n        b\n        c\n        d\n    e\n",
            15,
        ),
        ("ab\nc\nd\ne\nf\ng\n", ["l", ">", "j"], "    ab\n    c\nd\ne\nf\ng\n", 4),
        ("ab\nc\nd\ne\nf\ng\n", ["l", ">", "2j"], "    ab\n    c\n    d\ne\nf\ng\n", 4),
        (
            "ab\nc\nd\ne\nf\ng\n",
            ["l", "2>", "2>", "j", "."],
            "    ab\n        c\n        d\n        e\n    f\ng\n",
            15,
        ),
        ("ab\nc\nd\ne\nf\ng\n", ["4j", ">", "k"], "ab\nc\nd\n    e\n    f\ng\n", 11),
        (
            "ab\nc\nd\ne\nf\ng\n",
            ["4j", ">", "2k"],
            "ab\nc\n    d\n    e\n    f\ng\n",
            9,
        ),
        (
            "ab\nc\nd\ne\nf\ng\n",
            ["4j", "2>", "2k"],
            "    ab\n    c\n    d\n    e\n    f\ng\n",
            4,
        ),
        (
            "ab\nc\nd\ne\nf\ng",
            ["l", ">", "G"],
            "    ab\n    c\n    d\n    e\n    f\n    g",
            4,
        ),
        ("ab\nc\nd\ne\nf\ng", ["l", ">", "2G"], "    ab\n    c\nd\ne\nf\ng", 4),
        (
            "ab\nc\nd\ne\nf\ng",
            ["l", "2>", "2G"],
            "    ab\n    c\n    d\n    e\nf\ng",
            4,
        ),
        ("ab\nc\nd\ne\nf\ng", ["l", ">", "g", "g"], "    ab\nc\nd\ne\nf\ng", 4),
        ("ab\nc\nd\ne\nf\ng", ["l", ">", "2g", "g"], "    ab\n    c\nd\ne\nf\ng", 4),
        (
            "ab\nc\nd\ne\nf\ng",
            ["l", "2>", "2g", "g"],
            "    ab\n    c\n    d\n    e\nf\ng",
            4,
        ),
    ],
)
def test_greater_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test > command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ["<", "<"], "", 0),
        ("    abcde", ["2l", "<", "<"], "abcde", 0),
        ("    abcde", ["2l", "<", "%"], "    abcde", 2),
        ("   abcde", ["2l", "<", "<"], "abcde", 0),
        (" abcde\na", ["l", "<", "<"], "abcde\na", 0),
        ("    a\n\n    a", ["l", "3<", "<"], "a\n\na", 0),
        (
            "    ab\n    a\n    a\n    b\n    c\n    d\ne\n",
            ["l", "2<", "3<"],
            "ab\na\na\nb\nc\nd\ne\n",
            0,
        ),
        (
            "     ab\n     a\n     a\n     b\n     c\n     d\n     e\n",
            ["l", "2<", "3<", "j", "."],
            " ab\na\na\nb\nc\nd\n e\n",
            4,
        ),
        ("    ab\n    c\nd\ne\nf\ng\n", ["l", "<", "j"], "ab\nc\nd\ne\nf\ng\n", 0),
        ("    ab\n    c\n    d\ne\nf\ng\n", ["l", "<", "2j"], "ab\nc\nd\ne\nf\ng\n", 0),
        (
            "     ab\n     c\n     d\n     e\n     f\n g\n",
            ["l", "2<", "2<", "j", "."],
            " ab\nc\nd\ne\n f\n g\n",
            4,
        ),
        (" ab\n c\n d\n e\n f\n g\n", ["4j", "<", "k"], " ab\n c\n d\ne\nf\n g\n", 10),
        (" ab\n c\n d\n e\n f\n g\n", ["4j", "<", "2k"], " ab\n c\nd\ne\nf\n g\n", 7),
        (" ab\n c\n d\n e\n f\n g\n", ["4j", "2<", "2k"], "ab\nc\nd\ne\nf\n g\n", 0),
        (" ab\n c\n d\n e\n f\n g", ["l", "<", "G"], "ab\nc\nd\ne\nf\ng", 0),
        (" ab\n c\n d\n e\n f\n g", ["l", "<", "2G"], "ab\nc\n d\n e\n f\n g", 0),
        (" ab\n c\n d\n e\n f\n g", ["l", "2<", "2G"], "ab\nc\nd\ne\n f\n g", 0),
        (" ab\n c\n d\n e\n f\n g", ["l", "<", "g", "g"], "ab\n c\n d\n e\n f\n g", 0),
        (" ab\n c\n d\n e\n f\n g", ["l", "<", "2g", "g"], "ab\nc\n d\n e\n f\n g", 0),
        (" ab\n c\n d\n e\n f\n g", ["l", "2<", "2g", "g"], "ab\nc\nd\ne\n f\n g", 0),
    ],
)
def test_less_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test < command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "cmd_list, register_name",
    [
        (
            ['"', "+", "l"],
            "+",
        ),
        (
            ["v", '"', "0", "l"],
            "0",
        ),
        (
            ["V", '"', "a", "l"],
            "a",
        ),
    ],
)
def test_get_register_name(vim_bot, cmd_list, register_name):
    """Test get_register name."""
    _, _, _, vim, qtbot = vim_bot

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert vim.vim_cmd.vim_status.get_register_name() == register_name


def test_clipboard(vim_bot):
    """Test clipboard."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    clipboard = QApplication.clipboard()
    clipboard.setText("dhrwodn")

    cmd_line = vim.vim_cmd.commandline

    qtbot.keyClicks(cmd_line, '"')
    qtbot.keyClicks(cmd_line, "+")
    qtbot.keyClicks(cmd_line, "p")
    assert editor.toPlainText() == "dhrwodn"

    editor.set_text("1dhrwodn")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()
    qtbot.keyClicks(cmd_line, '"')
    qtbot.keyClicks(cmd_line, "+")
    qtbot.keyClicks(cmd_line, "y")
    qtbot.keyClicks(cmd_line, "y")

    assert clipboard.text() == "1dhrwodn\n"


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, register_name, text_yanked",
    [
        ("a", ["y", "l"], 0, '"', "a"),
        ("a", ["y", Qt.Key_Space], 0, '"', "a"),
        ("ab", ["l", "y", Qt.Key_Backspace], 0, '"', "a"),
        ("a", ["y", ","], 0, '"', ""),
        ("a", ["y", "i", "b"], 0, '"', ""),
        ("abcd", ["$", "y", "2h"], 1, '"', "bc"),
        ("a\nb", ["y", "j"], 0, '"', "a\nb\n"),
        ("a\nb", ["y", Qt.Key_Enter], 0, '"', "a\nb\n"),
        ("  a\n b", ["j", "l", "y", "k"], 1, '"', "  a\n b\n"),
        ("abcd", ["y", "$"], 0, '"', "abcd"),
        ("abcd", ["$", "y", "^"], 0, '"', "abc"),
        ("a b", ["y", "w"], 0, '"', "a "),
        ("  abcd\n b", ["3l", "y", "w"], 3, '"', "bcd"),
        ("a.dk b", ["y", "W"], 0, '"', "a.dk "),
        ("  abcd.wkdn\n b", ["3l", "y", "W"], 3, '"', "bcd.wkdn"),
        ("abcd", ["$", "y", "b"], 0, '"', "abc"),
        ("ab.cd", ["$", "y", "b"], 3, '"', "c"),
        ("ab.cd", ["$", "y", "B"], 0, '"', "ab.c"),
        ("  abcd \n b", ["3l", "y", "i", "w"], 2, '"', "abcd"),
        ("  abcd\n b\nc", ["3l", "y", "3i", "W"], 2, '"', "abcd\n b"),
        ("abcd\ne\nf\n", ["y", "y"], 0, '"', "abcd\n"),
        ("abcd", ["y", "y"], 0, '"', "abcd\n"),
        ("abcd\ne\nf\n", ["2y", "y"], 0, '"', "abcd\ne\n"),
        ("AB\nC\nD\nE", ["l", "y", "G"], 1, '"', "AB\nC\nD\nE\n"),
        ("AB\nC\nD\nE", ["l", "y", "2G"], 1, '"', "AB\nC\n"),
        ("AB\nC\nD\nE", ["l", "y", "g", "g"], 0, '"', "AB\n"),
        ("AB\nC\nD\nE", ["l", "y", "2g", "g"], 1, '"', "AB\nC\n"),
        ("AB(CD)", ["l", "y", "%"], 1, '"', "B(CD)"),
        ("AB(CD)", ["$", "y", "%"], 2, '"', "(CD)"),
        ("ABCD", ["y", "f", "D"], 0, '"', "ABCD"),
        ("ABCD", ["y", "f", "F"], 0, '"', ""),
        ("ABCD", ["y", "t", "D"], 0, '"', "ABC"),
        ("ABCD", ["$", "y", "F", "A"], 0, '"', "ABC"),
        ("ABCD", ["$", "y", "T", "A"], 1, '"', "BC"),
        ("AAAA", ["y", "2f", "A"], 0, '"', "AAA"),
        (' "AAA"', ["y", "i", '"'], 2, '"', "AAA"),
        (' "AAA"', ["y", "a", '"'], 0, '"', ' "AAA"'),
        (' "AAA" ', ["y", "a", '"'], 1, '"', '"AAA" '),
        ("(AAA)", ["y", "i", "("], 1, '"', "AAA"),
        ("(AAA)", ["y", "a", "("], 0, '"', "(AAA)"),
        ("(AAA)", ["%", "y", "a", ")"], 0, '"', "(AAA)"),
        ("dhr dhr", ["y", "*"], 0, '"', "dhr "),
        ("dhr dhr", ["w", "y", "#"], 0, '"', "dhr "),
        ("dhr dhr", ["yzdh"], 0, '"', "dhr "),
    ],
)
def test_y_cmd_in_normal(
    vim_bot, text, cmd_list, cursor_pos, register_name, text_yanked
):
    """Test y command in normal."""
    _, _, editor, vim, qtbot = vim_bot

    CONF.set(CONF_SECTION, "leader_key", "F1")
    CONF.set(CONF_SECTION, "use_sneak", True)
    vim.apply_plugin_settings("")

    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[register_name]
    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked
    if register_name == '"':
        reg0 = vim.vim_cmd.vim_status.register_dict["0"]
        assert reg0.content == text_yanked


def test_highlight_yank(vim_bot):
    """Test highlight yank."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("foo")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    CONF.set(CONF_SECTION, "highlight_yank", False)
    vim.apply_plugin_settings(None)

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "yy")

    sel = editor.get_extra_selections("hl_yank")
    assert len(sel) == 0

    CONF.set(CONF_SECTION, "highlight_yank", True)
    vim.apply_plugin_settings(None)

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "yy")

    sel = editor.get_extra_selections("hl_yank")
    assert len(sel) > 0


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected",
    [
        ("ak", ["p"], 0, "ak"),
        ("ak", ["v", "l", "y", "p"], 2, "aakk"),
        ("ak", ["v", "l", "y", "2p"], 4, "aakakk"),
        ("a\n", ["v", "y", "j", "p"], 2, "a\na"),
        ("a\n", ["v", "y", "j", "2p"], 3, "a\naa"),
        ("a", ["v", '"', "0", "y", "p"], 0, "a"),
        ("a", ["v", '"', "0", "y", '"', "0", "p"], 1, "aa"),
        ("a", ["V", "y", "p"], 2, "a\na"),
        ("a\n", ["V", "y", "p"], 2, "a\na\n"),
        ("a\n", ["V", "y", "2p"], 2, "a\na\na\n"),
        ("a\n", ["V", "y", "j", "p"], 3, "a\n\na"),
        ("a\n", ["V", "y", "j", "2p"], 3, "a\n\na\na"),
        ("\na", ["j", "V", "y", "k", "p"], 1, "\na\na"),
        ("a\na\n", ["V", "j", "y", "2j", "p"], 5, "a\na\n\na\na"),
        (" a\n a\n", ["V", "j", "y", "2j", "p"], 8, " a\n a\n\n a\n a"),
        ("a\nb\n", ["y", "y", "j", "d", "d", "p"], 3, "a\n\nb"),
        ("a\nb\n", ["y", "y", "j", "d", "d", "p", '"', "0", "p"], 5, "a\n\nb\na"),
    ],
)
def test_p_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected):
    """Test p command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected",
    [
        ("ak", ["v", "l", "y", "P"], 1, "akak"),
        ("ak", ["v", "l", "y", "2P"], 3, "akakak"),
        ("a\n", ["v", "y", "j", "P"], 2, "a\na"),
        ("a", ["v", '"', "0", "y", "P"], 0, "a"),
        ("a", ["V", "y", "P"], 0, "a\na"),
        ("a\n", ["V", "y", "P"], 0, "a\na\n"),
        ("a\n", ["V", "y", "2P"], 0, "a\na\na\n"),
        ("a\n", ["V", "y", "j", "P"], 2, "a\na\n"),
        ("\na", ["j", "V", "y", "k", "P"], 0, "a\n\na"),
        ("\na", ["j", "V", "y", "P"], 1, "\na\na"),
    ],
)
def test_P_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected):
    """Test P command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ("ab", ["s"], 0, "b", '"', "a"),
        ("ab", ["l", "s"], 1, "a", '"', "b"),
        ("ab", ["2s"], 0, "", '"', "ab"),
    ],
)
def test_s_cmd_in_normal(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test s command in normal."""
    CONF.set(CONF_SECTION, "use_sneak", False)
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert reg.content == text_yanked
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ("  ab", ["S"], 2, "  ", '"', "  ab\n"),
        ("  ab\n cc\ndd", ["j", "2S"], 6, "  ab\n ", '"', " cc\ndd\n"),
    ],
)
def test_S_cmd_in_normal(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test S command in normal."""
    CONF.set(CONF_SECTION, "use_sneak", False)
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert reg.content == text_yanked
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ("ab", ["x"], 0, "b", '"', "a"),
        ("ab", ["l", "x"], 0, "a", '"', "b"),
        ("ab", ["2x"], 0, "", '"', "ab"),
    ],
)
def test_x_cmd_in_normal(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test x command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert reg.content == text_yanked
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ("ab", ["D"], 0, "", '"', "ab"),
        ("ab\n", ["D"], 0, "\n", '"', "ab"),
        ("ab\n", ["l", "D"], 0, "a\n", '"', "b"),
        ("ab\ncd\n", ["l", "2D"], 0, "a\n", '"', "b\ncd"),
        ("abcdefg", ["3l", "D"], 2, "abc", '"', "defg"),
        ("abcdefg", ["3l", "D", "h", "."], 0, "a", '"', "bc"),
    ],
)
def test_D_cmd_in_normal(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test D command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert reg.content == text_yanked
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ("ab", ["C"], 0, "", '"', "ab"),
        ("ab\n", ["C"], 0, "\n", '"', "ab"),
        ("ab\n", ["l", "C"], 1, "a\n", '"', "b"),
        ("ab\ncd\n", ["l", "2C"], 1, "a\n", '"', "b\ncd"),
    ],
)
def test_C_cmd_in_normal(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test C command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert reg.content == text_yanked
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ("a", ["c", "l"], 0, "", '"', "a"),
        ("abcd", ["$", "c", "2h"], 1, "ad", '"', "bc"),
        ("a\nb", ["c", "j"], 0, "", '"', "a\nb\n"),
        ("  a\n b", ["j", "l", "c", "k"], 0, "", '"', "  a\n b\n"),
        (
            "  12\n  34\n  56\n  78",
            ["j", "c", "j"],
            5,
            "  12\n\n  78",
            '"',
            "  34\n  56\n",
        ),
        (
            "  12\n  34\n  56\n  78",
            ["2j", "c", "k"],
            5,
            "  12\n\n  78",
            '"',
            "  34\n  56\n",
        ),
        ("abcd", ["c", "$"], 0, "", '"', "abcd"),
        ("abcd", ["$", "c", "^"], 0, "d", '"', "abc"),
        ("a b", ["c", "w"], 0, " b", '"', "a"),
        ("a b", ["l", "c", "w"], 1, "ab", '"', " "),
        ("a b c ", ["c", "2w"], 0, " c ", '"', "a b"),
        ("a b c ", ["c", "3w"], 0, " ", '"', "a b c"),
        ("a\n b", ["c", "2w"], 0, "", '"', "a\n b"),
        ("a\nb\nc", ["c", "3w"], 0, "", '"', "a\nb\nc"),
        ("a\n b\nc", ["c", "3w"], 0, "", '"', "a\n b\nc"),
        ("a.dk b", ["c", "W"], 0, " b", '"', "a.dk"),
        (" a.dk b", ["c", "W"], 0, "a.dk b", '"', " "),
        ("a.dk b dd", ["c", "2W"], 0, " dd", '"', "a.dk b"),
        ("a.dk b dd", ["c", "2W"], 0, " dd", '"', "a.dk b"),
        ("b\n a.bc d", ["c", "2W"], 0, " d", '"', "b\n a.bc"),
        ("\n a.bc d", ["c", "2W"], 0, " d", '"', "\n a.bc"),
        ("a.dk\nb", ["c", "e"], 0, "dk\nb", '"', "a."),
        ("a.dk\nb", ["c", "2e"], 0, "\nb", '"', "a.dk"),
        ("abcd", ["$", "c", "b"], 0, "d", '"', "abc"),
        ("ab.cd", ["$", "c", "b"], 3, "ab.d", '"', "c"),
        ("ab.cd", ["$", "c", "B"], 0, "d", '"', "ab.c"),
        ("  abcd \n b", ["3l", "c", "i", "w"], 2, "   \n b", '"', "abcd"),
        ("  abcd \n b", ["3l", "c", "a", "w"], 2, "  \n b", '"', "abcd "),
        ("  12\n  78", ["j", "c", "c"], 5, "  12\n", '"', "  78\n"),
        ("  12\n  78", ["c", "c"], 0, "\n  78", '"', "  12\n"),
        ("abcd\ne\nf\n", ["c", "c"], 0, "\ne\nf\n", '"', "abcd\n"),
        ("abcd", ["c", "c"], 0, "", '"', "abcd\n"),
        ("abcd\ne\nf\n", ["2c", "c"], 0, "\nf\n", '"', "abcd\ne\n"),
        ("AB\nC\nD\nE", ["l", "c", "G"], 0, "", '"', "AB\nC\nD\nE\n"),
        ("AB\nC\nD\nE", ["l", "c", "2G"], 0, "\nD\nE", '"', "AB\nC\n"),
        ("AB\n C\nD\nE", ["l", "c", "g", "g"], 0, "\n C\nD\nE", '"', "AB\n"),
        ("AB\nC\nD\nE", ["l", "c", "2g", "g"], 0, "\nD\nE", '"', "AB\nC\n"),
        ("AB(CD)", ["l", "c", "%"], 1, "A", '"', "B(CD)"),
        ("AB(CD)", ["$", "c", "%"], 2, "AB", '"', "(CD)"),
        ("ABCD", ["c", "f", "D"], 0, "", '"', "ABCD"),
        ("ABCD", ["c", "f", "F"], 0, "ABCD", '"', ""),
        ("ABCD", ["c", "t", "D"], 0, "D", '"', "ABC"),
        ("ABCD", ["$", "c", "F", "A"], 0, "D", '"', "ABC"),
        ("ABCD", ["$", "c", "T", "A"], 1, "AD", '"', "BC"),
        ("AAAA", ["c", "2f", "A"], 0, "A", '"', "AAA"),
        (' "AAA"', ["c", "i", '"'], 2, ' ""', '"', "AAA"),
        (' "AAA"', ["c", "a", '"'], 0, "", '"', ' "AAA"'),
        (' "AAA" ', ["c", "a", '"'], 1, " ", '"', '"AAA" '),
        ("(AAA)", ["c", "i", "("], 1, "()", '"', "AAA"),
        ("(AAA)", ["c", "a", "("], 0, "", '"', "(AAA)"),
        ("(AAA)", ["%", "c", "a", ")"], 0, "", '"', "(AAA)"),
    ],
)
def test_c_cmd_in_normal(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test c command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list1, input_editor, cmd_list2, text_expected",
    [
        ("a\na\n", ["."], "", [], "a\na\n"),
        ("a\na\n", ["c", "w"], "bb", ["j", "."], "bb\nbb\n"),
        ("a\na\n", ["a"], "bb", ["j", "."], "abb\nabb\n"),
        ("aa\naa\n", ["A"], "bb", ["j", "."], "aabb\naabb\n"),
        ("aa\naa\n", ["i"], "bb", ["j", "."], "bbaa\nabba\n"),
        ("aa\naa\n", ["I"], "bb", ["j", "."], "bbaa\nbbaa\n"),
        ("aa\naa\n", ["o"], "bb", ["j", "."], "aa\nbb\naa\nbb\n"),
        ("aa\naa\n", ["O"], "bb", ["2j", "."], "bb\naa\nbb\naa\n"),
        ("aa\naa\n", ["C"], "bb", ["j", "."], "bb\nabb\n"),
        ("aa\naa\n", ["s"], "bb", ["j", "0", "."], "bba\nbba\n"),
        ("  aa\n  aa\n", ["S"], "bb", ["j", "."], "  bb\n  bb\n"),
        ("aa\naa\n", ["v", "c"], "bb", ["j", "0", "."], "bba\nbba\n"),
        ("aa\naa\n", ["v", "c"], "bb", ["j", "0", "."], "bba\nbba\n"),
        ("aa\naa\n", ["v", "s"], "bb", ["j", "0", "."], "bba\nbba\n"),
    ],
)
def test_dot_cmd_with_insert(
    vim_bot, text, cmd_list1, input_editor, cmd_list2, text_expected
):
    """Test . command with insert mode."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()
    CONF.set(CONF_SECTION, "use_sneak", False)
    vim.apply_plugin_settings("")

    cmd_line = vim.vim_cmd.commandline
    cmd_line.setFocus()
    for cmd in cmd_list1:
        qtbot.keyClicks(cmd_line, cmd)

    qtbot.keyClicks(editor, input_editor)

    vim.vim_cmd.vim_status.disconnect_from_editor()  # TODO: Fix
    cmd_line.setFocus()
    for cmd in cmd_list2:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        (
            "a",
            ["n"],
            0,
        ),
        (
            "a",
            ["N"],
            0,
        ),
        (
            "a",
            ["/", "b", Qt.Key_Escape],
            0,
        ),
        (
            "a",
            ["/", "b", "\r"],
            0,
        ),
        (
            "ddd",
            ["/", "d", Qt.Key_Return],
            1,
        ),
        (
            "ddd",
            ["/", "d", Qt.Key_Return, "n"],
            2,
        ),
        (
            "ddd",
            ["/", "d", Qt.Key_Return, "n", "n"],
            0,
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["/", "d", "h", "r", Qt.Key_Return],
            1,
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["/", "d", "h", "r", Qt.Key_Enter, "n"],
            7,
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["/", "d", "h", "r", Qt.Key_Return, "2n"],
            16,
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["/", "d", "h", "r", Qt.Key_Return, "5n"],
            7,
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["/", "d", "h", "r", Qt.Key_Return, "11n"],
            27,
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["l", "/", "d", "h", "r", Qt.Key_Enter],
            7,
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["/", "d", "h", "r", Qt.Key_Enter, "N"],
            27,
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["/", "d", "h", "r", Qt.Key_Enter, "2N"],
            16,
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["/", "d", "h", "r", Qt.Key_Enter, "3N"],
            7,
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["/", "d", "h", "r", Qt.Key_Enter, "5N"],
            27,
        ),
    ],
)
def test_search_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test / command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list",
    [
        ("", ["/", Qt.Key_Return]),
        ("", ["/", Qt.Key_Left, "d", Qt.Key_Enter]),
    ],
)
def test_search_corner_case_cmd(vim_bot, text, cmd_list):
    """Test search command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert vim.vim_cmd.vim_status.sub_mode is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", ["*"], 0),
        ("", ["#"], 0),
        ("dhr dhr", ["l", "*"], 4),
        ("dhr dhr", ["l", "#"], 0),
        ("dhr Dhr", ["l", "*"], 0),
        ("dhr _dhr dhrw dhr", ["l", "*"], 14),
        ("dhr _dhr dhrw _dhr", ["w", "#"], 14),
        ("dhr dhr dhrw dhr", ["l", "2*"], 13),
        ("dhr dhr dhrw dhr", ["w", "3#"], 4),
    ],
)
def test_asterisk_sharp_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test *, # command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


def test_search_backspace_command(vim_bot):
    """Test backspace in search."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "/")
    qtbot.keyClicks(cmd_line, "n")
    qtbot.keyPress(cmd_line, Qt.Key_Backspace)

    assert cmd_line.text() == "/"
    assert vim.vim_cmd.vim_status.sub_mode is not None

    qtbot.keyPress(cmd_line, Qt.Key_Backspace)

    assert cmd_line.text() == ""
    assert vim.vim_cmd.vim_status.sub_mode is None


def test_search_cmd_with_option(vim_bot):
    """Test / command with option."""
    _, _, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline

    editor.set_text("foo Foo foo Foo")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()
    get_start_list = vim.vim_cmd.vim_status.search.get_sel_start_list

    CONF.set(CONF_SECTION, "ignorecase", False)
    CONF.set(CONF_SECTION, "smartcase", False)

    qtbot.keyClicks(cmd_line, "/foo")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    assert get_start_list() == [0, 8]

    qtbot.keyClicks(cmd_line, "/Foo")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    assert get_start_list() == [4, 12]

    CONF.set(CONF_SECTION, "ignorecase", True)
    CONF.set(CONF_SECTION, "smartcase", False)
    qtbot.keyClicks(cmd_line, "/foo")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    assert get_start_list() == [0, 4, 8, 12]

    qtbot.keyClicks(cmd_line, "/Foo")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    assert get_start_list() == [0, 4, 8, 12]

    CONF.set(CONF_SECTION, "ignorecase", True)
    CONF.set(CONF_SECTION, "smartcase", True)
    qtbot.keyClicks(cmd_line, "/foo")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    assert get_start_list() == [0, 4, 8, 12]

    qtbot.keyClicks(cmd_line, "/Foo")
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    assert get_start_list() == [4, 12]


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ("a", ["d", "l"], 0, "", '"', "a"),
        ("a", ["d", "i", "b"], 0, "a", '"', ""),
        ("abcd", ["$", "d", "2h"], 1, "ad", '"', "bc"),
        ("a\nb", ["d", "j"], 0, "", '"', "a\nb\n"),
        ("  a\n b", ["j", "l", "d", "k"], 0, "", '"', "  a\n b\n"),
        (
            "  12\n  34\n  56\n  78",
            ["j", "d", "j"],
            7,
            "  12\n  78",
            '"',
            "  34\n  56\n",
        ),
        (
            "  12\n  34\n  56\n  78",
            ["2j", "d", "k"],
            7,
            "  12\n  78",
            '"',
            "  34\n  56\n",
        ),
        ("abcd", ["d", "$"], 0, "", '"', "abcd"),
        ("abcd", ["$", "d", "^"], 0, "d", '"', "abc"),
        ("a b", ["d", "w"], 0, "b", '"', "a "),
        ("a\nb", ["d", "w"], 0, "\nb", '"', "a"),
        ("a\nb", ["d", "2w"], 0, "", '"', "a\nb"),
        ("a\n b", ["d", "2w"], 0, "", '"', "a\n b"),
        ("a\nb c\n", ["d", "2w"], 0, "c\n", '"', "a\nb "),
        ("a b", ["l", "d", "w"], 1, "ab", '"', " "),
        ("a b c ", ["d", "2w"], 0, "c ", '"', "a b "),
        ("a b c ", ["d", "3w"], 0, "", '"', "a b c "),
        ("a.dk b", ["d", "W"], 0, "b", '"', "a.dk "),
        ("  a.dk b", ["d", "W"], 0, "a.dk b", '"', "  "),
        ("a.dk\nb", ["d", "W"], 0, "\nb", '"', "a.dk"),
        ("a.dk\nb c", ["d", "2W"], 0, "c", '"', "a.dk\nb "),
        ("a.dk\n b(f) c", ["d", "2W"], 0, "c", '"', "a.dk\n b(f) "),
        ("a.dk\nb", ["d", "e"], 0, "dk\nb", '"', "a."),
        ("a.dk\nb", ["d", "2e"], 0, "\nb", '"', "a.dk"),
        ("abcd", ["$", "d", "b"], 0, "d", '"', "abc"),
        ("ab.cd", ["$", "d", "b"], 3, "ab.d", '"', "c"),
        ("ab.cd", ["$", "d", "B"], 0, "d", '"', "ab.c"),
        ("  abcd \n b", ["3l", "d", "i", "w"], 2, "   \n b", '"', "abcd"),
        ("  abcd \n b", ["3l", "d", "a", "w"], 1, "  \n b", '"', "abcd "),
        ("  12\n  78", ["j", "d", "d"], 2, "  12", '"', "  78\n"),
        ("  12\n  78", ["d", "d"], 2, "  78", '"', "  12\n"),
        ("abcd\ne\nf\n", ["d", "d"], 0, "e\nf\n", '"', "abcd\n"),
        ("abcd", ["d", "d"], 0, "", '"', "abcd\n"),
        ("abcd\ne\nf\n", ["2d", "d"], 0, "f\n", '"', "abcd\ne\n"),
        ("AB\nC\nD\nE", ["l", "d", "G"], 0, "", '"', "AB\nC\nD\nE\n"),
        ("AB\nC\nD\nE", ["l", "d", "2G"], 0, "D\nE", '"', "AB\nC\n"),
        ("AB\n C\nD\nE", ["l", "d", "g", "g"], 1, " C\nD\nE", '"', "AB\n"),
        ("AB\nC\nD\nE", ["l", "d", "2g", "g"], 0, "D\nE", '"', "AB\nC\n"),
        ("AB(CD)", ["l", "d", "%"], 0, "A", '"', "B(CD)"),
        ("AB(CD)", ["$", "d", "%"], 1, "AB", '"', "(CD)"),
        ("ABCD", ["d", "f", "D"], 0, "", '"', "ABCD"),
        ("ABCD", ["d", "f", "F"], 0, "ABCD", '"', ""),
        ("ABCD", ["d", "t", "D"], 0, "D", '"', "ABC"),
        ("ABCD", ["$", "d", "F", "A"], 0, "D", '"', "ABC"),
        ("ABCD", ["$", "d", "T", "A"], 1, "AD", '"', "BC"),
        ("AAAA", ["d", "2f", "A"], 0, "A", '"', "AAA"),
        (' "AAA"', ["d", "i", '"'], 2, ' ""', '"', "AAA"),
        (' "AAA"', ["d", "a", '"'], 0, "", '"', ' "AAA"'),
        (' "AAA" ', ["d", "a", '"'], 0, " ", '"', '"AAA" '),
        ("(AAA)", ["d", "i", "("], 1, "()", '"', "AAA"),
        (" (AAA)", ["d", "i", "("], 2, " ()", '"', "AAA"),
        ("(AAA) ", ["$" "d", "i", "("], 5, "(AAA) ", '"', ""),
        ("(AAA)", ["d", "a", "("], 0, "", '"', "(AAA)"),
        ("(AAA)", ["%", "d", "a", ")"], 0, "", '"', "(AAA)"),
        (
            " dhrwodndhrwodn",
            ["d", "/", "d", "h", "r", "\r"],
            0,
            "dhrwodndhrwodn",
            '"',
            " ",
        ),
        (
            " dhrwodndhrwodn",
            ["d", "/", "d", "h", "r", "\r", "d", "n"],
            0,
            "dhrwodn",
            '"',
            "dhrwodn",
        ),
        (
            " dhrwodn dhrwodn",
            ["2w", "h", "d", "/", "d", "h", "r", "\r", "d", "N"],
            1,
            " dhrwodn",
            '"',
            "dhrwodn",
        ),
        (
            " fig.add_plot(1,1,1) ",
            ["4l", "d", "i", "W"],
            1,
            "  ",
            '"',
            "fig.add_plot(1,1,1)",
        ),
    ],
)
def test_d_cmd_in_normal(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test d command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("a\nb\nc", ["g", "c", "c"], "# a\nb\nc", 0),
        ("a\nb\nc", ["g", "c", "f", "k"], "a\nb\nc", 0),
        ("a\nb\nc", ["j", "g", "c", "i", "w"], "a\n# b\nc", 2),
        ("a\nb\nc", ["g", "c", "i", "b"], "a\nb\nc", 0),
        ("a\nb\nc", ["g", "c", "2j"], "# a\n# b\n# c", 0),
        ("a\nb\nc", ["g", "c", "2j", "."], "a\nb\nc", 0),
        ("a\nb\nc", ["2j", "g", "c", "2k"], "# a\n# b\n# c", 0),
        ("a\nb\nc", ["2j", "g", "c", "2k", "."], "a\n# b\n# c", 0),
        ("a\nb\nc", ["v", "j", "g", "c"], "# a\n# b\nc", 0),
        ("a\nb\nc", ["v", "j", "g", "c", "j", "."], "# a\n# # b\n# c", 4),
    ],
)
def test_gc_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gc command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("ab", [Qt.Key_Space], 1),
        ("abc", ["2", Qt.Key_Space], 2),
        ("a\nb\n", [Qt.Key_Space], 2),
        ("a\nb\nc", ["2", Qt.Key_Space], 4),
    ],
)
def test_space_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test space command."""
    _, _, editor, vim, qtbot = vim_bot

    CONF.set(CONF_SECTION, "leader_key", "F1")
    vim.apply_plugin_settings("")

    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("ab", ["l", Qt.Key_Backspace], 0),
        ("abcd", ["3l", "2", Qt.Key_Backspace], 1),
        ("a\nb\nc", ["2j", Qt.Key_Backspace], 2),
    ],
)
def test_backspace_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test backspace command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("ab\n   k", [Qt.Key_Enter], 6),
        ("ab\n   k\n b", ["2", Qt.Key_Return], 9),
        ("abcdef\n   k\n b", ["$", Qt.Key_Enter], 10),
    ],
)
def test_enter_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test enter command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


def test_q_cmd_message(vim_bot):
    """Test message of q command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "q$")
    assert vim.vim_cmd.msg_label.text() == ""

    qtbot.keyClicks(cmd_line, "qq")

    assert vim.vim_cmd.msg_label.text() == "recording @q... "

    qtbot.keyClicks(cmd_line, "q")
    assert vim.vim_cmd.msg_label.text() == ""


def test_q_cmd(vim_bot):
    """Test q command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("def foo(a, b, c)\n\ndef foo(a, b, c)\n\ndef foo(a, b, c)\n\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "qq")
    qtbot.keyClicks(cmd_line, "@")
    qtbot.wait(500)

    qtbot.keyClicks(cmd_line, "f,i")
    qtbot.keyClicks(editor, "_1st")
    cmd_line.setFocus()
    qtbot.wait(500)
    vim.vim_cmd.vim_status.disconnect_from_editor()  # TODO: Fix

    qtbot.keyClicks(cmd_line, ";i")
    qtbot.keyClicks(editor, "_2nd")
    cmd_line.setFocus()
    qtbot.wait(500)
    vim.vim_cmd.vim_status.disconnect_from_editor()  # TODO: Fix

    qtbot.keyClicks(cmd_line, "f).0jj")
    cmd_line.setFocus()
    qtbot.wait(500)
    vim.vim_cmd.vim_status.disconnect_from_editor()  # TODO: Fix

    qtbot.keyClicks(cmd_line, "q")

    qtbot.keyClicks(cmd_line, "2@q")

    qtbot.wait(500)

    assert (
        editor.toPlainText()
        == "def foo(a_1st, b_2nd, c_2nd)\n\ndef foo(a_1st, b_2nd, c_2nd)\n\ndef foo(a_1st, b_2nd, c_2nd)\n\n"
    )

    qtbot.keyClicks(cmd_line, "qa")
    qtbot.keyClicks(cmd_line, "i")
    qtbot.keyClicks(editor, "_")
    cmd_line.setFocus()
    qtbot.wait(500)
    vim.vim_cmd.vim_status.disconnect_from_editor()  # TODO: Fix
    qtbot.keyClicks(cmd_line, "q")
    qtbot.keyClicks(cmd_line, "@a")

    # to meet coverage
    foo = enable_coverage_tracing(print)
    foo()


def test_squarebracket_d_cmd(vim_bot):
    """Test goto warning."""
    _, _, editor, vim, qtbot = vim_bot

    editor.go_to_next_warning = Mock()
    editor.go_to_previous_warning = Mock()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "[d")
    qtbot.keyClicks(cmd_line, "]d")

    assert cmd_line.text() == ""
    assert editor.go_to_next_warning.called
    assert editor.go_to_previous_warning.called


@pytest.mark.parametrize(
    "start_line, cmd, expected",
    [
        (0, "]]", 2),
        (6, "]]", 6),
        (9, "]]", 9),
    ],
)
def test_next_python_definition(vim_bot, start_line, cmd, expected):
    """Jump to next Python function or class definition."""
    _, _, editor, vim, qtbot = vim_bot

    text = (
        "import os\n\n"
        "def a():\n    pass\n\n"
        "class Foo:\n    def b(self):\n        pass\n\n"
        "def c():\n    pass\n"
    )
    editor.set_text(text)

    block = editor.document().findBlockByNumber(start_line)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(block.position())
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().blockNumber() == expected


@pytest.mark.parametrize(
    "start_line, cmd, expected",
    [
        (10, "[[", 9),
        (6, "[[", 5),
        (2, "[[", 2),
    ],
)
def test_prev_python_definition(vim_bot, start_line, cmd, expected):
    """Jump to previous Python function or class definition."""
    _, _, editor, vim, qtbot = vim_bot

    text = (
        "import os\n\n"
        "def a():\n    pass\n\n"
        "class Foo:\n    def b(self):\n        pass\n\n"
        "def c():\n    pass\n"
    )
    editor.set_text(text)

    block = editor.document().findBlockByNumber(start_line)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(block.position())
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().blockNumber() == expected


@pytest.mark.parametrize(
    "start_line, cmd, expected",
    [
        (0, "}}", 3),
        (3, "}}", 6),
        (6, "}}", 9),
        (9, "}}", 12),
        (12, "}}", 17),
        (17, "}}", 20),
    ],
)
def test_next_python_block(vim_bot, start_line, cmd, expected):
    """Jump to next Python block."""
    _, _, editor, vim, qtbot = vim_bot

    text = (
        "def a():\n"
        "    pass\n\n"
        "if x:\n    pass\n\n"
        "for i in range(3):\n    pass\n\n"
        "while False:\n    pass\n\n"
        "try:\n    pass\nexcept Exception:\n    pass\n\n"
        "with open('file') as f:\n    pass\n\n"
        "class Foo:\n    def bar(self):\n        pass\n"
    )
    editor.set_text(text)

    block = editor.document().findBlockByNumber(start_line)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(block.position())
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().blockNumber() == expected


@pytest.mark.parametrize(
    "start_line, cmd, expected",
    [
        (20, "{{", 17),
        (17, "{{", 12),
        (12, "{{", 9),
        (9, "{{", 6),
        (6, "{{", 3),
        (3, "{{", 0),
    ],
)
def test_prev_python_block(vim_bot, start_line, cmd, expected):
    """Jump to previous Python block."""
    _, _, editor, vim, qtbot = vim_bot

    text = (
        "def a():\n"
        "    pass\n\n"
        "if x:\n    pass\n\n"
        "for i in range(3):\n    pass\n\n"
        "while False:\n    pass\n\n"
        "try:\n    pass\nexcept Exception:\n    pass\n\n"
        "with open('file') as f:\n    pass\n\n"
        "class Foo:\n    def bar(self):\n        pass\n"
    )
    editor.set_text(text)

    block = editor.document().findBlockByNumber(start_line)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(block.position())
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().blockNumber() == expected
