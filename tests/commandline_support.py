"""Shared command-line integration fixtures and interaction helpers.

History suggestions, substitute guidance, preview overlays and their opt-in
benchmarks exercise one input/view lifetime. Keep their setup and event helpers
here so collecting one test module never imports another module's test cases.
Only GUI integration tests import this module; pure tests keep Qt/Spyder lazy.
"""

# Standard Libraries
from types import SimpleNamespace

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QInputMethodEvent
from qtpy.QtWidgets import QPlainTextEdit
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from tests.qt_support import reset_vim_state


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
    reset_vim_state(status)
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
    """Check visibility without updating passive suggestion state."""
    popup = state.controller.popup
    return popup is not None and popup.isVisible()


def show(state, prefix=":", history=("old", "new"), kind="ex"):
    """Seed one history kind and open its interactive prompt."""
    state.line.histories[kind][:] = history
    state.qtbot.keyClicks(state.line, prefix)
    assert shown(state)
    return state.controller.popup


def select_next(state):
    """Select the next passive suggestion through the real input widget."""
    state.qtbot.keyPress(state.line, Qt.Key_N, Qt.ControlModifier)


def send_ime(state, preedit="", commit=""):
    """Deliver native-style composition/commit without ASCII key simulation."""
    event = QInputMethodEvent(preedit, [])
    event.setCommitString(commit)
    QCoreApplication.sendEvent(state.line, event)


@pytest.fixture
def preview(history_popup):
    """Use the real input lifecycle with isolated preview settings and timers."""
    state = history_popup
    state.preview = state.widget.substitute_preview
    preferences = {
        name: CONF.get(CONF_SECTION, name, True)
        for name in ("substitute_preview_enabled", "substitute_guide_enabled")
    }
    old_interval = state.preview._timer.interval()
    old_limits = state.preview.limits
    old_read_only = state.editor.isReadOnly()
    CONF.set(CONF_SECTION, "substitute_preview_enabled", True)
    CONF.set(CONF_SECTION, "substitute_guide_enabled", True)
    state.widget.apply_settings()
    state.preview._timer.setInterval(0)
    try:
        yield state
    finally:
        state.preview.cancel()
        state.preview._timer.setInterval(old_interval)
        state.preview.limits = old_limits
        state.editor.setReadOnly(old_read_only)
        for name, value in preferences.items():
            CONF.set(CONF_SECTION, name, value)
        state.widget.apply_settings()


def enter_command(state, command):
    """Replace a complete Ex draft, including Unicode and middle edits."""
    if state.status.sub_mode is None:
        state.qtbot.keyClicks(state.line, ":")
    state.line.setText(command)


def result(state):
    """Wait for the current bounded preview result after GUI delivery."""
    state.qtbot.waitUntil(lambda: state.preview.result is not None)
    return state.preview.result


def assert_no_replacement_panel(state):
    """Replacement text never appears in a second view while typing."""
    assert not hasattr(state.controller, "preview_popup")
    assert state.editor.viewport().findChild(QPlainTextEdit) is None


def selections(state):
    """Return preview-owned extra selections without changing the document."""
    return state.editor.get_extra_selections("vim_substitute_preview")
