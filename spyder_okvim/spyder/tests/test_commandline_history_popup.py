"""History suggestions share the existing command-line input and lifetime."""

import os
from threading import Event
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QInputMethodEvent, QKeyEvent
from qtpy.QtWidgets import QApplication
from spyder.config.manager import CONF

from spyder_okvim.executor.executor_colon import ExecutorColon
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.vim import KeyInfo, VimState


@pytest.fixture
def history_popup(vim_bot, qtbot):
    """Restore histories, preferences, active view and focus after each test."""
    main, stack, _, vim, _ = vim_bot
    widget = vim.vim_cmd
    line = widget.commandline
    status = widget.vim_status
    controller = widget.commandline_popup
    previous_index = stack.get_stack_index()
    previous_enabled = CONF.get(CONF_SECTION, "commandline_history_enabled", True)
    previous_preview = CONF.get(CONF_SECTION, "substitute_preview_enabled", True)
    previous_completion = CONF.get(CONF_SECTION, "commandline_completion_enabled", True)
    previous_histories = {kind: items[:] for kind, items in line.histories.items()}
    widget.cancel_macro()
    line.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    vim._use_stack(stack)
    status.reset_for_test()
    editor = stack.get_current_editor()
    previous_text = editor.toPlainText()
    editor.set_text("alpha beta\nfoo x foo x foo\nlast line")
    status.cursor.set_cursor_pos(0)
    for items in line.histories.values():
        items.clear()
    CONF.set(CONF_SECTION, "commandline_history_enabled", True)
    CONF.set(CONF_SECTION, "commandline_completion_enabled", True)
    CONF.set(CONF_SECTION, "substitute_preview_enabled", False)
    widget.apply_settings()
    main.show()
    main.activateWindow()
    line.setFocus()
    qtbot.waitUntil(line.hasFocus)
    state = SimpleNamespace(
        main=main,
        stack=stack,
        vim=vim,
        widget=widget,
        controller=controller,
        line=line,
        status=status,
        editor=editor,
        qtbot=qtbot,
    )
    try:
        yield state
    finally:
        widget.cancel_macro()
        if widget.worker_macro.isRunning():
            widget.worker_macro.wait()
        if status.is_recording_macro():
            status.stop_recording_macro()
        status.running_dot_cmd = False
        line.esc_pressed()
        status.finish_insert(apply_count=False)
        status.disconnect_from_editor()
        editor.set_text(previous_text)
        for kind, items in previous_histories.items():
            line.histories[kind][:] = items
        CONF.set(CONF_SECTION, "commandline_history_enabled", previous_enabled)
        CONF.set(CONF_SECTION, "substitute_preview_enabled", previous_preview)
        CONF.set(CONF_SECTION, "commandline_completion_enabled", previous_completion)
        widget.apply_settings()
        controller.cancel()
        stack.set_stack_index(previous_index)
        vim._use_stack(stack)
        main.activateWindow()
        line.setFocus()


def shown(state):
    popup = state.controller.popup
    return popup is not None and popup.isVisible()


def history_bodies(state):
    """Return full-history rows without the active prompt prefix."""
    context = state.line._history_context(state.line.text())
    prompt = context[1] if context is not None else ":"
    return [
        candidate.text[len(prompt) :]
        for candidate in state.controller.candidates
        if "history" in candidate.source.split(", ")
    ]


def show(state, prefix=":", history=("old", "new"), kind="ex"):
    state.line.histories[kind][:] = history
    state.qtbot.keyClicks(state.line, prefix)
    assert shown(state)
    return state.controller.popup


def select_next(state):
    state.qtbot.keyPress(state.line, Qt.Key_N, Qt.ControlModifier)


def send_ime(state, preedit="", commit=""):
    event = QInputMethodEvent(preedit, [])
    event.setCommitString(commit)
    QCoreApplication.sendEvent(state.line, event)


@pytest.mark.parametrize(
    "prefix, kind", [(":", "ex"), ("/", "search"), ("?", "search")]
)
def test_recent_candidates_are_read_only_and_keep_focus(history_popup, prefix, kind):
    state = history_popup
    state.line.histories["search" if kind == "ex" else "ex"][:] = ["unrelated"]
    popup = show(state, prefix, ("foo", "far", "foo"), kind)
    original = state.editor.toPlainText()
    position = state.editor.textCursor().position()
    revision = state.editor.document().revision()
    assert history_bodies(state) == ["foo", "far"]
    assert state.controller.selected_index is None
    assert popup.list_widget.currentRow() == -1
    select_next(state)
    assert state.controller.selected_index == 0
    select_next(state)
    assert state.controller.selected_index == 1
    state.qtbot.keyPress(state.line, Qt.Key_P, Qt.ControlModifier)
    assert state.controller.selected_index == 0
    assert state.line.text() == prefix
    assert state.editor.toPlainText() == original
    assert state.editor.textCursor().position() == position
    assert state.editor.document().revision() == revision
    assert state.line.histories[kind] == ["foo", "far", "foo"]
    assert state.line.hasFocus()
    assert popup.parentWidget() is state.controller.host
    assert state.controller.host.parentWidget() is state.editor.viewport()


