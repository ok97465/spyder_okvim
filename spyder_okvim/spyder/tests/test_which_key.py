"""Prefix hints observe command execution without taking keyboard focus."""

# Standard Libraries
import os.path as osp
from types import SimpleNamespace
import weakref

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QPoint, QRect, QSize, Qt
from qtpy.QtWidgets import QAbstractScrollArea
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.spyder.which_key import display_key
from spyder_okvim.vim import KeyInfo, VimState


@pytest.fixture
def which_key(vim_bot, qtbot):
    """Enable hints only here and restore the session UI before flushing events."""
    main, stack, _, vim, _ = vim_bot
    widget = vim.vim_cmd
    controller = widget.which_key
    commandline = widget.commandline
    previous_index = stack.get_stack_index()
    previous_config = {
        key: CONF.get(CONF_SECTION, key, default=default)
        for key, default in (
            ("which_key_enabled", False),
            ("which_key_delay", 300),
            ("leader_key", "Space"),
        )
    }
    controller.cancel()
    stack.set_stack_index(0)
    vim._use_stack(stack)
    editor = stack.get_current_editor()
    previous_text = editor.toPlainText()
    widget.cancel_macro()
    commandline.esc_pressed()
    widget.vim_status.reset_for_test()
    editor.set_text("alpha beta\nsecond line\nthird alpha\n")
    widget.vim_status.cursor.set_cursor_pos(0)
    CONF.set(CONF_SECTION, "which_key_enabled", True)
    CONF.set(CONF_SECTION, "which_key_delay", 20)
    CONF.set(CONF_SECTION, "leader_key", "Space")
    vim.apply_plugin_settings("")
    main.show()
    main.activateWindow()
    commandline.setFocus()
    qtbot.waitUntil(commandline.hasFocus)
    state = SimpleNamespace(
        main=main,
        stack=stack,
        vim=vim,
        widget=widget,
        controller=controller,
        commandline=commandline,
        editor=editor,
        status=widget.vim_status,
        qtbot=qtbot,
    )
    try:
        yield state
    finally:
        controller.cancel()
        widget.cancel_macro()
        if widget.worker_macro.isRunning():
            widget.worker_macro.wait()
        commandline.esc_pressed()
        widget.vim_status.finish_insert(apply_count=False)
        widget.vim_status.disconnect_from_editor()
        editor.set_text(previous_text)
        for key, value in previous_config.items():
            CONF.set(CONF_SECTION, key, value)
        widget.set_leader_key()
        controller.cancel()
        stack.set_stack_index(previous_index)
        vim._use_stack(stack)
        main.activateWindow()
        commandline.setFocus()


def _shown(state):
    popup = state.controller.popup
    return popup is not None and popup.isVisible()


def _show(state, prefix=" "):
    state.qtbot.keyClicks(state.commandline, prefix)
    state.qtbot.waitUntil(lambda: _shown(state))
    return state.controller.popup


def _stays_hidden(state):
    # Exceed the small test delay, including zero-delay queued delivery.
    state.qtbot.wait(state.controller.delay + 15)
    assert not _shown(state)
    assert not state.controller.timer.isActive()


def _seed_prefix_hints(state):
    """Provide a local mark and named register without changing the cursor."""
    filename = state.stack.get_current_filename()
    state.status.bookmarks[filename]["a"] = {
        "file": filename,
        "line": 1,
        "col": 2,
    }
    state.status.set_register("a", "saved text", VimState.NORMAL)


def _candidate_texts(popup):
    return {
        key.text(): description.text() for key, description in popup.candidate_labels
    }


