"""The substitution guide explains input without owning any input state."""

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, QObject, Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QApplication, QLineEdit, QWidget
from spyder.utils.palette import SpyderPalette
from spyder.utils.stylesheet import APP_STYLESHEET

from spyder_okvim.spyder.substitute_guide import (
    SUBSTITUTION_OPTIONS,
    SubstituteGuidePopup,
)
from spyder_okvim.utils.ex_parser import (
    ExError,
    SubstituteGuideContext,
    SubstituteSpec,
    parse_substitute,
    scan_substitute_guide,
)


@pytest.fixture
def guide_panel(qtbot, vim_bot):
    viewport = QWidget()
    viewport.resize(700, 600)
    qtbot.addWidget(viewport)
    line = QLineEdit(viewport)
    viewport.show()
    line.show()
    viewport.activateWindow()
    line.setFocus()
    QCoreApplication.processEvents()
    popup = SubstituteGuidePopup(viewport)
    popup.refresh_appearance(QFont("Courier New", 10))
    try:
        yield viewport, line, popup
    finally:
        viewport.close()
        main, _stack, _editor, vim, _qtbot = vim_bot
        main.show()
        main.activateWindow()
        vim.vim_cmd.commandline.setFocus()
        QCoreApplication.processEvents()


def show(popup, command, previous=None):
    context = scan_substitute_guide(command, len(command), previous)
    assert context is not None
    popup.set_context(context)
    popup.update_geometry()
    popup.show()
    QCoreApplication.processEvents()
    return context


@pytest.mark.parametrize(
    "command, title, description",
    [
        (":s/", "Search pattern", r"\d = digit"),
        (":s/foo/bar/", "Substitution options", ""),
        (":s/foo/bar/g 3", "Line count", "number of lines"),
    ],
)
def test_stage_help_is_plain_text_and_keeps_input_focus(
    guide_panel, command, title, description
):
    viewport, line, popup = guide_panel
    line.setText(command)
    position = line.cursorPosition()
    show(popup, command)

    assert popup.header.text() == title
    assert description in popup.description.text()
    assert popup.header.textFormat() == Qt.PlainText
    assert popup.description.textFormat() == Qt.PlainText
    assert QApplication.focusWidget() is line
    assert line.text() == command
    assert line.cursorPosition() == position
    assert viewport.rect().contains(popup.geometry())
    assert popup.testAttribute(Qt.WA_ShowWithoutActivating)
    assert popup.testAttribute(Qt.WA_TransparentForMouseEvents)
    for widget in (
        popup,
        popup.scroll_area,
        popup.scroll_area.viewport(),
        popup.scroll_area.verticalScrollBar(),
        popup.scroll_area.horizontalScrollBar(),
        *popup.findChildren(QWidget),
    ):
        assert widget.focusPolicy() == Qt.NoFocus


def test_pattern_shows_expression_references(guide_panel):
    _viewport, _line, popup = guide_panel
    show(popup, ":s#old/path")
    assert "[a-z] = character range" in popup.description.text()
    assert r"\b = word boundary" in popup.description.text()
    assert "+ = one or more" in popup.description.text()
    assert "(...) = capture group; a|b = a or b" in popup.description.text()
    assert "Qt" not in popup.description.text()
    assert "Next #" not in popup.description.text()
    assert not popup.range_label.isVisible()
    show(popup, ":%s#old/path#new/path#g 3")
    assert "% selects the entire file" in popup.range_label.text()


def test_basic_option_rows_show_effective_values(guide_panel):
    _viewport, _line, popup = guide_panel
    previous = SubstituteSpec("foo", "bar", "/", "gci")
    show(popup, ":s/foo/bar/&gInr", previous)

    assert popup.options_widget.isVisible()
    assert tuple(label.text() for label, _description in popup.option_labels) == tuple(
        flag for flag, _description in SUBSTITUTION_OPTIONS
    )
    assert "Currently applied: In" == popup.effective_label.text()
    assert "no effect with an explicit pattern" in popup.note.text()
    assert "r" not in tuple(label.text() for label, _ in popup.option_labels)
    show(popup, ":s/foo/bar/ggccee")
    assert popup.effective_label.text() == "Currently applied: none"
    assert len(popup.option_labels) == len(SUBSTITUTION_OPTIONS)


def test_default_options_show_only_compact_reference_and_fit_content(guide_panel):
    _viewport, _line, popup = guide_panel
    show(popup, ":s/")
    pattern_width = popup.width()
    show(popup, ":s/foo/bar/")
    for label in (
        popup.description,
        popup.range_label,
        popup.effective_label,
        popup.note,
    ):
        assert not label.isVisible()
    assert popup.width() < 400
    assert popup.width() < pattern_width
    assert popup.height() < 240
    assert popup.scroll_area.verticalScrollBar().maximum() == 0


def test_basic_option_descriptions_match_the_execution_parser():
    described = {flag for flag, description in SUBSTITUTION_OPTIONS if description}
    accepted = set()
    for flag in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ&#":
        try:
            parse_substitute("/a/b/" + flag)
        except ExError:
            continue
        accepted.add(flag)
    assert described == accepted - {"r", "e", "&"}


