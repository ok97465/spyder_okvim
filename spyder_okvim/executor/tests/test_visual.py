# -*- coding: utf-8 -*-
"""Tests for the executor_visual."""

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
        ("import numpy as np", ["v"], 0, [0, 1]),
        ("import numpy as np", ["v", "5l"], 5, [0, 6]),
        ("import numpy as np", ["5l", "v"], 5, [5, 6]),
        ("import numpy as np", ["5l", "v", "3l"], 8, [5, 9]),
        ("import numpy as np", ["5l", "v", "3l", "7h"], 1, [1, 6]),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["v", "j"],
            19,
            [0, 20],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["v", "j", "5l"],
            24,
            [0, 25],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["v", "j", "5l", "3h"],
            21,
            [0, 22],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["l", "v", "2j"],
            52,
            [1, 53],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["l", "v", "2j", "4l"],
            56,
            [1, 57],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["l", "v", "2j", "4l", "k"],
            24,
            [1, 25],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["j", "5l", "v", "k"],
            5,
            [5, 25],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["j", "5l", "v", "k", "5h"],
            0,
            [0, 25],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["j", "5l", "v", "k", "5h", "j"],
            19,
            [19, 25],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["j", "5l", "v", "k", "5h", "2j"],
            51,
            [24, 52],
        ),
        (
            """
import matplotlib.pyplot as plt
import scipy.scipy as sc
""",
            ["v", "3j", "30l"],
            58,
            [0, 58],
        ),
    ],
)
def test_v_cmd(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test v command."""
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
        ("import numpy as np", ["v", "0"], 0, [0, 1]),
        ("import numpy as np", ["5l", "v", "0"], 0, [0, 6]),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["v", "j", "0"],
            19,
            [0, 20],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["v", "j", "5l", "0"],
            19,
            [0, 20],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["l", "v", "2j", "0"],
            51,
            [1, 52],
        ),
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["l", "v", "2j", "4l", "k", "0"],
            19,
            [1, 20],
        ),
        (
            """
import matplotlib.pyplot as plt
import scipy.scipy as sc
""",
            ["v", "3j", "0"],
            58,
            [0, 58],
        ),
    ],
)
def test_zero_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test 0 command in visual."""
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
        ("   import numpy as np", ["v", "^"], 3, [0, 4]),
        ("   import numpy as np", ["10l", "v", "^"], 3, [3, 11]),
    ],
)
def test_caret_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test ^ command in visual."""
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
        ("import numpy as np", ["v", "$"], 18, [0, 18]),
    ],
)
def test_dollar_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test $ command in visual."""
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
        ("01 34", ["v", "w"], 3, [0, 4]),
        ("01 34", ["v", "w", "o"], 0, [0, 4]),
        ("01 34", ["v", "w", "o", "o"], 3, [0, 4]),
        ("\n", ["j", "v"], 1, [1, 1]),
        ("\n", ["j", "v", "o"], 1, [1, 1]),
        ("01 34\n6", ["v", "j"], 6, [0, 7]),
        ("01 34\n6", ["v", "j", "o"], 0, [0, 7]),
    ],
)
def test_o_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test o command in visual."""
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
        ("", ["v", "J"], "", 0),
        ("\n\n", ["3j", "v", "J"], "\n\n", 2),
        ("0\n23", ["j", "l", "v", "k", "J"], "0 23", 1),
        ("0\n2\n4\n6\n8\n", ["v", "2j", "J"], "0 2 4\n6\n8\n", 3),
        ("0\n2\n4\n6\n8\n", ["v", "2j", "J", "."], "0 2 4 6 8\n", 7),
    ],
)
def test_J_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test J command in visual."""
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
        ("01 34", ["v", "w"], 3, [0, 4]),
        ("01 34", ["v", "2w"], 5, [0, 5]),
        ("01 34\na\n", ["v", "3w"], 8, [0, 8]),
        ("01 34\n  a\n", ["v", "3w"], 10, [0, 10]),
    ],
)
def test_w_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test w command in visual."""
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
        ("", ["v", "W"], 0, [0, 0]),
        ("029.d98@jl 34", ["v", "W"], 11, [0, 12]),
        ("029.d98@jl 34", ["v", "2W"], 13, [0, 13]),
        ("029.d98@jl 34\na", ["v", "2W"], 14, [0, 15]),
        ("029.d98@jl 34\n  a", ["v", "2W"], 16, [0, 17]),
    ],
)
def test_W_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test W command in visual."""
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
        ("01 34", ["$", "v", "b"], 3, [3, 5]),
    ],
)
def test_b_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test b command in visual."""
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
        ("01.34", ["$", "v", "B"], 0, [0, 5]),
    ],
)
def test_B_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test B command in visual."""
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
        ("01 34", ["v", "e"], 1, [0, 2]),
    ],
)
def test_e_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test e command in visual."""
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
        ("0\n2\n4\n", ["v", "2G"], 2, [0, 3]),
        ("0\n     \n8\n", ["v", "2G"], 6, [0, 7]),
        ("0\n2\n4\n", ["v", "G"], 6, [0, 6]),
        ("0\n2\n4\n     a", ["v", "G"], 11, [0, 12]),
    ],
)
def test_G_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test G command in visual."""
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
        ("0\n2\n4\n", ["v", "2gg"], 2, [0, 3]),
        ("0\n     \n8\n", ["v", "2gg"], 6, [0, 7]),
        ("    0\n2\n4\n", ["4j", "v", "gg"], 4, [4, 10]),
    ],
)
def test_gg_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test gg command in visual."""
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
        ("0\n2\n4\n", ["v", ":", "2", Qt.Key_Return], 4),
        ("0\n     \n8\n", ["v", ":", "2", Qt.Key_Return], 8),
        ("0\n\n2\n4\n", ["v", ":", "3", Qt.Key_Return], 5),
        (
            "aaa\nbbb\nccc\nddd\neee\n",
            ["j", "v", ":", "3", Qt.Key_Return],
            16,
        ),
        (
            "aaa\nbbb\nccc\nddd\neee\n",
            ["j", "l", "v", ":", "3", Qt.Key_Return],
            17,
        ),
    ],
)
def test_colon_num_cmd_in_v(vim_bot, text, cmd_list, cursor_pos):
    """Test :num command in visual."""
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
        ("abcde", ["v", "~"], "Abcde", 0),
        ("abcde\na", ["l", "v", "$", "~"], "aBCDE\na", 1),
        ("abcde\na", ["l", "v", "3l", "~", "0", "."], "AbcdE\na", 0),
        ("", ["v", "~"], "", 0),
    ],
)
def test_tilde_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test ~ command in visual."""
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
        ("", ["v", "%"], 0, [0, 0]),
        ("\n", ["j", "v", "%"], 1, [1, 1]),
        (" ()", ["v", "%"], 2, [0, 3]),
        (" ()", ["v", "%", "%"], 1, [0, 2]),
    ],
)
def test_percent_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test % command in visual."""
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
        ("", ["v", "f", "r"], 0, [0, 0]),
        ("\n", ["j", "v", "f", "r"], 1, [1, 1]),
        (" rr", ["v", "f", "r"], 1, [0, 2]),
        (" rr", ["v", "f", "r", ";"], 2, [0, 3]),
        (" rr", ["v", "f", "r", ";", ","], 1, [0, 2]),
    ],
)
def test_f_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test f command in visual."""
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
        ("", ["v", "F", "r"], 0, [0, 0]),
        ("\n", ["j", "v", "F", "r"], 1, [1, 1]),
        (" rr ", ["v", "$", "F", "r"], 2, [0, 3]),
        (" rr ", ["v", "$", "F", "r", ";"], 1, [0, 2]),
        (" rr ", ["v", "$", "F", "r", ";", ","], 2, [0, 3]),
    ],
)
def test_F_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test F command in visual."""
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
        ("", ["v", "s", "aa"], 0, [0, 0]),
        ("", ["v", ";"], 0, [0, 0]),
        ("", ["v", ","], 0, [0, 0]),
        ("\n", ["v", "j", "s", "rr"], 1, [0, 1]),
        ("d\ndhr Dhr dhr", ["v", "sdh"], 2, [0, 3]),
        ("d\ndhr Dhr dhr", ["v", "sdh", ";"], 10, [0, 11]),
        ("d\ndhr Dhr dhr", ["v", "sdh", ";,"], 2, [0, 3]),
    ],
)
def test_sneak_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
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
        ("", ["v", "t", "r"], 0, [0, 0]),
        ("\n", ["j", "v", "t", "r"], 1, [1, 1]),
        ("  rr", ["v", "t", "r"], 1, [0, 2]),
        ("  rr", ["v", "t", "r", ";"], 2, [0, 3]),
        ("  rrrr", ["v", "t", "r", "4;"], 4, [0, 5]),
        ("  rrrr", ["v", "t", "r", "4;", ","], 3, [0, 4]),
    ],
)
def test_t_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test t command in visual."""
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
        ("", ["v", "T", "r"], 0, [0, 0]),
        ("r\n", ["j", "v", "T", "r"], 2, [2, 2]),
        ("  rr  ", ["v", "$", "T", "r"], 4, [0, 5]),
        ("  rr  ", ["v", "$", "T", "r", ";"], 3, [0, 4]),
        ("  rrrr", ["v", "$", "T", "r", "4;"], 3, [0, 4]),
        ("  rrrr", ["v", "$", "T", "r", "4;", ","], 4, [0, 5]),
    ],
)
def test_T_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test T command in visual."""
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
        ("", ["v", "r", "r"], "", 0),
        ("1\n", ["j", "v", "r", "r"], "1\n", 2),
        ("\n\na", ["j", "v", "r", "r"], "\n\na", 1),
        ("a", ["v", "r", "r"], "r", 0),
        (" a\nbc\n", ["l", "v", "j", "r", "r"], " r\nrr\n", 1),
        (" a\nbc\nde", ["l", "v", "j", "r", "r"], " r\nrr\nde", 1),
        (" a\nbc\nde", ["l", "v", "j", "r", "r", "j", "."], " r\nrr\nrr", 4),
    ],
)
def test_r_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test r command in visual."""
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
        ("ABCDE", ["v", "u"], "aBCDE", 0),
        ("ABCDE\nA", ["l", "v", "$", "u"], "Abcde\nA", 1),
        ("ABCDE\nA", ["l", "v", "3l", "u", "0", "."], "abcde\nA", 0),
        ("", ["v", "u"], "", 0),
    ],
)
def test_u_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test u command in visual."""
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
        ("ABCDE", ["v", "g", "u"], "aBCDE", 0),
        ("ABCDE\nA", ["l", "v", "$", "g", "u"], "Abcde\nA", 1),
        ("ABCDE\nA", ["l", "v", "3l", "g", "u", "0", "."], "abcde\nA", 0),
        ("", ["v", "g", "u"], "", 0),
    ],
)
def test_gu_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gu command in visual."""
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
        ("abcde", ["v", "U"], "Abcde", 0),
        ("abcde\na", ["l", "v", "$", "U"], "aBCDE\na", 1),
        ("abcde\na", ["l", "v", "3l", "U", "0", "."], "ABCDE\na", 0),
        ("", ["v", "U"], "", 0),
    ],
)
def test_U_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test U command in visual."""
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
        ("abcde", ["v", "g", "U"], "Abcde", 0),
        ("abcde\na", ["l", "v", "$", "g", "U"], "aBCDE\na", 1),
        ("abcde\na", ["l", "v", "3l", "g", "U", "0", "."], "ABCDE\na", 0),
        ("", ["v", "g", "U"], "", 0),
    ],
)
def test_gU_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gU command in visual."""
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
        ("abCde", ["v", "g", "~"], "AbCde", 0),
        ("abCde\na", ["l", "v", "$", "g", "~"], "aBcDE\na", 1),
        ("abCde\na", ["l", "v", "3l", "g", "~", "0", "."], "AbCdE\na", 0),
        ("", ["v", "g", "~"], "", 0),
    ],
)
def test_gtilde_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test g~ command in visual."""
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
        ("", ["v", ">"], "", 0),
        ("abcde", ["2l", "v", ">"], "    abcde", 4),
        (" abcde\na", ["v", ">"], "     abcde\na", 5),
        ("a\n\na", ["v", "2j", ">"], "    a\n\n    a", 4),
    ],
)
def test_greater_cmd_in_visual(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test > command in visual."""
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
        ("", ["v", "<"], "", 0),
        ("    abcde", ["2l", "v", "<"], "abcde", 0),
        ("     abcde\na", ["v", "<"], " abcde\na", 1),
        ("    a\n\n    a", ["v", "2j", "<"], "a\n\na", 0),
    ],
)
def test_less_cmd_in_visual(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test < command in visual."""
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
        ('"dkwh"  "sdalkj"', ["8l", "v", "i", '"'], 14, [9, 15]),
        ('"dkwh"  "sdalkj"', ["7l", "v", "i", '"'], 7, [6, 8]),
        ('"dkwh"sd"', ["$", "v", "i", '"'], 8, [8, 9]),
        ("", ["v", "i", '"'], 0, [0, 0]),
        ('"0"', ["v", "i", '"'], 1, [1, 2]),
        ('"0"', ["l", "v", "i", '"'], 1, [1, 2]),
        ('"0"', ["2l", "v", "i", '"'], 1, [1, 2]),
        ('"0" ', ["3l", "v", "i", '"'], 3, [3, 4]),
        (' "0" ', ["v", "i", '"'], 2, [2, 3]),
        ("'0'", ["v", "i", "'"], 1, [1, 2]),
        ("'0'", ["l", "v", "i", "'"], 1, [1, 2]),
        ("'0'", ["2l", "v", "i", "'"], 1, [1, 2]),
        ("'0' ", ["3l", "v", "i", "'"], 3, [3, 4]),
        (" '0' ", ["v", "i", "'"], 2, [2, 3]),
    ],
)
def test_iquote_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test i" i' command in visual."""
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
        ('"dkwh"  "sdalkj"', ["8l", "v", "a", '"'], 15, [6, 16]),
        ('"dkwh"  "sdalkj"', ["7l", "v", "a", '"'], 8, [5, 9]),
        ('"dkwh"sd"', ["$", "v", "a", '"'], 8, [8, 9]),
        ("", ["v", "a", '"'], 0, [0, 0]),
        ('"0"', ["v", "a", '"'], 2, [0, 3]),
        ('"0"a', ["l", "v", "a", '"'], 2, [0, 3]),
        ('"0"   ', ["2l", "v", "a", '"'], 5, [0, 6]),
        ('"0"   a', ["2l", "v", "a", '"'], 5, [0, 6]),
        ('"0"   \na', ["2l", "v", "a", '"'], 5, [0, 6]),
        ('"0" ', ["3l", "v", "a", '"'], 3, [3, 4]),
        (' "0" ', ["v", "a", '"'], 4, [1, 5]),
        ("'0'", ["v", "a", "'"], 2, [0, 3]),
        ("'0'", ["l", "v", "a", "'"], 2, [0, 3]),
        ("'0'", ["2l", "v", "a", "'"], 2, [0, 3]),
        ("'0' ", ["3l", "v", "a", "'"], 3, [3, 4]),
    ],
)
def test_aquote_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test a" a' command in visual."""
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
        ("kk 2 3", ["v", "i", "w"], 1, [0, 2]),
        ("kk 2 3", ["l", "v", "i", "w"], 1, [0, 2]),
        ("kk 2 3", ["v", "2i", "w"], 2, [0, 3]),
        ("kk 2 3", ["l", "v", "5i", "w"], 5, [0, 6]),
        ("kk   2 3", ["3l", "v", "i", "w"], 4, [2, 5]),
        ("kk   2 3", ["2l", "v", "i", "w"], 4, [2, 5]),
        ("kk   2 3", ["4l", "v", "i", "w"], 4, [2, 5]),
        ("kk   2 3", ["2l", "v", "2i", "w"], 5, [2, 6]),
        ("kk   2 3\na", ["2l", "v", "4i", "w"], 7, [2, 8]),
        ("kk   2 3\na", ["2l", "v", "5i", "w"], 9, [2, 10]),
        ("kk   2 3\n   a", ["2l", "v", "5i", "w"], 11, [2, 12]),
        ("kk   2 3\na", ["v", "6i", "w"], 9, [0, 10]),
        ("abc.def", ["v", "i", "w"], 2, [0, 3]),
        ("abc.def", ["v", "2i", "w"], 3, [0, 4]),
        ("abc.def", ["v", "3i", "w"], 6, [0, 7]),
        ("abc.def", ["3l", "v", "i", "w"], 3, [3, 4]),
    ],
)
def test_iw_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test iw command in visual."""
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
        ("", ["v", "i", "W"], 0, [0, 0]),
        ("\n\n", ["j", "v", "i", "W"], 1, [1, 2]),
        ("fig.add_subplot(111)  # ", ["4l", "v", "i", "W"], 19, [0, 20]),
        ("fig.add_subplot(111)  # ", ["4l", "v", "2i", "W"], 21, [0, 22]),
        ("fig.add_subplot(111)  # ", ["4l", "v", "3i", "W"], 22, [0, 23]),
        ("fig.add_subplot(111)  # ", ["20l", "v", "i", "W"], 21, [20, 22]),
        ("fig.add_subplot(111)  # ", ["20l", "v", "2i", "W"], 22, [20, 23]),
        (" # \n 1", ["l", "v", "3i", "W"], 4, [1, 5]),
    ],
)
def test_iW_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test iW command in visual."""
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
        ("kk 2 3", ["v", "a", "w"], 2, [0, 3]),
        ("kk 2 3", ["l", "v", "a", "w"], 2, [0, 3]),
        ("kk 2 3", ["v", "2a", "w"], 4, [0, 5]),
        ("kk 2 3", ["v", "3a", "w"], 5, [0, 6]),
        ("kk 2 3 ", ["v", "3a", "w"], 6, [0, 7]),
        ("kk 2 3\n", ["v", "4a", "w"], 6, [0, 7]),
        ("kk 2 3 \n", ["v", "4a", "w"], 7, [0, 8]),
        ("kk 2 3 \na", ["v", "4a", "w"], 8, [0, 9]),
        ("kk 2 3\na ", ["v", "4a", "w"], 8, [0, 9]),
        ("kk   2 3", ["3l", "v", "a", "w"], 5, [2, 6]),
        ("kk   2 3", ["2l", "v", "a", "w"], 5, [2, 6]),
        ("kk   2 3", ["4l", "v", "a", "w"], 5, [2, 6]),
        ("kk   2 3 ", ["2l", "v", "2a", "w"], 7, [2, 8]),
        ("kk   2 3 4 ", ["2l", "v", "3a", "w"], 9, [2, 10]),
        ("kk   2 3\na", ["2l", "v", "3a", "w"], 9, [2, 10]),
        ("kk   2 3\n a", ["2l", "v", "3a", "w"], 10, [2, 11]),
        ("kk   2 3 \n a", ["2l", "v", "3a", "w"], 11, [2, 12]),
        ("kk   2 3 \n a", ["5l", "v", "a", "w"], 6, [5, 7]),
        ("kk   2 3 \n a", ["5l", "v", "2a", "w"], 8, [5, 9]),
        ("kk   2 3 \n a", ["5l", "v", "3a", "w"], 10, [5, 11]),
    ],
)
def test_aw_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test aw command in visual."""
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
        ("", ["v", "a", ")"], 0, [0, 0]),
        (" () ", ["v", "a", ")"], 2, [1, 3]),
        (" () ", ["l", "v", "a", ")"], 2, [1, 3]),
        (" (01234) ", ["3l", "v", "a", ")"], 7, [1, 8]),
        (" (01234) ", ["3l", "v", "a", "("], 7, [1, 8]),
        (" (01234) ", ["3l", "v", "a", "b"], 7, [1, 8]),
        (" [01234] ", ["3l", "v", "a", "["], 7, [1, 8]),
        (" [01234] ", ["3l", "v", "a", "]"], 7, [1, 8]),
        (" {01234} ", ["3l", "v", "a", "{"], 7, [1, 8]),
        (" {01234} ", ["3l", "v", "a", "B"], 7, [1, 8]),
        (" {01234} ", ["3l", "v", "a", "}"], 7, [1, 8]),
        (" {01234} ", ["l", "v", "a", "}"], 7, [1, 8]),
        (" {01234} ", ["7l", "v", "a", "}"], 7, [1, 8]),
        (" {\n(\nasdf)\nasdf} ", ["3l", "v", "a", "}"], 15, [1, 16]),
        (" (((kk)))", ["l", "v", "a", "("], 8, [1, 9]),
        (" (((kk)))", ["$", "v", "a", "("], 8, [1, 9]),
    ],
)
def test_a_bracket_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test a_bracket command in visual."""
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
        ("", ["v", "i", ")"], 0, [0, 0]),
        (" () ", ["v", "i", ")"], 0, [0, 1]),
        (" () ", ["l", "v", "i", ")"], 1, [1, 2]),
        (" (01234) ", ["3l", "v", "i", ")"], 6, [2, 7]),
        (" (01234) ", ["3l", "v", "i", "("], 6, [2, 7]),
        (" (01234) ", ["3l", "v", "i", "b"], 6, [2, 7]),
        (" [01234] ", ["3l", "v", "i", "["], 6, [2, 7]),
        (" [01234] ", ["3l", "v", "i", "]"], 6, [2, 7]),
        (" {01234} ", ["3l", "v", "i", "{"], 6, [2, 7]),
        (" {01234} ", ["3l", "v", "i", "}"], 6, [2, 7]),
        (" {01234} ", ["3l", "v", "i", "B"], 6, [2, 7]),
        (" {01234} ", ["l", "v", "i", "}"], 6, [2, 7]),
        (" {01234} ", ["7l", "v", "i", "}"], 6, [2, 7]),
        (" {\n(\nasdf)\nasdf} ", ["3l", "v", "i", "}"], 14, [2, 15]),
    ],
)
def test_i_bracket_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test i_bracket command in visual."""
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
    "text, cmd_list, cursor_pos, register_name, text_yanked",
    [
        ("a", ["v", "y"], 0, '"', "a"),
        ("abcd", ["l", "v", "2l", "y"], 1, '"', "bcd"),
        ("abcd", ["l", "v", "2l", '"', "0", "y"], 1, "0", "bcd"),
        ("abcd\ne", ["l", "v", "2l", "j", '"', "a", "y"], 1, "a", "bcd\ne"),
    ],
)
def test_y_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, register_name, text_yanked):
    """Test y command in visual."""
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
    assert reg.type == VimState.NORMAL
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None
    if register_name == '"':
        reg0 = vim.vim_cmd.vim_status.register_dict["0"]
        assert reg0.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected",
    [
        ("ak", ["v", "p"], 0, "k"),
        ("ak", ["v", "l", "y", "v", "p"], 1, "akk"),
        ("ak", ["v", "l", "y", "v", "P"], 1, "akk"),
        ("ak", ["v", "l", "y", "v", "2p"], 3, "akakk"),
        ("ab\ncd\nef", ["v", "j", "l", "y", "j", "v", "p"], 3, "ab\nab\ncdd\nef"),
        ("ab\ncd\nef", ["V", "y", "j", "v", "p"], 4, "ab\n\nab\nd\nef"),
    ],
)
def test_p_P_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, text_expected):
    """Test p command in visual."""
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
        ("ak", ["v", "d"], 0, "k", '"', "a"),
        ("ak", ["v", "l", "d"], 0, "", '"', "ak"),
        ("ab\nc\nde", ["v", "2j", "l", "d"], 0, "", '"', "ab\nc\nde"),
        ("ab\nc\nde", ["l", "v", "d"], 0, "a\nc\nde", '"', "b"),
    ],
)
def test_d_cmd_in_visual(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test d command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected
    assert reg.content == text_yanked
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ("ak", ["v", "x"], 0, "k", '"', "a"),
        ("ak", ["v", "l", "x"], 0, "", '"', "ak"),
        ("ab\nc\nde", ["v", "2j", "l", "x"], 0, "", '"', "ab\nc\nde"),
        ("ab\nc\nde", ["l", "v", "x"], 0, "a\nc\nde", '"', "b"),
    ],
)
def test_x_cmd_in_visual(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test x command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected
    assert reg.content == text_yanked
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ("ak", ["v", "c"], 0, "k", '"', "a"),
        ("ak", ["v", "l", "c"], 0, "", '"', "ak"),
        ("ab\nc\nde", ["v", "2j", "l", "c"], 0, "", '"', "ab\nc\nde"),
        ("ab\nc\nde", ["l", "v", "c"], 1, "a\nc\nde", '"', "b"),
    ],
)
def test_c_cmd_in_visual(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test c command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected
    assert reg.content == text_yanked
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ("ak", ["v", "s"], 0, "k", '"', "a"),
        ("ak", ["v", "l", "s"], 0, "", '"', "ak"),
        ("ab\nc\nde", ["v", "2j", "l", "s"], 0, "", '"', "ab\nc\nde"),
        ("ab\nc\nde", ["l", "v", "s"], 1, "a\nc\nde", '"', "b"),
    ],
)
def test_s_cmd_in_visual(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test s command in visual."""
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
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected
    assert reg.content == text_yanked
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("a", ["v", "/", "b", "\r"], 0, [0, 1]),
        ("a", ["v", "/", "b", "\r", "n"], 0, [0, 1]),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["v", "/", "d", "h", "r", Qt.Key_Return],
            1,
            [0, 2],
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["v", "/", "d", "h", "r", Qt.Key_Return, "n"],
            7,
            [0, 8],
        ),
        (
            " dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn",
            ["v", "/", "d", "h", "r", Qt.Key_Enter, "n", "N"],
            1,
            [0, 2],
        ),
    ],
)
def test_search_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test / command in visual."""
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
        ("a", ["v", "*"], 0, [0, 1]),
        ("a", ["v", "#"], 0, [0, 1]),
        ("dhr\n  Dhr\n\n_dhr\n   dhr", ["v", "*"], 19, [0, 20]),
        ("dhr\n  dhr\n\n_dhr\n   dhr", ["j2l", "v", "#"], 0, [0, 7]),
    ],
)
def test_asterisk_sharp_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test *, # command in visual."""
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
        ("01 34", ["v", Qt.Key_Space], 1, [0, 2]),
    ],
)
def test_space_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test space command in visual."""
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
        ("01 34", ["l", "v", Qt.Key_Backspace], 0, [0, 2]),
    ],
)
def test_backspace_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test backspace command in visual."""
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
        ("01 34\n   k", ["v", Qt.Key_Enter], 9, [0, 10]),
    ],
)
def test_enter_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test enter command in visual."""
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


def test_jump_mark_in_visual(vim_bot):
    """Jump to mark while in visual mode."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.reset_for_test()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyClicks(cmd_line, "ma")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(4)
    qtbot.keyClicks(cmd_line, "v'a")
    assert vim.vim_cmd.vim_status.vim_state == VimState.VISUAL
    assert editor.textCursor().position() == 0