def test_enter_accepts_then_executes_and_records_once(history_popup, monkeypatch):
    state = history_popup
    show(state, history=("2",))
    remember = Mock(wraps=state.line.remember_command)
    monkeypatch.setattr(state.line, "remember_command", remember)
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.line.text() == ":2"
    assert not shown(state)
    assert state.controller.selected_index is None
    assert state.editor.textCursor().position() == 0
    remember.assert_not_called()
    state.controller.sync()
    assert not shown(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    remember.assert_called_once_with(":2")
    assert state.editor.textCursor().blockNumber() == 1
    assert state.line.text() == ""
    assert state.status.sub_mode is None
    assert not shown(state)


def test_enter_without_selection_executes_existing_text(history_popup):
    state = history_popup
    show(state, prefix=":2", history=("2", "20"))
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.status.sub_mode is None
    assert state.line.text() == ""
    assert state.editor.textCursor().blockNumber() == 1
    assert not shown(state)


def test_automatic_commands_merge_with_history_in_history_order(history_popup):
    state = history_popup
    show(state, prefix=":w", history=("wq", "w", "write draft.py", "w"))

    candidates = state.controller.candidates
    assert [candidate.text for candidate in candidates] == [
        ":w",
        ":write draft.py",
        ":wq",
    ]
    assert candidates[0].source.split(", ") == ["history", "command"]
    assert candidates[0].apply_scope == "full command"
    assert candidates[1].source == "history"
    assert candidates[2].source.split(", ") == ["history", "command"]
    assert state.controller.selected_index is None
    assert state.line.text() == ":w"


def test_enter_after_tab_executes_once(history_popup, monkeypatch):
    state = history_popup
    clear = Mock()
    remember = Mock(wraps=state.line.remember_command)
    monkeypatch.setattr(state.widget, "clear_yank_history", clear)
    monkeypatch.setattr(state.line, "remember_command", remember)
    state.qtbot.keyClicks(state.line, ":YankyClear")

    state.qtbot.keyPress(state.line, Qt.Key_Tab)

    assert state.line.text() == ":YankyClearHistory"
    assert shown(state)
    assert state.controller.selected_index is not None
    clear.assert_not_called()
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    clear.assert_called_once_with()
    remember.assert_called_once_with(":YankyClearHistory")
    assert state.line.text() == ""


def test_ctrl_navigation_after_tab_requires_acceptance_before_execution(
    history_popup, monkeypatch
):
    state = history_popup
    remember = Mock(wraps=state.line.remember_command)
    monkeypatch.setattr(state.line, "remember_command", remember)
    state.qtbot.keyClicks(state.line, ":v")
    state.qtbot.keyPress(state.line, Qt.Key_Tab)
    assert state.line.text() == ":vs"

    select_next(state)

    assert state.line.text() == ":vs"
    assert state.controller.candidates[state.controller.selected_index].text == ":vsp"
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.line.text() == ":vsp"
    assert state.status.sub_mode is not None
    assert state.controller.selected_index is None
    remember.assert_not_called()


def test_manual_cursor_move_after_tab_restores_automatic_command_candidates(
    history_popup,
):
    state = history_popup
    show(state, prefix=":w", history=("write draft.py",))
    state.qtbot.keyPress(state.line, Qt.Key_Tab)
    state.qtbot.keyPress(state.line, Qt.Key_Tab)
    assert state.line.text() == ":wq"
    assert state.line.completion_result is not None

    state.qtbot.keyPress(state.line, Qt.Key_Left)

    assert state.line.text() == ":wq"
    assert state.line.cursorPosition() == 2
    assert state.line.completion_result is None
    assert shown(state)
    assert [candidate.text for candidate in state.controller.candidates] == [
        ":w",
        ":wq",
    ]
    assert all(
        candidate.source == "command" for candidate in state.controller.candidates
    )
    assert state.controller.selected_index is None
    assert state.controller.popup.list_widget.currentRow() == -1


def test_edit_resets_selection_and_empty_results_hide(history_popup):
    state = history_popup
    show(state, history=("foo", "far", "Foo"))
    select_next(state)
    state.qtbot.keyClicks(state.line, "f")
    assert history_bodies(state) == ["far", "foo"]
    assert state.controller.selected_index is None
    select_next(state)
    state.qtbot.keyClicks(state.line, "z")
    assert not shown(state)
    assert state.controller.selected_index is None
    state.qtbot.keyPress(state.line, Qt.Key_Backspace)
    assert shown(state)
    assert state.controller.selected_index is None


def test_navigation_keeps_geometry_while_scrolling_selection(
    history_popup, monkeypatch
):
    state = history_popup
    popup = show(state, history=tuple(f"command {index}" for index in range(12)))
    geometry = popup.geometry()
    measure = Mock(wraps=popup.preferred_size)
    monkeypatch.setattr(popup, "preferred_size", measure)

    for _ in range(10):
        select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_P, Qt.ControlModifier)

    assert state.controller.selected_index == 8
    assert popup.geometry() == geometry
    measure.assert_not_called()
    item = popup.list_widget.currentItem()
    assert (
        popup.list_widget.viewport()
        .rect()
        .intersects(popup.list_widget.visualItemRect(item))
    )


def test_font_change_refits_existing_popup(history_popup, monkeypatch):
    state = history_popup
    popup = show(state)
    original_font = state.line.font()
    font = state.line.font()
    font.setPointSize(max(1, font.pointSize()) + 2)
    measure = Mock(wraps=popup.preferred_size)
    monkeypatch.setattr(popup, "preferred_size", measure)

    try:
        state.line.setFont(font)
        state.controller.sync()
        assert state.controller.popup is popup
        assert popup.font() == font
        measure.assert_called_once()
    finally:
        state.line.setFont(original_font)