@pytest.mark.parametrize(
    "mode_prefix, mode, prefix",
    [
        (mode_prefix, mode, prefix)
        for mode_prefix, mode in (
            ("", VimState.NORMAL),
            ("vl", VimState.VISUAL),
            ("Vj", VimState.VLINE),
        )
        for prefix in ("g", "'", '"')
    ]
    + [("", VimState.NORMAL, "z")],
)
def test_delayed_prefix_hints_preserve_mode_selection_and_focus(
    which_key, mode_prefix, mode, prefix
):
    state = which_key
    _seed_prefix_hints(state)
    state.qtbot.keyClicks(state.commandline, mode_prefix)
    before = [
        selection.cursor.selectedText()
        for selection in state.editor.get_extra_selections("vim_selection")
    ]
    position = state.editor.textCursor().position()
    state.qtbot.keyClicks(state.commandline, prefix)
    executor = state.status.sub_mode
    assert executor is not None
    assert state.commandline.text() == ""
    assert not _shown(state)
    state.qtbot.waitUntil(lambda: _shown(state))
    popup = state.controller.popup
    candidates = _candidate_texts(popup)
    if prefix == "g":
        assert set(candidates) == set("gdtTuUc~")
    elif prefix == "z":
        assert set(candidates) == set("ztb")
    elif prefix == "'":
        assert set(candidates) == {"a"}
    else:
        assert {'"', "0", "-", "+", "_", "a"} <= set(candidates)
    assert popup.header.text().endswith(prefix)
    assert state.status.sub_mode is executor
    assert state.status.vim_state == mode
    assert state.editor.textCursor().position() == position
    assert state.commandline.hasFocus()
    assert [
        selection.cursor.selectedText()
        for selection in state.editor.get_extra_selections("vim_selection")
    ] == before
    assert popup.parentWidget() is state.editor.viewport()


@pytest.mark.parametrize(
    "prefix, completion", [("g", "g"), ("z", "z"), ("'", "a"), ('"', "a")]
)
def test_completed_prefix_hides_and_reuses_popup(which_key, prefix, completion):
    state = which_key
    _seed_prefix_hints(state)
    popup = _show(state, prefix)
    state.qtbot.keyClicks(state.commandline, completion)
    assert state.status.sub_mode is None
    _stays_hidden(state)
    assert _show(state, prefix) is popup


@pytest.mark.parametrize("prefix", ["g", "z", "'", '"'])
@pytest.mark.parametrize("key", [Qt.Key_Escape, Qt.Key_Backspace, Qt.Key_Question])
def test_prefix_cancellation_hides_hints(which_key, prefix, key):
    state = which_key
    _seed_prefix_hints(state)
    _show(state, prefix)
    state.qtbot.keyClick(state.commandline, key)
    assert state.status.sub_mode is None
    assert state.commandline.hasFocus()
    _stays_hidden(state)


@pytest.mark.parametrize(
    "prefix, completion", [("g", "g"), ("z", "z"), ("'", "a"), ('"', "ap")]
)
def test_prefix_hints_preserve_execution(which_key, prefix, completion):
    state = which_key
    results = []
    for enabled in (False, True):
        state.commandline.esc_pressed()
        state.status.reset_for_test()
        state.editor.set_text("alpha beta\nsecond line\nthird alpha\n")
        _seed_prefix_hints(state)
        state.status.cursor.set_cursor_pos(12)
        CONF.set(CONF_SECTION, "which_key_enabled", enabled)
        state.vim.apply_plugin_settings("")
        state.qtbot.keyClicks(state.commandline, prefix)
        if enabled:
            state.qtbot.waitUntil(lambda: _shown(state))
        state.qtbot.keyClicks(state.commandline, completion)
        _stays_hidden(state)
        results.append(
            (
                state.editor.toPlainText(),
                state.editor.textCursor().position(),
                state.status.vim_state,
                {
                    name: (info.content, info.type)
                    for name, info in state.status.register_dict.items()
                },
            )
        )
    assert results[0] == results[1]


@pytest.mark.parametrize("command", ["gg", "zz", "'a", '"ap'])
def test_fast_prefix_commands_do_not_show_hints(which_key, command):
    state = which_key
    _seed_prefix_hints(state)
    state.qtbot.keyClicks(state.commandline, command)
    assert state.status.sub_mode is None
    _stays_hidden(state)


