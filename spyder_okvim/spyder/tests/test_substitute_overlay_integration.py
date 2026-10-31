"""Editor overlays share the substitute input and document lifetime."""

# Standard Libraries
from dataclasses import replace
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QApplication
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from tests.commandline_support import (
    assert_no_replacement_panel,
    enter_command,
)
from tests.commandline_support import history_popup as history_popup
from tests.commandline_support import preview as preview
from tests.commandline_support import result
from tests.qt_support import reset_vim_state

# ruff: noqa: F811 - imported pytest fixtures are injected by parameter name


def overlay_rows(state):
    """Wait for source calculation and inspect the painter's immutable rows."""
    value = result(state)
    assert state.preview.overlay.rows == value.rows
    return value.rows


def assert_overlay_cleared(state):
    overlay = state.preview.overlay
    assert overlay.rows == ()
    assert overlay.widget is None or not overlay.widget.isVisible()


def test_closed_pattern_draws_latest_replacement_over_unchanged_source(preview):
    state = preview
    enter_command(state, ":%s/foo")
    assert result(state).rows == ()
    assert_overlay_cleared(state)

    enter_command(state, ":%s/foo/")
    assert [(row.block_number, row.after) for row in overlay_rows(state)] == [
        (1, " x foo x foo")
    ]
    enter_command(state, ":%s/foo/<tag>&/g")
    assert [row.after for row in overlay_rows(state)] == [
        "<tag>foo x <tag>foo x <tag>foo"
    ]
    assert state.preview.overlay.widget.parentWidget() is state.editor.viewport()
    assert state.preview.overlay.widget.isVisible()
    assert state.preview.overlay.widget.testAttribute(Qt.WA_TransparentForMouseEvents)
    assert state.editor.toPlainText() == "alpha beta\nfoo x foo x foo\nlast line"
    assert state.line.hasFocus()
    assert_no_replacement_panel(state)

    enter_command(state, ":%s/foo")
    assert result(state).rows == ()
    assert_overlay_cleared(state)


def test_paste_and_history_recall_draw_without_executing_or_recording(preview):
    state = preview
    state.line.histories["ex"][:] = ["%s/foo/이전/g"]
    state.qtbot.keyClicks(state.line, ":")
    state.qtbot.keyPress(state.line, Qt.Key_Up)
    assert [row.after for row in overlay_rows(state)] == ["이전 x 이전 x 이전"]
    assert state.line.histories["ex"] == ["%s/foo/이전/g"]
    clipboard = QApplication.clipboard()
    previous_clipboard = clipboard.text()
    try:
        state.line.selectAll()
        clipboard.setText(":%s/foo/<tag>😀/g")
        state.line.paste()
        assert [row.after for row in overlay_rows(state)] == [
            "<tag>😀 x <tag>😀 x <tag>😀"
        ]
        assert state.editor.toPlainText() == "alpha beta\nfoo x foo x foo\nlast line"
        assert state.line.histories["ex"] == ["%s/foo/이전/g"]
        assert state.line.hasFocus()
    finally:
        clipboard.setText(previous_clipboard)


