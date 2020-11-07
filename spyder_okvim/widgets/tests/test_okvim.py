# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
#
"""Tests for the plugin."""

# Standard library imports
import os
import os.path as osp

# Test library imports
import pytest
from unittest.mock import Mock

# Qt imports
from qtpy.QtWidgets import QWidget, QVBoxLayout, QApplication
from qtpy.QtGui import QTextCursor, QFont, QKeyEvent
from qtpy.QtCore import Qt, QEvent

# Spyder imports
from spyder.plugins.editor.widgets.editor import EditorStack

# Local imports
from spyder_okvim.plugin import OkVim
from spyder_okvim.utils.vim_status import VimState


LOCATION = osp.realpath(osp.join(
    os.getcwd(), osp.dirname(__file__)))


class VimTesting(OkVim):
    CONF_FILE = False

    def __init(self, parent):
        OkVim.__init__(self, parent)


class EditorMock(QWidget):
    """Editor plugin mock."""

    def __init__(self, editor_stack):
        """Editor Mock constructor."""
        QWidget.__init__(self, None)
        self.editor_stack = editor_stack
        self.editorsplitter = self.editor_stack
        self.open_action = Mock()
        self.new_action = Mock()
        self.save_action = Mock()
        self.close_action = Mock()

        layout = QVBoxLayout()
        layout.addWidget(self.editor_stack)
        self.setLayout(layout)

    def get_current_editorstack(self):
        """Return EditorStack instance."""
        return self.editor_stack


class StatusBarMock(QWidget):
    """Stausbar mock."""

    def __init__(self):
        QWidget.__init__(self, None)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

    def insertPermanentWidget(self, idx, widget):
        self.layout.addWidget(widget)


class MainMock(QWidget):
    """Spyder MainWindow mock."""

    def __init__(self, editor_stack):
        """Main Window Mock constructor."""
        QWidget.__init__(self, None)
        self.plugin_focus_changed = Mock()
        self.editor = EditorMock(editor_stack)
        layout = QVBoxLayout()
        layout.addWidget(self.editor)
        self.setLayout(layout)
        self.status_bar = StatusBarMock()

    add_dockwidget = Mock()

    def statusBar(self):
        return self.status_bar


@pytest.fixture
def editor_bot(qtbot):
    """Editorstack pytest fixture."""
    text = ('   123\n'
            'line 1\n'
            'line 2\n'
            'line 3\n'
            'line 4')  # a newline is added at end
    editor_stack = EditorStack(None, [])

    # Fix the area of the selection
    font = QFont("Courier New")
    font.setPointSize(10)
    editor_stack.set_default_font(font)

    editor_stack.set_find_widget(Mock())
    editor_stack.set_io_actions(Mock(), Mock(), Mock(), Mock())
    finfo = editor_stack.new(osp.join(LOCATION, 'foo.txt'), 'utf-8', text)
    editor_stack.new(osp.join(LOCATION, 'foo1.txt'), 'utf-8', text)
    editor_stack.new(osp.join(LOCATION, 'foo2.txt'), 'utf-8', text)
    editor_stack.new(osp.join(LOCATION, 'foo3.txt'), 'utf-8', text)
    main = MainMock(editor_stack)
    # main.show()
    qtbot.addWidget(main)
    return main, editor_stack, finfo.editor, qtbot


@pytest.fixture
def vim_bot(editor_bot):
    """Create an spyder-vim plugin instance."""
    main, editor_stack, editor, qtbot = editor_bot
    vim = VimTesting(main)
    vim.register_plugin()
    return main, editor_stack, editor, vim, qtbot


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('\ncdef\naslkdj\ndslkj', ['h'], 0),
        ('\ncdef\naslkdj\ndslkj', ['j', '4l', 'h'], 3),
        ('\ncdef\naslkdj\ndslkj', ['j', '3l', 'j', '3h'], 6),
        ('    ab\ncdef\n', ['5l', '10h'], 0),
        ('    ab\ncdef\n', ['2j', '5h'], 12)
    ]
)
def test_h_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test h command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('\ncdef\naslkdj\ndslkj', ['j'], 1),
        ('\ncdef\naslkdj\ndslkj', ['j', '4l', 'j'], 9),
        ('\ncdef\naslkdj\ndslkj', ['j', '3l', '2j'], 16),
        ('\ncdef\naslkdj\ndslkj', ['j', '3l', '3j'], 16),
        ('    ab\ncdef\n', ['5l', 'j'], 10),
        ('    ab\ncdef\n', ['5l', '2j', 'j'], 12)
    ]
)
def test_j_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test j command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('    ab\ncdef\n', ['2j', '2k'], 0),
        ('    ab\ncdef\n', ['5l', '2j', 'k'], 7)
    ]
)
def test_k_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test k command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('\ncdef\naslkdj\ndslkj', ['l'], 0),
        ('\ncdef\naslkdj\ndslkj', ['j', '4l'], 4),
        ('\ncdef\naslkdj\ndslkj', ['j', '3l', 'j', 'l'], 10),
        ('    ab\ncdef\n', ['5l'], 5),
        ('    ab\ncdef\n', ['2j', '5l'], 12)
    ]
)
def test_l_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test l command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("import numpy as np", ['v'], 0, [0, 1]),
        ("import numpy as np", ['v', '5l'], 5, [0, 6]),
        ("import numpy as np", ['5l', 'v'], 5, [5, 6]),
        ("import numpy as np", ['5l', 'v', '3l'], 8, [5, 9]),
        ("import numpy as np", ['5l', 'v', '3l', '7h'], 1, [1, 6]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['v', 'j'], 19, [0, 20]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['v', 'j', '5l'], 24, [0, 25]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['v', 'j', '5l', '3h'], 21, [0, 22]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['l', 'v', '2j'], 52, [1, 53]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['l', 'v', '2j', '4l'], 56, [1, 57]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['l', 'v', '2j', '4l', 'k'], 24, [1, 25]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['j', '5l', 'v', 'k'], 5, [5, 25]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['j', '5l', 'v', 'k', '5h'], 0, [0, 25]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['j', '5l', 'v', 'k', '5h', 'j'], 19, [19, 25]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['j', '5l', 'v', 'k', '5h', '2j'], 51, [24, 52]),
        ("""
import matplotlib.pyplot as plt
import scipy.scipy as sc
""", ['v', '3j', '30l'], 58, [0, 58])
    ]
)
def test_v_cmd(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test v command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("import numpy as np", ['V'], 0, [0, 18]),
        ("import numpy as np", ['V', 'l', 'h'], 0, [0, 18]),
        ("import numpy as np", ['V', '5l'], 5, [0, 18]),
        ("import numpy as np", ['5l', 'V'], 5, [0, 18]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['V', 'j'], 19, [0, 50]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['2l', 'V', '2j', '5l'], 58, [0, 75]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc
""", ['2l', 'V', '3j', 'k', 'j'], 76, [0, 76]),
        ("""
import matplotlib.pyplot as plt
import scipy.scipy as sc
""", ['5j', 'V', '5k'], 0, [0, 58]),
    ]
)
def test_V_cmd(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test V command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['0'], 0),
        ('cdef', ['l', '0'], 0),
        ('\ncdef\naslkdj\ndslkj', ['j', '4l', '0'], 1),
        ('c\n', ['j', '0'], 2),
    ]
)
def test_zero_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test 0 command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("import numpy as np", ['v', '0'], 0, [0, 1]),
        ("import numpy as np", ['5l', 'v', '0'], 0, [0, 6]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['v', 'j', '0'], 19, [0, 20]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['v', 'j', '5l', '0'], 19, [0, 20]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['l', 'v', '2j', '0'], 51, [1, 52]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['l', 'v', '2j', '4l', 'k', '0'], 19, [1, 20]),
        ("""
import matplotlib.pyplot as plt
import scipy.scipy as sc
""", ['v', '3j', '0'], 58, [0, 58])
    ]
)
def test_zero_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test 0 command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("import numpy as np", ['V', '0'], 0, [0, 18]),
        ("import numpy as np", ['5l', 'V', '0'], 0, [0, 18]),
        ("""import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""", ['V', 'j', '5l', '0'], 19, [0, 50])
    ]
)
def test_zero_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test 0 command in v-line."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['i'], 0)
    ]
)
def test_i_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test i command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    # assert vim.vim_cmd.vim_status.vim_state == VimState.INSERT


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('', ['I'], 0),
        ('  ', ['I'], 0),
        ('  a', ['I'], 2),
        ('  ab', ['5l', 'I'], 2),
    ]
)
def test_I_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test I command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('', ['a'], 0),
        ('0', ['a'], 1),
        ('\n1', ['j', 'a'], 2),
        ('\n1\n', ['2j', 'a'], 3),
    ]
)
def test_a_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test a command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('', ['A'], 0),
        ('012', ['A'], 3),
        ('\n123', ['j', 'A'], 4),
        ('\n1\n', ['2j', 'A'], 3),
    ]
)
def test_A_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test A command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('', ['^'], 0),
        ('   ', ['l', '^'], 1),
        (' cdef', ['5l', '^'], 1),
        ('\n cdef\naslkdj\ndslkj', ['j', '4l', '^'], 2),
        ('c\n', ['j', '^'], 2),
    ]
)
def test_caret_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test ^ command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("   import numpy as np", ['v', '^'], 3, [0, 4]),
        ("   import numpy as np", ['10l', 'v', '^'], 3, [3, 11]),
    ]
)
def test_caret_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test ^ command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("   import numpy as np", ['V', '^'], 3, [0, 21]),
        ("   import numpy as np", ['10l', 'V', '^'], 3, [0, 21]),
    ]
)
def test_caret_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test ^ command in v-line."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['$'], 0),
        ('cdef', ['l', '$'], 3),
        ('\ncdef\naslkdj\ndslkj', ['j', '4l', '$'], 4),
        ('c\n', ['j', '$'], 2),
    ]
)
def test_dollar_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test $ command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos




@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("import numpy as np", ['v', '$'], 18, [0, 18]),
    ]
)
def test_dollar_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test $ command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("import numpy as np", ['V', '$'], 18, [0, 18])
    ]
)
def test_dollar_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test $ command in v-line."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("import re", ['7l', 'K'], 7)
    ]
)
def test_K_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test K command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ['o'], "\n", 1),
        ("\na\n", ['3j', 'o'], "\na\n\n", 4)
    ]
)
def test_o_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test o command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01 34", ['v', 'w'], 3, [0, 4]),
        ("01 34", ['v', 'w', 'o'], 0, [0, 4]),
        ("01 34", ['v', 'w', 'o', 'o'], 3, [0, 4]),
        ("\n", ['j', 'v'], 1, [1, 1]),
        ("\n", ['j', 'v', 'o'], 1, [1, 1]),
        ("01 34\n6", ['v', 'j'], 6, [0, 7]),
        ("01 34\n6", ['v', 'j', 'o'], 0, [0, 7]),
    ]
)
def test_o_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test o command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("01 34\n", ['V', 'w'], 3, [0, 5]),
        ("01 34\n", ['V', 'w', 'o'], 0, [0, 5]),
        ("01 34\n", ['V', 'w', 'o', 'o'], 4, [0, 5]),
        ("\n", ['j', 'V'], 1, [1, 1]),
        ("\n", ['j', 'V', 'o'], 1, [1, 1]),
        ("01 34\n6\n", ['V', 'j'], 6, [0, 7]),
        ("01 34\n6\n", ['V', 'j', 'o'], 0, [0, 7]),
    ]
)
def test_o_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test o command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("", ['O'], "\n", 0),
        ("\na\n", ['3j', 'O'], "\na\n\n", 3)
    ]
)
def test_O_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test O command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected


def test_undo_redo(vim_bot):
    """Test undo redo command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text('a')
    editor.moveCursor(QTextCursor.EndOfLine)
    qtbot.keyPress(editor, Qt.Key_Enter)
    qtbot.keyPress(editor, Qt.Key_1)

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, '2u')

    assert editor.toPlainText() == 'a'
    assert editor.textCursor().position() == 0

    qtbot.keyClicks(cmd_line, 'g')
    qtbot.keyPress(cmd_line, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == 'a'
    assert editor.textCursor().position() == 0

    qtbot.keyClicks(cmd_line, 'v')
    qtbot.keyPress(cmd_line, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == 'a'
    assert editor.textCursor().position() == 0

    qtbot.keyClicks(cmd_line, '/')
    qtbot.keyPress(cmd_line, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == 'a'
    assert editor.textCursor().position() == 0

    qtbot.keyPress(cmd_line, Qt.Key_Escape)
    qtbot.keyClicks(cmd_line, '2')
    qtbot.keyPress(cmd_line, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == 'a\n1'
    assert editor.textCursor().position() == 2


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ['J'], "", 0),
        ("\n\n", ['3j', 'J'], "\n\n", 2),
        ("0\n23", ['J'], "0 23", 1),
        ("0\n23\n5", ['2J'], "0 23\n5", 1),
        ("0\n2\n  \n3", ['4J'], "0 2 3", 3),
        ("0\n23\n5", ['2J', '.'], "0 23 5", 4),
    ]
)
def test_J_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test J command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ['v', 'J'], "", 0),
        ("\n\n", ['3j', 'v', 'J'], "\n\n", 2),
        ("0\n23", ['j', 'l', 'v', 'k', 'J'], "0 23", 1),
        ("0\n2\n4\n6\n8\n", ['v', '2j', 'J'], "0 2 4\n6\n8\n", 3),
        ("0\n2\n4\n6\n8\n", ['v', '2j', 'J', '.'], "0 2 4 6 8\n", 7)
    ]
)
def test_J_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test J command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ['V', 'J'], "", 0),
        ("\n\n", ['3j', 'V', 'J'], "\n\n", 2),
        ("0\n23", ['j', 'l', 'V', 'k', 'J'], "0 23", 1),
        ("0\n2\n4\n6\n8\n", ['V', '2j', 'J'], "0 2 4\n6\n8\n", 3),
        ("0\n2\n4\n6\n8\n", ['V', '2j', 'J', '.'], "0 2 4 6 8\n", 7)
    ]
)
def test_J_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test J command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('01 34', ['w'], 3),
        ('01 34', ['2w'], 4),
        ('01 34\na', ['3w'], 6),
        ('01 34\n  a', ['3w'], 8),
        ('01 34\n  a', ['2l', 'w'], 3),
    ]
)
def test_w_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test w command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01 34", ['v', 'w'], 3, [0, 4]),
        ("01 34", ['v', '2w'], 5, [0, 5]),
        ("01 34\na\n", ['v', '3w'], 8, [0, 8]),
        ("01 34\n  a\n", ['v', '3w'], 10, [0, 10]),
    ]
)
def test_w_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test w command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("01 34", ['V', 'w'], 3, [0, 5]),
    ]
)
def test_w_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test w command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['W'], 0),
        ('029.d98@jl 34', ['W'], 11),
        ('029.d98@jl 34', ['2W'], 12),
        ('029.d98@jl 34\na', ['2W'], 14),
        ('029.d98@jl 34\n  a', ['2W'], 16),
        ('\na (', ['W'], 1),
        ('\n  a (', ['W'], 3),
    ]
)
def test_W_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test W command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ('', ['v', 'W'], 0, [0, 0]),
        ('029.d98@jl 34', ['v', 'W'], 11, [0, 12]),
        ('029.d98@jl 34', ['v', '2W'], 13, [0, 13]),
        ('029.d98@jl 34\na', ['v', '2W'], 14, [0, 15]),
        ('029.d98@jl 34\n  a', ['v', '2W'], 16, [0, 17]),
    ]
)
def test_W_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test W command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['V', 'W'], 0, [0, 0]),
        ('029.d98@jl 34', ['V', 'W'], 11, [0, 13]),
        ('029.d98@jl 34', ['V', '2W'], 13, [0, 13]),
        ('029.d98@jl 34\na', ['V', '2W'], 14, [0, 15]),
        ('029.d98@jl 34\n  a', ['V', '2W'], 16, [0, 17]),
    ]
)
def test_W_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test W command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('01 34', ['b'], 0),
        ('01 34', ['$', 'b'], 3),
        ('0\n2\n4\n6', ['3j', '3b'], 0),
    ]
)
def test_b_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test b command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01 34", ['$', 'v', 'b'], 3, [3, 5]),
    ]
)
def test_b_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test b command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("01 34", ['$', 'V', 'b'], 3, [0, 5]),
    ]
)
def test_b_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test b command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['e'], 0),
        ('01', ['e'], 1),
        ('01 ', ['e', 'e'], 2),
        ('01 34', ['e', 'e'], 4),
        ('01 34\n6 ', ['3e'], 6),
        ('01 34\n 7 ', ['3e'], 7),
        ('01 34\n67 ', ['3e'], 7),
        ('01 34\n\n   \n  ab', ['3e'], 14),
        ('01 34\n\n   \n  ab', ['e', 'e', 'e'], 14),
        (' 12 45', ['e'], 2),
    ]
)
def test_e_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test e command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ("01 34", ['v', 'e'], 1, [0, 2]),
    ]
)
def test_e_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test e command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("01 34\n67 90", ['V', 'e'], 1, [0, 5]),
        ("01 34\n67 90", ['V', '3e'], 7, [0, 11]),
    ]
)
def test_e_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test e command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


