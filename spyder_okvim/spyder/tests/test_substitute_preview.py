"""Incremental substitution preserves editing state and rejects stale work."""

# Standard Libraries
from dataclasses import replace
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QFocusEvent, QTextCursor, QTextFormat
from qtpy.QtWidgets import QApplication, QPlainTextEdit
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.spyder.substitute_preview import SubstitutePreviewController
from spyder_okvim.utils.ex_parser import SubstituteSpec
from tests.commandline_support import (
    assert_no_replacement_panel,
    enter_command,
)
from tests.commandline_support import history_popup as history_popup
from tests.commandline_support import preview as preview
from tests.commandline_support import result, select_next, selections, send_ime, shown
from tests.qt_support import reset_vim_state


def test_pattern_then_replacement_and_backspace_clear_stale_results(preview):
    state = preview
    enter_command(state, ":%s/")
    QCoreApplication.processEvents()
    assert not selections(state)
    assert_no_replacement_panel(state)

    enter_command(state, ":%s/fo")
    assert result(state).match_count == 1
    assert len(selections(state)) == 1
    assert_no_replacement_panel(state)

    enter_command(state, ":%s/foo/")
    assert result(state).match_count == 1
    assert_no_replacement_panel(state)

    enter_command(state, ":%s/foo/bar/g")
    assert result(state).match_count == 3
    assert len(selections(state)) == 3

    enter_command(state, ":%s/foo")
    assert result(state).match_count == 1
    assert_no_replacement_panel(state)
    assert state.editor.toPlainText() == "alpha beta\nfoo x foo x foo\nlast line"


def test_only_closed_empty_pattern_reuses_previous_search(preview):
    state = preview
    state.status.search.search("foo")
    enter_command(state, ":%s/")
    QCoreApplication.processEvents()
    assert state.preview.result is None
    assert not selections(state)

    enter_command(state, ":%s//bar/g")
    assert result(state).match_count == 3
    assert [row.after for row in state.preview.overlay.rows] == ["bar x bar x bar"]

    state.status.search.txt_searched = ""
    enter_command(state, ":%s//new/g")
    QCoreApplication.processEvents()
    assert state.preview.result is None
    assert not selections(state)


def test_preview_and_cancel_preserve_document_and_confirmed_records(preview):
    state = preview
    search = state.status.search
    search.search("alpha", ignorecase=False, forward=False)
    search.clear_highlights()
    state.status.last_substitute = SubstituteSpec("saved", "value", "/", "g")
    state.status.register_dict['"'].content = "register value"
    state.status.jump_list.push("saved.py", 8)
    state.status.dot_cmd.cmd = "dd"
    state.qtbot.keyClicks(state.line, ":")
    document = state.editor.document()
    document.setModified(False)

    def snapshot():
        cursor = state.editor.textCursor()
        return (
            state.editor.toPlainText(),
            document.revision(),
            document.isModified(),
            document.availableUndoSteps(),
            document.availableRedoSteps(),
            cursor.position(),
            cursor.anchor(),
            state.editor.verticalScrollBar().value(),
            state.editor.horizontalScrollBar().value(),
            search.snapshot(),
            state.status.last_substitute,
            tuple(
                (key, item.content, item.type)
                for key, item in state.status.register_dict.items()
            ),
            tuple((jump.file, jump.pos) for jump in state.status.jump_list.jumps),
            state.status.jump_list.index,
            state.status.dot_cmd.to_cmd_string(1, ""),
            {kind: items[:] for kind, items in state.line.histories.items()},
        )

    original = snapshot()
    enter_command(state, ":%s/foo/<tag>&/g")
    assert result(state).match_count == 3
    assert snapshot() == original
    assert_no_replacement_panel(state)
    assert state.line.hasFocus()
    state.qtbot.keyPress(state.line, Qt.Key_Escape)
    assert snapshot() == original
    assert state.preview.result is None
    assert not selections(state)
    assert_no_replacement_panel(state)