def test_missing_previous_options_and_literal_unsupported_input(guide_panel):
    _viewport, _line, popup = guide_panel
    show(popup, ":s/foo/bar/&")
    assert "no previous substitution" in popup.note.text()
    popup.set_context(
        SubstituteGuideContext("unsupported", "/", unsupported="<b>literal</b>")
    )
    assert "<b>literal</b>" in popup.description.text()
    assert popup.description.textFormat() == Qt.PlainText
    assert not popup.options_widget.isVisible()
    assert not popup.effective_label.isVisible()


def test_unchanged_stage_reuses_text_and_widgets(guide_panel):
    _viewport, _line, popup = guide_panel
    show(popup, ":s/foo")
    labels = popup.findChildren(QWidget)
    content = popup.header.text(), popup.description.text()
    assert not popup.set_context(scan_substitute_guide(":s/longer", len(":s/longer")))
    assert popup.findChildren(QWidget) == labels
    assert (popup.header.text(), popup.description.text()) == content
    assert popup.set_context(scan_substitute_guide(":s/foo/bar/", len(":s/foo/bar/")))
    assert popup.findChildren(QWidget) == labels


def test_wrapping_and_scrolling_fit_narrow_viewports(guide_panel):
    viewport, line, popup = guide_panel
    show(popup, ":s/foo/bar/gn")
    for width, height in ((160, 140), (600, 500), (20, 20)):
        viewport.resize(width, height)
        popup.update_geometry()
        QCoreApplication.processEvents()
        assert viewport.rect().contains(popup.geometry())
        assert QApplication.focusWidget() is line
    viewport.resize(120, 100)
    popup.update_geometry()
    QCoreApplication.processEvents()
    assert popup.scroll_area.verticalScrollBar().maximum() > 0
    popup.scroll_area.ensureWidgetVisible(popup.option_labels[-1][1])
    QCoreApplication.processEvents()
    assert popup.scroll_area.verticalScrollBar().value() > 0
    for _flag, description in popup.option_labels:
        assert description.wordWrap()


@pytest.mark.parametrize("themed", [False, True])
def test_narrow_guide_wraps_content_inside_scroll_viewport(guide_panel, themed):
    viewport, _line, popup = guide_panel
    if themed:
        viewport.setStyleSheet(APP_STYLESHEET.to_string())
    popup.refresh_appearance(QFont("Courier New", 14))
    show(popup, ":s/foo/bar/gn")
    for width in (160, 600, 240):
        viewport.resize(width, 400)
        popup.update_geometry()
        QCoreApplication.processEvents()
        assert popup.content_widget.width() == popup.scroll_area.viewport().width()
        assert popup.scroll_area.horizontalScrollBar().maximum() == 0
        for label in (popup.description, popup.range_label, popup.note):
            if label.isVisible():
                assert label.height() >= label.heightForWidth(label.width())
        for flag, description in popup.option_labels:
            assert flag.width() >= flag.sizeHint().width()
            assert description.height() >= description.heightForWidth(
                description.width()
            )


def test_font_and_theme_refresh_do_not_repolish_unchanged_help(
    guide_panel, monkeypatch
):
    _viewport, _line, popup = guide_panel
    show(popup, ":s/foo/bar/g")

    class AppearanceObserver(QObject):
        def __init__(self):
            super().__init__(popup)
            self.changes = []

        def eventFilter(self, watched, event):
            if event.type() in (QEvent.StyleChange, QEvent.FontChange):
                self.changes.append(event.type())
            return False

    observer = AppearanceObserver()
    for widget in (popup, *popup.findChildren(QWidget)):
        widget.installEventFilter(observer)
    font = QFont("Courier New", 10)
    for _ in range(3):
        assert not popup.refresh_appearance(font)
    QCoreApplication.processEvents()
    assert observer.changes == []

    font.setPointSize(14)
    assert popup.refresh_appearance(font)
    popup.update_geometry()
    QCoreApplication.processEvents()
    for label in (
        popup.header,
        popup.description,
        popup.range_label,
        popup.effective_label,
    ):
        assert label.font().family() == font.family()
        assert label.font().pointSize() == font.pointSize()
    for flag, explanation in popup.option_labels:
        assert flag.font().family() == font.family()
        assert flag.font().pointSize() == font.pointSize()
        assert explanation.font().family() == font.family()
        assert explanation.font().pointSize() == font.pointSize()
    observer.changes.clear()
    assert not popup.refresh_appearance(font)
    QCoreApplication.processEvents()
    assert observer.changes == []

    monkeypatch.setattr(SpyderPalette, "COLOR_TEXT_1", "#123456")
    assert popup.refresh_appearance(font)
    QCoreApplication.processEvents()
    assert "#123456" in popup.styleSheet()
    assert QEvent.StyleChange in observer.changes
    observer.changes.clear()
    assert not popup.refresh_appearance(font)
    QCoreApplication.processEvents()
    assert observer.changes == []