@pytest.mark.parametrize("prefix", ["3g", "2z", "dg", "d'"])
def test_counted_and_operator_prefix_hints_use_the_active_executor(which_key, prefix):
    state = which_key
    _seed_prefix_hints(state)
    popup = _show(state, prefix)
    assert popup.header.text().endswith(prefix[-1])
    candidates = _candidate_texts(popup)
    if prefix == "dg":
        assert set(candidates) == {"g"}
    elif prefix == "d'":
        assert set(candidates) == {"a"}


def test_g_operator_transition_hides_completed_prefix_hints(which_key):
    state = which_key
    _show(state, "g")
    state.qtbot.keyClicks(state.commandline, "u")
    assert state.status.sub_mode is not None
    _stays_hidden(state)


def test_bookmark_hints_include_current_local_and_global_marks_only(which_key):
    state = which_key
    _seed_prefix_hints(state)
    filename = state.stack.get_current_filename()
    other = next(path for path in state.stack.get_filenames() if path != filename)
    state.status.bookmarks[other]["b"] = {"file": other, "line": 0, "col": 0}
    state.status.bookmarks_global["A"] = {"file": other, "line": 2, "col": 0}
    popup = _show(state, "'")
    candidates = _candidate_texts(popup)
    assert set(candidates) == {"a", "A"}
    assert candidates["a"].endswith(":2")
    assert candidates["A"].endswith(":3")
    assert osp.basename(other) in candidates["A"]


def test_register_previews_do_not_create_or_modify_registers(which_key):
    state = which_key
    content = "first\nsecond\t" + "x" * 100
    state.status.set_register("a", content, VimState.NORMAL)
    before = {
        name: (info.content, info.type)
        for name, info in state.status.register_dict.items()
    }
    candidates = _candidate_texts(_show(state, '"'))
    assert "first" in candidates["a"]
    assert "\n" not in candidates["a"]
    assert "\t" not in candidates["a"]
    assert len(candidates["a"]) < 100
    assert {
        name: (info.content, info.type)
        for name, info in state.status.register_dict.items()
    } == before


@pytest.mark.parametrize("prefix", ["g", "z", "'", '"'])
def test_prefix_hints_follow_enabled_setting_and_focus(which_key, prefix):
    state = which_key
    _seed_prefix_hints(state)
    _show(state, prefix)
    executor = state.status.sub_mode
    CONF.set(CONF_SECTION, "which_key_enabled", False)
    state.vim.apply_plugin_settings("")
    _stays_hidden(state)
    assert state.status.sub_mode is executor
    CONF.set(CONF_SECTION, "which_key_enabled", True)
    state.vim.apply_plugin_settings("")
    state.qtbot.waitUntil(lambda: _shown(state))
    state.editor.setFocus()
    _stays_hidden(state)
    state.commandline.setFocus()
    state.qtbot.waitUntil(lambda: _shown(state))
    assert state.status.sub_mode is executor


def test_apostrophe_without_marks_does_not_show_an_empty_popup(which_key):
    state = which_key
    state.qtbot.keyClicks(state.commandline, "'")
    _stays_hidden(state)


@pytest.mark.parametrize(
    "prefix, mode",
    [("", VimState.NORMAL), ("v", VimState.VISUAL), ("V", VimState.VLINE)],
)
def test_delayed_leader_hints_preserve_mode_selection_and_focus(
    which_key, prefix, mode
):
    state = which_key
    state.qtbot.keyClicks(state.commandline, prefix)
    selections = state.editor.get_extra_selections("vim_selection")
    before = [selection.cursor.selectedText() for selection in selections]
    state.qtbot.keyClicks(state.commandline, " ")
    assert state.commandline.text() == ""
    assert state.status.sub_mode is state.widget.executor_leader_key
    assert not _shown(state)
    state.qtbot.waitUntil(lambda: _shown(state))
    assert "Space" in state.controller.popup.header.text()
    assert state.status.vim_state == mode
    assert state.commandline.hasFocus()
    after = state.editor.get_extra_selections("vim_selection")
    assert [selection.cursor.selectedText() for selection in after] == before
    assert state.controller.popup.parentWidget() is state.editor.viewport()


