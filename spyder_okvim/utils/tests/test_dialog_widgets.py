# Third Party Libraries
import pytest
from qtpy.QtCore import Qt, QEvent
from qtpy.QtGui import QKeyEvent, QStandardItem
from qtpy.QtWidgets import QDialog

# Project Libraries
from spyder_okvim.utils.list_dialog import PopupListDialog, PopupTableDialog
from spyder_okvim.utils.jump_dialog import JumpListDialog
from spyder_okvim.utils.mark_dialog import MarkListDialog
from spyder_okvim.utils.jump_list import JumpList


class DummyVimStatus:
    """Simple stand-in for VimStatus used in dialogs."""

    def __init__(self, jump_list):
        self.jump_list = jump_list
        self.focused = False

    def jump_backward(self):
        self.jump_list.back()

    def jump_forward(self):
        self.jump_list.forward()

    def set_focus_to_vim(self):
        self.focused = True


def test_popup_list_dialog_navigation(qtbot):
    dlg = PopupListDialog("Test", min_width=100)
    qtbot.addWidget(dlg)
    dlg.list_model.setStringList(["a", "b", "c"])
    dlg.list_viewer.setCurrentIndex(dlg.list_model.index(0, 0))
    dlg.show()
    qtbot.waitExposed(dlg)

    dlg.next_row()
    assert dlg.list_viewer.currentIndex().row() == 1
    dlg.prev_row()
    assert dlg.list_viewer.currentIndex().row() == 0

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_N, Qt.ControlModifier)
    dlg.keyPressEvent(event)
    assert dlg.list_viewer.currentIndex().row() == 1
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_P, Qt.ControlModifier)
    dlg.keyPressEvent(event)
    assert dlg.list_viewer.currentIndex().row() == 0

    dlg.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
    assert dlg.result() == QDialog.Accepted


def test_popup_list_dialog_escape_and_pages(qtbot):
    dlg = PopupListDialog("Test")
    qtbot.addWidget(dlg)
    dlg.list_model.setStringList(["a", "b", "c", "d"])
    dlg.list_viewer.setCurrentIndex(dlg.list_model.index(0, 0))
    dlg.show()
    qtbot.waitExposed(dlg)

    dlg.pg_down()
    dlg.pg_up()
    dlg.pg_half_down()
    dlg.pg_half_up()
    dlg.get_number_of_visible_lines()

    dlg.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    assert dlg.result() == QDialog.Rejected


def test_popup_table_dialog_keys(qtbot):
    dlg = PopupTableDialog("Table", headers=["col"])
    qtbot.addWidget(dlg)
    dlg.list_model.appendRow([QStandardItem("x")])
    dlg.list_model.appendRow([QStandardItem("y")])
    dlg.list_viewer.setCurrentIndex(dlg.list_model.index(0, 0))
    dlg.list_viewer.selectRow(0)
    dlg.show()
    qtbot.waitExposed(dlg)

    dlg.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_N, Qt.ControlModifier))
    assert dlg.list_viewer.currentIndex().row() == 1

    dlg.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
    assert dlg.result() == QDialog.Accepted


def test_popup_table_dialog_escape(qtbot):
    dlg = PopupTableDialog("Table", headers=["col"], min_width=120)
    qtbot.addWidget(dlg)
    dlg.list_model.appendRow([QStandardItem("x")])
    dlg.list_viewer.setCurrentIndex(dlg.list_model.index(0, 0))
    dlg.list_viewer.selectRow(0)
    dlg.show()
    qtbot.waitExposed(dlg)

    dlg.pg_up()
    dlg.pg_down()
    dlg.pg_half_up()
    dlg.pg_half_down()
    dlg.get_number_of_visible_lines()

    dlg.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    assert dlg.result() == QDialog.Rejected


def test_jump_list_dialog_navigation(qtbot, tmpdir):
    file1 = tmpdir.join("a.txt")
    file1.write("alpha\nbeta\n")
    file2 = tmpdir.join("b.txt")
    file2.write("gamma\n")

    jl = JumpList()
    jl.push(str(file1), 0)
    jl.push(str(file2), 0)
    vs = DummyVimStatus(jl)

    dlg = JumpListDialog(vs)
    qtbot.addWidget(dlg)
    dlg.show()
    qtbot.waitExposed(dlg)

    assert dlg.list_model.rowCount() == 2
    assert dlg.list_model.item(1, 0).text().startswith(">")

    qtbot.keyPress(dlg.list_viewer, Qt.Key_O, modifier=Qt.ControlModifier)
    assert vs.jump_list.index == 1

    qtbot.keyPress(dlg.list_viewer, Qt.Key_I, modifier=Qt.ControlModifier)
    assert vs.jump_list.index == 2

    idx_before = vs.jump_list.index
    qtbot.keyPress(dlg.list_viewer, Qt.Key_N, modifier=Qt.ControlModifier)
    assert vs.jump_list.index == idx_before

    dlg.reject()
    assert vs.focused


def test_mark_list_dialog_accept_reject(qtbot, tmpdir):
    file1 = tmpdir.join("c.txt")
    file1.write("line1\nline2\n")
    marks = [("a", {"file": str(file1), "line": 1, "col": 0})]

    dlg = MarkListDialog(marks)
    qtbot.addWidget(dlg)
    dlg.show()
    qtbot.waitExposed(dlg)

    assert dlg.list_model.rowCount() == 1
    row = dlg.list_model.item(0, 0).text()
    assert row == "a"

    dlg.accept()
    assert dlg.get_selected_mark() == "a"

    dlg.reject()
    assert dlg.get_selected_mark() == ""


def test_jump_list_get_line_info(tmpdir):
    file1 = tmpdir.join("eof.txt")
    file1.write("foo")
    jl = JumpList()
    vs = DummyVimStatus(jl)
    dlg = JumpListDialog(vs)
    line, col, text = dlg._get_line_info(str(file1), 1)
    assert (line, col, text) == (1, 2, "foo")

    missing = tmpdir.join("missing.txt")
    line, col, text = dlg._get_line_info(str(missing), 0)
    assert (line, col, text) == (1, 1, "")


def test_mark_list_dialog_invalid_accept_and_populate(tmpdir):
    bad_file = tmpdir.join("missing.txt")
    marks = [("a", {"file": str(bad_file), "line": 0, "col": 0})]
    dlg = MarkListDialog(marks)
    dlg.list_viewer.setCurrentIndex(dlg.list_model.index(1, 0))
    dlg.accept()
    assert dlg.get_selected_mark() == ""
    assert dlg.list_model.item(0, 4).text() == ""
