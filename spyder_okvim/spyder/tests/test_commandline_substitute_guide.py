"""Substitution guidance shares history's stable input and editor lifetime."""

import gc
import weakref
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt
from qtpy.QtGui import QKeyEvent, QWheelEvent
from qtpy.QtWidgets import QApplication, QWidget
from spyder.config.manager import CONF

from spyder_okvim.spyder.commandline_popup_controller import CommandlinePopupController
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.spyder.substitute_guide import SubstituteGuidePopup
from spyder_okvim.spyder.tests.test_commandline_history_popup import (
    history_popup,
    select_next,
    send_ime,
    show,
    shown,
)
from spyder_okvim.utils.ex_parser import SubstituteSpec, scan_substitute_guide
from spyder_okvim.utils.qtcompat import widget_is_deleted


@pytest.fixture
def guide(history_popup):
    state = history_popup
    previous = CONF.get(CONF_SECTION, "substitute_guide_enabled", True)
    previous_preview = CONF.get(CONF_SECTION, "substitute_preview_enabled", True)
    CONF.set(CONF_SECTION, "substitute_guide_enabled", True)
    CONF.set(CONF_SECTION, "substitute_preview_enabled", False)
    state.widget.apply_settings()
    try:
        yield state
    finally:
        CONF.set(CONF_SECTION, "substitute_guide_enabled", previous)
        CONF.set(CONF_SECTION, "substitute_preview_enabled", previous_preview)
        state.widget.apply_settings()


def guide_shown(state):
    popup = state.controller.guide_popup
    return popup is not None and popup.isVisible()


def assert_stage(state, title):
    assert guide_shown(state)
    assert state.controller.guide_popup.header.text() == title
    assert not shown(state)
    assert state.controller.candidates == []
    assert state.controller.selected_index is None
    assert state.line.hasFocus()


def test_stages_forward_backspace_and_middle_cursor(guide):
    state = guide
    show(state, ":s", ("s/foo/bar/g",))
    state.qtbot.keyClicks(state.line, "/")
    assert_stage(state, "Search pattern")
    popup = state.controller.guide_popup
    state.qtbot.keyClicks(state.line, "foo/")
    assert not guide_shown(state)
    assert not shown(state)
    state.qtbot.keyClicks(state.line, "bar/")
    assert_stage(state, "Substitution options")
    assert state.controller.guide_popup is popup
    state.qtbot.keyPress(state.line, Qt.Key_Backspace)
    assert not guide_shown(state)
    assert not shown(state)
    for _ in range(4):
        state.qtbot.keyPress(state.line, Qt.Key_Backspace)
    assert_stage(state, "Search pattern")
    state.line.setText(":s/foo/bar/g")
    state.line.setCursorPosition(4)
    assert_stage(state, "Search pattern")
    state.line.setCursorPosition(7)
    assert not guide_shown(state)
    assert not shown(state)
    state.line.setCursorPosition(11)
    assert_stage(state, "Substitution options")
    state.line.setCursorPosition(2)
    assert not guide_shown(state)
    state.line.setText(":s")
    assert shown(state)


