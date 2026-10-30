"""History filtering and viewport panel behavior."""

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, QObject, Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QApplication, QLineEdit, QWidget
from spyder.utils.palette import SpyderPalette

# Project Libraries
from spyder_okvim.spyder.commandline_history import HistoryPopup, history_candidates


@pytest.mark.parametrize(
    "history, prefix, expected",
    [
        ([], "", []),
        (["write", "quit", "write", "wall"], "", ["wall", "write", "quit"]),
        (["Write", "write", "wall", "write"], "w", ["write", "wall"]),
        (["write", "quit"], "missing", []),
        (["a.*b", "abc", "a.*c"], "a.*", ["a.*c", "a.*b"]),
        (["한글😀", "한글😁", "한글😀"], "한글", ["한글😀", "한글😁"]),
        (["😀first", "😀last"], "😀", ["😀last", "😀first"]),
        (["'<,'>s/old/new/", "%s/old/new/"], "'<", ["'<,'>s/old/new/"]),
    ],
)
def test_history_candidates_are_literal_unique_and_latest_first(
    history, prefix, expected
):
    original = list(history)
    assert history_candidates(history, prefix) == expected
    assert history == original


@pytest.fixture
def history_panel(qtbot, vim_bot):
    viewport = QWidget()
    viewport.resize(360, 220)
    qtbot.addWidget(viewport)
    viewport.show()
    line_edit = QLineEdit(viewport)
    line_edit.show()
    viewport.activateWindow()
    line_edit.setFocus()
    QCoreApplication.processEvents()
    panel = HistoryPopup(viewport)
    panel.refresh_appearance(QFont("Courier New", 10))
    try:
        yield viewport, line_edit, panel
    finally:
        viewport.close()
        main, _stack, _editor, vim, _qtbot = vim_bot
        main.show()
        main.activateWindow()
        vim.vim_cmd.commandline.setFocus()
        QCoreApplication.processEvents()


def test_history_panel_preserves_focus_and_starts_without_selection(history_panel):
    viewport, line_edit, panel = history_panel
    panel.set_candidates(["<b>literal</b>", "한글😀"])
    panel.update_geometry()
    panel.show()
    QCoreApplication.processEvents()

    assert QApplication.focusWidget() is line_edit
    assert panel.list_widget.currentRow() == -1
    assert panel.list_widget.selectedItems() == []
    assert panel.list_widget.item(0).text() == "<b>literal</b>"
    assert viewport.rect().contains(panel.geometry())
    assert panel.testAttribute(Qt.WA_TransparentForMouseEvents)
    for widget in (
        panel,
        panel.header,
        panel.list_widget,
        panel.list_widget.viewport(),
        panel.list_widget.verticalScrollBar(),
        panel.list_widget.horizontalScrollBar(),
    ):
        assert widget.focusPolicy() == Qt.NoFocus


def test_history_panel_scrolls_every_candidate_into_view(history_panel):
    viewport, line_edit, panel = history_panel
    panel.set_candidates([f"command {index}" for index in range(100)])
    panel.update_geometry()
    panel.show()
    QCoreApplication.processEvents()

    panel.select(99)
    QCoreApplication.processEvents()
    assert panel.list_widget.currentRow() == 99
    assert len(panel.list_widget.selectedItems()) == 1
    bounds = panel.list_widget.visualItemRect(panel.list_widget.item(99))
    assert panel.list_widget.viewport().rect().contains(bounds)
    assert panel.list_widget.verticalScrollBar().value() > 0
    assert viewport.rect().contains(panel.geometry())
    assert QApplication.focusWidget() is line_edit

    panel.set_candidates(["replacement"])
    panel.update_geometry()
    QCoreApplication.processEvents()
    assert panel.list_widget.count() == 1
    assert panel.list_widget.currentRow() == -1
    assert panel.height() < viewport.height() // 2


def test_history_panel_fits_a_narrow_viewport_after_resize(history_panel):
    viewport, _line_edit, panel = history_panel
    panel.set_candidates(["long command " * 20 for _ in range(20)])
    for width, height in ((120, 90), (600, 500), (20, 20)):
        viewport.resize(width, height)
        panel.update_geometry()
        panel.show()
        QCoreApplication.processEvents()
        assert viewport.rect().contains(panel.geometry())


def test_history_panel_refreshes_only_when_appearance_changes(
    history_panel, monkeypatch
):
    _viewport, _line_edit, panel = history_panel
    panel.set_candidates(["write"])
    panel.update_geometry()
    panel.show()
    QCoreApplication.processEvents()

    class AppearanceObserver(QObject):
        def __init__(self):
            super().__init__(panel)
            self.changes = []

        def eventFilter(self, watched, event):
            if event.type() in (QEvent.StyleChange, QEvent.FontChange):
                self.changes.append(event.type())
            return False

    observer = AppearanceObserver()
    for widget in (panel, panel.header, panel.list_widget):
        widget.installEventFilter(observer)
    font = QFont("Courier New", 10)
    for _ in range(3):
        assert not panel.refresh_appearance(font)
    QCoreApplication.processEvents()
    assert observer.changes == []

    font.setPointSize(14)
    assert panel.refresh_appearance(font)
    QCoreApplication.processEvents()
    assert panel.font().pointSize() == 14
    assert panel.header.font().pointSize() == 14
    assert panel.list_widget.font().pointSize() == 14
    assert QEvent.FontChange in observer.changes
    observer.changes.clear()
    assert not panel.refresh_appearance(font)

    monkeypatch.setattr(SpyderPalette, "COLOR_TEXT_1", "#123456")
    assert panel.refresh_appearance(font)
    QCoreApplication.processEvents()
    assert "#123456" in panel.styleSheet()
    assert QEvent.StyleChange in observer.changes
    observer.changes.clear()
    assert not panel.refresh_appearance(font)
    QCoreApplication.processEvents()
    assert observer.changes == []