def test_gt_cmd(vim_bot):
    """Test gt, gT command."""
    _, editor_stack, editor, vim, qtbot = vim_bot

    assert 0 == editor_stack.get_stack_index()

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'gt')
    assert 1 == editor_stack.get_stack_index()

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'gt')
    assert 2 == editor_stack.get_stack_index()

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'gt')
    assert 3 == editor_stack.get_stack_index()

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'gT')
    assert 2 == editor_stack.get_stack_index()

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, '1gt')
    assert 0 == editor_stack.get_stack_index()

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, '2gt')
    assert 1 == editor_stack.get_stack_index()

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, '3gt')
    assert 2 == editor_stack.get_stack_index()

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'gt')
    qtbot.keyClicks(cmd_line, 'gT')
    assert 2 == editor_stack.get_stack_index()

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, '2gT')
    assert 0 == editor_stack.get_stack_index()

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'gT')
    assert 3 == editor_stack.get_stack_index()

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'gt')
    assert 0 == editor_stack.get_stack_index()


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('0\n2\n4\n', ['j', '10G'], 2),
        ('0\n2\n4\n', ['2G'], 2),
        ('0\n     \n8\n', ['2G'], 6),
        ('0\n2\n4\n', ['G'], 6),
        ('0\n2\n4\n     a', ['G'], 11)
    ]
)
def test_G_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test G command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ('0\n2\n4\n', ['v', '2G'], 2, [0, 3]),
        ('0\n     \n8\n', ['v', '2G'], 6, [0, 7]),
        ('0\n2\n4\n', ['v', 'G'], 6, [0, 6]),
        ('0\n2\n4\n     a', ['v', 'G'], 11, [0, 12])
    ]
)
def test_G_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test G command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('0\n2\n4\n', ['V', '2G'], 2, [0, 3]),
        ('0\n     \n8\n', ['V', '2G'], 6, [0, 7]),
        ('0\n2\n4\n', ['V', 'G'], 6, [0, 6]),
        ('0\n2\n4\n     a', ['V', 'G'], 11, [0, 12])
    ]
)
def test_G_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test G command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('0\n2\n4\n', ['4j', 'gg'], 0),
        ('0\n2\n4\n', ['2gg'], 2),
        ('0\n     \n8\n', ['2gg'], 6),
        ('0\n2\n4\n', ['gg'], 0),
        ('0\n2\n4\n     a', ['4gg'], 11),
        ('', ['gg'], 0),
        ('', ['2gg'], 0)
    ]
)
def test_gg_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test gg command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ('0\n2\n4\n', ['v', '2gg'], 2, [0, 3]),
        ('0\n     \n8\n', ['v', '2gg'], 6, [0, 7]),
        ('    0\n2\n4\n', ['4j', 'v', 'gg'], 4, [4, 10])
    ]
)
def test_gg_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test gg command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('0\n2\n4\n', ['V', '2gg'], 2, [0, 3]),
        ('0\n     \n8\n', ['V', '2gg'], 6, [0, 7]),
        ('    0\n2\n4\n', ['4j', 'V', 'gg'], 4, [0, 10])
    ]
)
def test_gg_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test gg command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('abcde', ['~'], 'Abcde', 1),
        ('abcde', ['2~'], 'ABcde', 2),
        ('abcde', ['2~', '.'], 'ABCDe', 4),
        ('abcde', ['20~'], 'ABCDE', 4),
        ('', ['10~'], '', 0)
    ]
)
def test_tilde_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test ~ command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('abcde', ['v','~'], 'Abcde', 0),
        ('abcde\na', ['l', 'v', '$', '~'], 'aBCDE\na', 1),
        ('abcde\na', ['l', 'v', '3l', '~', '0', '.'], 'AbcdE\na', 0),
        ('', ['v', '~'], '', 0)
    ]
)
def test_tilde_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test ~ command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('abcde', ['V', '~'], 'ABCDE', 0),
        ('abcde\na', ['l', 'V', '$', '~'], 'ABCDE\na', 0),
        ('abcde\na', ['l', 'V', '$', '~', 'j', '.'], 'ABCDE\nA', 6),
        ('', ['V', '~'], '', 0)
    ]
)
def test_tilde_cmd_in_vline(vim_bot, text, cmd_list, text_expected,
                            cursor_pos):
    """Test ~ command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('', ['^A'], '', 0),
        ('\n1\n', ['2j', '^A'], '\n1\n', 3),
        ('1', ['^A'], '2', 0),
        ('9', ['^A'], '10', 1),
        ('100', ['^A'], '101', 2),
        ('100', ['l', '^A'], '101', 2),
        (' 100a', ['l', '^A'], ' 101a', 3),
        (' -1a', ['2l', '^A'], ' 0a', 1),
        (' -2a', ['l', '^A'], ' -1a', 2),
        (' -2a', ['l', '15', '^A'], ' 13a', 2),
        (' -2a', ['l', '15', '^A', '.'], ' 28a', 2),
        (' -2a', ['l', '15', '^A', '2.'], ' 15a', 2),
        (' -2a', ['l', 'c', '^A'], ' -2a', 1),
        (' -2a', ['l', '/', '^A'], ' -2a', 1),
    ]
)
def test_add_num_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test add_num."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        if cmd != '^A':
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
        ('', ['^X'], '', 0),
        ('\n1\n', ['2j', '^X'], '\n1\n', 3),
        ('1', ['^X'], '0', 0),
        ('0', ['^X'], '-1', 1),
        ('100', ['^X'], '99', 1),
        ('100', ['l', '^X'], '99', 1),
        (' 100a', ['l', '^X'], ' 99a', 2),
        (' -1a', ['2l', '^X'], ' -2a', 2),
        (' -2a', ['l', '^X'], ' -3a', 2),
        (' -2a', ['l', '15', '^X'], ' -17a', 3),
        (' -2a', ['l', '15', '^X', '.'], ' -32a', 3),
        (' -2a', ['l', '15', '^X', '2.'], ' -19a', 3),
        (' -2a', ['l', 'c', '^X'], ' -2a', 1),
        (' -2a', ['l', '/', '^X'], ' -2a', 1),
    ]
)
def test_subtract_num_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test subtract_num."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        if cmd != '^X':
            qtbot.keyClicks(cmd_line, cmd)
        else:
            event = QKeyEvent(QEvent.KeyPress, Qt.Key_X, Qt.ControlModifier)
            vim.vim_cmd.commandline.keyPressEvent(event)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cmd_line_expected",
    [
        ('', [":", "k", "k"], ':kk'),
        ('', [":", "k", "k", Qt.Key_Escape], '')
    ]
)
def test_colon_cmd(vim_bot, text, cmd_list, cmd_line_expected):
    """Test colon command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == cmd_line_expected


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('', ['%'], 0),
        ('\n', ['j', '%'], 1),
        ('()', ['%'], 1),
        ('()', ['$', '%'], 0),
        (' () ', ['$', '%'], 3),
        (' () ', ['2l', '%'], 1),
        (' (  \n) ', ['%'], 5),
        (' (  \n) ', ['%', '%'], 1),
        (' ({  \n}) ', ['%'], 7),
        (' ({  \n}) ', ['%', '%'], 1),
        (' ({  \n}) ', ['2l', '%'], 6),
        (' ({  \n}) ', ['2l', '%', '%'], 2)
    ]
)
def test_percent_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test % command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ('', ['v', '%'], 0, [0, 0]),
        ('\n', ['j', 'v', '%'], 1, [1, 1]),
        (' ()', ['v', '%'], 2, [0, 3]),
        (' ()', ['v', '%', '%'], 1, [0, 2])
    ]
)
def test_percent_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test % command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['V', '%'], 0, [0, 0]),
        ('\n', ['j', 'V', '%'], 1, [1, 1]),
        (' ()', ['V', '%'], 2, [0, 3]),
        (' ()', ['V', '%', '%'], 1, [0, 3])
    ]
)
def test_percent_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test % command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['f', 'r'], 0),
        ('', [';'], 0),
        ('', [','], 0),
        ('\n', ['j', 'f', 'r'], 1),
        ('\n r', ['j', 'f', 'r'], 2),
        ('\n r', ['j', '2', 'f', 'r'], 1),
        ('\n rr', ['j', '2', 'f', 'r'], 3),
        ('\n rr', ['j', '3', 'f', 'r'], 1),
        ('\n rr', ['j', 'l', 'f', 'r'], 3),
        ('\n rr', ['l', 'f', 'r'], 0),
        ('\n rr', ['j', 'f', 'r', ';'], 3),
        ('\n rr', ['j', 'f', 'r', ';', ','], 2),
        ('\n rrr', ['j', 'f', 'r', '2;'], 4),
        ('\n rrr', ['j', 'f', 'r', '2;', '2,'], 2)
    ]
)
def test_f_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test f command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.sub_mode is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ('', ['v', 'f', 'r'], 0, [0, 0]),
        ('\n', ['j', 'v', 'f', 'r'], 1, [1, 1]),
        (' rr', ['v', 'f', 'r'], 1, [0, 2]),
        (' rr', ['v', 'f', 'r', ';'], 2, [0, 3]),
        (' rr', ['v', 'f', 'r', ';', ','], 1, [0, 2]),
    ]
)
def test_f_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test f command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['V', 'f', 'r'], 0, [0, 0]),
        ('\n', ['j', 'V', 'f', 'r'], 1, [1, 1]),
        (' rr', ['V', 'f', 'r'], 1, [0, 3]),
        (' rr', ['V', 'f', 'r', ';'], 2, [0, 3]),
        (' rr', ['V', 'f', 'r', ';', ','], 1, [0, 3]),
    ]
)
def test_f_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test f command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['F', 'r'], 0),
        ('\n', ['j', 'F', 'r'], 1),
        ('\n r', ['j', 'F', 'r'], 1),
        ('\n r', ['j', '$', 'F', 'r'], 2),
        ('\n  r ', ['j', '$', 'F', 'r'], 3),
        ('\n  rr', ['j', '$', 'F', 'r'], 3),
        ('\n  rr', ['j', '$', 'F', 'r', ','], 4),
        ('\n  rr', ['j', '$', 'F', 'r', ',', ';'], 3),
        ('\n  rr', ['j', '$', '2F', 'r'], 4),
    ]
)
def test_F_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test F command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.sub_mode is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ('', ['v', 'F', 'r'], 0, [0, 0]),
        ('\n', ['j', 'v', 'F', 'r'], 1, [1, 1]),
        (' rr ', ['v', '$', 'F', 'r'], 2, [0, 3]),
        (' rr ', ['v', '$', 'F', 'r', ';'], 1, [0, 2]),
        (' rr ', ['v', '$', 'F', 'r', ';', ','], 2, [0, 3]),
    ]
)
def test_F_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test F command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['V', 'F', 'r'], 0, [0, 0]),
        ('\n', ['j', 'V', 'F', 'r'], 1, [1, 1]),
        (' rr ', ['V', '$', 'F', 'r'], 2, [0, 4]),
        (' rr ', ['V', '$', 'F', 'r', ';'], 1, [0, 4]),
        (' rr ', ['V', '$', 'F', 'r', ';', ','], 2, [0, 4]),
    ]
)
def test_F_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test F command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['t', 'r'], 0),
        ('\n', ['j', 't', 'r'], 1),
        ('\n r', ['j', 't', 'r'], 1),
        ('\n  r', ['j', 't', 'r'], 2),
        ('\n  rr', ['j', 't', 'r', ';'], 3),
        ('\n  rr', ['j', 't', 'r', ';', ','], 3),
        ('\n  rrr', ['j', 't', 'r', '2;'], 3),
        ('\n  rrr', ['j', 't', 'r', ';', ';'], 4),
        ('\n  rrr', ['j', 't', 'r', ';', ';', ','], 4),
        ('\n  rrrr', ['j', 't', 'r', '4;'], 5),
        ('\n  rrrr', ['j', 't', 'r', '4;', ','], 4),
        ('\n  r\n', ['j', 't', 'r'], 2),
        ('\n  rr\n', ['j', 't', 'r', ';'], 3),
        ('\n  rr\n', ['j', 't', 'r', ';', ','], 3),
        ('\n  rrr\n', ['j', 't', 'r', '2;'], 3),
        ('\n  rrr\n', ['j', 't', 'r', ';', ';'], 4),
        ('\n  rrr\n', ['j', 't', 'r', ';', ';', ','], 4),
        ('\n  rrrr\n', ['j', 't', 'r', '4;'], 5),
        ('\n  rrrr\n', ['j', 't', 'r', '4;', ','], 4),
        ('\n  r r r r', ['j', '2t', 'r'], 4),
        ('\n  r r r r', ['j', '2t', 'r', '0'], 1),
        ('\n  r r r r', ['j', '2t', 'r', '0', ';'], 2),
        ('\n  r r r r', ['j', '2t', 'r', '0', '2;'], 4),
    ]
)
def test_t_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test t command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.sub_mode is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('', ['T', 'r'], 0),
        ('r\n', ['j', 'T', 'r'], 2),
        ('r ', ['T', 'r'], 0),
        ('r ', ['T', 'r', ';'], 0),
        ('r ', ['T', 'r', ';', ','], 0),
        ('\n r ', ['j', '$',  'T', 'r'], 3),
        ('\n rr ', ['j', '$',  'T', 'r'], 4),
        ('\n rr ', ['j', '$',  '2T', 'r'], 3),
        ('\n rrr ', ['j', '$',  '2T', 'r', ';'], 3),
        ('\n rrr r', ['j', '$', '2T', 'r', ';', ','], 5),
        ('\n r \n', ['j', '$', 'T', 'r'], 3),
        ('\n rr \n', ['j', '$', 'T', 'r'], 4),
        ('\n rr \n', ['j', '$', '2T', 'r'], 3),
        ('\n rrr \n', ['j', '$', '2T', 'r', ';'], 3),
        ('\n rrr r\n', ['j', '$', '2T', 'r', ';', ','], 5),
    ]
)
def test_T_cmd(vim_bot, text, cmd_list, cursor_pos):
    """Test T command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.sub_mode is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ('', ['v', 't', 'r'], 0, [0, 0]),
        ('\n', ['j', 'v', 't', 'r'], 1, [1, 1]),
        ('  rr', ['v', 't', 'r'], 1, [0, 2]),
        ('  rr', ['v', 't', 'r', ';'], 2, [0, 3]),
        ('  rrrr', ['v', 't', 'r', '4;'], 4, [0, 5]),
        ('  rrrr', ['v', 't', 'r', '4;', ','], 3, [0, 4]),
    ]
)
def test_t_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test t command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['V', 't', 'r'], 0, [0, 0]),
        ('\n', ['j', 'V', 't', 'r'], 1, [1, 1]),
        ('  rr', ['V', 't', 'r'], 1, [0, 4]),
        ('  rr', ['V', 't', 'r', ';'], 2, [0, 4]),
        ('  rrrr', ['V', 't', 'r', '4;'], 4, [0, 6]),
        ('  rrrr', ['V', 't', 'r', '4;', ','], 3, [0, 6]),
    ]
)
def test_t_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test t command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['v', 'T', 'r'], 0, [0, 0]),
        ('r\n', ['j', 'v', 'T', 'r'], 2, [2, 2]),
        ('  rr  ', ['v', '$', 'T', 'r'], 4, [0, 5]),
        ('  rr  ', ['v', '$', 'T', 'r', ';'], 3, [0, 4]),
        ('  rrrr', ['v', '$', 'T', 'r', '4;'], 3, [0, 4]),
        ('  rrrr', ['v', '$', 'T', 'r', '4;', ','], 4, [0, 5]),
    ]
)
def test_T_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test T command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['V', 'T', 'r'], 0, [0, 0]),
        ('r\n', ['j', 'V', 'T', 'r'], 2, [2, 2]),
        ('  rr  ', ['V', '$', 'T', 'r'], 4, [0, 6]),
        ('  rr  ', ['V', '$', 'T', 'r', ';'], 3, [0, 6]),
        ('  rrrr', ['V', '$', 'T', 'r', '4;'], 3, [0, 6]),
        ('  rrrr', ['V', '$', 'T', 'r', '4;', ','], 4, [0, 6]),
    ]
)
def test_T_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test T command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("", ['r', 'r'], "", 0),
        ("\n", ['j', 'r', 'r'], "\n", 1),
        ("\n\na", ['j', 'r', 'r'], "\n\na", 1),
        ("a", ['r', 'r'], "r", 0),
        ("a", ['2r', 'r'], "a", 0),
        ("aa", ['2r', 'r'], "rr", 1),
        (" aa", ['3r', 'r'], "rrr", 2),
        (" aaaa", ['2l', '2r', 'r'], " arra", 3),
        (" aaaa", ['2l', '2r', 'r', '.'], " arrr", 4),
        (" aaaa", ['2l', '2r', 'r', '3.'], " arra", 3),
    ]
)
def test_r_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test r command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ['v', 'r', 'r'], "", 0),
        ("1\n", ['j', 'v', 'r', 'r'], "1\n", 2),
        ("\n\na", ['j', 'v', 'r', 'r'], "\n\na", 1),
        ("a", ['v', 'r', 'r'], "r", 0),
        (" a\nbc\n", ['l', 'v', 'j', 'r', 'r'], " r\nrr\n", 1),
        (" a\nbc\nde", ['l', 'v', 'j', 'r', 'r'], " r\nrr\nde", 1),
        (" a\nbc\nde", ['l', 'v', 'j', 'r', 'r', 'j', '.'], " r\nrr\nrr", 4)
    ]
)
def test_r_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test r command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ("", ['V', 'r', 'r'], "", 0),
        ("1\n", ['j', 'V', 'r', 'r'], "1\n", 2),
        ("\n\na", ['j', 'V', 'r', 'r'], "\n\na", 1),
        ("a", ['V', 'r', 'r'], "r", 0),
        (" a\nbc\n", ['l', 'V', 'j', 'r', 'r'], "rr\nrr\n", 0),
        (" a\nbc\nkk", ['l', 'V', 'j', 'r', 'r'], "rr\nrr\nkk", 0),
        (" a\nbc\nkk", ['l', 'V', 'j', 'r', 'r', 'j', '.'], "rr\nrr\nrr", 3),
    ]
)
def test_r_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test r command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")

    assert sel == []
    assert cmd_line.text() == ""
    assert vim.vim_cmd.vim_status.vim_state == VimState.NORMAL
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected


def test_ZZ_cmd(vim_bot):
    """Test ZZ command."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'ZZ')
    main.editor.save_action.trigger.assert_called_once_with()
    main.editor.close_action.trigger.assert_called_once_with()


