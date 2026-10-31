"""History filtering and viewport panel behavior."""

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, QObject, Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QApplication, QLineEdit, QWidget
from spyder.utils.palette import SpyderPalette
from spyder.utils.stylesheet import APP_STYLESHEET

# Project Libraries
from spyder_okvim.spyder.commandline_history import HistoryPopup, history_candidates
from spyder_okvim.spyder.commandline_popup import CommandlinePopupHost
from spyder_okvim.utils.commandline import CompletionCandidate
from spyder_okvim.utils.ex_parser import scan_substitute_guide


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
    host = CommandlinePopupHost(viewport)
    panel = host.popup
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


def show_candidates(panel):
    host = panel.parentWidget()
    host.invalidate_geometry()
    host.show_sections(candidates=True, guide=False)


def test_history_panel_preserves_focus_and_starts_without_selection(history_panel):
    viewport, line_edit, panel = history_panel
    panel.set_candidates(["<b>literal</b>", "한글😀"])
    show_candidates(panel)
    QCoreApplication.processEvents()

    assert QApplication.focusWidget() is line_edit
    assert panel.list_widget.currentRow() == -1
    assert panel.list_widget.selectedItems() == []
    assert panel.list_widget.item(0).text() == "<b>literal</b>"
    assert viewport.rect().contains(panel.parentWidget().geometry())
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


def test_candidate_rows_identify_abbreviated_sources(history_panel):
    _viewport, _line_edit, panel = history_panel
    candidate = CompletionCandidate(
        "history, command", ":write", "full command", ":write original😀", 16
    )
    panel.set_candidates([candidate])
    label = panel.list_widget.item(0).text()
    assert label == "[H,C]   :write"
    assert panel._candidates == (candidate,)
    assert candidate.text == ":write original😀"


def test_common_host_stacks_scrollable_sections_inside_the_viewport(history_panel):
    viewport, line_edit, _panel = history_panel
    host = CommandlinePopupHost(viewport)
    host.popup.set_candidates([f":s/foo/value{index}/g" for index in range(20)])
    host.guide_popup.set_context(scan_substitute_guide(":s/foo/", len(":s/foo/")))
    for width, height in ((700, 600), (160, 140), (20, 20), (600, 500)):
        viewport.resize(width, height)
        host.show_sections(candidates=True, guide=True)
        QCoreApplication.processEvents()
        assert viewport.rect().contains(host.geometry())
        assert host.rect().contains(host.popup.geometry())
        assert host.rect().contains(host.guide_popup.geometry())
        assert host.popup.geometry().bottom() < host.guide_popup.geometry().top()
        assert host.popup.isVisible()
        assert host.guide_popup.isVisible()
        assert QApplication.focusWidget() is line_edit
    assert host.popup.list_widget.verticalScrollBar().maximum() > 0


def test_unchanged_host_reuses_measurement_and_selection(history_panel, monkeypatch):
    viewport, _line_edit, _panel = history_panel
    host = CommandlinePopupHost(viewport)
    host.popup.set_candidates(["write", "wall"])
    host.guide_popup.set_context(scan_substitute_guide(":s/", len(":s/")))
    host.show_sections(candidates=True, guide=True)
    host.popup.select(1)

    def unexpected(*args, **kwargs):
        pytest.fail("Unchanged popup content must not be measured again")

    monkeypatch.setattr(host.popup, "preferred_size", unexpected)
    monkeypatch.setattr(host.guide_popup, "preferred_size", unexpected)
    host.hide()
    for _ in range(3):
        host.show_sections(candidates=True, guide=True)
    assert host.popup.list_widget.currentRow() == 1


