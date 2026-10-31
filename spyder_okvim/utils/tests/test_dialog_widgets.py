# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, QRect, Qt
from qtpy.QtGui import QColor, QKeyEvent, QPalette, QStandardItem
from qtpy.QtWidgets import QDialog, QWidget

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


@pytest.mark.parametrize("key, expected", [(Qt.Key_O, 2), (Qt.Key_I, 4)])
def test_jump_shortcut_moves_exactly_once_away_from_boundaries(qtbot, key, expected):
    jumps = JumpList()
    for position in range(5):
        jumps.push("source.py", position)
    jumps.index = 3
    calls = []

    def snapshot():
        return build_jump_snapshot(jumps, read_location=lambda *_: (1, 1, "source"))

    def navigate(backward):
        calls.append(backward)
        jumps.back() if backward else jumps.forward()
        return snapshot()

    dialog = JumpListDialog(
        snapshot(), on_back=lambda: navigate(True), on_forward=lambda: navigate(False)
    )
    qtbot.addWidget(dialog)
    dialog.show()
    reserved = QKeyEvent(QEvent.ShortcutOverride, key, Qt.ControlModifier)
    QCoreApplication.sendEvent(dialog.list_viewer, reserved)
    assert reserved.isAccepted()
    assert calls == []
    assert jumps.index == 3

    qtbot.keyClick(dialog.list_viewer, key, Qt.ControlModifier)
    assert calls == [key == Qt.Key_O]
    assert jumps.index == expected
    assert dialog.list_viewer.currentIndex().row() == expected - 1


@pytest.mark.parametrize("confirm", [True, False])
def test_jump_selection_only_navigates_when_confirmed(qtbot, confirm):
    rows = tuple(JumpRow(i, 1, 1, "source.py", "source") for i in range(1, 6))
    applied, finished = [], []
    dialog = JumpListDialog(
        JumpSnapshot(rows, 3),
        on_select=applied.append,
        on_finished=lambda: finished.append(True),
    )
    dialog.setAttribute(Qt.WA_DeleteOnClose, False)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.keyClick(dialog.list_viewer, Qt.Key_N, Qt.ControlModifier)
    assert dialog.list_viewer.currentIndex().row() == 3
    assert applied == []
    assert dialog.snapshot.current_index == 3
    qtbot.keyClick(dialog.list_viewer, Qt.Key_Return if confirm else Qt.Key_Escape)
    assert applied == ([4] if confirm else [])
    assert finished == [True]


def test_mark_mouse_selection_and_confirmation(qtbot):
    dialog = MarkListDialog(
        (MarkRow("a", 1, 1, "a.py", "first"), MarkRow("b", 2, 1, "b.py", "second"))
    )
    qtbot.addWidget(dialog)
    dialog.show()
    point = dialog.list_viewer.visualRect(dialog.list_model.index(1, 0)).center()
    qtbot.mouseClick(dialog.list_viewer.viewport(), Qt.LeftButton, pos=point)
    assert dialog.get_selected_mark() == ""
    assert dialog.list_viewer.currentIndex().row() == 1
    qtbot.mouseDClick(dialog.list_viewer.viewport(), Qt.LeftButton, pos=point)
    assert dialog.get_selected_mark() == "b"


@pytest.mark.parametrize("size", [(340, 240), (180, 150)])
def test_picker_geometry_fits_small_parent_and_grows_with_rows(qtbot, size):
    parent = QWidget()
    parent.resize(*size)
    qtbot.addWidget(parent)
    parent.show()
    dialog = PopupTableDialog("Small picker", parent, headers=["Path"], min_width=800)
    qtbot.addWidget(dialog)
    dialog.list_model.appendRow(QStandardItem("short"))
    dialog.move(parent.mapToGlobal(parent.rect().bottomRight()))
    dialog.show()
    small_height = dialog.height()
    assert dialog._available_geometry().contains(dialog.geometry())
    for number in range(20):
        dialog.list_model.appendRow(QStandardItem(f"row {number}"))
    qtbot.waitUntil(lambda: dialog.height() > small_height)
    assert dialog._available_geometry().contains(dialog.geometry())


def test_picker_uses_owner_monitor_when_initial_position_is_elsewhere(
    qtbot, monkeypatch
):
    """The initial default popup position must not select the primary monitor."""
    from qtpy.QtWidgets import QApplication

    class Screen:
        def __init__(self, x):
            self.x = x

        def availableGeometry(self):
            return QRect(self.x, 0, 800, 600)

    primary, secondary = Screen(0), Screen(1000)
    monkeypatch.setattr(
        QApplication,
        "screenAt",
        lambda point: secondary if point.x() >= 1000 else primary,
    )
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(340, 240)
    parent.show()
    parent.move(1100, 100)
    dialog = PopupTableDialog("Secondary monitor", parent, headers=["Path"])
    qtbot.addWidget(dialog)
    dialog.move(0, 0)
    dialog.show()
    assert dialog.geometry().left() >= 1000
    assert dialog._available_geometry().contains(dialog.geometry())


def test_picker_uses_current_palette_and_accessible_help(qtbot):
    dialog = PopupTableDialog("Themed picker", headers=["Path"])
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.Text, QColor("#123456"))
    palette.setColor(QPalette.Base, QColor("#fefefe"))
    dialog.setPalette(palette)
    dialog.show()
    assert dialog.list_viewer.palette().color(QPalette.Text) == QColor("#123456")
    palette.setColor(QPalette.Text, QColor("#eeeeee"))
    dialog.setPalette(palette)
    assert dialog.list_viewer.palette().color(QPalette.Text) == QColor("#eeeeee")
    assert dialog.list_viewer.accessibleName() == "Themed picker results"
    assert "Enter" in dialog.help_label.text()