def test_noop_replacement_removes_prior_drawn_result(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    assert overlay_rows(state)
    enter_command(state, ":%s/foo/foo/g")
    value = result(state)
    assert value.match_count == 3
    assert value.rows == ()
    assert_overlay_cleared(state)
    assert state.editor.toPlainText() == "alpha beta\nfoo x foo x foo\nlast line"


def test_guide_and_overlay_coexist_across_fields(preview):
    state = preview
    assert CONF.get(CONF_SECTION, "substitute_guide_enabled") is True
    enter_command(state, ":%s/foo")
    result(state)
    assert state.controller.guide_popup.isVisible()
    enter_command(state, ":%s/foo/bar")
    assert overlay_rows(state)
    assert state.controller.guide_popup.isVisible()
    assert state.controller.guide_popup.header.text() == "Replacement text"
    assert CONF.get(CONF_SECTION, "substitute_guide_enabled") is True
    enter_command(state, ":%s/foo")
    result(state)
    assert_overlay_cleared(state)
    assert state.controller.guide_popup.isVisible()
    assert CONF.get(CONF_SECTION, "substitute_guide_enabled") is True


@pytest.mark.parametrize("input_method", ["typing", "paste"])
def test_final_delimiter_shows_options_before_and_after_preview(preview, input_method):
    state = preview
    enter_command(state, ":%s/foo/bar")
    assert overlay_rows(state)
    source = state.editor.toPlainText()
    state.preview._timer.setInterval(150)
    if input_method == "typing":
        state.qtbot.keyClicks(state.line, "/")
    else:
        clipboard = QApplication.clipboard()
        previous_clipboard = clipboard.text()
        try:
            clipboard.setText("/")
            state.line.paste()
        finally:
            clipboard.setText(previous_clipboard)

    assert state.line.text() == ":%s/foo/bar/"
    assert state.preview._timer.isActive()
    popup = state.controller.guide_popup
    assert popup is not None and popup.isVisible()
    assert popup.header.text() == "Substitution options"
    assert popup.options_widget.isVisible()
    assert overlay_rows(state)
    assert popup.isVisible()
    assert state.preview.overlay.widget.isVisible()
    assert state.line.hasFocus()
    assert state.editor.toPlainText() == source

    state.qtbot.keyPress(state.line, Qt.Key_Backspace)
    assert popup.isVisible()
    assert popup.header.text() == "Replacement text"
    state.qtbot.keyClicks(state.line, "/g")
    assert popup.isVisible()
    assert popup.header.text() == "Substitution options"
    assert popup.effective_label.text() == "Currently applied: g"
    assert overlay_rows(state)
    assert popup.isVisible()


@pytest.mark.parametrize(
    "tail, title",
    [
        ("g 3", "Line count"),
        ("unsupported", "Unsupported substitution option"),
    ],
)
def test_trailing_help_remains_visible_with_preview(preview, tail, title):
    state = preview
    enter_command(state, ":%s/foo/bar/")
    assert overlay_rows(state)
    state.qtbot.keyClicks(state.line, tail)
    popup = state.controller.guide_popup
    assert popup is not None and popup.isVisible()
    assert popup.header.text() == title
    QCoreApplication.processEvents()
    assert popup.isVisible()
    assert state.line.hasFocus()


def test_guide_and_candidates_show_while_preview_waits_for_debounce(preview):
    state = preview
    enter_command(state, ":%s/foo")
    result(state)
    assert state.controller.guide_popup.isVisible()
    state.preview._timer.setInterval(150)
    state.line.histories["ex"][:] = ["%s/foo/bar/g"]
    enter_command(state, ":%s/foo/")
    assert state.preview._timer.isActive()
    assert state.preview.result is None
    assert state.controller.guide_popup.isVisible()
    assert state.controller.popup.isVisible()
    assert state.controller.guide_popup.header.text() == "Replacement text"
    enter_command(state, ":%s/foo")
    assert state.controller.guide_popup.isVisible()
    assert CONF.get(CONF_SECTION, "substitute_guide_enabled") is True


@pytest.mark.parametrize("action", ["escape", "control_c", "off", "external", "reset"])
def test_cancellation_always_removes_drawn_replacement(preview, action):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    assert overlay_rows(state)
    if action == "escape":
        state.qtbot.keyPress(state.line, Qt.Key_Escape)
    elif action == "control_c":
        state.qtbot.keyPress(state.line, Qt.Key_C, Qt.ControlModifier)
    elif action == "off":
        CONF.set(CONF_SECTION, "substitute_preview_enabled", False)
        state.widget.apply_settings()
    elif action == "external":
        cursor = QTextCursor(state.editor.document())
        cursor.insertText("external ")
    else:
        reset_vim_state(state.status)
    QCoreApplication.processEvents()
    assert_overlay_cleared(state)
    assert state.preview.result is None


def test_enter_applies_replacement_once_and_one_undo_restores_source(
    preview, monkeypatch
):
    state = preview
    enter_command(state, ":%s/foo/한글😀/g")
    rows = overlay_rows(state)
    assert [row.after for row in rows] == ["한글😀 x 한글😀 x 한글😀"]
    source = state.editor.toPlainText()
    execute = Mock(wraps=state.status.sub_mode.substitute)
    monkeypatch.setattr(state.status.sub_mode, "substitute", execute)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    execute.assert_called_once()
    assert (
        state.editor.toPlainText() == "alpha beta\n한글😀 x 한글😀 x 한글😀\nlast line"
    )
    assert_overlay_cleared(state)
    state.qtbot.keyClicks(state.line, "u")
    assert state.editor.toPlainText() == source


def test_count_only_keeps_candidate_highlighting_without_replacement_overlay(preview):
    state = preview
    enter_command(state, r":%s/foo/\u/gnc")
    counted = result(state)
    assert counted.count_only and not counted.confirm
    assert counted.match_count == 3
    assert counted.rows == ()
    assert_overlay_cleared(state)


def test_read_only_document_draws_preview_but_enter_keeps_source(preview):
    state = preview
    state.editor.setReadOnly(True)
    enter_command(state, ":%s/foo/bar/g")
    assert result(state).read_only
    assert overlay_rows(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert "read-only" in state.status.msg_label.text().lower()
    assert_overlay_cleared(state)
    assert state.editor.toPlainText() == "alpha beta\nfoo x foo x foo\nlast line"


def test_confirmation_releases_overlay_before_first_prompt(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/gc")
    assert result(state).confirm
    assert overlay_rows(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.status.substitute_confirm is not None
    assert_overlay_cleared(state)
    assert state.editor.toPlainText() == "alpha beta\nfoo x foo x foo\nlast line"
    state.qtbot.keyClicks(state.line, "a")
    assert state.editor.toPlainText() == "alpha beta\nbar x bar x bar\nlast line"


def test_scrolling_recomputes_only_new_visible_result_rows(preview):
    state = preview
    state.editor.set_text("\n".join(f"foo {index}" for index in range(300)))
    state.status.cursor.set_cursor_pos(0)
    state.editor.verticalScrollBar().setValue(0)
    enter_command(state, ":%s/foo/bar/g")
    first = overlay_rows(state)
    assert first and first[0].block_number == 0
    state.editor.verticalScrollBar().setValue(
        state.editor.verticalScrollBar().maximum()
    )
    state.qtbot.waitUntil(
        lambda: bool(state.preview.result and state.preview.result.rows)
        and any(row.block_number == 299 for row in state.preview.result.rows)
    )
    last = overlay_rows(state)
    assert min(row.block_number for row in last) > max(
        row.block_number for row in first
    )
    assert all(row.after.startswith("bar ") for row in last)
    assert state.editor.toPlainText().startswith("foo 0\n")
    assert state.line.hasFocus()


def test_folding_refreshes_newly_visible_results_without_editing_document(preview):
    state = preview
    state.editor.set_text("\n".join(f"foo {index}" for index in range(100)))
    state.status.cursor.set_cursor_pos(0)
    state.editor.verticalScrollBar().setValue(0)
    enter_command(state, ":%s/foo/bar/g")
    first = overlay_rows(state)
    previous_last = max(row.block_number for row in first)
    document = state.editor.document()
    cursor = state.editor.textCursor()
    snapshot = (
        state.editor.toPlainText(),
        document.revision(),
        document.isModified(),
        document.availableUndoSteps(),
        document.availableRedoSteps(),
        cursor.position(),
        cursor.anchor(),
    )
    folded = [document.findBlockByNumber(number) for number in range(1, 11)]
    try:
        for block in folded:
            block.setVisible(False)
            block.setLineCount(0)
        document.markContentsDirty(0, document.characterCount())
        state.editor.viewport().update()
        state.editor.updateRequest.emit(state.editor.viewport().rect(), 0)
        state.qtbot.waitUntil(
            lambda: bool(state.preview.result and state.preview.result.rows)
            and max(row.block_number for row in state.preview.result.rows)
            > previous_last
        )
        assert state.editor.verticalScrollBar().value() == 0
        assert all(
            row.after == f"bar {row.block_number}" for row in overlay_rows(state)
        )
        cursor = state.editor.textCursor()
        assert (
            state.editor.toPlainText(),
            document.revision(),
            document.isModified(),
            document.availableUndoSteps(),
            document.availableRedoSteps(),
            cursor.position(),
            cursor.anchor(),
        ) == snapshot
    finally:
        for block in folded:
            block.setVisible(True)
            block.setLineCount(1)
        document.markContentsDirty(0, document.characterCount())
        state.editor.viewport().update()


def test_font_and_palette_refresh_do_not_recompile_current_expression(
    preview, monkeypatch
):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    previous = overlay_rows(state)
    prepare = Mock(side_effect=AssertionError("appearance recompiled preview"))
    monkeypatch.setattr(
        "spyder_okvim.spyder.substitute_preview.prepare_substitution", prepare
    )
    font = state.editor.font()
    changed_font = state.editor.font()
    changed_font.setPointSize(changed_font.pointSize() + 1)
    try:
        state.editor.setFont(changed_font)
        state.preview.overlay.refresh_geometry()
        state.editor.viewport().update()
        QCoreApplication.sendEvent(
            state.editor.viewport(), QEvent(QEvent.PaletteChange)
        )
        QCoreApplication.processEvents()
        assert state.preview.overlay.rows == previous
        prepare.assert_not_called()
    finally:
        state.editor.setFont(font)


def test_output_budget_keeps_source_visible_when_replacement_cannot_be_drawn(preview):
    state = preview
    state.preview.limits = replace(state.preview.limits, max_output_chars=8)
    enter_command(state, ":%s/foo/" + "replacement" * 50 + "/g")
    limited = result(state)
    assert limited.match_count == 3
    assert limited.output_truncated
    assert limited.rows == ()
    assert limited.omitted_blocks == (1,)
    assert state.preview.overlay.rows == ()
    assert state.preview.overlay.widget.isVisible()
    assert state.editor.toPlainText() == "alpha beta\nfoo x foo x foo\nlast line"
    assert state.editor.get_extra_selections("vim_substitute_preview")


def test_visible_output_limit_marks_omitted_source_lines(preview):
    state = preview
    state.editor.set_text("foo\nfoo\nfoo")
    state.preview.limits = replace(state.preview.limits, max_preview_lines=1)
    enter_command(state, ":%s/foo/bar/g")
    value = result(state)
    assert [(row.block_number, row.after) for row in value.rows] == [(0, "bar")]
    assert value.output_truncated
    assert value.omitted_blocks
    assert 1 in value.omitted_blocks
    assert state.preview.overlay.widget.isVisible()
    assert state.editor.toPlainText() == "foo\nfoo\nfoo"


@pytest.mark.parametrize("command", [":%s/foo", ":%s/foo/bar/gn"])
def test_visible_result_limit_does_not_create_overlay_for_search_or_count(
    preview, command
):
    state = preview
    state.editor.set_text("foo\nfoo\nfoo")
    state.preview.limits = replace(state.preview.limits, max_preview_lines=1)
    enter_command(state, command)
    value = result(state)
    assert value.match_count == 3
    assert value.rows == ()
    assert not value.output_truncated
    assert not value.omitted_blocks
    assert_overlay_cleared(state)