def test_history_panel_scrolls_every_candidate_into_view(history_panel):
    viewport, line_edit, panel = history_panel
    panel.set_candidates([f"command {index}" for index in range(100)])
    show_candidates(panel)
    QCoreApplication.processEvents()

    panel.select(99)
    QCoreApplication.processEvents()
    assert panel.list_widget.currentRow() == 99
    assert len(panel.list_widget.selectedItems()) == 1
    bounds = panel.list_widget.visualItemRect(panel.list_widget.item(99))
    assert panel.list_widget.viewport().rect().contains(bounds)
    assert panel.list_widget.verticalScrollBar().value() > 0
    assert viewport.rect().contains(panel.parentWidget().geometry())
    assert QApplication.focusWidget() is line_edit

    panel.set_candidates(["replacement"])
    show_candidates(panel)
    QCoreApplication.processEvents()
    assert panel.list_widget.count() == 1
    assert panel.list_widget.currentRow() == -1
    assert panel.height() < viewport.height() // 2


@pytest.mark.parametrize("themed", [False, True])
@pytest.mark.parametrize("font_size", [10, 14])
@pytest.mark.parametrize(
    "candidates",
    [
        ["write"],
        ["write", "quit"],
        ["write", "한글😀"],
        ["한글😀", "write"],
        ["write", "한글😀"] * (HistoryPopup.MAX_VISIBLE_ROWS // 2),
    ],
)
def test_default_panel_fits_complete_rows_without_scrollbars(
    history_panel, themed, font_size, candidates
):
    viewport, _line_edit, panel = history_panel
    viewport.resize(700, 500)
    if themed:
        viewport.setStyleSheet(APP_STYLESHEET.to_string())
    panel.refresh_appearance(QFont("Courier New", font_size))
    panel.set_candidates(candidates)
    show_candidates(panel)
    QCoreApplication.processEvents()

    listing = panel.list_widget
    assert listing.font().family() == "Courier New"
    assert listing.font().pointSize() == font_size
    assert panel.width() >= panel.MIN_WIDTH
    assert listing.verticalScrollBar().maximum() == 0
    assert not listing.verticalScrollBar().isVisible()
    assert not listing.horizontalScrollBar().isVisible()
    assert listing.viewport().width() >= listing.sizeHintForColumn(0)
    for row in range(listing.count()):
        bounds = listing.visualItemRect(listing.item(row))
        assert bounds.height() >= listing.sizeHintForRow(row)
        assert listing.viewport().rect().contains(bounds)
    assert viewport.rect().contains(panel.parentWidget().geometry())


def test_themed_panel_reserves_scrollbar_space_for_long_commands(history_panel):
    viewport, _line_edit, panel = history_panel
    viewport.resize(1000, 600)
    viewport.setStyleSheet(APP_STYLESHEET.to_string())
    panel.set_candidates([f"s/{'old' * 15}/한글😀{row}/g" for row in range(12)])
    show_candidates(panel)
    QCoreApplication.processEvents()

    listing = panel.list_widget
    assert listing.verticalScrollBar().isVisible()
    assert listing.viewport().width() >= listing.sizeHintForColumn(0)
    for row in range(panel.MAX_VISIBLE_ROWS):
        bounds = listing.visualItemRect(listing.item(row))
        assert listing.viewport().rect().contains(bounds)
    panel.select(11)
    assert listing.viewport().rect().contains(listing.visualItemRect(listing.item(11)))


def test_history_panel_fits_a_narrow_viewport_after_resize(history_panel):
    viewport, _line_edit, panel = history_panel
    panel.set_candidates(["long command " * 20 for _ in range(20)])
    for width, height in ((120, 90), (600, 500), (20, 20)):
        viewport.resize(width, height)
        show_candidates(panel)
        QCoreApplication.processEvents()
        assert viewport.rect().contains(panel.parentWidget().geometry())


@pytest.mark.parametrize("themed", [False, True])
def test_history_panel_refreshes_only_when_appearance_changes(
    history_panel, monkeypatch, themed
):
    viewport, _line_edit, panel = history_panel
    if themed:
        viewport.setStyleSheet(APP_STYLESHEET.to_string())
    panel.set_candidates(["write"])
    show_candidates(panel)
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