def test_fast_command_does_not_wait_for_or_show_hints(which_key):
    state = which_key
    actions = []

    def handler(*args):
        actions.append(args)

    state.stack.sig_trigger_action.connect(handler)
    try:
        state.qtbot.keyClicks(state.commandline, " d")
        assert actions and actions[-1][0] == "run cell in debugger"
        assert state.status.sub_mode is None
        _stays_hidden(state)
    finally:
        state.stack.sig_trigger_action.disconnect(handler)


@pytest.mark.parametrize("prefix", ["", "vl", "Vj"])
def test_hints_do_not_change_leader_execution_or_selection(which_key, prefix):
    state = which_key
    results = []
    executed_selections = []

    def capture_selection(*args):
        executed_selections.append((args, state.editor.textCursor().selectedText()))

    state.stack.sig_trigger_action.connect(capture_selection)
    try:
        for enabled in (False, True):
            state.commandline.esc_pressed()
            state.status.to_normal()
            state.status.cursor.set_cursor_pos(0)
            CONF.set(CONF_SECTION, "which_key_enabled", enabled)
            state.vim.apply_plugin_settings("")
            state.qtbot.keyClicks(state.commandline, prefix + " ")
            if enabled:
                state.qtbot.waitUntil(lambda: _shown(state))
            state.qtbot.keyClicks(state.commandline, "r")
            selections = state.editor.get_extra_selections("vim_selection")
            results.append(
                (
                    state.editor.toPlainText(),
                    state.editor.textCursor().position(),
                    [selection.cursor.selectedText() for selection in selections],
                    state.status.vim_state,
                )
            )
        assert results[0] == results[1]
        assert len(executed_selections) == 2
        assert executed_selections[0] == executed_selections[1]
    finally:
        state.stack.sig_trigger_action.disconnect(capture_selection)


@pytest.mark.parametrize("key", [Qt.Key_Escape, Qt.Key_Backspace, Qt.Key_Question])
def test_escape_backspace_and_invalid_input_hide_hints(which_key, key):
    state = which_key
    _show(state)
    state.qtbot.keyClick(state.commandline, key)
    assert state.status.sub_mode is None
    assert state.commandline.hasFocus()
    _stays_hidden(state)


def test_completed_command_hides_and_reuses_popup(which_key):
    state = which_key
    popup = _show(state)
    state.qtbot.keyClicks(state.commandline, "d")
    _stays_hidden(state)
    assert _show(state) is popup


def test_same_context_keeps_original_timer_deadline(which_key):
    state = which_key
    CONF.set(CONF_SECTION, "which_key_delay", 100)
    state.vim.apply_plugin_settings("")
    state.qtbot.keyClicks(state.commandline, " ")
    state.qtbot.wait(20)
    remaining = state.controller.timer.remainingTime()
    assert remaining > 0
    for _ in range(4):
        state.controller.sync()
    state.vim.apply_plugin_settings("")
    assert 0 < state.controller.timer.remainingTime() <= remaining
    state.qtbot.waitUntil(lambda: _shown(state))


def test_control_key_keeps_same_wait_and_already_displayed_hints(which_key):
    state = which_key
    popup = _show(state)
    state.qtbot.keyClick(state.commandline, Qt.Key_C, Qt.ControlModifier)
    assert state.status.sub_mode is state.widget.executor_leader_key
    assert _shown(state)
    assert state.controller.popup is popup
    assert not state.controller.timer.isActive()