def test_enter_before_debounce_executes_once_and_keeps_single_undo(
    preview, monkeypatch
):
    state = preview
    state.preview._timer.setInterval(150)
    enter_command(state, ":%s/foo/bar/g")
    assert state.preview._timer.isActive()
    executor = state.status.sub_mode
    substitute = Mock(wraps=executor.substitute)
    monkeypatch.setattr(executor, "substitute", substitute)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    substitute.assert_called_once()
    assert state.editor.toPlainText() == "alpha beta\nbar x bar x bar\nlast line"
    assert state.line.histories["ex"] == ["%s/foo/bar/g"]
    assert state.preview.result is None
    assert not state.preview._timer.isActive()
    assert not selections(state)
    state.qtbot.keyClicks(state.line, "u")
    assert state.editor.toPlainText() == "alpha beta\nfoo x foo x foo\nlast line"


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("command", [":%s/foo/bar/g", ":s"])
def test_control_c_cancels_substitute_input_and_existing_search(
    preview, enabled, command
):
    state = preview
    state.status.search.search("alpha")
    assert state.editor.get_extra_selections("vim_search")
    CONF.set(CONF_SECTION, "substitute_preview_enabled", enabled)
    state.widget.apply_settings()
    enter_command(state, command)
    if enabled and command != ":s":
        result(state)
    state.qtbot.keyPress(state.line, Qt.Key_C, Qt.ControlModifier)
    assert state.line.text() == ""
    assert state.status.sub_mode is None
    assert state.preview.result is None
    assert not selections(state)
    assert not state.editor.get_extra_selections("vim_search")
    assert not state.line.histories["ex"]


def test_explicit_delimiter_releases_history_selection_before_enter(preview):
    state = preview
    CONF.set(CONF_SECTION, "substitute_guide_enabled", False)
    state.widget.apply_settings()
    state.line.histories["ex"][:] = ["s/alpha/unwanted/"]
    enter_command(state, ":s")
    assert shown(state)
    select_next(state)
    assert state.controller.selected_index is not None
    state.qtbot.keyClicks(state.line, "/alpha/wanted/")
    assert not shown(state)
    assert state.controller.selected_index is None
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.editor.toPlainText().startswith("wanted beta\n")
    assert state.line.text() == ""