def test_cursor_movement_hides_history_but_keeps_command_completions(history_popup):
    state = history_popup
    show(state, prefix=":f", history=("foo", "far"))
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Left)
    assert shown(state)
    assert history_bodies(state) == []
    assert all(
        candidate.source == "command" for candidate in state.controller.candidates
    )
    assert state.controller.selected_index is None
    state.line.setCursorPosition(len(state.line.text().encode("utf-16-le")) // 2)
    assert shown(state)
    assert state.controller.selected_index is None


def test_acceptance_suppresses_programmatic_replacements_until_user_edit(history_popup):
    state = history_popup
    show(state, history=("foo", "food"))
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert not shown(state)
    state.line.setText(":f")
    state.controller.sync()
    assert not shown(state)
    state.qtbot.keyClicks(state.line, "o")
    assert shown(state)
    assert state.controller.selected_index is None
    state.qtbot.keyPress(state.line, Qt.Key_Escape)
    state.qtbot.keyClicks(state.line, ":")
    assert shown(state)


def test_up_down_preserve_draft_and_cursor_while_suppressing_popup(history_popup):
    state = history_popup
    show(state, prefix=":f", history=("foo", "far"))
    state.line.setCursorPosition(1)
    state.qtbot.keyPress(state.line, Qt.Key_Up)
    assert state.line.text() == ":far"
    assert not shown(state)
    state.qtbot.keyPress(state.line, Qt.Key_Down)
    assert state.line.text() == ":f"
    assert state.line.cursorPosition() == 1
    assert not shown(state)
    state.line.setCursorPosition(len(state.line.text().encode("utf-16-le")) // 2)
    assert not shown(state)
    state.qtbot.keyClicks(state.line, "o")
    assert shown(state)


@pytest.mark.parametrize("key", [Qt.Key_Tab, Qt.Key_Backtab])
@pytest.mark.parametrize(
    "prefix, kind", [(":w", "ex"), ("/w", "search"), ("?w", "search")]
)
def test_tab_shows_applied_completion_list_for_ex_only(
    history_popup, key, prefix, kind
):
    state = history_popup
    show(state, prefix=prefix, history=("write", "write copy.py"), kind=kind)
    state.qtbot.keyPress(state.line, key)
    assert shown(state) is (kind == "ex")
    if kind == "ex":
        assert all(
            candidate.source == "command" for candidate in state.controller.candidates
        )
        assert state.controller.selected_index is not None
        selected = state.controller.candidates[state.controller.selected_index]
        assert selected.text == state.line.text()
    state.controller.sync()
    assert shown(state) is (kind == "ex")
    assert state.line.hasFocus()


def test_acceptance_discards_previous_navigation_state(history_popup):
    state = history_popup
    show(state, prefix=":f", history=("foo", "far"))
    state.qtbot.keyPress(state.line, Qt.Key_Up)
    state.qtbot.keyPress(state.line, Qt.Key_Backspace)
    assert shown(state)
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.line.text() == ":far"
    state.qtbot.keyPress(state.line, Qt.Key_Up)
    state.qtbot.keyPress(state.line, Qt.Key_Down)
    assert state.line.text() == ":far"


def test_shortcut_override_reserves_only_popup_navigation(history_popup, monkeypatch):
    state = history_popup
    fallback = Mock()
    monkeypatch.setitem(state.line.dispatcher, Qt.Key_P, fallback)
    show(state)
    for key in (Qt.Key_N, Qt.Key_P):
        event = QKeyEvent(QEvent.ShortcutOverride, key, Qt.ControlModifier)
        event.ignore()
        QCoreApplication.sendEvent(state.line, event)
        assert event.isAccepted()
        assert state.controller.selected_index is None
        assert state.line.text() == ":"
    state.qtbot.keyPress(state.line, Qt.Key_P, Qt.ControlModifier)
    fallback.assert_not_called()
    state.qtbot.keyPress(state.line, Qt.Key_Escape)
    state.qtbot.keyPress(state.line, Qt.Key_P, Qt.ControlModifier)
    fallback.assert_called_once_with()


@pytest.mark.parametrize("prefix, expected", [("2/", "2/foo"), ("2?", "2?foo")])
def test_search_acceptance_preserves_count_and_direction(
    history_popup, prefix, expected
):
    state = history_popup
    state.status.cursor.set_cursor_pos(11)
    show(state, prefix, ("foo",), "search")
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.line.text() == expected
    assert state.line.histories["search"] == ["foo"]
    assert state.status.sub_mode is not None
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.status.search.txt_searched == "foo"
    assert state.status.search.forward == ("/" in prefix)
    assert state.status.sub_mode is None


@pytest.mark.parametrize(
    "prefix, mode", [("d/", None), ("v/", VimState.VISUAL), ("V/", VimState.VLINE)]
)
def test_search_acceptance_preserves_operator_and_visual_context(
    history_popup, prefix, mode
):
    state = history_popup
    state.editor.set_text("foo x foo x foo")
    state.status.cursor.set_cursor_pos(0)
    show(state, prefix, ("foo",), "search")
    original = state.editor.toPlainText()
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.editor.toPlainText() == original
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    if mode is None:
        assert state.editor.toPlainText() == "foo x foo"
        assert state.status.register_dict['"'].content == "foo x "
    else:
        assert state.status.vim_state == mode
        assert state.editor.get_extra_selections("vim_selection")
    assert state.line.histories["search"] == ["foo"]


def test_visual_ex_range_is_filtered_as_part_of_body(history_popup):
    state = history_popup
    show(state, "Vj:", ("1,2s/alpha/omega/", "3s/last/end/"))
    assert state.line.text() == ":1,2"
    assert history_bodies(state) == ["1,2s/alpha/omega/"]
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.line.text() == ":1,2s/alpha/omega/"


def test_composition_hides_and_commit_refreshes_without_old_selection(history_popup):
    state = history_popup
    show(state, "/", ("한글", "other"), "search")
    select_next(state)
    send_ime(state, preedit="ㅎ")
    assert not shown(state)
    assert state.controller.selected_index is None
    send_ime(state, commit="한", preedit="ㄱ")
    assert state.line.text() == "/한"
    assert not shown(state)
    send_ime(state, commit="글")
    assert state.line.text() == "/한글"
    assert shown(state)
    assert history_bodies(state) == ["한글"]
    assert state.controller.selected_index is None


def test_cancelled_composition_restores_candidates_without_selection(history_popup):
    state = history_popup
    show(state)
    select_next(state)
    send_ime(state, preedit="한")
    assert not shown(state)
    send_ime(state)
    assert shown(state)
    assert state.controller.selected_index is None
    assert state.line.text() == ":"


def test_accepting_enter_rechecks_ime_commit_and_never_executes(
    history_popup, monkeypatch
):
    state = history_popup
    show(state, history=("12", "2"))
    select_next(state)
    remember = Mock(wraps=state.line.remember_command)
    monkeypatch.setattr(state.line, "remember_command", remember)
    monkeypatch.setattr(
        QApplication.inputMethod(), "commit", lambda: send_ime(state, commit="1")
    )
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.line.text() == ":1"
    assert state.status.sub_mode is not None
    assert state.controller.selected_index is None
    assert state.editor.textCursor().position() == 0
    remember.assert_not_called()


def test_utf16_cursor_end_and_candidate_replacement(history_popup):
    state = history_popup
    show(state, "/", ("😀한글",), "search")
    send_ime(state, commit="😀")
    assert state.line.text() == "/😀"
    assert state.line.cursorPosition() == 3
    assert shown(state)
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.line.text() == "/😀한글"
    assert state.line.cursorPosition() == 5
    assert not shown(state)


def test_setting_and_focus_loss_clean_up_immediately(history_popup):
    state = history_popup
    show(state)
    select_next(state)
    CONF.set(CONF_SECTION, "commandline_history_enabled", False)
    state.widget.apply_settings()
    assert shown(state)
    assert history_bodies(state) == []
    assert all(
        candidate.source == "command" for candidate in state.controller.candidates
    )
    assert state.controller.selected_index is None
    assert state.line.text() == ":"
    state.qtbot.keyPress(state.line, Qt.Key_Up)
    assert state.line.text() == ":new"
    state.qtbot.keyPress(state.line, Qt.Key_Escape)
    CONF.set(CONF_SECTION, "commandline_history_enabled", True)
    state.widget.apply_settings()
    state.qtbot.keyClicks(state.line, ":")
    assert shown(state)
    state.editor.setFocus()
    assert not shown(state)
    assert state.controller.selected_index is None
    assert state.status.sub_mode is None


def test_completion_setting_is_independent_and_preserves_tab(history_popup):
    state = history_popup
    show(state, prefix=":w", history=("write draft.py",))
    assert any(
        "command" in candidate.source for candidate in state.controller.candidates
    )

    CONF.set(CONF_SECTION, "commandline_completion_enabled", False)
    state.widget.apply_settings()

    assert shown(state)
    assert history_bodies(state) == ["write draft.py"]
    assert all(
        candidate.source == "history" for candidate in state.controller.candidates
    )
    state.qtbot.keyPress(state.line, Qt.Key_Tab)
    state.qtbot.keyPress(state.line, Qt.Key_Tab)
    assert state.line.text() == ":wq"
    assert not shown(state)
    CONF.set(CONF_SECTION, "commandline_completion_enabled", True)
    state.widget.apply_settings()
    assert shown(state)
    assert all(
        candidate.source == "command" for candidate in state.controller.candidates
    )


@pytest.mark.parametrize(
    "option", ["substitute_guide_enabled", "substitute_preview_enabled"]
)
def test_guide_and_preview_settings_preserve_current_selection(history_popup, option):
    state = history_popup
    show(state, prefix=":w", history=("write draft.py",))
    select_next(state)
    candidates = state.controller.candidates[:]
    index = state.controller.selected_index
    previous = CONF.get(CONF_SECTION, option, True)
    try:
        CONF.set(CONF_SECTION, option, not previous)
        state.widget.apply_settings()

        assert state.controller.candidates == candidates
        assert state.controller.selected_index == index
        assert state.controller.popup.list_widget.currentRow() == index
        assert state.line.text() == ":w"
    finally:
        CONF.set(CONF_SECTION, option, previous)
        state.widget.apply_settings()


def test_editor_switch_releases_old_panel_and_pending_input(history_popup):
    state = history_popup
    popup = show(state)
    select_next(state)
    state.stack.set_stack_index(1)
    state.vim._use_stack(state.stack)
    assert not shown(state)
    assert state.controller.selected_index is None
    assert state.line.text() == ""
    assert state.status.sub_mode is None
    # Flush deferred deletion before testing the new viewport's ownership.
    QCoreApplication.processEvents()
    state.line.setFocus()
    state.qtbot.keyClicks(state.line, ":")
    assert shown(state)
    assert state.controller.popup is not popup
    assert (
        state.controller.host.parentWidget()
        is state.stack.get_current_editor().viewport()
    )


def test_window_deactivation_discards_candidates_and_selection(history_popup):
    state = history_popup
    show(state)
    select_next(state)
    QCoreApplication.sendEvent(state.line.window(), QEvent(QEvent.WindowDeactivate))
    assert not shown(state)
    assert state.controller.candidates == []
    assert state.controller.selected_index is None


def test_automatic_history_filtering_never_reads_path_completion(
    history_popup, monkeypatch
):
    state = history_popup
    completion = Mock(side_effect=AssertionError("automatic disk lookup"))
    monkeypatch.setattr("spyder_okvim.spyder.vim_widgets.completion_items", completion)
    show(state, prefix=":w", history=("write first.py", "write second.py"))
    state.qtbot.keyClicks(state.line, "r")
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    assert state.line.text() == ":write second.py"
    completion.assert_not_called()


def test_controller_cleanup_disconnects_observers_and_releases_panel(history_popup):
    state = history_popup
    show(state)

    class ObservedController(type(state.controller)):
        def __init__(self, widget):
            self.observations = 0
            super().__init__(widget)

        def sync(self):
            self.observations += 1
            super().sync()

    controller = ObservedController(state.widget)
    controller.set_editor(state.editor)
    controller.sync()
    assert controller.popup.isVisible()
    previous_observations = controller.observations
    state.widget.sig_input_finished.emit()
    assert controller.observations == previous_observations + 1
    controller.cleanup()
    controller.cleanup()
    assert controller.popup is None
    assert controller.candidates == []
    assert controller.selected_index is None
    previous_observations = controller.observations
    state.widget.sig_input_finished.emit()
    assert controller.observations == previous_observations
    controller.deleteLater()


@pytest.mark.parametrize("suppression", ["recording", "playback", "dot"])
def test_macro_and_dot_keep_popup_keys_out_of_input(
    history_popup, suppression, monkeypatch
):
    state = history_popup
    fallback = Mock()
    monkeypatch.setitem(state.line.dispatcher, Qt.Key_P, fallback)
    if suppression == "recording":
        state.status.manager_macro.start_record("a")
    elif suppression == "playback":
        state.widget._macro_generation = 1
    else:
        state.status.running_dot_cmd = True
    state.line.histories["ex"][:] = ["2"]
    state.qtbot.keyClicks(state.line, ":")
    assert not shown(state)
    state.qtbot.keyPress(state.line, Qt.Key_P, Qt.ControlModifier)
    if suppression == "playback":
        # Existing playback guards consume a cycle without a preceding put.
        fallback.assert_not_called()
    else:
        fallback.assert_called_once_with()
    assert state.controller.selected_index is None


def test_recorded_command_executes_on_its_only_enter(history_popup):
    state = history_popup
    state.line.histories["ex"][:] = ["2"]
    state.status.manager_macro.registers["a"] = [
        KeyInfo(Qt.Key_Colon, ":", Qt.NoModifier, 0),
        KeyInfo(Qt.Key_2, "2", Qt.NoModifier, 0),
        KeyInfo(Qt.Key_Return, "\r", Qt.NoModifier, 0),
    ]
    state.qtbot.keyClicks(state.line, "@a")
    state.qtbot.waitUntil(lambda: not state.widget.is_playing_macro)
    assert state.line.text() == ""
    assert state.status.sub_mode is None
    assert state.editor.textCursor().blockNumber() == 1
    assert not shown(state)


def test_nested_input_never_shows_or_accepts_intermediate_candidates(history_popup):
    state = history_popup
    show(state)
    select_next(state)
    with state.widget.input_processing():
        assert not shown(state)
        state.line.setText(":n")
        QCoreApplication.processEvents()
        assert not shown(state)
        state.qtbot.keyPress(state.line, Qt.Key_N, Qt.ControlModifier)
        assert state.line.text() == ":n"
    assert shown(state)
    assert history_bodies(state) == ["new"]
    assert state.controller.selected_index is None


@pytest.mark.parametrize("action", ["accept", "next"])
@pytest.mark.parametrize("transition", ["rewrite", "cancel"])
def test_input_started_callback_cannot_use_stale_candidates(
    history_popup, monkeypatch, action, transition
):
    state = history_popup
    show(state)
    select_next(state)
    remember = Mock(wraps=state.line.remember_command)
    monkeypatch.setattr(state.line, "remember_command", remember)

    def replace_before_dispatch():
        if transition == "rewrite":
            state.line.setText(":n")
        else:
            state.line.esc_pressed()

    state.widget.sig_input_started.connect(replace_before_dispatch)
    try:
        if action == "accept":
            state.qtbot.keyPress(state.line, Qt.Key_Return)
        else:
            # QtTest synthesizes a separate Control press first; exercise the
            # captured navigation action itself rather than that earlier key.
            state.line.keyPressEvent(
                QKeyEvent(QEvent.KeyPress, Qt.Key_N, Qt.ControlModifier, "n")
            )
    finally:
        state.widget.sig_input_started.disconnect(replace_before_dispatch)
    assert state.line.text() == (":n" if transition == "rewrite" else "")
    assert history_bodies(state) == (["new"] if transition == "rewrite" else [])
    assert state.controller.selected_index is None
    assert (state.status.sub_mode is not None) == (transition == "rewrite")
    remember.assert_not_called()


@pytest.mark.parametrize("transition", ["cursor", "executor"])
def test_acceptance_rechecks_cursor_and_executor_identity(
    history_popup, monkeypatch, transition
):
    state = history_popup
    show(state, prefix=":w", history=("write draft.py",))
    select_next(state)
    remember = Mock(wraps=state.line.remember_command)
    monkeypatch.setattr(state.line, "remember_command", remember)

    def change_before_dispatch():
        if transition == "cursor":
            state.line.setCursorPosition(1)
        else:
            state.status.sub_mode = ExecutorColon(state.status)

    state.widget.sig_input_started.connect(change_before_dispatch)
    try:
        state.qtbot.keyPress(state.line, Qt.Key_Return)
    finally:
        state.widget.sig_input_started.disconnect(change_before_dispatch)

    assert state.line.text() == ":w"
    assert state.status.sub_mode is not None
    assert state.controller.selected_index is None
    remember.assert_not_called()


def test_acceptance_rechecks_removed_history_row_without_input_change(
    history_popup, monkeypatch
):
    state = history_popup
    show(state, prefix=":w", history=("write draft.py",))
    select_next(state)
    remember = Mock(wraps=state.line.remember_command)
    monkeypatch.setattr(state.line, "remember_command", remember)

    def remove_before_dispatch():
        state.line.histories["ex"].clear()

    state.widget.sig_input_started.connect(remove_before_dispatch)
    try:
        state.qtbot.keyPress(state.line, Qt.Key_Return)
    finally:
        state.widget.sig_input_started.disconnect(remove_before_dispatch)

    assert state.line.text() == ":w"
    assert state.line.histories["ex"] == []
    assert state.status.sub_mode is not None
    assert history_bodies(state) == []
    assert state.controller.selected_index is None
    remember.assert_not_called()


def test_selected_path_rechecks_working_directory_before_acceptance(
    history_popup, monkeypatch, tmp_path
):
    state = history_popup
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "alpha.py").touch()
    (first / "alpine.py").touch()
    monkeypatch.chdir(first)
    state.qtbot.keyClicks(state.line, ":e al")
    state.qtbot.keyPress(state.line, Qt.Key_Tab)
    state.qtbot.waitUntil(lambda: not state.controller.path_tab_pending, timeout=2000)
    assert state.line.text() == ":e alpha.py"
    select_next(state)
    assert (
        state.controller.candidates[state.controller.selected_index].text
        == ":e alpine.py"
    )
    remember = Mock(wraps=state.line.remember_command)
    monkeypatch.setattr(state.line, "remember_command", remember)

    def change_before_dispatch():
        monkeypatch.chdir(second)

    state.widget.sig_input_started.connect(change_before_dispatch)
    try:
        state.qtbot.keyPress(state.line, Qt.Key_Return)
    finally:
        state.widget.sig_input_started.disconnect(change_before_dispatch)

    assert state.line.text() == ":e alpha.py"
    assert state.status.sub_mode is not None
    assert state.controller.selected_index is None
    remember.assert_not_called()


@pytest.fixture
def path_popup(history_popup, monkeypatch, tmp_path):
    """Observe filesystem enumeration after preparing a small completion folder."""
    state = history_popup
    (tmp_path / "alpha.py").touch()
    (tmp_path / "alpine.json").touch()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "child.toml").touch()
    monkeypatch.chdir(tmp_path)
    state.root = tmp_path
    state.scans = Mock(wraps=os.scandir)
    monkeypatch.setattr(os, "scandir", state.scans)
    return state


