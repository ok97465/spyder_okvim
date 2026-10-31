# Third Party Libraries
import pytest
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent, QStandardItem
from qtpy.QtWidgets import QDialog

# Project Libraries
from spyder_okvim.utils.jump_dialog import (
    JumpListDialog,
    JumpRow,
    JumpSnapshot,
    build_jump_snapshot,
    read_jump_location,
)
from spyder_okvim.utils.jump_list import JumpList
from spyder_okvim.utils.list_dialog import PopupListDialog, PopupTableDialog
from spyder_okvim.utils.mark_dialog import MarkListDialog, MarkRow, build_mark_rows


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


def test_jump_list_dialog_navigation(qtbot):
    jump_list = JumpList()
    jump_list.push("a.txt", 0)
    jump_list.push("b.txt", 0)
    metadata = {"a.txt": (1, 1, "alpha"), "b.txt": (1, 1, "gamma")}
    focused = []

    def snapshot():
        return build_jump_snapshot(
            jump_list, read_location=lambda path, position: metadata[path]
        )

    def backward():
        jump_list.back()
        return snapshot()

    def forward():
        jump_list.forward()
        return snapshot()

    dlg = JumpListDialog(
        snapshot(),
        on_back=backward,
        on_forward=forward,
        on_finished=lambda: focused.append(True),
    )
    qtbot.addWidget(dlg)
    dlg.show()
    qtbot.waitExposed(dlg)

    assert dlg.list_model.rowCount() == 2
    assert dlg.list_model.item(1, 0).text().startswith(">")
    assert dlg.list_model.item(0, 4).text() == "alpha"

    qtbot.keyPress(dlg.list_viewer, Qt.Key_O, modifier=Qt.ControlModifier)
    assert jump_list.index == 1
    assert dlg.list_viewer.currentIndex().row() == 0

    qtbot.keyPress(dlg.list_viewer, Qt.Key_I, modifier=Qt.ControlModifier)
    assert jump_list.index == 2
    assert dlg.list_viewer.currentIndex().row() == 1

    index_before = jump_list.index
    qtbot.keyPress(dlg.list_viewer, Qt.Key_N, modifier=Qt.ControlModifier)
    assert jump_list.index == index_before

    dlg.reject()
    assert focused


def test_mark_list_dialog_accept_reject(qtbot):
    rows = (MarkRow("a", 2, 1, "c.txt", "line2"),)
    dlg = MarkListDialog(rows)
    qtbot.addWidget(dlg)
    dlg.show()
    qtbot.waitExposed(dlg)

    assert dlg.list_model.rowCount() == 1
    assert dlg.list_model.item(0, 0).text() == "a"
    assert dlg.list_model.item(0, 4).text() == "line2"

    dlg.accept()
    assert dlg.get_selected_mark() == "a"

    dlg.reject()
    assert dlg.get_selected_mark() == ""


def test_read_jump_location(tmpdir):
    file1 = tmpdir.join("eof.txt")
    file1.write("foo")
    assert read_jump_location(str(file1), 1) == (1, 2, "foo")
    missing = tmpdir.join("missing.txt")
    assert read_jump_location(str(missing), 0) == (1, 1, "")


def test_mark_list_dialog_invalid_accept_and_populate(qtbot):
    marks = [("a", {"file": "missing.txt", "line": 0, "col": 0})]
    rows = build_mark_rows(marks, read_line=lambda path, block: "")
    dlg = MarkListDialog(rows)
    qtbot.addWidget(dlg)
    dlg.list_viewer.setCurrentIndex(dlg.list_model.index(1, 0))
    dlg.accept()
    assert dlg.get_selected_mark() == ""
    assert dlg.list_model.item(0, 4).text() == ""


def test_prepared_rows_render_without_file_or_host_access(qtbot, monkeypatch):
    """Display consumes supplied rows even when no filesystem access is allowed."""

    def unexpected_open(*args, **kwargs):
        raise AssertionError("Rendering prepared rows must not read files")

    monkeypatch.setattr("builtins.open", unexpected_open)
    marks = MarkListDialog((MarkRow("A", 8, 4, "prepared.py", "source"),))
    jumps = JumpListDialog(
        JumpSnapshot((JumpRow(1, 8, 4, "prepared.py", "source"),), 1)
    )
    qtbot.addWidget(marks)
    qtbot.addWidget(jumps)
    assert marks.list_model.item(0, 4).text() == "source"
    assert jumps.list_model.item(0, 4).text() == "source"


def test_mark_row_preparation_can_use_in_memory_metadata():
    marks = [("b", {"file": "project/source.py", "line": 3, "col": 2})]
    lookups = []

    def read_line(path, block):
        lookups.append((path, block))
        return "prepared source"

    assert build_mark_rows(marks, read_line=read_line) == (
        MarkRow("b", 4, 3, "source.py", "prepared source"),
    )
    assert lookups == [("project/source.py", 3)]
