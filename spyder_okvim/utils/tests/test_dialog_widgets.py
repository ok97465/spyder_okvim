"""The table popup retained by YankHistory keeps its own navigation contract."""

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, QRect, Qt
from qtpy.QtGui import QColor, QKeyEvent, QPalette, QStandardItem
from qtpy.QtWidgets import QDialog, QWidget
from spyder_okvim.utils.list_dialog import PopupTableDialog


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


@pytest.mark.parametrize("dark", [True, False])
def test_table_popup_uses_spyder_theme_over_native_light_palette(
    qtbot, monkeypatch, dark
):
    """Yank lists and headers must agree with their surrounding styled popup."""
    import qdarkstyle
    from spyder.utils import palette as spyder_palette

    from spyder_okvim.utils.theme import contrast_ratio

    colors = (
        spyder_palette.SpyderPaletteDark if dark else spyder_palette.SpyderPaletteLight
    )
    monkeypatch.setattr(spyder_palette, "SpyderPalette", colors)
    parent = QWidget()
    qtbot.addWidget(parent)
    native_palette = QPalette(parent.palette())
    for role in (QPalette.Base, QPalette.Window, QPalette.Mid):
        native_palette.setColor(role, QColor("#ffffff"))
    for role in (QPalette.Text, QPalette.WindowText):
        native_palette.setColor(role, QColor("#000000"))
    parent.setPalette(native_palette)
    parent.setStyleSheet(qdarkstyle.load_stylesheet(palette=colors))
    parent.resize(480, 320)
    parent.show()
    dialog = PopupTableDialog("Yank history", parent, headers=["Text"])
    qtbot.addWidget(dialog)
    dialog.list_model.appendRow(QStandardItem("Saved text"))
    dialog.show()
    QCoreApplication.processEvents()

    expected_background = QColor(colors.COLOR_BACKGROUND_1)
    expected_border = QColor(colors.COLOR_BACKGROUND_4)
    for widget in (dialog, dialog.list_viewer, dialog.list_viewer.viewport()):
        for group in (QPalette.Active, QPalette.Inactive):
            palette = widget.palette()
            assert palette.color(group, QPalette.Base) == expected_background
            assert palette.color(group, QPalette.Mid) == expected_border
            assert (
                contrast_ratio(palette.color(group, QPalette.Text), expected_background)
                >= 4.5
            )
    viewport = dialog.list_viewer.viewport()
    pixels = viewport.grab().toImage()
    assert pixels.pixelColor(2, pixels.height() - 2) == expected_background
    header = dialog.list_viewer.horizontalHeader()
    pixels = header.grab().toImage()
    assert pixels.pixelColor(pixels.width() - 8, pixels.height() // 2) == QColor(
        colors.COLOR_BACKGROUND_2
    )