def path_rows(state):
    return [
        candidate.text
        for candidate in state.controller.candidates
        if "path" in candidate.source.split(", ")
    ]


def wait_for_paths(state):
    state.qtbot.waitUntil(lambda: bool(path_rows(state)), timeout=2000)


def test_edit_argument_automatically_lists_paths_without_changing_input(path_popup):
    state = path_popup
    original = state.editor.toPlainText()
    position = state.editor.textCursor().position()
    revision = state.editor.document().revision()

    state.qtbot.keyClicks(state.line, ":e ")

    assert path_rows(state) == []
    state.scans.assert_not_called()
    wait_for_paths(state)
    assert path_rows(state) == [":e alpha.py", ":e alpine.json", ":e src" + os.sep]
    assert state.line.text() == ":e "
    assert state.line.cursorPosition() == 3
    assert state.controller.selected_index is None
    assert state.controller.popup.list_widget.currentRow() == -1
    assert state.line.histories["ex"] == []
    assert state.editor.toPlainText() == original
    assert state.editor.textCursor().position() == position
    assert state.editor.document().revision() == revision
    state.scans.assert_called_once()


def test_automatic_path_enter_accepts_then_opens_on_next_enter(path_popup, monkeypatch):
    state = path_popup
    load = Mock()
    monkeypatch.setattr(state.status.editor_widget, "load", load, raising=False)
    state.qtbot.keyClicks(state.line, ":e al")
    wait_for_paths(state)

    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)

    assert state.line.text() == ":e alpha.py"
    assert state.status.sub_mode is not None
    assert state.line.histories["ex"] == []
    assert not shown(state)
    load.assert_not_called()
    state.qtbot.wait(160)
    state.controller.sync()
    assert not shown(state)
    state.scans.assert_called_once()

    state.qtbot.keyPress(state.line, Qt.Key_Return)

    load.assert_called_once_with(str(state.root / "alpha.py"))
    assert state.line.histories["ex"] == ["e alpha.py"]
    assert state.status.sub_mode is None