def test_external_edit_ends_session_but_enter_uses_latest_document(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    result(state)
    cursor = QTextCursor(state.editor.document())
    cursor.movePosition(QTextCursor.End)
    cursor.insertText(" foo")
    assert state.preview.result is None
    assert not selections(state)
    assert_no_replacement_panel(state)
    state.preview.sync()
    QCoreApplication.processEvents()
    assert state.preview.result is None
    assert not state.preview._timer.isActive()
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.editor.toPlainText().endswith("last line bar")


def test_setting_off_clears_immediately_and_on_reuses_live_session(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    assert result(state).match_count == 3
    CONF.set(CONF_SECTION, "substitute_preview_enabled", False)
    state.widget.apply_settings()
    assert state.preview.result is None
    assert not selections(state)
    assert_no_replacement_panel(state)
    CONF.set(CONF_SECTION, "substitute_preview_enabled", True)
    state.widget.apply_settings()
    assert result(state).match_count == 3
    assert state.line.text() == ":%s/foo/bar/g"


def test_window_suspend_restores_only_unchanged_document(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    result(state)
    QCoreApplication.sendEvent(state.main, QEvent(QEvent.WindowDeactivate))
    assert state.preview.result is None
    assert not selections(state)
    QCoreApplication.sendEvent(state.main, QEvent(QEvent.WindowActivate))
    assert result(state).match_count == 3
    QCoreApplication.sendEvent(state.main, QEvent(QEvent.WindowDeactivate))
    cursor = QTextCursor(state.editor.document())
    cursor.insertText("changed ")
    QCoreApplication.sendEvent(state.main, QEvent(QEvent.WindowActivate))
    QCoreApplication.processEvents()
    assert state.preview.result is None
    assert not state.preview._timer.isActive()


def test_ime_preedit_suppresses_results_and_commit_refreshes(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    result(state)
    send_ime(state, preedit="한")
    assert state.preview.result is None
    assert not selections(state)
    send_ime(state)
    assert result(state).match_count == 3


def test_commandline_cursor_movement_keeps_whole_command_result(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    previous = result(state)
    state.line.setCursorPosition(4)
    QCoreApplication.processEvents()
    assert state.preview.result is previous
    assert not state.preview._timer.isActive()
    assert len(selections(state)) == 3


@pytest.mark.parametrize(
    "command", [":%s/[invalid/x/g", ":%s/foo/bar/unsupported", ":w"]
)
def test_invalid_or_other_command_discards_old_results(preview, command):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    result(state)
    enter_command(state, command)
    state.qtbot.waitUntil(lambda: not state.preview._timer.isActive())
    assert state.preview.result is None
    assert not selections(state)
    assert_no_replacement_panel(state)


def test_read_only_preview_and_count_only_ignore_replacement_expansion(preview):
    state = preview
    state.editor.setReadOnly(True)
    enter_command(state, ":%s/foo/bar/g")
    assert result(state).read_only
    enter_command(state, r":%s/foo/\u/gn")
    counted = result(state)
    assert counted.count_only
    assert counted.match_count == 3
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.editor.toPlainText() == "alpha beta\nfoo x foo x foo\nlast line"


def test_reset_invalidates_debounce_before_processing_queued_events(preview):
    state = preview
    state.preview._timer.setInterval(150)
    enter_command(state, ":%s/foo/bar/g")
    assert state.preview._timer.isActive()
    reset_vim_state(state.status)
    assert not state.preview._timer.isActive()
    assert not state.preview._chunk_timer.isActive()
    assert state.preview.result is None
    assert not selections(state)


def test_highlight_scan_limit_does_not_limit_enter_execution(preview):
    state = preview
    state.editor.set_text("foo\nfoo\nfoo\nfoo")
    state.status.cursor.set_cursor_pos(0)
    state.preview.limits = replace(state.preview.limits, max_lines=2)
    enter_command(state, ":%s/foo/bar/g")
    scanned = result(state)
    assert scanned.partial
    assert scanned.match_count == 2
    assert scanned.scanned_lines == 2
    assert "line limit" in scanned.reasons
    assert len(scanned.spans) == 2
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.editor.toPlainText() == "bar\nbar\nbar\nbar"


@pytest.mark.parametrize("suppression", ["recording", "dot", "playback"])
def test_macro_and_dot_never_calculate_or_display(preview, monkeypatch, suppression):
    state = preview
    if suppression == "recording":
        state.status.manager_macro.start_record("a")
    elif suppression == "dot":
        state.status.running_dot_cmd = True
    else:
        monkeypatch.setattr(
            type(state.widget), "is_playing_macro", property(lambda _: True)
        )
    enter_command(state, ":%s/foo/bar/g")
    QCoreApplication.processEvents()
    assert state.preview.result is None
    assert not state.preview._timer.isActive()
    assert not selections(state)
    assert_no_replacement_panel(state)


def test_confirmation_replaces_preview_with_existing_confirmation_state(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/gc")
    assert result(state).confirm
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.status.substitute_confirm is not None
    assert state.preview.result is None
    assert not selections(state)
    assert_no_replacement_panel(state)
    state.qtbot.keyClicks(state.line, "a")
    assert state.editor.toPlainText() == "alpha beta\nbar x bar x bar\nlast line"


@pytest.mark.parametrize("address", ["", "."])
def test_default_range_uses_ex_entry_line_without_moving_editor(preview, address):
    state = preview
    state.status.cursor.set_cursor_pos(
        state.editor.document().findBlockByNumber(1).position()
    )
    state.qtbot.keyClicks(state.line, ":")
    state.status.cursor.set_cursor_pos(0)
    enter_command(state, f":{address}s/foo/bar/g")
    shown_result = result(state)
    assert shown_result.match_count == 3
    assert shown_result.first_line == shown_result.last_line == 2
    assert all(selection.cursor.blockNumber() == 1 for selection in selections(state))
    assert state.editor.textCursor().position() == 0
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.editor.toPlainText() == "alpha beta\nbar x bar x bar\nlast line"


def test_final_ime_commit_executes_latest_replacement_once(preview, monkeypatch):
    state = preview
    enter_command(state, ":%s/foo/")
    result(state)
    send_ime(state, preedit="한글")
    assert state.preview.result is None
    executor = state.status.sub_mode
    substitute = Mock(wraps=executor.substitute)
    monkeypatch.setattr(executor, "substitute", substitute)
    monkeypatch.setattr(
        QApplication.inputMethod(), "commit", lambda: send_ime(state, commit="한글")
    )
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    substitute.assert_called_once()
    assert state.editor.toPlainText() == "alpha beta\n한글 x foo x foo\nlast line"
    assert state.line.histories["ex"] == ["%s/foo/한글"]
    assert not selections(state)
    assert_no_replacement_panel(state)


def test_reentrant_input_events_never_calculate_intermediate_text(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    result(state)
    with state.widget.input_processing():
        state.line.setText(":%s/foo/intermediate/g")
        QCoreApplication.processEvents()
        assert state.preview.result is None
        assert not state.preview._timer.isActive()
        assert not state.preview._chunk_timer.isActive()
        assert not selections(state)
        state.line.setText(":%s/foo/final/g")
    assert result(state).match_count == 3
    assert state.line.text() == ":%s/foo/final/g"
    assert state.editor.toPlainText() == "alpha beta\nfoo x foo x foo\nlast line"
    assert_no_replacement_panel(state)


def test_new_input_invalidates_resumable_chunk(preview, monkeypatch):
    state = preview
    state.editor.set_text("\n".join("foo" for _ in range(1000)))
    state.preview._timer.setInterval(150)
    monkeypatch.setattr(state.preview, "TICK_MS", 0)
    enter_command(state, ":%s/foo/old/g")
    state.preview._timer.stop()
    state.preview._start()
    assert state.preview._chunk_timer.isActive()
    assert state.preview.result is None
    enter_command(state, ":%s/foo/new/g")
    assert not state.preview._chunk_timer.isActive()
    assert not selections(state)
    state.preview._timer.setInterval(0)
    state.preview._timer.start()
    latest = result(state)
    assert latest.match_count == 1000
    assert len(selections(state)) == 1000
    assert state.line.text() == ":%s/foo/new/g"
    assert_no_replacement_panel(state)


def test_case_preferences_recalculate_the_current_input(preview):
    state = preview
    state.editor.set_text("FOO foo")
    previous = {
        name: CONF.get(CONF_SECTION, name, True) for name in ("ignorecase", "smartcase")
    }
    try:
        CONF.set(CONF_SECTION, "ignorecase", False)
        state.widget.apply_settings()
        enter_command(state, ":%s/foo/bar/g")
        assert result(state).match_count == 1
        CONF.set(CONF_SECTION, "ignorecase", True)
        state.widget.apply_settings()
        assert result(state).match_count == 2
    finally:
        for name, value in previous.items():
            CONF.set(CONF_SECTION, name, value)
        state.widget.apply_settings()


def test_edit_from_shared_document_split_ends_preview(preview):
    state = preview
    split = QPlainTextEdit()
    state.qtbot.addWidget(split)
    split.setDocument(state.editor.document())
    enter_command(state, ":%s/foo/bar/g")
    result(state)
    cursor = split.textCursor()
    cursor.insertText("external ")
    assert state.preview.result is None
    assert not selections(state)
    assert_no_replacement_panel(state)
    state.preview.sync()
    QCoreApplication.processEvents()
    assert state.preview.result is None
    assert not state.preview._timer.isActive()


def test_replacing_document_ends_session_before_queued_results(preview):
    state = preview
    holder = QPlainTextEdit()
    state.qtbot.addWidget(holder)
    holder.setPlainText("replacement document")
    original = state.editor.document()
    original_parent = original.parent()
    state.widget.put_controller.bind_editor(None)
    # Retain the editor-owned document while QPlainTextEdit changes documents.
    original.setParent(holder)
    try:
        enter_command(state, ":%s/foo/bar/g")
        result(state)
        state.editor.setDocument(holder.document())
        state.preview.sync()
        QCoreApplication.processEvents()
        assert state.preview.result is None
        assert not selections(state)
        assert_no_replacement_panel(state)
        assert not state.preview._timer.isActive()
    finally:
        state.editor.setDocument(original)
        original.setParent(original_parent)
        state.widget.put_controller.bind_editor(state.editor)


def test_switch_clears_old_editor_and_pending_callbacks(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    result(state)
    state.stack.set_stack_index(1)
    state.vim._use_stack(state.stack)
    QCoreApplication.processEvents()
    assert not state.editor.get_extra_selections("vim_substitute_preview")
    assert not state.stack.get_current_editor().get_extra_selections(
        "vim_substitute_preview"
    )
    assert state.preview.result is None
    assert not state.preview._timer.isActive()
    assert not state.preview._chunk_timer.isActive()
    assert state.line.text() == ""


def test_cleanup_disconnects_pending_controller_and_document_watch(preview):
    state = preview
    state.preview._timer.setInterval(150)
    enter_command(state, ":%s/foo/bar/g")
    controller = SubstitutePreviewController(state.widget)
    controller.begin_session(state.status.sub_mode)
    controller.sync()
    assert controller._timer.isActive()
    controller.cleanup()
    controller.cleanup()
    state.widget.sig_command_changed.emit()
    state.widget.sig_input_finished.emit()
    controller._start()
    controller._step()
    assert controller.result is None
    assert not controller._timer.isActive()
    assert not controller._chunk_timer.isActive()
    assert not controller._connections
    assert not controller._document_connections
    controller.deleteLater()


def test_count_only_utf16_highlights_widen_without_changing_counts(preview):
    state = preview
    state.editor.set_text("😀")
    enter_command(state, r":s/\C/\u/gn")
    counted = result(state)
    assert counted.match_count == 2
    assert counted.spans == ((0, 2), (0, 2))
    assert len(selections(state)) == 2
    assert all(
        selection.cursor.selectedText() == "😀" for selection in selections(state)
    )
    assert state.editor.toPlainText() == "😀"


def test_zero_width_matches_remain_visible_at_eof_and_empty_line(preview):
    state = preview
    state.editor.set_text("foo\n")
    enter_command(state, ":%s/$/x/g")
    zero_width = result(state)
    assert zero_width.match_count == 2
    assert zero_width.spans == ((3, 3), (4, 4))
    assert state.editor.toPlainText() == "foo\n"
    assert len(selections(state)) == 2
    assert all(
        selection.format.property(QTextFormat.FullWidthSelection)
        for selection in selections(state)
    )
    assert all(not selection.cursor.hasSelection() for selection in selections(state))


def test_oversized_replacement_stops_before_regex_preparation(preview, monkeypatch):
    state = preview
    state.preview.limits = replace(state.preview.limits, max_command_chars=32)
    forbidden = Mock(side_effect=AssertionError("oversized command prepared a regex"))
    monkeypatch.setattr(
        "spyder_okvim.spyder.substitute_preview.prepare_substitution", forbidden
    )
    enter_command(state, ":%s/foo/" + "x" * 10000)
    limited = result(state)
    assert limited.partial
    assert limited.reasons == ("command length limit",)
    assert not limited.spans
    assert limited.scanned_lines == 0
    forbidden.assert_not_called()


def test_window_focus_roundtrip_preserves_ex_draft_and_preview_session(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    result(state)
    executor = state.status.sub_mode
    QCoreApplication.sendEvent(state.main, QEvent(QEvent.WindowDeactivate))
    QCoreApplication.sendEvent(
        state.line, QFocusEvent(QEvent.FocusOut, Qt.ActiveWindowFocusReason)
    )
    assert state.line.text() == ":%s/foo/bar/g"
    assert state.status.sub_mode is executor
    assert state.preview.result is None
    assert not selections(state)
    QCoreApplication.sendEvent(state.main, QEvent(QEvent.WindowActivate))
    QCoreApplication.sendEvent(
        state.line, QFocusEvent(QEvent.FocusIn, Qt.ActiveWindowFocusReason)
    )
    assert state.line.text() == ":%s/foo/bar/g"
    assert state.status.sub_mode is executor
    assert result(state).match_count == 3


def test_regular_focus_transfer_cancels_input_and_session(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    result(state)
    QCoreApplication.sendEvent(
        state.line, QFocusEvent(QEvent.FocusOut, Qt.TabFocusReason)
    )
    assert state.line.text() == ""
    assert state.status.sub_mode is None
    assert state.preview.result is None
    assert not selections(state)


def test_hiding_and_showing_window_preserves_unchanged_ex_draft(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    result(state)
    executor = state.status.sub_mode
    state.main.hide()
    QCoreApplication.processEvents()
    assert state.line.text() == ":%s/foo/bar/g"
    assert state.status.sub_mode is executor
    assert state.preview.result is None
    assert not selections(state)
    state.main.show()
    state.main.activateWindow()
    QApplication.setActiveWindow(state.line.window())
    state.line.setFocus()
    state.qtbot.waitUntil(state.line.hasFocus)
    assert state.line.text() == ":%s/foo/bar/g"
    assert state.status.sub_mode is executor
    assert result(state).match_count == 3


def test_unrelated_prompt_preferences_do_not_recalculate_preview(preview):
    state = preview
    enter_command(state, ":%s/foo/bar/g")
    previous = result(state)
    CONF.set(CONF_SECTION, "substitute_guide_enabled", False)
    state.widget.apply_settings()
    assert state.preview.result is previous
    assert not state.preview._timer.isActive()
    assert not state.preview._chunk_timer.isActive()


@pytest.mark.parametrize("command", [":%s/foo", r":%s/foo/<tag>&\u/gn"])
def test_search_and_count_stages_do_not_expand_replacements(
    preview, monkeypatch, command
):
    state = preview
    forbidden = Mock(
        side_effect=AssertionError("highlighting prepared replacement text")
    )
    monkeypatch.setattr("spyder_okvim.utils.substitute.tokenize_replacement", forbidden)
    monkeypatch.setattr("spyder_okvim.utils.substitute.substitution_match", forbidden)
    enter_command(state, command)
    counted = result(state)
    expected = 3 if counted.count_only else 1
    assert counted.match_count == expected
    assert len(selections(state)) == expected
    assert counted.rows == ()
    assert_no_replacement_panel(state)
    assert state.editor.toPlainText() == "alpha beta\nfoo x foo x foo\nlast line"
    assert state.line.hasFocus()
    forbidden.assert_not_called()
