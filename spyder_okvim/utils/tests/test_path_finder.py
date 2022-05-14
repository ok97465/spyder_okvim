# -*- coding: utf-8 -*-
"""Tests for path finder."""
# Third party imports
import pytest
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent

# Local imports
from spyder_okvim.utils.path_finder import PathFinder


def test_open_path_finder(vim_bot, monkeypatch, tmpdir):
    """Test open path finder."""
    _, _, _, vim, qtbot = vim_bot

    fn = tmpdir.join('tmp.txt')
    fn.write('content')
    monkeypatch.setattr(PathFinder, "exec_", lambda x: x)
    monkeypatch.setattr(PathFinder, "get_path_selected", lambda x: str(fn))
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_P, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)


def test_invaild_folder(qtbot):
    """Test if input of path finder is invalid."""
    pf = PathFinder(None)
    qtbot.addWidget(pf)
    pf.show()

    edit = pf.edit

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_P, Qt.ControlModifier)
    edit.keyPressEvent(event)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_N, Qt.ControlModifier)
    edit.keyPressEvent(event)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_U, Qt.ControlModifier)
    edit.keyPressEvent(event)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_D, Qt.ControlModifier)
    edit.keyPressEvent(event)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_F, Qt.ControlModifier)
    edit.keyPressEvent(event)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_U, Qt.ControlModifier)
    edit.keyPressEvent(event)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
    edit.keyPressEvent(event)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.NoModifier)
    edit.keyPressEvent(event)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_PageUp, Qt.NoModifier)
    edit.keyPressEvent(event)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_PageDown, Qt.NoModifier)
    edit.keyPressEvent(event)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Enter, Qt.NoModifier)
    edit.keyPressEvent(event)
    assert pf.get_path_selected() == ''

    pf.show()
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    edit.keyPressEvent(event)
    assert pf.get_path_selected() == ''


def test_valid_folder(qtbot, tmpdir):
    """Test valid folder."""
    folder = tmpdir.mkdir('projects')
    for name in ['a', 'ok97465.py', 'test.md', 'fig.txt']:
        tmp = folder.join(name)
        tmp.write('contents')

    folder_sub = folder.mkdir('sub1')
    for name in ['b', 'path_finder.py', '__init__.md', 'config.txt']:
        tmp = folder_sub.join(name)
        tmp.write('contents')

    pf = PathFinder(str(folder))

    qtbot.addWidget(pf)
    pf.show()

    edit = pf.edit
    lv = pf.list_viewer
    lm = pf.list_model

    assert lm.rowCount() == 6

    qtbot.keyPress(edit, Qt.Key_N, modifier=Qt.ControlModifier)
    assert lv.currentIndex().row() == 1

    qtbot.keyPress(edit, Qt.Key_P, modifier=Qt.ControlModifier)
    assert lv.currentIndex().row() == 0

    qtbot.keyPress(edit, Qt.Key_Down)
    assert lv.currentIndex().row() == 1

    qtbot.keyPress(edit, Qt.Key_Up)
    assert lv.currentIndex().row() == 0

    qtbot.keyPress(edit, Qt.Key_D, modifier=Qt.ControlModifier)
    assert lv.currentIndex().row() > 0

    qtbot.keyPress(edit, Qt.Key_U, modifier=Qt.ControlModifier)
    qtbot.keyPress(edit, Qt.Key_U, modifier=Qt.ControlModifier)
    assert lv.currentIndex().row() == 0

    qtbot.keyPress(edit, Qt.Key_F, modifier=Qt.ControlModifier)
    assert lv.currentIndex().row() > 0

    qtbot.keyPress(edit, Qt.Key_B, modifier=Qt.ControlModifier)
    qtbot.keyPress(edit, Qt.Key_B, modifier=Qt.ControlModifier)
    assert lv.currentIndex().row() == 0

    qtbot.keyPress(edit, Qt.Key_PageDown)
    assert lv.currentIndex().row() > 0

    qtbot.keyPress(edit, Qt.Key_PageUp)
    assert lv.currentIndex().row() == 0

    qtbot.keyClicks(edit, 'o')
    assert lm.rowCount() == 2

    qtbot.keyPress(edit, Qt.Key_Backspace)
    assert lm.rowCount() == 6

    qtbot.keyClicks(edit, 'ok9')
    qtbot.keyPress(edit, Qt.Key_Enter)
    assert pf.get_path_selected() != ''

