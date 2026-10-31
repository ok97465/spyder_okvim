"""Adaptive popup and status presentation through real Qt layout events."""

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, QRect, Qt
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QLineEdit, QMainWindow, QWidget
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.commandline_popup import CommandlinePopupHost
from spyder_okvim.spyder.plugin import StatusBarVimWidget
from spyder_okvim.spyder.popup_geometry import popup_area
from spyder_okvim.spyder.vim_widgets import VimMessageLabel, VimStateLabel
from spyder_okvim.spyder.which_key_popup import WhichKeyPopup
from spyder_okvim.utils.ex_parser import scan_substitute_guide
from spyder_okvim.vim.state import VimState


class EditorHost(QWidget):
    """Expose a movable cursor line while using ordinary Qt child geometry."""

    def cursorRect(self):
        return QRect(50, self.cursor_y, 2, 20)


@pytest.mark.parametrize("cursor_y", [0, 100, 250])
def test_combined_help_keeps_cursor_visible(qtbot, cursor_y):
    editor = EditorHost()
    editor.cursor_y = cursor_y
    viewport = QWidget(editor)
    viewport.resize(360, 280)
    qtbot.addWidget(editor)
    host = CommandlinePopupHost(viewport)
    host.popup.set_candidates([f"command {index}" for index in range(20)])
    host.guide_popup.set_context(scan_substitute_guide(":s/", 3))
    host.show_sections(candidates=True, guide=True)

    assert viewport.rect().contains(host.geometry())
    assert not host.geometry().intersects(editor.cursorRect())
    assert host.geometry().height() <= popup_area(viewport).height()
    assert host.rect().contains(host.popup.geometry())
    assert host.rect().contains(host.guide_popup.geometry())

    editor.cursor_y = 260 if cursor_y == 0 else 0
    host.update_geometry()
    assert not host.geometry().intersects(editor.cursorRect())


def test_which_key_reflows_existing_candidates_on_resize(qtbot):
    viewport = QWidget()
    qtbot.addWidget(viewport)
    popup = WhichKeyPopup(viewport)
    candidates = [(str(index), "설명 example action") for index in range(12)]
    popup.set_candidates("g", candidates)
    labels = tuple(popup.candidate_labels)
    for width, columns in ((240, 1), (900, 2), (240, 1)):
        viewport.resize(width, 240)
        popup.update_geometry()
        assert popup.column_count == columns
        assert tuple(popup.candidate_labels) == labels
        assert viewport.rect().contains(popup.geometry())
        assert popup.focusPolicy() == Qt.NoFocus


def test_mode_palette_and_custom_colors(qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    label = VimStateLabel(parent)
    palette = QPalette(label.palette())
    palette.setColor(QPalette.Highlight, QColor("#ffe080"))
    palette.setColor(QPalette.HighlightedText, QColor("#202020"))
    label.setPalette(palette)
    label.change_state(VimState.VISUAL)
    assert "#ffe080" in label.styleSheet()
    assert "#202020" in label.styleSheet()
    assert label.text() == "VISUAL"
    assert "VISUAL" in label.accessibleDescription()

    original = CONF.get
    overrides = {"mode_fg_color": "#123456", "mode_bg_color": "#fedcba"}
    monkeypatch.setattr(
        CONF,
        "get",
        lambda section, option, *args, **kwargs: overrides.get(
            option, original(section, option, *args, **kwargs)
        ),
    )
    label.refresh_appearance()
    assert "#123456" in label.styleSheet()
    assert "#fedcba" in label.styleSheet()


def test_statusbar_stays_stable_during_input_and_tracks_window_resize(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    message = VimMessageLabel(window)
    mode = VimStateLabel(window)
    line = QLineEdit(window)
    statusbar = window.statusBar()
    # Spyder constructs with the main window, then inserts into its status bar.
    widget = StatusBarVimWidget(window, message, mode, line)
    statusbar.addPermanentWidget(widget)
    window.resize(1000, 400)
    window.show()
    window.activateWindow()
    line.setFocus()
    QCoreApplication.processEvents()
    message.setText("긴 검색 오류와 상태 메시지 " * 30)
    QCoreApplication.processEvents()
    initial_geometry = widget.geometry(), line.geometry()
    line.clearFocus()
    QCoreApplication.processEvents()
    assert (widget.geometry(), line.geometry()) == initial_geometry
    line.setFocus()
    QCoreApplication.processEvents()
    assert (widget.geometry(), line.geometry()) == initial_geometry
    for text in ("/foo", "/" + "긴 검색어" * 30, "", "/" + "긴 검색어" * 30):
        line.setText(text)
        QCoreApplication.processEvents()
        assert (widget.geometry(), line.geometry()) == initial_geometry
    assert message.toolTip() == message.text()
    assert message.accessibleDescription() == message.text()

    window.resize(320, 400)
    QCoreApplication.processEvents()
    assert widget.width() <= statusbar.width()
    assert widget.rect().contains(line.geometry())
    assert line.text().endswith("긴 검색어")

    # Resizing only the new parent must also update the available space.
    statusbar.resize(240, statusbar.height())
    assert widget.maximumWidth() <= round(statusbar.width() * 0.65)

    # Status-bar layout events can outlive the command input during shutdown.
    line.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    statusbar.resize(260, statusbar.height())
    QCoreApplication.processEvents()


def test_real_command_input_accepts_statusbar_allocation(vim_bot):
    """The command widget must allow the status bar to allocate extra width."""
    main, _stack, _editor, vim, _qtbot = vim_bot
    line = vim.vim_cmd.commandline
    previous_size = line.size()
    try:
        requested_width = line.fontMetrics().horizontalAdvance("M") * 60
        line.resize(requested_width, line.height())
        assert line.width() == requested_width
    finally:
        line.resize(previous_size)
        main.activateWindow()
        line.setFocus()
        QCoreApplication.processEvents()