def test_paste_delete_and_utf16_cursor(guide):
    state = guide
    state.qtbot.keyClicks(state.line, ":")
    send_ime(state, commit="s/😀한글/바꿈/g")
    assert_stage(state, "Substitution options")
    text = state.line.text()
    replacement_start = text.index("/바꿈") + 1
    state.line.setCursorPosition(len(text[:replacement_start].encode("utf-16-le")) // 2)
    assert not guide_shown(state)
    assert not shown(state)
    state.line.setCursorPosition(len(":s/😀한글".encode("utf-16-le")) // 2)
    assert_stage(state, "Search pattern")
    state.qtbot.keyPress(state.line, Qt.Key_Delete)
    assert_stage(state, "Search pattern")
    assert state.line.text() == ":s/😀한글바꿈/g"


def test_clipboard_paste_selects_stage_from_complete_input(guide):
    state = guide
    state.qtbot.keyClicks(state.line, ":")
    clipboard = QApplication.clipboard()
    previous = clipboard.text()
    try:
        clipboard.setText("s#old/path#new/path#g")
        state.line.paste()
        assert state.line.text() == ":s#old/path#new/path#g"
        assert_stage(state, "Substitution options")
    finally:
        clipboard.setText(previous)


@pytest.mark.parametrize("preview_enabled", [False, True])
def test_replacement_stage_has_no_guide_or_history_popup(guide, preview_enabled):
    state = guide
    CONF.set(CONF_SECTION, "substitute_preview_enabled", preview_enabled)
    state.widget.apply_settings()
    state.line.histories["ex"][:] = ["s/alpha/new/g"]
    state.qtbot.keyClicks(state.line, ":s/alpha/")
    assert not guide_shown(state)
    assert not shown(state)
    assert state.controller.candidates == []
    state.qtbot.keyClicks(state.line, "new")
    if preview_enabled:
        state.qtbot.waitUntil(lambda: state.widget.substitute_preview.has_overlay)
    QCoreApplication.processEvents()
    assert not guide_shown(state)
    assert not shown(state)
    assert state.controller.candidates == []
    assert state.line.hasFocus()
    state.qtbot.keyClicks(state.line, "/")
    assert_stage(state, "Substitution options")
    state.line.setCursorPosition(state.line.text().index("new"))
    assert not guide_shown(state)
    assert not shown(state)


def test_guide_is_read_only_and_does_not_search(guide, monkeypatch):
    state = guide
    previous = SubstituteSpec("saved", "value", "/", "g")
    state.status.last_substitute = previous
    search = state.status.search.txt_searched
    document = state.editor.document()
    snapshot = (
        document.revision(),
        document.availableUndoSteps(),
        document.availableRedoSteps(),
        state.editor.toPlainText(),
    )
    histories = {kind: items[:] for kind, items in state.line.histories.items()}
    forbidden = Mock(side_effect=AssertionError("guide attempted execution"))
    monkeypatch.setattr("spyder_okvim.utils.ex_parser.resolve_range", forbidden)
    monkeypatch.setattr(
        "spyder_okvim.spyder.vim_widgets.completion_candidates", forbidden
    )
    state.qtbot.keyClicks(state.line, ":%s/[invalid/long/&g")
    text, cursor = state.line.text(), state.line.cursorPosition()
    for _ in range(3):
        state.controller.sync()
    assert guide_shown(state)
    assert (state.line.text(), state.line.cursorPosition()) == (text, cursor)
    assert (
        document.revision(),
        document.availableUndoSteps(),
        document.availableRedoSteps(),
        state.editor.toPlainText(),
    ) == snapshot
    assert state.line.histories == histories
    assert state.status.last_substitute is previous
    assert state.status.search.txt_searched == search
    forbidden.assert_not_called()


def test_selected_history_cannot_intercept_guide_enter(guide):
    state = guide
    show(state, ":s", ("s/alpha/other/g",))
    select_next(state)
    state.qtbot.keyClicks(state.line, "/alpha/new/")
    assert_stage(state, "Substitution options")
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.editor.toPlainText().startswith("new beta\n")
    assert state.line.text() == ""
    assert state.status.sub_mode is None
    assert not guide_shown(state)
    assert state.line.histories["ex"][-1] == "s/alpha/new/"
    state.qtbot.keyClicks(state.line, "u")
    assert state.editor.toPlainText().startswith("alpha beta\n")


@pytest.mark.parametrize("command", [":s/alpha", ":s/alpha/"])
def test_unclosed_substitutions_keep_deletion_execution(guide, command):
    state = guide
    state.qtbot.keyClicks(state.line, command)
    assert guide_shown(state) is (command == ":s/alpha")
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.editor.toPlainText().startswith(" beta\n")
    assert not guide_shown(state)


@pytest.mark.parametrize("key", [Qt.Key_Tab, Qt.Key_Backtab])
def test_completion_suppression_does_not_hide_guide(guide, key):
    state = guide
    state.qtbot.keyClicks(state.line, ":s/alpha/new/")
    text = state.line.text()
    state.qtbot.keyPress(state.line, key)
    assert state.line.text() == text
    assert_stage(state, "Substitution options")
    state.line.setText(":s")
    state.line.histories["ex"][:] = ["s/old/new/"]
    state.controller.sync()
    assert not guide_shown(state)
    assert not shown(state)


def test_up_down_restore_draft_and_preserve_history_suppression(guide):
    state = guide
    state.line.histories["ex"][:] = ["s/alpha/new/g"]
    state.qtbot.keyClicks(state.line, ":s")
    state.qtbot.keyPress(state.line, Qt.Key_Up)
    assert_stage(state, "Substitution options")
    assert state.line.text() == ":s/alpha/new/g"
    state.qtbot.keyPress(state.line, Qt.Key_Down)
    assert state.line.text() == ":s"
    assert not shown(state)
    state.qtbot.keyClicks(state.line, "/")
    assert_stage(state, "Search pattern")


def test_accepting_substitute_history_shows_guide(guide):
    state = guide
    show(state, ":s", ("s/alpha/new/g",))
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.line.text() == ":s/alpha/new/g"
    assert_stage(state, "Substitution options")
    assert state.editor.toPlainText().startswith("alpha beta")
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.editor.toPlainText().startswith("new beta")


def test_guide_keeps_control_keys_on_default_path(guide, monkeypatch):
    state = guide
    fallback = Mock()
    monkeypatch.setitem(state.line.dispatcher, Qt.Key_P, fallback)
    state.qtbot.keyClicks(state.line, ":s/alpha/new/")
    for key in (Qt.Key_N, Qt.Key_P, Qt.Key_Return):
        modifiers = Qt.NoModifier if key == Qt.Key_Return else Qt.ControlModifier
        event = QKeyEvent(QEvent.KeyPress, key, modifiers)
        assert state.controller.key_action(event) is None
    state.qtbot.keyPress(state.line, Qt.Key_P, Qt.ControlModifier)
    fallback.assert_called_once_with()
    assert state.line.text() == ":s/alpha/new/"
    assert_stage(state, "Substitution options")


def test_ime_preedit_hides_and_commit_restores_current_stage(guide):
    state = guide
    show(state, ":s", ("s/old/new/",))
    select_next(state)
    send_ime(state, preedit="ㅎ")
    assert not shown(state)
    assert not guide_shown(state)
    send_ime(state, commit="/한", preedit="ㄱ")
    assert not guide_shown(state)
    send_ime(state, commit="글/")
    assert state.line.text() == ":s/한글/"
    assert not guide_shown(state)
    assert not shown(state)
    send_ime(state, commit="새글/")
    assert_stage(state, "Substitution options")


@pytest.mark.parametrize("suppression", ["recording", "playback", "dot"])
def test_macro_and_dot_hide_guide(guide, suppression):
    state = guide
    if suppression == "recording":
        state.status.manager_macro.start_record("a")
    elif suppression == "playback":
        state.widget._macro_generation = 1
    else:
        state.status.running_dot_cmd = True
    state.qtbot.keyClicks(state.line, ":s/alpha/new/")
    assert not guide_shown(state)
    assert not shown(state)


def test_confirmation_escape_focus_and_deactivation_hide_guide(guide):
    state = guide
    state.qtbot.keyClicks(state.line, ":s/alpha/new/c")
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.status.substitute_confirm is not None
    assert not guide_shown(state)
    state.qtbot.keyPress(state.line, Qt.Key_Escape)
    state.qtbot.keyClicks(state.line, ":s/")
    assert guide_shown(state)
    QCoreApplication.sendEvent(state.main, QEvent(QEvent.WindowDeactivate))
    assert not guide_shown(state)
    state.line.esc_pressed()
    state.qtbot.keyClicks(state.line, ":s/")
    assert guide_shown(state)
    state.editor.setFocus()
    assert not guide_shown(state)


@pytest.mark.parametrize("history_enabled", [False, True])
@pytest.mark.parametrize("guide_enabled", [False, True])
def test_independent_settings_and_immediate_toggling(
    guide, history_enabled, guide_enabled
):
    state = guide
    state.line.histories["ex"][:] = ["s/alpha/new/g"]
    state.qtbot.keyClicks(state.line, ":s/")
    CONF.set(CONF_SECTION, "commandline_history_enabled", history_enabled)
    CONF.set(CONF_SECTION, "substitute_guide_enabled", guide_enabled)
    state.widget.apply_settings()
    assert guide_shown(state) is guide_enabled
    assert shown(state) is (history_enabled and not guide_enabled)
    state.controller.suppress_history()
    CONF.set(CONF_SECTION, "substitute_guide_enabled", not guide_enabled)
    state.widget.apply_settings()
    assert guide_shown(state) is (not guide_enabled)
    assert not shown(state)


def test_count_comment_unsupported_and_effective_options(guide):
    state = guide
    state.status.last_substitute = SubstituteSpec("old", "new", "/", "gI")
    state.qtbot.keyClicks(state.line, ':s/alpha/new/&ginc 3 "comment')
    assert not guide_shown(state)
    state.line.setCursorPosition(state.line.text().index("3") + 1)
    assert_stage(state, "Line count")
    state.line.setCursorPosition(state.line.text().index(" 3"))
    assert_stage(state, "Substitution options")
    assert (
        state.controller.guide_popup.effective_label.text() == "Currently applied: in"
    )
    state.line.setText(":s/alpha/new/p")
    assert_stage(state, "Unsupported substitution option")


def test_same_stage_reuses_layout_and_font_changes_refresh(guide, monkeypatch):
    state = guide
    state.qtbot.keyClicks(state.line, ":s/")
    popup = state.controller.guide_popup
    geometry = Mock(wraps=popup.update_geometry)
    monkeypatch.setattr(popup, "update_geometry", geometry)
    state.qtbot.keyClicks(state.line, "alpha")
    state.controller.sync()
    geometry.assert_not_called()
    previous_font = state.line.font()
    font = state.line.font()
    font.setPointSize(font.pointSize() + 2)
    try:
        state.line.setFont(font)
        assert popup.header.font() == font
        geometry.assert_called_once_with()
    finally:
        state.line.setFont(previous_font)


def test_nested_input_and_cleanup_release_both_popups(guide):
    state = guide
    state.line.histories["ex"][:] = ["s/alpha/new/g"]
    state.qtbot.keyClicks(state.line, ":s")
    controller = type(state.controller)(state.widget)
    controller.set_editor(state.editor)
    controller.sync()
    history = controller.popup
    assert history.isVisible()
    state.qtbot.keyClicks(state.line, "/")
    popup = controller.guide_popup
    assert popup.isVisible()
    with state.widget.input_processing():
        assert not popup.isVisible()
        state.line.setText(":s/alpha/new/")
        QCoreApplication.processEvents()
        assert not popup.isVisible()
    assert popup.isVisible()
    assert popup.header.text() == "Substitution options"
    controller.cleanup()
    controller.cleanup()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert widget_is_deleted(history)
    assert widget_is_deleted(popup)
    assert controller.popup is None
    assert controller.guide_popup is None
    state.widget.sig_input_finished.emit()
    assert controller.guide_popup is None
    controller.deleteLater()


def test_wheel_over_guide_scrolls_help_without_changing_input(guide, monkeypatch):
    state = guide
    state.qtbot.keyClicks(state.line, ":s/")
    popup = state.controller.guide_popup
    monkeypatch.setattr(popup, "MAX_WIDTH", 90)
    popup.update_geometry()
    QCoreApplication.processEvents()
    scrollbar = popup.scroll_area.verticalScrollBar()
    assert scrollbar.maximum() > 0
    viewport = state.editor.viewport()
    document = state.editor.document()
    snapshot = (
        state.line.text(),
        state.line.cursorPosition(),
        state.editor.toPlainText(),
        document.revision(),
        document.availableUndoSteps(),
    )

    def wheel(position):
        event = QWheelEvent(
            QPointF(position),
            QPointF(viewport.mapToGlobal(position)),
            QPoint(),
            QPoint(0, -120),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.NoScrollPhase,
            False,
        )
        QCoreApplication.sendEvent(viewport, event)

    wheel(popup.geometry().center())
    assert scrollbar.value() > 0
    value = scrollbar.value()
    outside = QPoint(viewport.width() - 1, 0)
    assert not popup.geometry().contains(outside)
    wheel(outside)
    assert scrollbar.value() == value
    # Qt may ignore an end-of-range wheel and propagate it to the viewport.
    # The controller must not recursively forward the same event.
    scrollbar.setValue(scrollbar.maximum())
    wheel(popup.geometry().center())
    assert scrollbar.value() == scrollbar.maximum()
    assert state.line.hasFocus()
    assert (
        state.line.text(),
        state.line.cursorPosition(),
        state.editor.toPlainText(),
        document.revision(),
        document.availableUndoSteps(),
    ) == snapshot


def test_yank_picker_focus_loss_hides_the_guide(guide):
    state = guide
    state.status.yank_history.record("content", "charwise")
    state.qtbot.keyClicks(state.line, ":s/alpha/new/")
    popup = state.controller.guide_popup
    assert popup.isVisible()
    text, cursor = state.line.text(), state.line.cursorPosition()
    try:
        state.widget.show_yank_history()
        QCoreApplication.processEvents()
        assert not state.line.hasFocus()
        assert not popup.isVisible()
        assert not shown(state)
        assert state.controller.candidates == []
        assert state.controller.selected_index is None
        assert (state.line.text(), state.line.cursorPosition()) == (text, cursor)
    finally:
        state.widget.cancel_yank_picker()


def test_reactivating_window_restores_guide(guide):
    state = guide
    state.qtbot.keyClicks(state.line, ":s/alpha/new/")
    assert guide_shown(state)
    QCoreApplication.sendEvent(state.main, QEvent(QEvent.WindowDeactivate))
    assert not guide_shown(state)
    assert state.line.text() == ":s/alpha/new/"
    QCoreApplication.sendEvent(state.main, QEvent(QEvent.WindowActivate))
    assert guide_shown(state)


def test_layout_cache_does_not_retain_closed_guide_windows(guide):
    """A cached guide layout must not keep its former Qt parent alive."""
    viewport = QWidget()
    viewport.resize(400, 300)
    popup = SubstituteGuidePopup(viewport)
    popup.set_context(scan_substitute_guide(":s/foo/bar/", len(":s/foo/bar/")))
    viewport.show()
    popup.show()
    state = SimpleNamespace(
        _viewport=weakref.ref(viewport), guide_popup=popup, _layout_signature=None
    )
    CommandlinePopupController._layout_guide(state)
    popup_ref, viewport_ref = weakref.ref(popup), weakref.ref(viewport)
    state.guide_popup = None
    viewport.close()
    viewport.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    del popup, viewport
    gc.collect()
    assert popup_ref() is None
    assert viewport_ref() is None


def test_host_window_change_ends_preview_session(guide):
    state = guide
    state.qtbot.keyClicks(state.line, ":s/foo/bar/")
    preview = state.widget.substitute_preview
    assert preview._session is state.status.sub_mode
    controller = state.controller
    previous = state.editor.window()
    replacement = QWidget()
    state.qtbot.addWidget(replacement)
    try:
        controller._set_window(replacement)
        assert preview._session is None
        assert state.status.sub_mode is not None
    finally:
        controller._set_window(previous)