def test_ZQ_cmd(vim_bot):
    """Test ZQ command."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'ZQ')
    main.editor.close_action.trigger.assert_called_once_with()


def test_colon_w_command(vim_bot):
    """Test :w."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, ':')
    qtbot.keyClicks(cmd_line, 'w')
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.save_action.trigger.assert_called_once_with()


def test_colon_q_command(vim_bot):
    """Test :q."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, ':')
    qtbot.keyClicks(cmd_line, 'q')
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.close_action.trigger.assert_called_once_with()


def test_colon_qexclamation_command(vim_bot):
    """Test :q!."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, ':')
    qtbot.keyClicks(cmd_line, 'q')
    qtbot.keyClicks(cmd_line, '!')
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.close_action.trigger.assert_called_once_with()


def test_colon_wq_command(vim_bot):
    """Test :wq."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, ':')
    qtbot.keyClicks(cmd_line, 'w')
    qtbot.keyClicks(cmd_line, 'q')
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.close_action.trigger.assert_called_once_with()
    main.editor.save_action.trigger.assert_called_once_with()


def test_colon_n_command(vim_bot):
    """Test :n."""
    main, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, ':')
    qtbot.keyClicks(cmd_line, 'n')
    qtbot.keyPress(cmd_line, Qt.Key_Return)
    main.editor.new_action.trigger.assert_called_once_with()


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('ABcDE', ['2l', 'g', 'u', 'u'], 'abcde', 0),
        (' ABCDE\nA', ['l', 'g', 'u', 'u'], ' abcde\nA', 0),
        ('AB\nA\nA\nB\nC\nD\nE\n', ['l', '2g', 'u', '3u'], 'ab\na\na\nb\nc\nd\nE\n', 1),
        ('AB\nA\nA\nB\nC\nD\nE\n', ['l', '2g', 'u', '3u', 'j', '.'], 'ab\na\na\nb\nc\nd\ne\n', 3),
        ('ABCDE', ['$', 'g', 'u', '0'], 'abcdE', 0),
        ('ABCDE', ['g', 'u', 'l'], 'aBCDE', 0),
        ('ABCDE', ['g', 'u', '2l'], 'abCDE', 0),
        ('ABCDE', ['2g', 'u', '2l'], 'abcdE', 0),
        ('ABCDE', ['2g', 'u', '2l', 'l', '.'], 'abcde', 1),
        ('AB\nC\nD\nE\nF\nG\n', ['l', 'g', 'u', 'j'], 'ab\nc\nD\nE\nF\nG\n', 1),
        ('AB\nC\nD\nE\nF\nG\n', ['l', 'g', 'u', '2j'], 'ab\nc\nd\nE\nF\nG\n', 1),
        ('AB\nC\nD\nE\nF\nG\n', ['l', '2g', 'u', '2j'], 'ab\nc\nd\ne\nf\nG\n', 1),
        ('AB\nC\nD\nE\nF\nG\n', ['l', '2g', 'u', '2j', 'j', '.'], 'ab\nc\nd\ne\nf\ng\n', 3),
        ('AB\nC\nD\nE\nF\nG\n', ['4j', 'g', 'u', 'k'], 'AB\nC\nD\ne\nf\nG\n', 7),
        ('AB\nC\nD\nE\nF\nG\n', ['4j', 'g', 'u', '2k'], 'AB\nC\nd\ne\nf\nG\n', 5),
        ('AB\nC\nD\nE\nF\nG\n', ['4j', '2g', 'u', '2k'], 'ab\nc\nd\ne\nf\nG\n', 0),
        ('ABCDE', ['$', 'g', 'u', 'h'], 'ABCdE', 3),
        ('ABCDE', ['$', 'g', 'u', '2h'], 'ABcdE', 2),
        ('ABCDE', ['$', '2g', 'u', '2h'], 'abcdE', 0),
        ('ABCDE', ['g', 'u', '$'], 'abcde', 0),
        (' ABCDE', ['$', 'g', 'u', '^'], ' abcdE', 1),
        ('ABCDE', ['g', 'u', 'w'], 'abcde', 0),
        ('A B C D E', ['g', 'u', 'w'], 'a B C D E', 0),
        ('A B C D E', ['g', 'u', '2w'], 'a b C D E', 0),
        ('A B C D E', ['2g', 'u', '2w'], 'a b c d E', 0),
        ('AbC.DE', ['g', 'u', 'W'], 'abc.de', 0),
        ('AbC.DE', ['g', 'u', 'e'], 'abc.DE', 0),
        ('AbC.DE', ['g', 'u', '2e'], 'abc.DE', 0),
        ('AbC.DE', ['g', 'u', '3e'], 'abc.de', 0),
        ('A B C D E ', ['$', 'g', 'u', 'b'], 'A B C D e ', 8),
        ('A B C D E ', ['$', 'g', 'u', '2b'], 'A B C d e ', 6),
        ('A B C D E ', ['$', '2g', 'u', '2b'], 'A b c d e ', 2),
        ('AB\nC\nD\nE\nF\nG', ['l', 'g', 'u', 'G'], 'ab\nc\nd\ne\nf\ng', 1),
        ('AB\nC\nD\nE\nF\nG', ['l', 'g', 'u', '2G'], 'ab\nc\nD\nE\nF\nG', 1),
        ('AB\nC\nD\nE\nF\nG', ['l', '2g', 'u', '2G'], 'ab\nc\nd\ne\nF\nG', 1),
        ('AB\nC\nD\nE\nF\nG', ['l', 'g', 'u', 'g', 'g'], 'ab\nC\nD\nE\nF\nG', 0),
        ('AB\nC\nD\nE\nF\nG', ['l', 'g', 'u', '2g', 'g'], 'ab\nc\nD\nE\nF\nG', 1),
        ('AB\nC\nD\nE\nF\nG', ['l', '2g', 'u', '2g', 'g'], 'ab\nc\nd\ne\nF\nG', 1),
        ('AB(CD)', ['l', 'g', 'u', '%'], 'Ab(cd)', 1),
        ('ABCD ', ['g', 'u', 'f', 'D'], 'abcd ', 0),
        ('ABCD', ['g', 'u', 'f', 'F'], 'ABCD', 0),
        ('ABCD', ['g', 'u', 't', 'D'], 'abcD', 0),
        ('ABCD', ['$', 'g', 'u', 'F', 'A'], 'abcD', 0),
        ('ABCD', ['$', 'g', 'u', 'T', 'A'], 'AbcD', 1),
        ('AAAA', ['g', 'u', '2f', 'A'], 'aaaA', 0),
        ('AAAAAAA', ['2g', 'u', '2f', 'A'], 'aaaaaAA', 0),
        ('AAAAAAA', ['2g', 'u', '2f', 'A', '4l', 'g', 'u', ';'], 'aaaaaaA', 4),
        ('AAAAAAA', ['2g', 'u', '2f', 'A', '4l', 'g', 'u', ';'], 'aaaaaaA', 4),
        ('"AaA" "AaA"', ['2l', 'g', 'u', 'i', '"', '6l', '.'], '"aaa" "aaa"', 7),
        ("'AaA' 'AaA'", ['2l', 'g', 'u', 'a', "'", '7l', '.'], "'aaa' 'aaa'", 5),
        ("'AaA' 'AaA'", ['2l', 'g', 'u', 'i', "w", '7l', '.'], "'aaa' 'aaa'", 7),
        ("[AaA] [AaA]", ['2l', 'g', 'u', 'i', "[", '7l', '.'], "[aaa] [aaa]", 7),
        ("[AaA] [AaA]", ['2l', 'g', 'u', 'a', "[", '7l', '.'], "[aaa] [aaa]", 6),
        ("(AaA) (AaA)", ['2l', 'g', 'u', 'i', "b", '7l', '.'], "(aaa) (aaa)", 7),
        ("(AaA) (AaA)", ['2l', 'g', 'u', 'a', "b", '7l', '.'], "(aaa) (aaa)", 6),
    ]
)
def test_gu_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gu command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('abCde', ['2l', 'g', 'U', 'U'], 'ABCDE', 0),
        (' abcde\na', ['l', 'g', 'U', 'U'], ' ABCDE\na', 0),
        ('ab\na\na\nb\nc\nd\ne\n', ['l', '2g', 'U', '3U'], 'AB\nA\nA\nB\nC\nD\ne\n', 1),
        ('ab\na\na\nb\nc\nd\ne\n', ['l', '2g', 'U', '3U', 'j', '.'], 'AB\nA\nA\nB\nC\nD\nE\n', 3),
        ('abcde', ['$', 'g', 'U', '0'], 'ABCDe', 0),
        ('abcde', ['g', 'U', 'l'], 'Abcde', 0),
        ('abcde', ['g', 'U', '2l'], 'ABcde', 0),
        ('abcde', ['2g', 'U', '2l'], 'ABCDe', 0),
        ('abcde', ['2g', 'U', '2l', 'l', '.'], 'ABCDE', 1),
        ('ab\nc\nd\ne\nf\ng\n', ['l', 'g', 'U', 'j'], 'AB\nC\nd\ne\nf\ng\n', 1),
        ('ab\nc\nd\ne\nf\ng\n', ['l', 'g', 'U', '2j'], 'AB\nC\nD\ne\nf\ng\n', 1),
        ('ab\nc\nd\ne\nf\ng\n', ['l', '2g', 'U', '2j'], 'AB\nC\nD\nE\nF\ng\n', 1),
        ('ab\nc\nd\ne\nf\ng\n', ['l', '2g', 'U', '2j', 'j', '.'], 'AB\nC\nD\nE\nF\nG\n', 3),
        ('ab\nc\nd\ne\nf\ng\n', ['4j', 'g', 'U', 'k'], 'ab\nc\nd\nE\nF\ng\n', 7),
        ('ab\nc\nd\ne\nf\ng\n', ['4j', 'g', 'U', '2k'], 'ab\nc\nD\nE\nF\ng\n', 5),
        ('ab\nc\nd\ne\nf\ng\n', ['4j', '2g', 'U', '2k'], 'AB\nC\nD\nE\nF\ng\n', 0),
        ('abcde', ['$', 'g', 'U', 'h'], 'abcDe', 3),
        ('abcde', ['$', 'g', 'U', '2h'], 'abCDe', 2),
        ('abcde', ['$', '2g', 'U', '2h'], 'ABCDe', 0),
        ('abcde', ['g', 'U', '$'], 'ABCDE', 0),
        (' abcde', ['$', 'g', 'U', '^'], ' ABCDe', 1),
        ('abcde', ['g', 'U', 'w'], 'ABCDE', 0),
        ('a b c d e', ['g', 'U', 'w'], 'A b c d e', 0),
        ('a b c d e', ['g', 'U', '2w'], 'A B c d e', 0),
        ('a b c d e', ['2g', 'U', '2w'], 'A B C D e', 0),
        ('aBc.de', ['g', 'U', 'W'], 'ABC.DE', 0),
        ('a b c d e ', ['$', 'g', 'U', 'b'], 'a b c d E ', 8),
        ('a b c d e ', ['$', 'g', 'U', '2b'], 'a b c D E ', 6),
        ('a b c d e ', ['$', '2g', 'U', '2b'], 'a B C D E ', 2),
        ('ab\nc\nd\ne\nf\ng', ['l', 'g', 'U', 'G'], 'AB\nC\nD\nE\nF\nG', 1),
        ('ab\nc\nd\ne\nf\ng', ['l', 'g', 'U', '2G'], 'AB\nC\nd\ne\nf\ng', 1),
        ('ab\nc\nd\ne\nf\ng', ['l', '2g', 'U', '2G'], 'AB\nC\nD\nE\nf\ng', 1),
        ('ab\nc\nd\ne\nf\ng', ['l', 'g', 'U', 'g', 'g'], 'AB\nc\nd\ne\nf\ng', 0),
        ('ab\nc\nd\ne\nf\ng', ['l', 'g', 'U', '2g', 'g'], 'AB\nC\nd\ne\nf\ng', 1),
        ('ab\nc\nd\ne\nf\ng', ['l', '2g', 'U', '2g', 'g'], 'AB\nC\nD\nE\nf\ng', 1),
        ('ab(cd)', ['l', 'g', 'U', '%'], 'aB(CD)', 1),
        ('abcd ', ['g', 'U', 'f', 'd'], 'ABCD ', 0),
        ('abcd ', ['g', 'U', 'f', 'D'], 'abcd ', 0),
        ('abcd', ['g', 'U', 't', 'd'], 'ABCd', 0),
        ('abcd', ['$', 'g', 'U', 'F', 'a'], 'ABCd', 0),
        ('abcd', ['$', 'g', 'U', 'T', 'a'], 'aBCd', 1),
        ('aaaa', ['g', 'U', '2f', 'a'], 'AAAa', 0),
        ('aaaaaaa', ['2g', 'U', '2f', 'a'], 'AAAAAaa', 0),
        ('aaaaaaa', ['2g', 'U', '2f', 'a', '4l', 'g', 'U', ';'], 'AAAAAAa', 4),
        ('aaaaaaa', ['2g', 'U', '2f', 'a', '4l', 'g', 'U', ';'], 'AAAAAAa', 4),
        ('"aAa" "aAa"', ['2l', 'g', 'U', 'i', '"', '6l', '.'], '"AAA" "AAA"', 7),
        ("'aAa' 'aAa'", ['2l', 'g', 'U', 'a', "'", '7l', '.'], "'AAA' 'AAA'", 5),
        ('"aAa" "aAa"', ['2l', 'g', 'U', 'i', 'w', '6l', '.'], '"AAA" "AAA"', 7),
        ('{aAa} {aAa}', ['2l', 'g', 'U', 'i', '{', '6l', '.'], '{AAA} {AAA}', 7),
        ('{aAa} {aAa}', ['2l', 'g', 'U', 'a', '{', '6l', '.'], '{AAA} {AAA}', 6),
        ('{aAa} {aAa}', ['2l', 'g', 'U', 'i', 'B', '6l', '.'], '{AAA} {AAA}', 7),
        ('{aAa} {aAa}', ['2l', 'g', 'U', 'a', 'B', '6l', '.'], '{AAA} {AAA}', 6),
    ]
)
def test_gU_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gU command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('abCde', ['2l', 'g', '~', '~'], 'ABcDE', 0),
        (' abCde\na', ['l', 'g', '~', '~'], ' ABcDE\na', 0),
        ('ab\na\na\nb\nc\nd\ne\n', ['l', '2g', '~', '3~'], 'AB\nA\nA\nB\nC\nD\ne\n', 1),
        ('ab\na\na\nb\nc\nd\ne\n', ['l', '2g', '~', '3~', 'j', '.'], 'AB\na\na\nb\nc\nd\nE\n', 3),
        ('abcde', ['$', 'g', '~', '0'], 'ABCDe', 0),
        ('abcde', ['g', '~', 'l'], 'Abcde', 0),
        ('abcde', ['g', '~', '2l'], 'ABcde', 0),
        ('abcde', ['2g', '~', '2l'], 'ABCDe', 0),
        ('abcde', ['2g', '~', '2l', 'l', '.'], 'AbcdE', 1),
        ('ab\nc\nd\ne\nf\ng\n', ['l', 'g', '~', 'j'], 'AB\nC\nd\ne\nf\ng\n', 1),
        ('ab\nc\nd\ne\nf\ng\n', ['l', 'g', '~', '2j'], 'AB\nC\nD\ne\nf\ng\n', 1),
        ('ab\nc\nd\ne\nf\ng\n', ['l', '2g', '~', '2j'], 'AB\nC\nD\nE\nF\ng\n', 1),
        ('ab\nc\nd\ne\nf\ng\n', ['l', '2g', '~', '2j', 'j', '.'], 'AB\nc\nd\ne\nf\nG\n', 3),
        ('ab\nc\nd\ne\nf\ng\n', ['4j', 'g', '~', 'k'], 'ab\nc\nd\nE\nF\ng\n', 7),
        ('ab\nc\nd\ne\nf\ng\n', ['4j', 'g', '~', '2k'], 'ab\nc\nD\nE\nF\ng\n', 5),
        ('ab\nc\nd\ne\nf\ng\n', ['4j', '2g', '~', '2k'], 'AB\nC\nD\nE\nF\ng\n', 0),
        ('abcde', ['$', 'g', '~', 'h'], 'abcDe', 3),
        ('abcde', ['$', 'g', '~', '2h'], 'abCDe', 2),
        ('abcde', ['$', '2g', '~', '2h'], 'ABCDe', 0),
        ('abcde', ['g', '~', '$'], 'ABCDE', 0),
        (' abcde', ['$', 'g', '~', '^'], ' ABCDe', 1),
        ('abcde', ['g', '~', 'w'], 'ABCDE', 0),
        ('aBc.de', ['g', '~', 'W'], 'AbC.DE', 0),
        ('a b c d e', ['g', '~', 'w'], 'A b c d e', 0),
        ('a b c d e', ['g', '~', '2w'], 'A B c d e', 0),
        ('a b c d e', ['2g', '~', '2w'], 'A B C D e', 0),
        ('a b c d e ', ['$', 'g', '~', 'b'], 'a b c d E ', 8),
        ('a b c d e ', ['$', 'g', '~', '2b'], 'a b c D E ', 6),
        ('a b c d e ', ['$', '2g', '~', '2b'], 'a B C D E ', 2),
        ('ab\nc\nd\ne\nf\ng', ['l', 'g', '~', 'G'], 'AB\nC\nD\nE\nF\nG', 1),
        ('ab\nc\nd\ne\nf\ng', ['l', 'g', '~', '2G'], 'AB\nC\nd\ne\nf\ng', 1),
        ('ab\nc\nd\ne\nf\ng', ['l', '2g', '~', '2G'], 'AB\nC\nD\nE\nf\ng', 1),
        ('ab\nc\nd\ne\nf\ng', ['l', 'g', '~', 'g', 'g'], 'AB\nc\nd\ne\nf\ng', 0),
        ('ab\nc\nd\ne\nf\ng', ['l', 'g', '~', '2g', 'g'], 'AB\nC\nd\ne\nf\ng', 1),
        ('ab\nc\nd\ne\nf\ng', ['l', '2g', '~', '2g', 'g'], 'AB\nC\nD\nE\nf\ng', 1),
        ('ab(cd)', ['l', 'g', '~', '%'], 'aB(CD)', 1),
        ('abcd ', ['g', '~', 'f', 'd'], 'ABCD ', 0),
        ('abcd ', ['g', '~', 'f', 'D'], 'abcd ', 0),
        ('abcd', ['g', '~', 't', 'd'], 'ABCd', 0),
        ('abcd', ['$', 'g', '~', 'F', 'a'], 'ABCd', 0),
        ('abcd', ['$', 'g', '~', 'T', 'a'], 'aBCd', 1),
        ('aaaa', ['g', '~', '2f', 'a'], 'AAAa', 0),
        ('aaaaaaa', ['2g', '~', '2f', 'a'], 'AAAAAaa', 0),
        ('aaaaaaa', ['2g', '~', '2f', 'a', '4l', 'g', '~', ';'], 'AAAAaAa', 4),
        ('"aAa" "aAa"', ['2l', 'g', '~', 'i', '"', '6l', '.'], '"AaA" "AaA"', 7),
        ('"aAa" "aAa"', ['2l', 'g', '~', 'a', '"', '7l', '.'], '"AaA" "AaA"', 5),
        ('"aAa" "aAa"', ['2l', 'g', '~', 'i', 'w', '6l', '.'], '"AaA" "AaA"', 7),
        ('(aAa) (aAa)', ['2l', 'g', '~', 'i', '(', '6l', '.'], '(AaA) (AaA)', 7),
        ('(aAa) (aAa)', ['2l', 'g', '~', 'a', '(', '7l', '.'], '(AaA) (AaA)', 6),
    ]
)
def test_gtilde_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test g~ command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('ABCDE', ['v', 'u'], 'aBCDE', 0),
        ('ABCDE\nA', ['l', 'v', '$', 'u'], 'Abcde\nA', 1),
        ('ABCDE\nA', ['l', 'v', '3l', 'u', '0', '.'], 'abcde\nA', 0),
        ('', ['v', 'u'], '', 0)
    ]
)
def test_u_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test u command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('ABCDE', ['v', 'g', 'u'], 'aBCDE', 0),
        ('ABCDE\nA', ['l', 'v', '$', 'g', 'u'], 'Abcde\nA', 1),
        ('ABCDE\nA', ['l', 'v', '3l', 'g', 'u', '0', '.'], 'abcde\nA', 0),
        ('', ['v', 'g', 'u'], '', 0)
    ]
)
def test_gu_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gu command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('ABCDE', ['V', 'u'], 'abcde', 0),
        ('ABCDE\nA', ['l', 'V', '$', 'u'], 'abcde\nA', 0),
        ('ABCDE\nA', ['l', 'V', '$', 'u', 'j', '.'], 'abcde\na', 6),
        ('', ['V', 'u'], '', 0)
    ]
)
def test_u_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test u command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('ABCDE', ['V', 'g', 'u'], 'abcde', 0),
        ('ABCDE\nA', ['l', 'V', '$', 'g', 'u'], 'abcde\nA', 0),
        ('ABCDE\nA', ['l', 'V', '$', 'g', 'u', 'j', '.'], 'abcde\na', 6),
        ('', ['V', 'g', 'u'], '', 0)
    ]
)
def test_gu_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gu command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('abcde', ['v', 'U'], 'Abcde', 0),
        ('abcde\na', ['l', 'v', '$', 'U'], 'aBCDE\na', 1),
        ('abcde\na', ['l', 'v', '3l', 'U', '0', '.'], 'ABCDE\na', 0),
        ('', ['v', 'U'], '', 0)
    ]
)
def test_U_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test U command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('abcde', ['v', 'g', 'U'], 'Abcde', 0),
        ('abcde\na', ['l', 'v', '$', 'g', 'U'], 'aBCDE\na', 1),
        ('abcde\na', ['l', 'v', '3l', 'g', 'U', '0', '.'], 'ABCDE\na', 0),
        ('', ['v', 'g', 'U'], '', 0)
    ]
)
def test_gU_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gU command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('abcde', ['V', 'U'], 'ABCDE', 0),
        ('abcde\na', ['l', 'V', '$', 'U'], 'ABCDE\na', 0),
        ('abcde\na', ['l', 'V', '$', 'U', 'j', '.'], 'ABCDE\nA', 6),
        ('', ['V', 'U'], '', 0)
    ]
)
def test_U_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test U command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('abcde', ['V', 'g', 'U'], 'ABCDE', 0),
        ('abcde\na', ['l', 'V', '$', 'g', 'U'], 'ABCDE\na', 0),
        ('abcde\na', ['l', 'V', '$', 'g', 'U', 'j', '.'], 'ABCDE\nA', 6),
        ('', ['V', 'g', 'U'], '', 0)
    ]
)
def test_gU_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test gU command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('abCde', ['v', 'g', '~'], 'AbCde', 0),
        ('abCde\na', ['l', 'v', '$', 'g', '~'], 'aBcDE\na', 1),
        ('abCde\na', ['l', 'v', '3l', 'g', '~', '0', '.'], 'AbCdE\na', 0),
        ('', ['v', 'g', '~'], '', 0)
    ]
)
def test_gtilde_cmd_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test g~ command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('abCde', ['V', 'g', '~'], 'ABcDE', 0),
        ('abCde\na', ['l', 'V', '$', 'g', '~'], 'ABcDE\na', 0),
        ('abCde\na', ['l', 'V', '$', 'g', '~', 'j', '.'], 'ABcDE\nA', 6),
        ('', ['V', 'g', '~'], '', 0)
    ]
)
def test_gtilde_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test g~ command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('', ['>', '>'], '', 0),
        ('abcde', ['2l', '>', '>'], '    abcde', 4),
        ('abcde', ['2l', '>', '%'], 'abcde', 2),
        (' abcde\na', ['l', '>', '>'], '     abcde\na', 5),
        ('a\n\na', ['l', '3>', '>'], '    a\n\n    a', 4),
        ('ab\na\na\nb\nc\nd\ne\n', ['l', '2>', '3>'], '    ab\n    a\n    a\n    b\n    c\n    d\ne\n', 4),
        ('ab\na\na\nb\nc\nd\ne\n', ['l', '2>', '3>', 'j', '.'], '    ab\n        a\n        a\n        b\n        c\n        d\n    e\n', 15),
        ('ab\nc\nd\ne\nf\ng\n', ['l', '>', 'j'], '    ab\n    c\nd\ne\nf\ng\n', 4),
        ('ab\nc\nd\ne\nf\ng\n', ['l', '>', '2j'], '    ab\n    c\n    d\ne\nf\ng\n', 4),
        ('ab\nc\nd\ne\nf\ng\n', ['l', '2>', '2>', 'j', '.'], '    ab\n        c\n        d\n        e\n    f\ng\n', 15),
        ('ab\nc\nd\ne\nf\ng\n', ['4j', '>', 'k'], 'ab\nc\nd\n    e\n    f\ng\n', 11),
        ('ab\nc\nd\ne\nf\ng\n', ['4j', '>', '2k'], 'ab\nc\n    d\n    e\n    f\ng\n', 9),
        ('ab\nc\nd\ne\nf\ng\n', ['4j', '2>', '2k'],     '    ab\n    c\n    d\n    e\n    f\ng\n', 4),
        ('ab\nc\nd\ne\nf\ng', ['l', '>', 'G'], '    ab\n    c\n    d\n    e\n    f\n    g', 4),
        ('ab\nc\nd\ne\nf\ng', ['l', '>', '2G'], '    ab\n    c\nd\ne\nf\ng', 4),
        ('ab\nc\nd\ne\nf\ng', ['l', '2>', '2G'], '    ab\n    c\n    d\n    e\nf\ng', 4),
        ('ab\nc\nd\ne\nf\ng', ['l', '>', 'g', 'g'], '    ab\nc\nd\ne\nf\ng', 4),
        ('ab\nc\nd\ne\nf\ng', ['l', '>', '2g', 'g'], '    ab\n    c\nd\ne\nf\ng', 4),
        ('ab\nc\nd\ne\nf\ng', ['l', '2>', '2g', 'g'], '    ab\n    c\n    d\n    e\nf\ng', 4),
    ]
)
def test_greater_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test > command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('', ['v', '>'], '', 0),
        ('abcde', ['2l', 'v', '>'], '    abcde', 4),
        (' abcde\na', ['v', '>'], '     abcde\na', 5),
        ('a\n\na', ['v', '2j', '>'], '    a\n\n    a', 4),
    ]
)
def test_greater_cmd_in_visual(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test > command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('', ['V', '>'], '', 0),
        ('abcde', ['2l', 'V', '>'], '    abcde', 4),
        (' abcde\na', ['V', '>'], '     abcde\na', 5),
        ('a\n\na', ['V', '2j', '>'], '    a\n\n    a', 4),
    ]
)
def test_greater_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test > command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('', ['<', '<'], '', 0),
        ('    abcde', ['2l', '<', '<'], 'abcde', 0),
        ('    abcde', ['2l', '<', '%'], '    abcde', 2),
        ('   abcde', ['2l', '<', '<'], 'abcde', 0),
        (' abcde\na', ['l', '<', '<'], 'abcde\na', 0),
        ('    a\n\n    a', ['l', '3<', '<'], 'a\n\na', 0),
        ('    ab\n    a\n    a\n    b\n    c\n    d\ne\n', ['l', '2<', '3<'], 'ab\na\na\nb\nc\nd\ne\n', 0),
        ('     ab\n     a\n     a\n     b\n     c\n     d\n     e\n', ['l', '2<', '3<', 'j', '.'], ' ab\na\na\nb\nc\nd\n e\n', 4),
        ('    ab\n    c\nd\ne\nf\ng\n', ['l', '<', 'j'], 'ab\nc\nd\ne\nf\ng\n', 0),
        ('    ab\n    c\n    d\ne\nf\ng\n', ['l', '<', '2j'], 'ab\nc\nd\ne\nf\ng\n', 0),
        ('     ab\n     c\n     d\n     e\n     f\n g\n', ['l', '2<', '2<', 'j', '.'], ' ab\nc\nd\ne\n f\n g\n', 4),
        (' ab\n c\n d\n e\n f\n g\n', ['4j', '<', 'k'], ' ab\n c\n d\ne\nf\n g\n', 10),
        (' ab\n c\n d\n e\n f\n g\n', ['4j', '<', '2k'], ' ab\n c\nd\ne\nf\n g\n', 7),
        (' ab\n c\n d\n e\n f\n g\n', ['4j', '2<', '2k'], 'ab\nc\nd\ne\nf\n g\n', 0),
        (' ab\n c\n d\n e\n f\n g', ['l', '<', 'G'], 'ab\nc\nd\ne\nf\ng', 0),
        (' ab\n c\n d\n e\n f\n g', ['l', '<', '2G'], 'ab\nc\n d\n e\n f\n g', 0),
        (' ab\n c\n d\n e\n f\n g', ['l', '2<', '2G'], 'ab\nc\nd\ne\n f\n g', 0),
        (' ab\n c\n d\n e\n f\n g', ['l', '<', 'g', 'g'], 'ab\n c\n d\n e\n f\n g', 0),
        (' ab\n c\n d\n e\n f\n g', ['l', '<', '2g', 'g'], 'ab\nc\n d\n e\n f\n g', 0),
        (' ab\n c\n d\n e\n f\n g', ['l', '2<', '2g', 'g'], 'ab\nc\nd\ne\n f\n g', 0),
    ]
)
def test_less_cmd(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test < command."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('', ['v', '<'], '', 0),
        ('    abcde', ['2l', 'v', '<'], 'abcde', 0),
        ('     abcde\na', ['v', '<'], ' abcde\na', 1),
        ('    a\n\n    a', ['v', '2j', '<'], 'a\n\na', 0),
    ]
)
def test_less_cmd_in_visual(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test < command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ('', ['V', '<'], '', 0),
        ('    abcde', ['2l', 'V', '<'], 'abcde', 0),
        ('     abcde\na', ['V', '<'], ' abcde\na', 1),
        ('    a\n\n    a', ['V', '2j', '<'], 'a\n\na', 0),
    ]
)
def test_less_cmd_in_vline(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test < command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ('"dkwh"  "sdalkj"', ['8l', 'v', 'i', '"'], 14, [9, 15]),
        ('"dkwh"  "sdalkj"', ['7l', 'v', 'i', '"'], 7, [6, 8]),
        ('"dkwh"sd"', ['$', 'v', 'i', '"'], 8, [8, 9]),
        ('', ['v', 'i', '"'], 0, [0, 0]),
        ('"0"', ['v', 'i', '"'], 1, [1, 2]),
        ('"0"', ['l', 'v', 'i', '"'], 1, [1, 2]),
        ('"0"', ['2l', 'v', 'i', '"'], 1, [1, 2]),
        ('"0" ', ['3l', 'v', 'i', '"'], 3, [3, 4]),
        (' "0" ', ['v', 'i', '"'], 2, [2, 3]),
        ("'0'", ['v', 'i', "'"], 1, [1, 2]),
        ("'0'", ['l', 'v', 'i', "'"], 1, [1, 2]),
        ("'0'", ['2l', 'v', 'i', "'"], 1, [1, 2]),
        ("'0' ", ['3l', 'v', 'i', "'"], 3, [3, 4]),
        (" '0' ", ['v', 'i', "'"], 2, [2, 3])
    ]
)
def test_iquote_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test i" i' command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('"dkwh"  "sdalkj"', ['8l', 'v', 'a', '"'], 15, [6, 16]),
        ('"dkwh"  "sdalkj"', ['7l', 'v', 'a', '"'], 8, [5, 9]),
        ('"dkwh"sd"', ['$', 'v', 'a', '"'], 8, [8, 9]),
        ('', ['v', 'a', '"'], 0, [0, 0]),
        ('"0"', ['v', 'a', '"'], 2, [0, 3]),
        ('"0"a', ['l', 'v', 'a', '"'], 2, [0, 3]),
        ('"0"   ', ['2l', 'v', 'a', '"'], 5, [0, 6]),
        ('"0"   a', ['2l', 'v', 'a', '"'], 5, [0, 6]),
        ('"0"   \na', ['2l', 'v', 'a', '"'], 5, [0, 6]),
        ('"0" ', ['3l', 'v', 'a', '"'], 3, [3, 4]),
        (' "0" ', ['v', 'a', '"'], 4, [1, 5]),
        ("'0'", ['v', 'a', "'"], 2, [0, 3]),
        ("'0'", ['l', 'v', 'a', "'"], 2, [0, 3]),
        ("'0'", ['2l', 'v', 'a', "'"], 2, [0, 3]),
        ("'0' ", ['3l', 'v', 'a', "'"], 3, [3, 4]),
    ]
)
def test_aquote_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test a" a' command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('kk 2 3', ['v', 'i', 'w'], 1, [0, 2]),
        ('kk 2 3', ['l', 'v', 'i', 'w'], 1, [0, 2]),
        ('kk 2 3', ['v', '2i', 'w'], 2, [0, 3]),
        ('kk 2 3', ['l', 'v', '5i', 'w'], 5, [0, 6]),
        ('kk   2 3', ['3l', 'v', 'i', 'w'], 4, [2, 5]),
        ('kk   2 3', ['2l', 'v', 'i', 'w'], 4, [2, 5]),
        ('kk   2 3', ['4l', 'v', 'i', 'w'], 4, [2, 5]),
        ('kk   2 3', ['2l', 'v', '2i', 'w'], 5, [2, 6]),
        ('kk   2 3\na', ['2l', 'v', '4i', 'w'], 7, [2, 8]),
        ('kk   2 3\na', ['2l', 'v', '5i', 'w'], 9, [2, 10]),
        ('kk   2 3\n   a', ['2l', 'v', '5i', 'w'], 11, [2, 12]),
        ('kk   2 3\na', ['v', '6i', 'w'], 9, [0, 10]),
        ('abc.def', ['v', 'i', 'w'], 2, [0, 3]),
        ('abc.def', ['v', '2i', 'w'], 3, [0, 4]),
        ('abc.def', ['v', '3i', 'w'], 6, [0, 7]),
        ('abc.def', ['3l', 'v', 'i', 'w'], 3, [3, 4]),
    ]
)
def test_iw_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test iw command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['v', 'i', 'W'], 0, [0, 0]),
        ('\n\n', ['j', 'v', 'i', 'W'], 1, [1, 2]),
        ('fig.add_subplot(111)  # ', ['4l', 'v', 'i', 'W'], 19, [0, 20]),
        ('fig.add_subplot(111)  # ', ['4l', 'v', '2i', 'W'], 21, [0, 22]),
        ('fig.add_subplot(111)  # ', ['4l', 'v', '3i', 'W'], 22, [0, 23]),
        ('fig.add_subplot(111)  # ', ['20l', 'v', 'i', 'W'], 21, [20, 22]),
        ('fig.add_subplot(111)  # ', ['20l', 'v', '2i', 'W'], 22, [20, 23]),
        (' # \n 1', ['l', 'v', '3i', 'W'], 4, [1, 5]),
    ]
)
def test_iW_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test iW command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('kk 2 3', ['v', 'a', 'w'], 2, [0, 3]),
        ('kk 2 3', ['l', 'v', 'a', 'w'], 2, [0, 3]),
        ('kk 2 3', ['v', '2a', 'w'], 4, [0, 5]),
        ('kk 2 3', ['v', '3a', 'w'], 5, [0, 6]),
        ('kk 2 3 ', ['v', '3a', 'w'], 6, [0, 7]),
        ('kk 2 3\n', ['v', '4a', 'w'], 6, [0, 7]),
        ('kk 2 3 \n', ['v', '4a', 'w'], 7, [0, 8]),
        ('kk 2 3 \na', ['v', '4a', 'w'], 8, [0, 9]),
        ('kk 2 3\na ', ['v', '4a', 'w'], 8, [0, 9]),
        ('kk   2 3', ['3l', 'v', 'a', 'w'], 5, [2, 6]),
        ('kk   2 3', ['2l', 'v', 'a', 'w'], 5, [2, 6]),
        ('kk   2 3', ['4l', 'v', 'a', 'w'], 5, [2, 6]),
        ('kk   2 3 ', ['2l', 'v', '2a', 'w'], 7, [2, 8]),
        ('kk   2 3 4 ', ['2l', 'v', '3a', 'w'], 9, [2, 10]),
        ('kk   2 3\na', ['2l', 'v', '3a', 'w'], 9, [2, 10]),
        ('kk   2 3\n a', ['2l', 'v', '3a', 'w'], 10, [2, 11]),
        ('kk   2 3 \n a', ['2l', 'v', '3a', 'w'], 11, [2, 12]),
        ('kk   2 3 \n a', ['5l', 'v', 'a', 'w'], 6, [5, 7]),
        ('kk   2 3 \n a', ['5l', 'v', '2a', 'w'], 8, [5, 9]),
        ('kk   2 3 \n a', ['5l', 'v', '3a', 'w'], 10, [5, 11]),
    ]
)
def test_aw_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test aw command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['v', 'a', ')'], 0, [0, 0]),
        (' () ', ['v', 'a', ')'], 0, [0, 1]),
        (' () ', ['l', 'v', 'a', ')'], 2, [1, 3]),
        (' (01234) ', ['3l', 'v', 'a', ')'], 7, [1, 8]),
        (' (01234) ', ['3l', 'v', 'a', '('], 7, [1, 8]),
        (' (01234) ', ['3l', 'v', 'a', 'b'], 7, [1, 8]),
        (' [01234] ', ['3l', 'v', 'a', '['], 7, [1, 8]),
        (' [01234] ', ['3l', 'v', 'a', ']'], 7, [1, 8]),
        (' {01234} ', ['3l', 'v', 'a', '{'], 7, [1, 8]),
        (' {01234} ', ['3l', 'v', 'a', 'B'], 7, [1, 8]),
        (' {01234} ', ['3l', 'v', 'a', '}'], 7, [1, 8]),
        (' {01234} ', ['l', 'v', 'a', '}'], 7, [1, 8]),
        (' {01234} ', ['7l', 'v', 'a', '}'], 7, [1, 8]),
        (' {\n(\nasdf)\nasdf} ', ['3l', 'v', 'a', '}'], 15, [1, 16]),
        (' (((kk)))', ['l', 'v', 'a', '('], 8, [1, 9]),
        (' (((kk)))', ['$', 'v', 'a', '('], 8, [1, 9]),
    ]
)
def test_a_bracket_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test a_bracket command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('', ['v', 'i', ')'], 0, [0, 0]),
        (' () ', ['v', 'i', ')'], 0, [0, 1]),
        (' () ', ['l', 'v', 'i', ')'], 1, [1, 2]),
        (' (01234) ', ['3l', 'v', 'i', ')'], 6, [2, 7]),
        (' (01234) ', ['3l', 'v', 'i', '('], 6, [2, 7]),
        (' (01234) ', ['3l', 'v', 'i', 'b'], 6, [2, 7]),
        (' [01234] ', ['3l', 'v', 'i', '['], 6, [2, 7]),
        (' [01234] ', ['3l', 'v', 'i', ']'], 6, [2, 7]),
        (' {01234} ', ['3l', 'v', 'i', '{'], 6, [2, 7]),
        (' {01234} ', ['3l', 'v', 'i', '}'], 6, [2, 7]),
        (' {01234} ', ['3l', 'v', 'i', 'B'], 6, [2, 7]),
        (' {01234} ', ['l', 'v', 'i', '}'], 6, [2, 7]),
        (' {01234} ', ['7l', 'v', 'i', '}'], 6, [2, 7]),
        (' {\n(\nasdf)\nasdf} ', ['3l', 'v', 'i', '}'], 14, [2, 15]),
    ]
)
def test_i_bracket_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test i_bracket command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "cmd_list, register_name",
    [
        (['"', '+', 'l'], '+',),
        (['v', '"', '0', 'l'], '0',),
        (['V', '"', 'a', 'l'], 'a',),
    ]
)
def test_get_register_name(vim_bot, cmd_list, register_name):
    """Test get_register name."""
    _, _, _, vim, qtbot = vim_bot

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert vim.vim_cmd.vim_status.get_register_name() == register_name


def test_clipboard(vim_bot):
    """Test clipboard."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text('')

    clipboard = QApplication.clipboard()
    clipboard.setText("dhrwodn")

    cmd_line = vim.get_focus_widget()

    qtbot.keyClicks(cmd_line, '"')
    qtbot.keyClicks(cmd_line, '+')
    qtbot.keyClicks(cmd_line, 'p')
    assert editor.toPlainText() == "dhrwodn"

    editor.set_text('1dhrwodn')
    qtbot.keyClicks(cmd_line, '"')
    qtbot.keyClicks(cmd_line, '+')
    qtbot.keyClicks(cmd_line, 'y')
    qtbot.keyClicks(cmd_line, 'y')

    assert clipboard.text() == "1dhrwodn\n"


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, register_name, text_yanked",
    [
        ('a', ['y', 'l'], 0, '"', 'a'),
        ('a', ['y', ','], 0, '"', ''),
        ('a', ['y', 'i', 'b'], 0, '"', ''),
        ('abcd', ['$', 'y', '2h'], 1, '"', 'bc'),
        ('a\nb', ['y', 'j'], 0, '"', 'a\nb\n'),
        ('  a\n b', ['j', 'l', 'y', 'k'], 1, '"', '  a\n b\n'),
        ('abcd', ['y', '$'], 0, '"', 'abcd'),
        ('abcd', ['$', 'y', '^'], 0, '"', 'abc'),
        ('a b', ['y', 'w'], 0, '"', 'a '),
        ('a.dk b', ['y', 'W'], 0, '"', 'a.dk '),
        ('abcd', ['$', 'y', 'b'], 0, '"', 'abc'),
        ('  abcd \n b', ['3l', 'y', 'i', 'w'], 2, '"', 'abcd'),
        ('abcd\ne\nf\n', ['y', 'y'], 0, '"', 'abcd\n'),
        ('abcd', ['y', 'y'], 0, '"', 'abcd\n'),
        ('abcd\ne\nf\n', ['2y', 'y'], 0, '"', 'abcd\ne\n'),
        ('AB\nC\nD\nE', ['l', 'y', 'G'], 1, '"', 'AB\nC\nD\nE\n'),
        ('AB\nC\nD\nE', ['l', 'y', '2G'], 1, '"', 'AB\nC\n'),
        ('AB\nC\nD\nE', ['l', 'y', 'g', 'g'], 0, '"', 'AB\n'),
        ('AB\nC\nD\nE', ['l', 'y', '2g', 'g'], 1, '"', 'AB\nC\n'),
        ('AB(CD)', ['l', 'y', '%'], 1, '"', 'B(CD)'),
        ('AB(CD)', ['$', 'y', '%'], 2, '"', '(CD)'),
        ('ABCD', ['y', 'f', 'D'], 0, '"', 'ABCD'),
        ('ABCD', ['y', 'f', 'F'], 0, '"', ''),
        ('ABCD', ['y', 't', 'D'], 0, '"', 'ABC'),
        ('ABCD', ['$', 'y', 'F', 'A'], 0, '"', 'ABC'),
        ('ABCD', ['$', 'y', 'T', 'A'], 1, '"', 'BC'),
        ('AAAA', ['y', '2f', 'A'], 0, '"', 'AAA'),
        (' "AAA"', ['y', 'i', '"'], 2, '"', 'AAA'),
        (' "AAA"', ['y', 'a', '"'], 0, '"', ' "AAA"'),
        (' "AAA" ', ['y', 'a', '"'], 1, '"', '"AAA" '),
        ('(AAA)', ['y', 'i', '('], 1, '"', 'AAA'),
        ('(AAA)', ['y', 'a', '('], 0, '"', '(AAA)'),
        ('(AAA)', ['%', 'y', 'a', ')'], 0, '"', '(AAA)'),
    ]
)
def test_y_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, register_name,
                         text_yanked):
    """Test y command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[register_name]
    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked
    if register_name == '"':
        reg0 = vim.vim_cmd.vim_status.register_dict['0']
        assert reg0.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, register_name, text_yanked",
    [
        ('a', ['v', 'y'], 0, '"', 'a'),
        ('abcd', ['l', 'v', '2l', 'y'], 1, '"', 'bcd'),
        ('abcd', ['l', 'v', '2l', '"', '0', 'y'], 1, '0', 'bcd'),
        ('abcd\ne', ['l', 'v', '2l', 'j', '"', 'a', 'y'], 1, 'a', 'bcd\ne'),
    ]
)
def test_y_cmd_in_v(vim_bot, text, cmd_list, cursor_pos, register_name,
                    text_yanked):
    """Test y command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[register_name]
    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked
    assert reg.type == VimState.NORMAL
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None
    if register_name == '"':
        reg0 = vim.vim_cmd.vim_status.register_dict['0']
        assert reg0.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, register_name, text_yanked",
    [
        ('a', ['V', 'y'], 0, '"', 'a\n'),
        ('abcd', ['V', '"', '0', 'y'], 0, '0', 'abcd\n'),
        ('abcd\ne', ['V', 'j', '"', 'a', 'y'], 0, 'a', 'abcd\ne\n'),
    ]
)
def test_y_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, register_name,
                        text_yanked):
    """Test y command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[register_name]
    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked
    assert reg.type == VimState.VLINE
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None
    if register_name == '"':
        reg0 = vim.vim_cmd.vim_status.register_dict['0']
        assert reg0.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected",
    [
        ('ak', ['v', 'l', 'y', 'p'], 2, 'aakk'),
        ('a\n', ['v', 'y', 'j', 'p'], 2, 'a\na'),
        ('a', ['v', '"', '0', 'y', 'p'], 0, 'a'),
        ('a', ['v', '"', '0', 'y', '"', '0', 'p'], 1, 'aa'),
        ('a\n', ['V', 'y', 'p'], 2, 'a\na\n'),
        ('a\n', ['V', 'y', 'j', 'p'], 3, 'a\n\na'),
        ('\na', ['j', 'V', 'y', 'k', 'p'], 1, '\na\na'),
        ('a\na\n', ['V', 'j', 'y', '2j', 'p'], 5, 'a\na\n\na\na'),
        (' a\n a\n', ['V', 'j', 'y', '2j', 'p'], 8, ' a\n a\n\n a\n a'),
        ('a\nb\n', ['y', 'y', 'j', 'd', 'd', 'p'], 3, 'a\n\nb'),
        ('a\nb\n', ['y', 'y', 'j', 'd', 'd', 'p', '"', '0', 'p'], 5, 'a\n\nb\na'),
    ]
)
def test_p_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected):
    """Test p command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected",
    [
        ('ak', ['v', 'l', 'y', 'P'], 1, 'akak'),
        ('a\n', ['v', 'y', 'j', 'P'], 2, 'a\na'),
        ('a', ['v', '"', '0', 'y', 'P'], 0, 'a'),
        ('a\n', ['V', 'y', 'P'], 0, 'a\na\n'),
        ('a\n', ['V', 'y', 'j', 'P'], 2, 'a\na\n'),
        ('\na', ['j', 'V', 'y', 'k', 'P'], 0, 'a\n\na'),
        ('\na', ['j', 'V', 'y', 'P'], 1, '\na\na'),
    ]
)
def test_P_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected):
    """Test P command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected
    assert vim.vim_cmd.vim_status.get_pos_start_in_selection() is None


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ('ak', ['v', 'd'], 0, 'k', '"', 'a'),
        ('ak', ['v', 'l', 'd'], 0, '', '"', 'ak'),
        ('ab\nc\nde', ['v', '2j', 'l', 'd'], 0, '', '"', 'ab\nc\nde'),
        ('ab\nc\nde', ['l', 'v', 'd'], 0, 'a\nc\nde', '"', 'b'),
    ]
)
def test_d_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test d command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('ak', ['v', 'x'], 0, 'k', '"', 'a'),
        ('ak', ['v', 'l', 'x'], 0, '', '"', 'ak'),
        ('ab\nc\nde', ['v', '2j', 'l', 'x'], 0, '', '"', 'ab\nc\nde'),
        ('ab\nc\nde', ['l', 'v', 'x'], 0, 'a\nc\nde', '"', 'b'),
    ]
)
def test_x_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test x command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('ak', ['v', 'c'], 0, 'k', '"', 'a'),
        ('ak', ['v', 'l', 'c'], 0, '', '"', 'ak'),
        ('ab\nc\nde', ['v', '2j', 'l', 'c'], 0, '', '"', 'ab\nc\nde'),
        ('ab\nc\nde', ['l', 'v', 'c'], 1, 'a\nc\nde', '"', 'b'),
    ]
)
def test_c_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test c command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('ak', ['v', 's'], 0, 'k', '"', 'a'),
        ('ak', ['v', 'l', 's'], 0, '', '"', 'ak'),
        ('ab\nc\nde', ['v', '2j', 'l', 's'], 0, '', '"', 'ab\nc\nde'),
        ('ab\nc\nde', ['l', 'v', 's'], 1, 'a\nc\nde', '"', 'b'),
    ]
)
def test_s_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test s command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('ab', ['V', 'd'], 0, '', '"', 'ab\n'),
        (' ab\n cd\n ef', ['j', 'V', 'd'], 5, ' ab\n ef', '"', ' cd\n'),
        (' ab\n cd\n', ['V', 'G', 'd'], 0, '', '"', ' ab\n cd\n\n'),
        (' ab\n cd\n ef', ['2j', 'V', 'd'], 5, ' ab\n cd', '"', ' ef\n'),
        (' ab\n cd\n ef', ['2j', 'V', 'k', 'd'], 1, ' ab', '"', ' cd\n ef\n'),
        (' ab\n cd', ['$', 'V', 'd'], 1, ' cd', '"', ' ab\n'),
    ]
)
def test_d_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test d command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('ab', ['V', 'x'], 0, '', '"', 'ab\n'),
        (' ab\n cd\n ef', ['j', 'V', 'x'], 5, ' ab\n ef', '"', ' cd\n'),
        (' ab\n cd\n', ['V', 'G', 'x'], 0, '', '"', ' ab\n cd\n\n'),
        (' ab\n cd\n ef', ['2j', 'V', 'x'], 5, ' ab\n cd', '"', ' ef\n'),
        (' ab\n cd\n ef', ['2j', 'V', 'k', 'x'], 1, ' ab', '"', ' cd\n ef\n'),
        (' ab\n cd', ['$', 'V', 'x'], 1, ' cd', '"', ' ab\n'),
    ]
)
def test_x_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test x command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('ab', ['V', 'c'], 0, '', '"', 'ab\n'),
        (' ab\n cd\n ef', ['j', 'V', 'c'], 4, ' ab\n\n ef', '"', ' cd\n'),
        (' ab\n cd\n', ['V', 'G', 'c'], 0, '', '"', ' ab\n cd\n\n'),
        (' ab\n cd\n ef', ['2j', 'V', 'c'], 8, ' ab\n cd\n', '"', ' ef\n'),
        (' ab\n cd\n ef', ['2j', 'V', 'k', 'c'], 4, ' ab\n', '"', ' cd\n ef\n'),
        (' ab\n cd', ['$', 'V', 'c'], 0, '\n cd', '"', ' ab\n'),
    ]
)
def test_c_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test c command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('ab', ['V', 's'], 0, '', '"', 'ab\n'),
        (' ab\n cd\n ef', ['j', 'V', 's'], 4, ' ab\n\n ef', '"', ' cd\n'),
        (' ab\n cd\n', ['V', 'G', 's'], 0, '', '"', ' ab\n cd\n\n'),
        (' ab\n cd\n ef', ['2j', 'V', 's'], 8, ' ab\n cd\n', '"', ' ef\n'),
        (' ab\n cd\n ef', ['2j', 'V', 'k', 's'], 4, ' ab\n', '"', ' cd\n ef\n'),
        (' ab\n cd', ['$', 'V', 's'], 0, '\n cd', '"', ' ab\n'),
    ]
)
def test_s_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test s command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('ab', ['s'], 0, 'b', '"', 'a'),
        ('ab', ['l', 's'], 1, 'a', '"', 'b'),
        ('ab', ['2s'], 0, '', '"', 'ab'),
    ]
)
def test_s_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test s command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('  ab', ['S'], 2, '  ', '"', '  ab\n'),
        ('  ab\n cc\ndd', ['j', '2S'], 6, '  ab\n ', '"', ' cc\ndd\n'),
    ]
)
def test_S_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test S command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('ab', ['x'], 0, 'b', '"', 'a'),
        ('ab', ['l', 'x'], 0, 'a', '"', 'b'),
        ('ab', ['2x'], 0, '', '"', 'ab'),
    ]
)
def test_x_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test x command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('ab', ['D'], 0, '', '"', 'ab'),
        ('ab\n', ['D'], 0, '\n', '"', 'ab'),
        ('ab\n', ['l', 'D'], 0, 'a\n', '"', 'b'),
        ('ab\ncd\n', ['l', '2D'], 0, 'a\n', '"', 'b\ncd'),
        ('abcdefg', ['3l', 'D'], 2, 'abc', '"', 'defg'),
        ('abcdefg', ['3l', 'D', 'h', '.'], 0, 'a', '"', 'bc'),
    ]
)
def test_D_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test D command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('ab', ['C'], 0, '', '"', 'ab'),
        ('ab\n', ['C'], 0, '\n', '"', 'ab'),
        ('ab\n', ['l', 'C'], 1, 'a\n', '"', 'b'),
        ('ab\ncd\n', ['l', '2C'], 1, 'a\n', '"', 'b\ncd'),
    ]
)
def test_C_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked):
    """Test C command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('a', ['d', 'l'], 0, '', '"', 'a'),
        ('a', ['d', 'i', 'b'], 0, 'a', '"', ''),
        ('abcd', ['$', 'd', '2h'], 1, 'ad',  '"', 'bc'),
        ('a\nb', ['d', 'j'], 0, '', '"', 'a\nb\n'),
        ('  a\n b', ['j', 'l', 'd', 'k'], 0, '', '"', '  a\n b\n'),
        ('  12\n  34\n  56\n  78', ['j', 'd', 'j'], 7, '  12\n  78', '"', '  34\n  56\n'),
        ('  12\n  34\n  56\n  78', ['2j', 'd', 'k'], 7, '  12\n  78', '"', '  34\n  56\n'),
        ('abcd', ['d', '$'], 0, '', '"', 'abcd'),
        ('abcd', ['$', 'd', '^'], 0, 'd', '"', 'abc'),
        ('a b', ['d', 'w'], 0, 'b',  '"', 'a '),
        ('a\nb', ['d', 'w'], 0, '\nb',  '"', 'a'),
        ('a\nb', ['d', '2w'], 0, '',  '"', 'a\nb'),
        ('a\n b', ['d', '2w'], 0, '',  '"', 'a\n b'),
        ('a\nb c\n', ['d', '2w'], 0, 'c\n',  '"', 'a\nb '),
        ('a b', ['l', 'd', 'w'], 1, 'ab',  '"', ' '),
        ('a b c ', ['d', '2w'], 0, 'c ',  '"', 'a b '),
        ('a b c ', ['d', '3w'], 0, '',  '"', 'a b c '),
        ('a.dk b', ['d', 'W'], 0, 'b', '"', 'a.dk '),
        ('  a.dk b', ['d', 'W'], 0, 'a.dk b', '"', '  '),
        ('a.dk\nb', ['d', 'W'], 0, '\nb', '"', 'a.dk'),
        ('a.dk\nb c', ['d', '2W'], 0, 'c', '"', 'a.dk\nb '),
        ('a.dk\n b(f) c', ['d', '2W'], 0, 'c', '"', 'a.dk\n b(f) '),
        ('a.dk\nb', ['d', 'e'], 0, 'dk\nb', '"', 'a.'),
        ('a.dk\nb', ['d', '2e'], 0, '\nb', '"', 'a.dk'),
        ('abcd', ['$', 'd', 'b'], 0, 'd', '"', 'abc'),
        ('  abcd \n b', ['3l', 'd', 'i', 'w'], 2, '   \n b', '"', 'abcd'),
        ('  abcd \n b', ['3l', 'd', 'a', 'w'], 1, '  \n b', '"', 'abcd '),
        ('  12\n  78', ['j', 'd', 'd'], 2, '  12', '"', '  78\n'),
        ('  12\n  78', ['d', 'd'], 2, '  78', '"', '  12\n'),
        ('abcd\ne\nf\n', ['d', 'd'], 0, 'e\nf\n', '"', 'abcd\n'),
        ('abcd', ['d', 'd'], 0, '', '"', 'abcd\n'),
        ('abcd\ne\nf\n', ['2d', 'd'], 0, 'f\n', '"', 'abcd\ne\n'),
        ('AB\nC\nD\nE', ['l', 'd', 'G'], 0, '', '"', 'AB\nC\nD\nE\n'),
        ('AB\nC\nD\nE', ['l', 'd', '2G'], 0, 'D\nE', '"', 'AB\nC\n'),
        ('AB\n C\nD\nE', ['l', 'd', 'g', 'g'], 1, ' C\nD\nE', '"', 'AB\n'),
        ('AB\nC\nD\nE', ['l', 'd', '2g', 'g'], 0, 'D\nE', '"', 'AB\nC\n'),
        ('AB(CD)', ['l', 'd', '%'], 0, 'A', '"', 'B(CD)'),
        ('AB(CD)', ['$', 'd', '%'], 1, 'AB', '"', '(CD)'),
        ('ABCD', ['d', 'f', 'D'], 0, '', '"', 'ABCD'),
        ('ABCD', ['d', 'f', 'F'], 0, 'ABCD', '"', ''),
        ('ABCD', ['d', 't', 'D'], 0, 'D', '"', 'ABC'),
        ('ABCD', ['$', 'd', 'F', 'A'], 0, 'D', '"', 'ABC'),
        ('ABCD', ['$', 'd', 'T', 'A'], 1, 'AD', '"', 'BC'),
        ('AAAA', ['d', '2f', 'A'], 0, 'A', '"', 'AAA'),
        (' "AAA"', ['d', 'i', '"'], 2, ' ""', '"', 'AAA'),
        (' "AAA"', ['d', 'a', '"'], 0, '', '"', ' "AAA"'),
        (' "AAA" ', ['d', 'a', '"'], 0, ' ', '"', '"AAA" '),
        ('(AAA)', ['d', 'i', '('], 1, '()', '"', 'AAA'),
        ('(AAA)', ['d', 'a', '('], 0, '', '"', '(AAA)'),
        ('(AAA)', ['%', 'd', 'a', ')'], 0, '', '"', '(AAA)'),
        (' dhrwodndhrwodn', ['d', '/', 'd', 'h', 'r', '\r'], 0, 'dhrwodndhrwodn', '"', ' '),
        (' dhrwodndhrwodn', ['d', '/', 'd', 'h', 'r', '\r', 'd', 'n'], 0, 'dhrwodn', '"', 'dhrwodn'),
        (' dhrwodn dhrwodn', ['2w', 'h', 'd', '/', 'd', 'h', 'r', '\r', 'd', 'N'], 1, ' dhrwodn', '"', 'dhrwodn'),
        (' fig.add_plot(1,1,1) ', ['4l', 'd', 'i', 'W'], 1, '  ', '"', 'fig.add_plot(1,1,1)'),
    ]
)
def test_d_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected,
                         reg_name, text_yanked):
    """Test d command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        ('a', ['c', 'l'], 0, '', '"', 'a'),
        ('abcd', ['$', 'c', '2h'], 1, 'ad',  '"', 'bc'),
        ('a\nb', ['c', 'j'], 0, '', '"', 'a\nb\n'),
        ('  a\n b', ['j', 'l', 'c', 'k'], 0, '', '"', '  a\n b\n'),
        ('  12\n  34\n  56\n  78', ['j', 'c', 'j'], 5, '  12\n\n  78', '"', '  34\n  56\n'),
        ('  12\n  34\n  56\n  78', ['2j', 'c', 'k'], 5, '  12\n\n  78', '"', '  34\n  56\n'),
        ('abcd', ['c', '$'], 0, '', '"', 'abcd'),
        ('abcd', ['$', 'c', '^'], 0, 'd', '"', 'abc'),
        ('a b', ['c', 'w'], 0, ' b',  '"', 'a'),
        ('a b', ['l', 'c', 'w'], 1, 'ab',  '"', ' '),
        ('a b c ', ['c', '2w'], 0, ' c ',  '"', 'a b'),
        ('a b c ', ['c', '3w'], 0, ' ',  '"', 'a b c'),
        ('a\n b', ['c', '2w'], 0, '',  '"', 'a\n b'),
        ('a\nb\nc', ['c', '3w'], 0, '',  '"', 'a\nb\nc'),
        ('a\n b\nc', ['c', '3w'], 0, '',  '"', 'a\n b\nc'),
        ('a.dk b', ['c', 'W'], 0, ' b', '"', 'a.dk'),
        (' a.dk b', ['c', 'W'], 0, 'a.dk b', '"', ' '),
        ('a.dk b dd', ['c', '2W'], 0, ' dd', '"', 'a.dk b'),
        ('a.dk b dd', ['c', '2W'], 0, ' dd', '"', 'a.dk b'),
        ('b\n a.bc d', ['c', '2W'], 0, ' d', '"', 'b\n a.bc'),
        ('\n a.bc d', ['c', '2W'], 0, ' d', '"', '\n a.bc'),
        ('a.dk\nb', ['c', 'e'], 0, 'dk\nb', '"', 'a.'),
        ('a.dk\nb', ['c', '2e'], 0, '\nb', '"', 'a.dk'),
        ('abcd', ['$', 'c', 'b'], 0, 'd', '"', 'abc'),
        ('  abcd \n b', ['3l', 'c', 'i', 'w'], 2, '   \n b', '"', 'abcd'),
        ('  abcd \n b', ['3l', 'c', 'a', 'w'], 2, '  \n b', '"', 'abcd '),
        ('  12\n  78', ['j', 'c', 'c'], 5, '  12\n', '"', '  78\n'),
        ('  12\n  78', ['c', 'c'], 0, '\n  78', '"', '  12\n'),
        ('abcd\ne\nf\n', ['c', 'c'], 0, '\ne\nf\n', '"', 'abcd\n'),
        ('abcd', ['c', 'c'], 0, '', '"', 'abcd\n'),
        ('abcd\ne\nf\n', ['2c', 'c'], 0, '\nf\n', '"', 'abcd\ne\n'),
        ('AB\nC\nD\nE', ['l', 'c', 'G'], 0, '', '"', 'AB\nC\nD\nE\n'),
        ('AB\nC\nD\nE', ['l', 'c', '2G'], 0, '\nD\nE', '"', 'AB\nC\n'),
        ('AB\n C\nD\nE', ['l', 'c', 'g', 'g'], 0, '\n C\nD\nE', '"', 'AB\n'),
        ('AB\nC\nD\nE', ['l', 'c', '2g', 'g'], 0, '\nD\nE', '"', 'AB\nC\n'),
        ('AB(CD)', ['l', 'c', '%'], 1, 'A', '"', 'B(CD)'),
        ('AB(CD)', ['$', 'c', '%'], 2, 'AB', '"', '(CD)'),
        ('ABCD', ['c', 'f', 'D'], 0, '', '"', 'ABCD'),
        ('ABCD', ['c', 'f', 'F'], 0, 'ABCD', '"', ''),
        ('ABCD', ['c', 't', 'D'], 0, 'D', '"', 'ABC'),
        ('ABCD', ['$', 'c', 'F', 'A'], 0, 'D', '"', 'ABC'),
        ('ABCD', ['$', 'c', 'T', 'A'], 1, 'AD', '"', 'BC'),
        ('AAAA', ['c', '2f', 'A'], 0, 'A', '"', 'AAA'),
        (' "AAA"', ['c', 'i', '"'], 2, ' ""', '"', 'AAA'),
        (' "AAA"', ['c', 'a', '"'], 0, '', '"', ' "AAA"'),
        (' "AAA" ', ['c', 'a', '"'], 1, ' ', '"', '"AAA" '),
        ('(AAA)', ['c', 'i', '('], 1, '()', '"', 'AAA'),
        ('(AAA)', ['c', 'a', '('], 0, '', '"', '(AAA)'),
        ('(AAA)', ['%', 'c', 'a', ')'], 0, '', '"', '(AAA)'),
    ]
)
def test_c_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos, text_expected,
                         reg_name, text_yanked):
    """Test c command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ('a', ['n'], 0,),
        ('a', ['N'], 0,),
        ('a', ['/', 'b', Qt.Key_Escape], 0,),
        ('a', ['/', 'b', '\r'], 0,),
        ('ddd', ['/', 'd', Qt.Key_Return], 1,),
        ('ddd', ['/', 'd', Qt.Key_Return, 'n'], 2,),
        ('ddd', ['/', 'd', Qt.Key_Return, 'n', 'n'], 0,),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['/', 'd', 'h', 'r', Qt.Key_Return], 1,),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['/', 'd', 'h', 'r', Qt.Key_Enter, 'n'], 7,),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['/', 'd', 'h', 'r', Qt.Key_Return, '2n'], 16,),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['/', 'd', 'h', 'r', Qt.Key_Return, '5n'], 7,),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['/', 'd', 'h', 'r', Qt.Key_Return, '11n'], 27,),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['l', '/', 'd', 'h', 'r', Qt.Key_Enter], 7,),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['/', 'd', 'h', 'r', Qt.Key_Enter, 'N'], 27,),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['/', 'd', 'h', 'r', Qt.Key_Enter, '2N'], 16,),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['/', 'd', 'h', 'r', Qt.Key_Enter, '3N'], 7,),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['/', 'd', 'h', 'r', Qt.Key_Enter, '5N'], 27,),
    ]
)
def test_search_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test / command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        ('a', ['v', '/', 'b', '\r'], 0, [0, 1]),
        ('a', ['v', '/', 'b', '\r', 'n'], 0, [0, 1]),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['v', '/', 'd', 'h', 'r', Qt.Key_Return], 1, [0, 2]),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['v', '/', 'd', 'h', 'r', Qt.Key_Return, 'n'], 7, [0, 8]),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['v', '/', 'd', 'h', 'r', Qt.Key_Enter, 'n', 'N'], 1, [0, 2]),
    ]
)
def test_search_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test / command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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
        ('a', ['V', '/', 'b', '\r'], 0, [0, 1]),
        ('a', ['V', '/', 'b', '\r', 'n'], 0, [0, 1]),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['V', '/', 'd', 'h', 'r', Qt.Key_Enter], 1, [0, 4]),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['V', '/', 'd', 'h', 'r', Qt.Key_Enter, 'n'], 7, [0, 14]),
        (' dhr\n  dhrwodn\n\ndhrwodn\n   dhrwodn', ['V', '/', 'd', 'h', 'r', Qt.Key_Return, 'n', 'N'], 1, [0, 4]),
    ]
)
def test_search_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test / command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.get_focus_widget()
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