@pytest.mark.parametrize(
    "start_line, cmd_list, expected",
    [
        (0, ["v", "]]"], 2),
        (6, ["v", "]]"], 6),
        (9, ["v", "]]"], 9),
    ],
)
def test_next_python_definition_in_visual(vim_bot, start_line, cmd_list, expected):
    """Jump to next Python definition while in Visual mode."""
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
        (10, ["v", "[["], 9),
        (6, ["v", "[["], 5),
        (2, ["v", "[["], 2),
    ],
)
def test_prev_python_definition_in_visual(vim_bot, start_line, cmd_list, expected):
    """Jump to previous Python definition while in Visual mode."""
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
        (0, ["v", "}}"], 3),
        (3, ["v", "}}"], 6),
        (6, ["v", "}}"], 9),
        (9, ["v", "}}"], 12),
        (12, ["v", "}}"], 17),
        (17, ["v", "}}"], 20),
    ],
)
def test_next_python_block_in_visual(vim_bot, start_line, cmd_list, expected):
    """Jump to next Python block while in Visual mode."""
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
        (20, ["v", "{{"], 17),
        (17, ["v", "{{"], 12),
        (12, ["v", "{{"], 9),
        (9, ["v", "{{"], 6),
        (6, ["v", "{{"], 3),
        (3, ["v", "{{"], 0),
    ],
)
def test_prev_python_block_in_visual(vim_bot, start_line, cmd_list, expected):
    """Jump to previous Python block while in Visual mode."""
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
