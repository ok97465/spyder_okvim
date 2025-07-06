# -*- coding: utf-8 -*-
"""Tests for the executor_vline."""

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.vim import VimState


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("import numpy as np", ["V"], 0, [0, 18]),
        ("import numpy as np", ["V", "l", "h"], 0, [0, 18]),
        ("import numpy as np", ["V", "5l"], 5, [0, 18]),
        ("import numpy as np", ["5l", "V"], 5, [0, 18]),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["V", "j"],
            19,
            [0, 50],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["2l", "V", "2j", "5l"],
            58,
            [0, 75],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc
""",
            ["2l", "V", "3j", "k", "j"],
            76,
            [0, 76],
        ),
        (
            """
import matplotlib.pyplot as plt
import scipy.scipy as sc
""",
            ["5j", "V", "5k"],
            0,
            [0, 58],
        ),
    ],
)
def test_V_cmd(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test V command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("import numpy as np", ["V", "0"], 0, [0, 18]),
        ("import numpy as np", ["5l", "V", "0"], 0, [0, 18]),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["V", "j", "5l", "0"],
            19,
            [0, 50],
        ),
    ],
)
def test_zero_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test 0 command in v-line."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("   import numpy as np", ["V", "^"], 3, [0, 21]),
        ("   import numpy as np", ["10l", "V", "^"], 3, [0, 21]),
    ],
)
def test_caret_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test ^ command in v-line."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [("import numpy as np", ["V", "$"], 18, [0, 18])],
)
def test_dollar_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test $ command in v-line."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01 34\n", ["V", "w"], 3, [0, 5]),
        ("01 34\n", ["V", "w", "o"], 0, [0, 5]),
        ("01 34\n", ["V", "w", "o", "o"], 4, [0, 5]),
        ("\n", ["j", "V"], 1, [1, 1]),
        ("\n", ["j", "V", "o"], 1, [1, 1]),
        ("01 34\n6\n", ["V", "j"], 6, [0, 7]),
        ("01 34\n6\n", ["V", "j", "o"], 0, [0, 7]),
        ("01 34\n6\n", ["j", "V", "k", "o"], 6, [0, 7]),
        ("01 34\n6\n8\n", ["j", "V", "j", "2k", "o"], 6, [0, 7]),
    ],
)
def test_o_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test o command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ["V", "J"], "", 0),
        ("\n\n", ["3j", "V", "J"], "\n\n", 2),
        ("0\n23", ["j", "l", "V", "k", "J"], "0 23", 1),
        ("0\n2\n4\n6\n8\n", ["V", "2j", "J"], "0 2 4\n6\n8\n", 3),
        ("0\n2\n4\n6\n8\n", ["V", "2j", "J", "."], "0 2 4 6 8\n", 7),
    ],
)
def test_J_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test J command in vline."""
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
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01 34", ["V", "w"], 3, [0, 5]),
    ],
)
def test_w_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test w command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("", ["V", "W"], 0, [0, 0]),
        ("029.d98@jl 34", ["V", "W"], 11, [0, 13]),
        ("029.d98@jl 34", ["V", "2W"], 13, [0, 13]),
        ("029.d98@jl 34\na", ["V", "2W"], 14, [0, 15]),
        ("029.d98@jl 34\n  a", ["V", "2W"], 16, [0, 17]),
    ],
)
def test_W_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test W command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01 34", ["$", "V", "b"], 3, [0, 5]),
    ],
)
def test_b_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test b command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01.34", ["$", "V", "B"], 0, [0, 5]),
    ],
)
def test_B_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test B command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01 34\n67 90", ["V", "e"], 1, [0, 5]),
        ("01 34\n67 90", ["V", "3e"], 7, [0, 11]),
    ],
)
def test_e_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test e command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("0\n2\n4\n", ["V", "2G"], 2, [0, 3]),
        ("0\n     \n8\n", ["V", "2G"], 6, [0, 7]),
        ("0\n2\n4\n", ["V", "G"], 6, [0, 6]),
        ("0\n2\n4\n     a", ["V", "G"], 11, [0, 12]),
    ],
)
def test_G_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test G command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("0\n2\n4\n", ["V", "2gg"], 2, [0, 3]),
        ("0\n     \n8\n", ["V", "2gg"], 6, [0, 7]),
        ("    0\n2\n4\n", ["4j", "V", "gg"], 4, [0, 10]),
    ],
)
def test_gg_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test gg command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("0\n2\n4\n", ["V", ":", "2", Qt.Key_Return], 4),
        ("0\n     \n8\n", ["V", ":", "2", Qt.Key_Return], 8),
        ("0\n\n2\n4\n", ["V", ":", "3", Qt.Key_Return], 5),
        (
            "aaa\nbbb\nccc\nddd\neee\n",
            ["j", "V", ":", "3", Qt.Key_Return],
            16,
        ),
        (
            "aaa\nbbb\nccc\nddd\neee\n",
            ["j", "l", "V", ":", "3", Qt.Key_Return],
            17,
        ),
    ],
)
def test_colon_num_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos):
    """Test :num command in vline."""
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
    assert not editor.get_extra_selections("vim_selection")


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("abcde", ["V", "~"], "ABCDE", 0),
        ("abcde\na", ["l", "V", "$", "~"], "ABCDE\na", 0),
        ("abcde\na", ["l", "V", "$", "~", "j", "."], "ABCDE\nA", 6),
        ("", ["V", "~"], "", 0),
    ],
)
def test_tilde_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test ~ command in vline."""
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
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("", ["V", "%"], 0, [0, 0]),
        ("\n", ["j", "V", "%"], 1, [1, 1]),
        (" ()", ["V", "%"], 2, [0, 3]),
        (" ()", ["V", "%", "%"], 1, [0, 3]),
    ],
)
def test_percent_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test % command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("", ["V", "f", "r"], 0, [0, 0]),
        ("\n", ["j", "V", "f", "r"], 1, [1, 1]),
        (" rr", ["V", "f", "r"], 1, [0, 3]),
        (" rr", ["V", "f", "r", ";"], 2, [0, 3]),
        (" rr", ["V", "f", "r", ";", ","], 1, [0, 3]),
    ],
)
def test_f_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test f command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("", ["V", "F", "r"], 0, [0, 0]),
        ("\n", ["j", "V", "F", "r"], 1, [1, 1]),
        (" rr ", ["V", "$", "F", "r"], 2, [0, 4]),
        (" rr ", ["V", "$", "F", "r", ";"], 1, [0, 4]),
        (" rr ", ["V", "$", "F", "r", ";", ","], 2, [0, 4]),
    ],
)
def test_F_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test F command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("", ["V", "s", "aa"], 0, [0, 0]),
        ("", ["V", ";"], 0, [0, 0]),
        ("", ["V", ","], 0, [0, 0]),
        ("\n", ["V", "j", "s", "rr"], 1, [0, 1]),
        ("d\ndhr Dhr dhr", ["V", "sdh"], 2, [0, 13]),
        ("d\ndhr Dhr dhr", ["V", "sdh", ";"], 10, [0, 13]),
        ("d\ndhr Dhr dhr", ["V", "sdh", ";,"], 2, [0, 13]),
        ("d\ndhr Dhr dhr", ["V", "j$" "Sdh"], 10, [0, 13]),
        ("d\ndhr Dhr dhr", ["V", "j$" "Sdh", ";"], 2, [0, 13]),
        ("d\ndhr Dhr dhr", ["V", "j$" "Sdh", ";,"], 10, [0, 13]),
    ],
)
def test_sneak_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test sneak command in visual."""
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

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("", ["V", "t", "r"], 0, [0, 0]),
        ("\n", ["j", "V", "t", "r"], 1, [1, 1]),
        ("  rr", ["V", "t", "r"], 1, [0, 4]),
        ("  rr", ["V", "t", "r", ";"], 2, [0, 4]),
        ("  rrrr", ["V", "t", "r", "4;"], 4, [0, 6]),
        ("  rrrr", ["V", "t", "r", "4;", ","], 3, [0, 6]),
    ],
)
def test_t_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test t command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("", ["V", "T", "r"], 0, [0, 0]),
        ("r\n", ["j", "V", "T", "r"], 2, [2, 2]),
        ("  rr  ", ["V", "$", "T", "r"], 4, [0, 6]),
        ("  rr  ", ["V", "$", "T", "r", ";"], 3, [0, 6]),
        ("  rrrr", ["V", "$", "T", "r", "4;"], 3, [0, 6]),
        ("  rrrr", ["V", "$", "T", "r", "4;", ","], 4, [0, 6]),
    ],
)
def test_T_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test T command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ["V", "r", "r"], "", 0),
        ("1\n", ["j", "V", "r", "r"], "1\n", 2),
        ("\n\na", ["j", "V", "r", "r"], "\n\na", 1),
        ("a", ["V", "r", "r"], "r", 0),
        (" a\nbc\n", ["l", "V", "j", "r", "r"], "rr\nrr\n", 0),
        (" a\nbc\nkk", ["l", "V", "j", "r", "r"], "rr\nrr\nkk", 0),
        (" a\nbc\nkk", ["l", "V", "j", "r", "r", "j", "."], "rr\nrr\nrr", 3),
    ],
)
def test_r_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test r command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

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
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("ABCDE", ["V", "u"], "abcde", 0),
        ("ABCDE\nA", ["l", "V", "$", "u"], "abcde\nA", 0),
        ("ABCDE\nA", ["l", "V", "$", "u", "j", "."], "abcde\na", 6),
        ("", ["V", "u"], "", 0),
    ],
)
def test_u_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test u command in vline."""
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
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("ABCDE", ["V", "g", "u"], "abcde", 0),
        ("ABCDE\nA", ["l", "V", "$", "g", "u"], "abcde\nA", 0),
        ("ABCDE\nA", ["l", "V", "$", "g", "u", "j", "."], "abcde\na", 6),
        ("", ["V", "g", "u"], "", 0),
    ],
)
def test_gu_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gu command in vline."""
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
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("abcde", ["V", "U"], "ABCDE", 0),
        ("abcde\na", ["l", "V", "$", "U"], "ABCDE\na", 0),
        ("abcde\na", ["l", "V", "$", "U", "j", "."], "ABCDE\nA", 6),
        ("", ["V", "U"], "", 0),
    ],
)
def test_U_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test U command in vline."""
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
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("abcde", ["V", "g", "U"], "ABCDE", 0),
        ("abcde\na", ["l", "V", "$", "g", "U"], "ABCDE\na", 0),
        ("abcde\na", ["l", "V", "$", "g", "U", "j", "."], "ABCDE\nA", 6),
        ("", ["V", "g", "U"], "", 0),
    ],
)
def test_gU_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gU command in vline."""
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
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("abCde", ["V", "g", "~"], "ABcDE", 0),
        ("abCde\na", ["l", "V", "$", "g", "~"], "ABcDE\na", 0),
        ("abCde\na", ["l", "V", "$", "g", "~", "j", "."], "ABcDE\nA", 6),
        ("", ["V", "g", "~"], "", 0),
    ],
)
def test_gtilde_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test g~ command in vline."""
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
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ["V", ">"], "", 0),
        ("abcde", ["2l", "V", ">"], "    abcde", 4),
        (" abcde\na", ["V", ">"], "     abcde\na", 5),
        ("a\n\na", ["V", "2j", ">"], "    a\n\n    a", 4),
    ],
)
def test_greater_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test > command in vline."""
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
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ["V", "<"], "", 0),
        ("    abcde", ["2l", "V", "<"], "abcde", 0),
        ("     abcde\na", ["V", "<"], " abcde\na", 1),
        ("    a\n\n    a", ["V", "2j", "<"], "a\n\na", 0),
    ],
)
def test_less_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test < command in vline."""
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
    "text, cmd_list, cursor_pos, register_name, text_yanked",
    [
        ("a", ["V", "y"], 0, '"', "a\n"),
        ("abcd", ["V", '"', "0", "y"], 0, "0", "abcd\n"),
        ("abcd\ne", ["V", "j", '"', "a", "y"], 0, "a", "abcd\ne\n"),
    ],
)
def test_y_cmd_in_vline(
    vim_bot, text, cmd_list, cursor_pos, register_name, text_yanked
):
    """Test y command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[register_name]
    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked
    assert reg.type == VimState.VLINE
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None
    if register_name == '"':
        reg0 = vim.vim_cmd.vim_status.register_dict["0"]
        assert reg0.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected",
    [
        ("ak", ["V", "p"], 0, ""),
        ("ak", ["v", "l", "y", "V", "p"], 0, "ak"),
        ("ak", ["v", "l", "y", "V", "P"], 0, "ak"),
        ("ak", ["v", "l", "y", "V", "2p"], 0, "ak\nak"),
        ("ab\n\ncd\n", ["v", "j", "y", "2j", "V", "2p"], 4, "ab\n\nab\n\n\nab\n\n\n"),
        (
            "ab\ncd\nef\ngh\n",
            ["V", "j", "y", "2j", "V", "p"],
            6,
            "ab\ncd\nab\ncd\ngh\n",
        ),
        (
            "ab\ncd\nef\ngh\n",
            ["V", "j", "y", "2j", "V", "2p"],
            6,
            "ab\ncd\nab\ncd\nab\ncd\ngh\n",
        ),
    ],
)
def test_p_P_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, text_expected):
    """Test p command in vline."""
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
        ("ab", ["V", "d"], 0, "", '"', "ab\n"),
        (" ab\n cd\n ef", ["j", "V", "d"], 5, " ab\n ef", '"', " cd\n"),
        (" ab\n cd\n", ["V", "G", "d"], 0, "", '"', " ab\n cd\n\n"),
        (" ab\n cd\n ef", ["2j", "V", "d"], 5, " ab\n cd", '"', " ef\n"),
        (" ab\n cd\n ef", ["2j", "V", "k", "d"], 1, " ab", '"', " cd\n ef\n"),
        (" ab\n cd", ["$", "V", "d"], 1, " cd", '"', " ab\n"),
    ],
)
def test_d_cmd_in_vline(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test d command in vline."""
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
        ("ab", ["V", "x"], 0, "", '"', "ab\n"),
        (" ab\n cd\n ef", ["j", "V", "x"], 5, " ab\n ef", '"', " cd\n"),
        (" ab\n cd\n", ["V", "G", "x"], 0, "", '"', " ab\n cd\n\n"),
        (" ab\n cd\n ef", ["2j", "V", "x"], 5, " ab\n cd", '"', " ef\n"),
        (" ab\n cd\n ef", ["2j", "V", "k", "x"], 1, " ab", '"', " cd\n ef\n"),
        (" ab\n cd", ["$", "V", "x"], 1, " cd", '"', " ab\n"),
    ],
)
def test_x_cmd_in_vline(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test x command in vline."""
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
        ("ab", ["V", "c"], 0, "", '"', "ab\n"),
        (" ab\n cd\n ef", ["j", "V", "c"], 4, " ab\n\n ef", '"', " cd\n"),
        (" ab\n cd\n", ["V", "G", "c"], 0, "", '"', " ab\n cd\n\n"),
        (" ab\n cd\n ef", ["2j", "V", "c"], 8, " ab\n cd\n", '"', " ef\n"),
        (" ab\n cd\n ef", ["2j", "V", "k", "c"], 4, " ab\n", '"', " cd\n ef\n"),
        (" ab\n cd", ["$", "V", "c"], 0, "\n cd", '"', " ab\n"),
    ],
)
def test_c_cmd_in_vline(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test c command in vline."""
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
        ("ab", ["V", "s"], 0, "", '"', "ab\n"),
        (" ab\n cd\n ef", ["j", "V", "s"], 4, " ab\n\n ef", '"', " cd\n"),
        (" ab\n cd\n", ["V", "G", "s"], 0, "", '"', " ab\n cd\n\n"),
        (" ab\n cd\n ef", ["2j", "V", "s"], 8, " ab\n cd\n", '"', " ef\n"),
        (" ab\n cd\n ef", ["2j", "V", "k", "s"], 4, " ab\n", '"', " cd\n ef\n"),
        (" ab\n cd", ["$", "V", "s"], 0, "\n cd", '"', " ab\n"),
    ],
)
def test_s_cmd_in_vline(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test s command in vline."""
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
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("a", ["V", "/", "b", "\r"], 0, [0, 1]),
        ("a", ["V", "/", "b", "\r", "n"], 0, [0, 1]),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["V", "/", "d", "h", "r", Qt.Key_Enter],
            1,
            [0, 4],
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["V", "/", "d", "h", "r", Qt.Key_Enter, "n"],
            7,
            [0, 14],
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["V", "/", "d", "h", "r", Qt.Key_Return, "n", "N"],
            1,
            [0, 4],
        ),
    ],
)
def test_search_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test / command in vline."""
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

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos == sel_pos_


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("a", ["V", "*"], 0, [0, 1]),
        ("a", ["V", "#"], 0, [0, 1]),
        ("dhr\n  Dhr\n\n_dhr\n   dhr", ["V", "*"], 19, [0, 22]),
        ("dhr\n  dhr\n\n_dhr\n   dhr", ["j2l", "V", "#"], 0, [0, 9]),
    ],
)
def test_asterisk_sharp_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test *,# command in vline."""
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

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos == sel_pos_


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01 34", ["V", Qt.Key_Space], 1, [0, 5]),
    ],
)
def test_space_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test space command in vline."""
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

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01 34", ["2l", "V", Qt.Key_Backspace], 1, [0, 5]),
    ],
)
def test_backspace_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test backspace command in vline."""
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

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01 34\n   kj", ["V", Qt.Key_Enter], 9, [0, 11]),
    ],
)
def test_enter_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test enter command in vline."""
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

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


def test_jump_mark_in_vline(vim_bot):
    """Jump to mark while in vline mode."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(4)
    qtbot.keyClicks(cmd_line, "V'a")
    assert vim.vim_cmd.vim_status.vim_state == VimState.VLINE
    assert editor.textCursor().position() == 0


