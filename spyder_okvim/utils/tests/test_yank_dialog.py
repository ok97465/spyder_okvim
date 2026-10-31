"""History picker key handling, preview limits, and original payloads."""

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QDialog

from spyder_okvim.utils.yank_dialog import YankHistoryDialog
from spyder_okvim.vim.state import VimState
from spyder_okvim.vim.yank_history import YankEntry


@pytest.fixture
def history_dialog(qtbot):
    entries = (
        YankEntry.from_register("한글\noriginal\t😀\n", VimState.VLINE),
        YankEntry.from_register("second", VimState.NORMAL),
    )
    dialog = YankHistoryDialog(entries)
    dialog.setAttribute(Qt.WA_DeleteOnClose, False)
    qtbot.addWidget(dialog)
    dialog.show()
    yield dialog, entries
    dialog.close()


def test_history_picker_is_read_only_and_selects_first_entry(history_dialog):
    dialog, entries = history_dialog
    assert dialog.list_viewer.currentIndex().row() == 0
    assert dialog.list_model.item(0, 0).text() == "Line"
    assert dialog.list_model.item(0, 1).text() == "2"
    for row in range(dialog.list_model.rowCount()):
        for col in range(dialog.list_model.columnCount()):
            item = dialog.list_model.item(row, col)
            assert not item.isEditable()
            assert item.data(Qt.UserRole) is entries[row]
    assert "\n" not in dialog.list_model.item(0, 2).text()
    assert "\t" not in dialog.list_model.item(0, 2).text()


@pytest.mark.parametrize("key", [Qt.Key_N, Qt.Key_P])
def test_shortcut_override_only_reserves_navigation(history_dialog, key):
    dialog, _ = history_dialog
    dialog.next_row()
    before = dialog.list_viewer.currentIndex().row()
    event = QKeyEvent(QEvent.ShortcutOverride, key, Qt.ControlModifier)
    QCoreApplication.sendEvent(dialog.list_viewer, event)
    assert event.isAccepted()
    assert dialog.list_viewer.currentIndex().row() == before


def test_table_focus_keys_select_original_payload(history_dialog, qtbot):
    dialog, entries = history_dialog
    selected = []
    dialog.finished.connect(lambda result: selected.append(dialog.selected_entry))
    qtbot.keyClick(dialog.list_viewer, Qt.Key_N, Qt.ControlModifier)
    assert dialog.list_viewer.currentIndex().row() == 1
    qtbot.keyClick(dialog.list_viewer, Qt.Key_Up)
    assert dialog.list_viewer.currentIndex().row() == 0
    qtbot.keyClick(dialog.list_viewer, Qt.Key_Down)
    qtbot.keyClick(dialog.list_viewer, Qt.Key_P, Qt.ControlModifier)
    qtbot.keyClick(dialog.list_viewer, Qt.Key_Return)
    assert dialog.result() == QDialog.Accepted
    assert selected == [entries[0]]
    assert selected[0] is entries[0]
    assert dialog.selected_entry.text == "한글\noriginal\t😀\n"


def test_selected_entry_follows_its_row_after_order_changes(history_dialog):
    dialog, entries = history_dialog
    row = dialog.list_model.takeRow(1)
    dialog.list_model.insertRow(0, row)
    dialog.list_viewer.setCurrentIndex(dialog.list_model.index(0, 0))
    dialog.accept()
    assert dialog.selected_entry is entries[1]


def test_escape_and_empty_history_return_no_payload(history_dialog, qtbot):
    dialog, _ = history_dialog
    selected = []
    dialog.finished.connect(lambda result: selected.append(dialog.selected_entry))
    qtbot.keyClick(dialog.list_viewer, Qt.Key_Escape)
    assert dialog.result() == QDialog.Rejected
    assert dialog.selected_entry is None
    assert selected == [None]
    empty = YankHistoryDialog(())
    empty.setAttribute(Qt.WA_DeleteOnClose, False)
    qtbot.addWidget(empty)
    empty.finished.connect(lambda result: selected.append(empty.selected_entry))
    empty.accept()
    assert empty.selected_entry is None
    assert selected == [None, None]


def test_history_previews_stay_bounded():
    for content in ("x" * 10000, "\n" * 10000, "😀" * 10000, "\t" * 10000):
        preview = YankHistoryDialog.preview(content)
        assert len(preview) <= YankHistoryDialog.PREVIEW_LENGTH
        assert preview.endswith("…")
        assert "\n" not in preview
        assert "\t" not in preview