@pytest.mark.parametrize(
    "draft",
    [
        ":e",
        ":%e ",
        ":1,2e ",
        ":edit ",
        ":unknown ",
        ":q ",
        ":marks ",
        ":w al",
        ":s/al/be/",
        "/al",
        "?al",
    ],
)
def test_automatic_paths_only_scan_unranged_edit_arguments(path_popup, draft):
    state = path_popup

    state.qtbot.keyClicks(state.line, draft)
    state.qtbot.wait(160)
    for _ in range(3):
        state.controller.sync()

    assert path_rows(state) == []
    state.scans.assert_not_called()


def test_path_results_merge_after_current_history_without_selecting(path_popup):
    state = path_popup
    state.line.histories["ex"][:] = ["e another.py", "e alpha.py"]
    state.qtbot.keyClicks(state.line, ":e a")

    assert [candidate.text for candidate in state.controller.candidates] == [
        ":e alpha.py",
        ":e another.py",
    ]
    state.scans.assert_not_called()
    select_next(state)
    assert state.controller.selected_index == 0
    wait_for_paths(state)

    assert [candidate.text for candidate in state.controller.candidates] == [
        ":e alpha.py",
        ":e another.py",
        ":e alpine.json",
    ]
    assert state.controller.candidates[0].source == "history, path"
    assert state.controller.selected_index is None
    assert state.line.text() == ":e a"
    state.scans.assert_called_once()