def test_zero_delay_still_waits_for_event_delivery(which_key):
    state = which_key
    CONF.set(CONF_SECTION, "which_key_delay", 0)
    state.vim.apply_plugin_settings("")
    state.qtbot.keyClicks(state.commandline, " ")
    assert state.controller.timer.isActive()
    assert not _shown(state)
    state.qtbot.waitUntil(lambda: _shown(state))


def test_focus_loss_cancels_immediately(which_key):
    state = which_key
    _show(state)
    state.editor.setFocus()
    assert not _shown(state)
    _stays_hidden(state)


def test_returning_focus_rechecks_the_existing_leader_wait(which_key):
    state = which_key
    _show(state)
    state.editor.setFocus()
    assert state.status.sub_mode is state.widget.executor_leader_key
    _stays_hidden(state)
    state.commandline.setFocus()
    state.qtbot.waitUntil(lambda: _shown(state))
    assert state.commandline.hasFocus()


@pytest.mark.parametrize(
    "text", ["i", "/", "?", ":", "j", "2", "m", "`", "q", "@", "dz", "Z"]
)
def test_other_commands_do_not_schedule_hints(which_key, text):
    state = which_key
    _seed_prefix_hints(state)
    state.qtbot.keyClicks(state.commandline, text)
    _stays_hidden(state)


@pytest.mark.parametrize("command", [" ", "g", "z", "'", '"'])
def test_past_input_command_is_not_pending_state(which_key, command):
    state = which_key
    _seed_prefix_hints(state)
    state.status.input_cmd.cmd = command
    state.controller.sync()
    _stays_hidden(state)


def test_settings_cancel_and_recheck_the_pending_command(which_key):
    state = which_key
    _show(state)
    CONF.set(CONF_SECTION, "which_key_enabled", False)
    state.vim.apply_plugin_settings("")
    assert state.status.sub_mode is state.widget.executor_leader_key
    _stays_hidden(state)
    CONF.set(CONF_SECTION, "which_key_enabled", True)
    state.vim.apply_plugin_settings("")
    state.qtbot.waitUntil(lambda: _shown(state))
    CONF.set(CONF_SECTION, "which_key_delay", 50)
    state.vim.apply_plugin_settings("")
    assert not _shown(state)
    assert state.controller.timer.isActive()
    state.qtbot.waitUntil(lambda: _shown(state))
    CONF.set(CONF_SECTION, "leader_key", "Backspace")
    state.vim.apply_plugin_settings("")
    state.qtbot.waitUntil(lambda: _shown(state))
    assert "Backspace" in state.controller.popup.header.text()


def test_input_nested_event_loop_cannot_show_intermediate_state(which_key, monkeypatch):
    state = which_key
    _show(state)
    original = state.widget._process_text

    def process_text(text):
        if text == "d":
            # Simulate an existing command opening a nested Qt event loop while
            # its leader executor is still current.
            state.qtbot.wait(35)
            assert not _shown(state)
        original(text)

    monkeypatch.setattr(state.widget, "_process_text", process_text)
    state.qtbot.keyClicks(state.commandline, "d")
    _stays_hidden(state)


def test_timeout_during_input_rearms_only_after_outer_processing(which_key):
    state = which_key
    state.qtbot.keyClicks(state.commandline, " ")
    with state.widget.input_processing():
        state.qtbot.wait(35)
        assert not _shown(state)
        assert not state.controller.timer.isActive()
    assert state.controller.timer.isActive()
    state.qtbot.waitUntil(lambda: _shown(state))


def test_dot_suppression_and_macro_recording(which_key):
    state = which_key
    state.status.running_dot_cmd = True
    state.qtbot.keyClicks(state.commandline, " ")
    _stays_hidden(state)
    state.commandline.esc_pressed()
    state.status.running_dot_cmd = False
    state.qtbot.keyClicks(state.commandline, "qa")
    assert state.status.is_recording_macro()
    _show(state)
    state.commandline.esc_pressed()
    state.qtbot.keyClicks(state.commandline, "q")
    assert not state.status.is_recording_macro()


