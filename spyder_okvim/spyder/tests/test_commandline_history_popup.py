"""History suggestions share the existing command-line input and lifetime."""

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