def test_sync_and_path_selection_reuse_completed_query(path_popup):
    state = path_popup
    state.qtbot.keyClicks(state.line, ":e al")
    wait_for_paths(state)

    for _ in range(3):
        state.controller.sync()
        select_next(state)
        state.qtbot.keyPress(state.line, Qt.Key_P, Qt.ControlModifier)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    state.qtbot.wait(160)

    assert state.line.text() == ":e alpine.json"
    state.scans.assert_called_once()


def test_fast_edits_scan_only_final_input_and_cache_empty_results(path_popup):
    state = path_popup
    state.qtbot.keyClicks(state.line, ":e a")
    state.qtbot.keyPress(state.line, Qt.Key_Backspace)
    state.qtbot.keyClicks(state.line, "missing")
    state.scans.assert_not_called()

    state.qtbot.waitUntil(lambda: state.scans.call_count == 1, timeout=2000)
    for _ in range(3):
        state.controller.sync()
    state.qtbot.wait(160)

    assert state.line.text() == ":e missing"
    assert path_rows(state) == []
    assert not shown(state)
    state.scans.assert_called_once()


def test_old_paths_disappear_during_next_query_while_history_remains(path_popup):
    state = path_popup
    state.line.histories["ex"][:] = ["e alphabet.py"]
    state.qtbot.keyClicks(state.line, ":e a")
    wait_for_paths(state)

    state.qtbot.keyClicks(state.line, "lphab")

    assert path_rows(state) == []
    assert history_bodies(state) == ["e alphabet.py"]
    assert state.controller.selected_index is None
    assert state.scans.call_count == 1
    state.qtbot.waitUntil(lambda: state.scans.call_count == 2, timeout=2000)
    assert history_bodies(state) == ["e alphabet.py"]
    assert path_rows(state) == []


@pytest.mark.parametrize(
    "transition", ["escape", "setting", "focus", "deactivate", "editor"]
)
def test_pending_path_query_is_cancelled_on_lifecycle_transition(
    path_popup, transition
):
    state = path_popup
    state.qtbot.keyClicks(state.line, ":e al")
    state.scans.assert_not_called()

    if transition == "escape":
        state.qtbot.keyPress(state.line, Qt.Key_Escape)
    elif transition == "setting":
        CONF.set(CONF_SECTION, "commandline_completion_enabled", False)
        state.widget.apply_settings()
    elif transition == "focus":
        state.editor.setFocus()
    elif transition == "deactivate":
        QCoreApplication.sendEvent(state.line.window(), QEvent(QEvent.WindowDeactivate))
    else:
        state.stack.set_stack_index(1)
        state.vim._use_stack(state.stack)
    state.qtbot.wait(160)

    state.scans.assert_not_called()
    assert path_rows(state) == []
    assert not shown(state)


@pytest.mark.parametrize("suppression", ["recording", "playback", "dot"])
def test_pending_path_query_is_invalidated_by_macro_and_dot(path_popup, suppression):
    state = path_popup
    state.qtbot.keyClicks(state.line, ":e al")
    if suppression == "recording":
        state.status.manager_macro.start_record("a")
    elif suppression == "playback":
        state.widget._macro_generation = 1
    else:
        state.status.running_dot_cmd = True
    state.controller.sync()
    state.qtbot.wait(160)

    state.scans.assert_not_called()
    assert path_rows(state) == []
    assert not shown(state)


def test_ime_cancels_pending_query_and_resumes_after_composition(path_popup):
    state = path_popup
    state.qtbot.keyClicks(state.line, ":e a")
    send_ime(state, preedit="한")
    state.qtbot.wait(160)
    state.scans.assert_not_called()
    assert not shown(state)

    send_ime(state)
    wait_for_paths(state)

    assert state.line.text() == ":e a"
    assert state.controller.selected_index is None
    state.scans.assert_called_once()


@pytest.mark.parametrize("change_input", [False, True])
def test_expired_path_timer_defers_until_outer_input_finishes(path_popup, change_input):
    state = path_popup
    state.qtbot.keyClicks(state.line, ":e a")

    with state.widget.input_processing():
        if change_input:
            state.line.setText(":e al")
            state.line.setCursorPosition(len(state.line.text()))
        state.qtbot.wait(160)
        state.controller.sync()
        state.scans.assert_not_called()
        assert not shown(state)

    wait_for_paths(state)

    assert state.line.text() == (":e al" if change_input else ":e a")
    assert path_rows(state) == [":e alpha.py", ":e alpine.json"]
    assert state.controller.selected_index is None
    state.scans.assert_called_once()


def test_completed_paths_are_invalidated_when_cwd_changes(path_popup, monkeypatch):
    state = path_popup
    state.qtbot.keyClicks(state.line, ":e ")
    wait_for_paths(state)
    select_next(state)

    monkeypatch.chdir(state.root / "src")
    state.controller.sync()

    assert path_rows(state) == []
    assert state.controller.selected_index is None
    wait_for_paths(state)
    assert path_rows(state) == [":e child.toml"]
    assert state.scans.call_count == 2