def test_ctrl_u(vim_bot):
    """Test ^u."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\n")

    cmd_line = vim.get_focus_widget()
    for cmd in ['j']:
        qtbot.keyClicks(cmd_line, cmd)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_U, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == 0


def test_ctrl_d(vim_bot):
    """Test ^d."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\n")

    cmd_line = vim.get_focus_widget()
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == 2


def test_HML(vim_bot):
    """Test HML."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\n")

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'V')
    qtbot.keyClicks(cmd_line, 'v')
    qtbot.keyClicks(cmd_line, 'L')
    qtbot.keyClicks(cmd_line, 'M')
    qtbot.keyClicks(cmd_line, 'H')

    qtbot.keyClicks(cmd_line, 'V')
    qtbot.keyClicks(cmd_line, 'L')
    qtbot.keyClicks(cmd_line, 'M')
    qtbot.keyClicks(cmd_line, 'H')

    qtbot.keyPress(cmd_line, Qt.Key_Escape)
    qtbot.keyClicks(cmd_line, 'L')
    qtbot.keyClicks(cmd_line, 'M')
    qtbot.keyClicks(cmd_line, 'H')

    qtbot.keyClicks(cmd_line, 'y')
    qtbot.keyClicks(cmd_line, 'L')

    qtbot.keyClicks(cmd_line, 'y')
    qtbot.keyClicks(cmd_line, 'M')

    qtbot.keyClicks(cmd_line, 'y')
    qtbot.keyClicks(cmd_line, 'H')

    assert cmd_line.text() == ""


def test_toggle_comment(vim_bot):
    """Test toogle comment."""
    # TODO: Use CodeEditor of spyder for exact test.
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\n")

    cmd_line = vim.get_focus_widget()
    qtbot.keyClicks(cmd_line, 'g')
    qtbot.keyClicks(cmd_line, 'c')
    qtbot.keyClicks(cmd_line, 'c')

    qtbot.keyClicks(cmd_line, 'g')
    qtbot.keyClicks(cmd_line, 'c')
    qtbot.keyClicks(cmd_line, 'f')
    qtbot.keyClicks(cmd_line, 'k')

    qtbot.keyClicks(cmd_line, 'g')
    qtbot.keyClicks(cmd_line, 'c')
    qtbot.keyClicks(cmd_line, 'i')
    qtbot.keyClicks(cmd_line, 'w')

    qtbot.keyClicks(cmd_line, 'g')
    qtbot.keyClicks(cmd_line, 'c')
    qtbot.keyClicks(cmd_line, 'i')
    qtbot.keyClicks(cmd_line, 'b')

    qtbot.keyClicks(cmd_line, 'v')
    qtbot.keyClicks(cmd_line, 'g')
    qtbot.keyClicks(cmd_line, 'c')