@pytest.mark.parametrize(
    "start_line, cmd_list, expected",
    [
        (0, ["V", "]]"], 2),
        (6, ["V", "]]"], 6),
        (9, ["V", "]]"], 9),
    ],
)
def test_next_python_definition_in_vline(vim_bot, start_line, cmd_list, expected):
    """Jump to next Python definition while in Vline mode."""
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
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().blockNumber() == expected


@pytest.mark.parametrize(
    "start_line, cmd_list, expected",
    [
        (10, ["V", "[["], 9),
        (6, ["V", "[["], 5),
        (2, ["V", "[["], 2),
    ],
)
def test_prev_python_definition_in_vline(vim_bot, start_line, cmd_list, expected):
    """Jump to previous Python definition while in Vline mode."""
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
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().blockNumber() == expected


@pytest.mark.parametrize(
    "start_line, cmd_list, expected",
    [
        (0, ["V", "}}"], 3),
        (3, ["V", "}}"], 6),
        (6, ["V", "}}"], 9),
        (9, ["V", "}}"], 12),
        (12, ["V", "}}"], 17),
        (17, ["V", "}}"], 20),
    ],
)
def test_next_python_block_in_vline(vim_bot, start_line, cmd_list, expected):
    """Jump to next Python block while in Vline mode."""
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
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().blockNumber() == expected


@pytest.mark.parametrize(
    "start_line, cmd_list, expected",
    [
        (20, ["V", "{{"], 17),
        (17, ["V", "{{"], 12),
        (12, ["V", "{{"], 9),
        (9, ["V", "{{"], 6),
        (6, ["V", "{{"], 3),
        (3, ["V", "{{"], 0),
    ],
)
def test_prev_python_block_in_vline(vim_bot, start_line, cmd_list, expected):
    """Jump to previous Python block while in Vline mode."""
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
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().blockNumber() == expected