def test_directory_history_recall_waits_for_real_edit(path_popup):
    state = path_popup
    state.line.histories["ex"][:] = ["e src" + os.sep]
    state.qtbot.keyClicks(state.line, ":e s")
    state.qtbot.keyPress(state.line, Qt.Key_Up)

    state.qtbot.wait(160)
    state.controller.sync()

    assert state.line.text() == ":e src" + os.sep
    assert not shown(state)
    state.scans.assert_not_called()
    state.qtbot.keyClicks(state.line, "c")
    wait_for_paths(state)
    assert path_rows(state) == [":e src" + os.sep + "child.toml"]
    state.scans.assert_called_once()


def test_directory_acceptance_automatically_lists_unselected_children(
    path_popup, monkeypatch
):
    state = path_popup
    state.line.histories["ex"][:] = ["e src" + os.sep]
    state.qtbot.keyClicks(state.line, ":e s")
    wait_for_paths(state)
    select_next(state)
    original = state.editor.toPlainText()

    def unexpected_path_check(*args, **kwargs):
        pytest.fail("Accepting a directory must use the cached candidate metadata")

    with monkeypatch.context() as patch:
        patch.setattr(os.path, "isdir", unexpected_path_check)
        patch.setattr(os.path, "isfile", unexpected_path_check)
        state.qtbot.keyPress(state.line, Qt.Key_Return)

    state.qtbot.waitUntil(
        lambda: path_rows(state) == [":e src" + os.sep + "child.toml"], timeout=2000
    )
    assert state.line.text() == ":e src" + os.sep
    assert state.status.sub_mode is not None
    assert state.controller.selected_index is None
    assert state.controller.popup.list_widget.currentRow() == -1
    assert state.line.histories["ex"] == ["e src" + os.sep]
    assert state.editor.toPlainText() == original
    assert state.scans.call_count == 2


def test_directory_acceptance_can_descend_through_nested_directories(path_popup):
    state = path_popup
    nested = state.root / "docs" / "nested"
    nested.mkdir(parents=True)
    (nested / "leaf.py").touch()
    state.qtbot.keyClicks(state.line, ":e docs")
    wait_for_paths(state)

    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    state.qtbot.waitUntil(
        lambda: path_rows(state) == [":e docs" + os.sep + "nested" + os.sep],
        timeout=2000,
    )
    assert state.line.text() == ":e docs" + os.sep
    assert state.controller.selected_index is None

    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    state.qtbot.waitUntil(
        lambda: path_rows(state)
        == [":e docs" + os.sep + "nested" + os.sep + "leaf.py"],
        timeout=2000,
    )
    assert state.line.text() == ":e docs" + os.sep + "nested" + os.sep
    assert state.controller.selected_index is None
    assert state.line.histories["ex"] == []
    assert state.scans.call_count == 3


def test_enter_without_selecting_child_executes_current_directory_command(
    path_popup, monkeypatch
):
    state = path_popup
    execute = Mock()
    monkeypatch.setattr(ExecutorColon, "e", execute)
    state.qtbot.keyClicks(state.line, ":e s")
    wait_for_paths(state)
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    state.qtbot.waitUntil(
        lambda: path_rows(state) == [":e src" + os.sep + "child.toml"], timeout=2000
    )
    execute.assert_not_called()
    assert state.controller.selected_index is None

    state.qtbot.keyPress(state.line, Qt.Key_Return)

    execute.assert_called_once_with("src" + os.sep)
    assert state.line.text() == ""
    assert state.status.sub_mode is None
    assert state.line.histories["ex"] == ["e src" + os.sep]
    assert not shown(state)


def test_cursor_move_invalidates_completed_path_query(path_popup):
    state = path_popup
    state.qtbot.keyClicks(state.line, ":e al")
    wait_for_paths(state)

    state.line.setCursorPosition(4)

    assert path_rows(state) == []
    state.scans.assert_called_once()
    wait_for_paths(state)
    assert path_rows(state) == [":e alpha.py", ":e alpine.json"]
    assert state.scans.call_count == 2
    assert state.line.text() == ":e al"
    assert state.line.cursorPosition() == 4


def test_reenabling_completion_queries_after_discarding_old_path_cache(path_popup):
    state = path_popup
    state.qtbot.keyClicks(state.line, ":e al")
    wait_for_paths(state)
    CONF.set(CONF_SECTION, "commandline_completion_enabled", False)
    state.widget.apply_settings()
    assert path_rows(state) == []
    assert not shown(state)
    state.qtbot.wait(160)
    state.scans.assert_called_once()

    CONF.set(CONF_SECTION, "commandline_completion_enabled", True)
    state.widget.apply_settings()
    wait_for_paths(state)

    assert path_rows(state) == [":e alpha.py", ":e alpine.json"]
    assert state.scans.call_count == 2
    assert state.controller.selected_index is None


def test_cancelled_callback_cannot_reuse_same_input_after_composition(path_popup):
    state = path_popup
    state.qtbot.keyClicks(state.line, ":e al")
    previous_callback = state.controller._path_callback
    send_ime(state, preedit="한")
    send_ime(state)
    assert state.line.text() == ":e al"

    previous_callback()

    state.scans.assert_not_called()
    assert path_rows(state) == []
    wait_for_paths(state)
    assert path_rows(state) == [":e alpha.py", ":e alpine.json"]
    state.scans.assert_called_once()


def test_repeated_sync_does_not_postpone_unchanged_pending_query(path_popup):
    state = path_popup
    state.qtbot.keyClicks(state.line, ":e al")

    for _ in range(6):
        state.qtbot.wait(25)
        state.controller.sync()

    assert path_rows(state) == [":e alpha.py", ":e alpine.json"]
    state.scans.assert_called_once()


@pytest.fixture
def blocked_path_lookup(path_popup, monkeypatch):
    """Hold a filesystem worker while allowing the GUI event loop to continue."""
    from spyder_okvim.spyder import commandline_path_lookup

    state = path_popup
    lookup = commandline_path_lookup.path_completion_items
    state.lookup_started = Event()
    state.lookup_released = Event()
    state.lookup_finished = Event()

    def blocked(request, cancelled=None):
        state.lookup_started.set()
        try:
            if not state.lookup_released.wait(timeout=5):
                raise AssertionError("test did not release the path lookup")
            return lookup(request, cancelled)
        finally:
            state.lookup_finished.set()

    state.lookup = Mock(side_effect=blocked)
    monkeypatch.setattr(commandline_path_lookup, "path_completion_items", state.lookup)
    try:
        yield state
    finally:
        state.lookup_released.set()
        if state.lookup_started.is_set():
            state.qtbot.waitUntil(state.lookup_finished.is_set, timeout=2000)
            # Deliver the queued worker completion before restoring the fixture.
            state.qtbot.wait(30)


