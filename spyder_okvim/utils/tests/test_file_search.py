# -*- coding: utf-8 -*-
"""Tests for the file search dialog."""

# Third Party Libraries
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent

# Project Libraries
from spyder_okvim.utils.file_search import FileSearchDialog
from spyder_okvim.utils.jump_list import Jump


def test_open_file_search(vim_bot, monkeypatch, tmpdir):
    """Test opening the file search dialog and jump list update."""
    main, stack, _, vim, qtbot = vim_bot

    fn = tmpdir.join("tmp.txt")
    fn.write("content")

    monkeypatch.setattr(FileSearchDialog, "exec_", lambda x: x)
    monkeypatch.setattr(FileSearchDialog, "get_selected_path", lambda x: str(fn))

    monkeypatch.setattr(main, "load_edit", lambda path: None)

    vs = vim.vim_cmd.vim_status
    vs.cursor.set_cursor_pos(0)
    vs.reset_for_test()
    current = stack.get_current_filename()

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_P, Qt.ControlModifier)
    vim.vim_cmd.commandline.keyPressEvent(event)

    assert vs.jump_list.jumps == [
        Jump(current, 0),
        Jump(str(fn), 0),
    ]


def test_invalid_folder(qtbot):
    """Test dialog behavior with an invalid folder."""
    pf = FileSearchDialog(None)
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
    assert pf.get_selected_path() == ""

    pf.show()
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    edit.keyPressEvent(event)
    assert pf.get_selected_path() == ""


def test_valid_folder(qtbot, tmpdir):
    """Test valid folder."""
    folder = tmpdir.mkdir("projects")
    for name in ["a", "ok97465.py", "test.md", "fig.txt"]:
        tmp = folder.join(name)
        tmp.write("contents")

    folder_sub = folder.mkdir("sub1")
    for name in ["b", "path_finder.py", "__init__.md", "config.txt"]:
        tmp = folder_sub.join(name)
        tmp.write("contents")

    pf = FileSearchDialog(str(folder))

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

    qtbot.keyClicks(edit, "o")
    assert lm.rowCount() == 2

    qtbot.keyPress(edit, Qt.Key_Backspace)
    assert lm.rowCount() == 6

    qtbot.keyClicks(edit, "ok9")
    qtbot.keyPress(edit, Qt.Key_Enter)
    assert pf.get_selected_path() != ""