def test_macro_suppression_lasts_through_final_gui_key(which_key, monkeypatch):
    state = which_key
    state.status.manager_macro.registers["a"] = [
        KeyInfo(Qt.Key_Space, " ", Qt.NoModifier, 0),
    ]
    original = state.widget._process_text
    last_key = []

    def process_text(text):
        original(text)
        if text == " " and state.widget._macro_playing:
            # The thread can already be finished while its final GUI slot and
            # queued completion signal still have work to do.
            state.qtbot.wait(35)
            assert state.widget._macro_playing
            assert not _shown(state)
            last_key.append(True)

    monkeypatch.setattr(state.widget, "_process_text", process_text)
    state.qtbot.keyClicks(state.commandline, "@a")
    assert state.widget._macro_playing
    state.qtbot.waitUntil(lambda: not state.widget._macro_playing)
    assert last_key
    assert state.status.sub_mode is state.widget.executor_leader_key
    state.qtbot.waitUntil(lambda: _shown(state))


def test_cancelled_or_old_macro_completion_cannot_release_current_playback(which_key):
    state = which_key
    widget = state.widget
    widget._macro_generation = 12
    widget._macro_editor = weakref.ref(state.editor)
    widget._macro_playing = True
    with widget.input_processing():
        widget._finish_macro(11)
        assert widget._macro_playing
        widget._finish_macro(12)
        assert widget._macro_completion == 12
        widget.cancel_macro()
        assert widget._macro_completion is None
        widget._macro_generation = 13
        widget._macro_editor = weakref.ref(state.editor)
        widget._macro_playing = True
        widget._finish_macro(12)
    assert widget._macro_playing
    assert widget._macro_generation == 13
    widget._finish_macro(13)
    assert not widget._macro_playing


def test_easymotion_transition_hides_leader_hints(which_key):
    state = which_key
    _show(state)
    state.qtbot.keyClicks(state.commandline, " ")
    assert state.status.sub_mode is not state.widget.executor_leader_key
    _stays_hidden(state)


@pytest.mark.parametrize("size", [(360, 260), (700, 400)])
def test_compact_popup_shows_every_candidate_without_scrolling(which_key, size):
    state = which_key
    popup = _show(state)
    viewport = state.editor.viewport()
    editor = state.editor
    previous_size = editor.size()
    previous_minimum = editor.minimumSize()
    previous_maximum = editor.maximumSize()
    try:
        editor.setFixedSize(
            editor.width() - viewport.width() + size[0],
            editor.height() - viewport.height() + size[1],
        )
        QCoreApplication.processEvents()
        assert viewport.size() == QSize(*size)
        assert viewport.rect().contains(popup.geometry())
        assert popup.column_count >= 2
        assert not popup.findChildren(QAbstractScrollArea)
        assert popup.font().pointSizeF() < state.commandline.font().pointSizeF()
        assert len(popup.candidate_labels) == len(
            state.widget.executor_leader_key.get_hint_candidates()
        )
        for labels in popup.candidate_labels:
            for label in labels:
                bounds = QRect(label.mapTo(popup, QPoint(0, 0)), label.size())
                assert label.isVisible()
                assert popup.contentsRect().contains(bounds)
                if label.hasHeightForWidth():
                    assert label.height() >= label.heightForWidth(label.width())
        assert popup.focusPolicy() == Qt.NoFocus
        assert state.commandline.hasFocus()
    finally:
        editor.setMinimumSize(previous_minimum)
        editor.setMaximumSize(previous_maximum)
        editor.resize(previous_size)


@pytest.mark.parametrize(
    "key, label",
    [
        (" ", "Space"),
        ("\r", "Enter"),
        ("\b", "Backspace"),
        ("\t", "Tab"),
        ("d", "d"),
        ("D", "D"),
    ],
)
def test_readable_key_names_preserve_case(key, label):
    assert display_key(key) == label