def start_blocked_lookup(state):
    state.qtbot.keyClicks(state.line, ":e a")
    state.qtbot.waitUntil(state.lookup_started.is_set, timeout=2000)
    assert not state.lookup_finished.is_set()
    assert not shown(state)


def finish_blocked_lookup(state):
    state.lookup_released.set()
    state.qtbot.waitUntil(state.lookup_finished.is_set, timeout=2000)
    state.qtbot.wait(30)


def test_worker_result_waits_for_outer_input_without_repeating_lookup(
    blocked_path_lookup,
):
    state = blocked_path_lookup
    start_blocked_lookup(state)

    with state.widget.input_processing():
        finish_blocked_lookup(state)
        state.qtbot.waitUntil(
            lambda: state.controller._path_deferred is not None, timeout=2000
        )
        state.controller.sync()
        assert path_rows(state) == []
        assert not shown(state)
        state.lookup.assert_called_once()

    wait_for_paths(state)

    assert path_rows(state) == [":e alpha.py", ":e alpine.json"]
    state.lookup.assert_called_once()
    state.scans.assert_called_once()


@pytest.mark.parametrize("transition", ["edit", "cancel"])
def test_deferred_worker_result_is_discarded_when_input_changes(
    blocked_path_lookup, transition
):
    state = blocked_path_lookup
    start_blocked_lookup(state)

    with state.widget.input_processing():
        finish_blocked_lookup(state)
        state.qtbot.waitUntil(
            lambda: state.controller._path_deferred is not None, timeout=2000
        )
        assert not shown(state)
        if transition == "edit":
            state.line.setText(":e s")
            state.line.setCursorPosition(len(state.line.text()))
        else:
            state.line.esc_pressed()
        assert path_rows(state) == []

    if transition == "edit":
        wait_for_paths(state)
        assert path_rows(state) == [":e src" + os.sep]
        assert state.lookup.call_count == 2
    else:
        state.qtbot.wait(160)
        assert state.line.text() == ""
        assert state.status.sub_mode is None
        assert path_rows(state) == []
        assert not shown(state)
        state.lookup.assert_called_once()


def test_slow_path_worker_keeps_typing_and_escape_responsive(blocked_path_lookup):
    state = blocked_path_lookup
    start_blocked_lookup(state)
    started = perf_counter()

    state.qtbot.keyClicks(state.line, "l")
    assert state.line.text() == ":e al"
    state.qtbot.keyPress(state.line, Qt.Key_Escape)

    assert perf_counter() - started < 0.2
    assert not state.lookup_finished.is_set()
    assert state.line.text() == ""
    assert state.status.sub_mode is None
    assert not shown(state)
    finish_blocked_lookup(state)
    state.qtbot.wait(160)
    assert path_rows(state) == []
    assert not shown(state)
    state.lookup.assert_called_once()


def test_cleanup_does_not_wait_for_worker_and_ignores_late_result(blocked_path_lookup):
    state = blocked_path_lookup
    state.qtbot.keyClicks(state.line, ":e a")
    state.controller.cancel()
    controller = type(state.controller)(state.widget)
    controller.set_editor(state.editor)
    controller.sync()
    state.qtbot.waitUntil(state.lookup_started.is_set, timeout=2000)
    assert not state.lookup_finished.is_set()
    started = perf_counter()

    controller.cleanup()

    assert perf_counter() - started < 0.2
    assert not state.lookup_finished.is_set()
    assert controller.popup is None
    assert controller.candidates == []
    finish_blocked_lookup(state)
    assert controller.popup is None
    assert controller.candidates == []
    state.lookup.assert_called_once()
    controller.deleteLater()


@pytest.mark.parametrize("transition", ["setting", "escape"])
def test_directory_child_lookup_cannot_show_popup_after_cancellation(
    blocked_path_lookup, transition
):
    state = blocked_path_lookup
    state.lookup_released.set()
    state.qtbot.keyClicks(state.line, ":e s")
    wait_for_paths(state)
    state.lookup_started.clear()
    state.lookup_finished.clear()
    state.lookup_released.clear()
    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    state.qtbot.waitUntil(state.lookup_started.is_set, timeout=2000)
    assert state.line.text() == ":e src" + os.sep
    assert not state.lookup_finished.is_set()

    if transition == "setting":
        CONF.set(CONF_SECTION, "commandline_completion_enabled", False)
        state.widget.apply_settings()
    else:
        state.qtbot.keyPress(state.line, Qt.Key_Escape)
    finish_blocked_lookup(state)
    state.qtbot.wait(160)

    assert path_rows(state) == []
    assert not shown(state)
    assert state.controller.selected_index is None
    assert state.lookup.call_count == 2


def test_directory_acceptance_preserves_quoted_emoji_suffix_and_advances_cursor(
    path_popup,
):
    state = path_popup
    directory = "docs 😀"
    nested = state.root / directory / "nested"
    nested.mkdir(parents=True)
    (nested / "leaf.py").touch()
    state.qtbot.keyClicks(
        state.line, ':e "do' + os.sep + "nested" + os.sep + 'leaf.py"'
    )
    state.line.setCursorPosition(len(':e "do'))
    wait_for_paths(state)
    expected = ':e "' + directory + os.sep + "nested" + os.sep + 'leaf.py"'
    assert path_rows(state) == [expected]

    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    state.qtbot.waitUntil(lambda: state.scans.call_count == 2, timeout=2000)
    wait_for_paths(state)

    assert state.line.text() == expected
    assert (
        state.line.cursorPosition()
        == len((':e "' + directory + os.sep).encode("utf-16-le")) // 2
    )
    assert path_rows(state) == [expected]
    assert state.controller.selected_index is None

    select_next(state)
    state.qtbot.keyPress(state.line, Qt.Key_Return)
    state.qtbot.waitUntil(lambda: state.scans.call_count == 3, timeout=2000)
    wait_for_paths(state)

    assert state.line.text() == expected
    assert (
        state.line.cursorPosition()
        == len((':e "' + directory + os.sep + "nested" + os.sep).encode("utf-16-le"))
        // 2
    )
    assert path_rows(state) == [expected]
    assert state.controller.selected_index is None
    assert state.line.histories["ex"] == []
