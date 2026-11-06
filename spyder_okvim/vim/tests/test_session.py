"""Cancelled session timers cannot refocus or alter a closed/switched view."""

# Standard Libraries
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import QEvent, Qt, QTimer
from qtpy.QtGui import QKeyEvent

# Project Libraries
from tests.qt_support import reset_vim_state


def test_delayed_focus_tolerates_no_active_editor(vim_bot, monkeypatch):
    """A close notification can arrive after the last editor has disappeared."""
    _, _, _, vim, qtbot = vim_bot
    status = vim.vim_cmd.vim_status
    reset_vim_state(status)
    with monkeypatch.context() as patch:
        focus = Mock()
        patch.setattr(status, "get_editor", lambda: None)
        patch.setattr(status, "set_focus_to_vim", focus)
        status.set_focus_to_vim_after_delay(0)
        qtbot.wait(10)
        focus.assert_not_called()


@pytest.mark.parametrize("reset_view", [False, True])
def test_cancelled_definition_callbacks_leave_jump_history_unchanged(
    vim_bot, reset_view
):
    """Late watch/deadline events must not add or remove navigation entries."""
    _, _, _, vim, _ = vim_bot
    status = vim.vim_cmd.vim_status
    reset_vim_state(status)
    previous = status.get_current_location()
    status.push_jump()
    expected = list(status.jump_list.jumps)
    status.start_definition_tracking(previous)
    if reset_view:
        vim._reset_view()
    else:
        status.cancel_pending_work()

    status._definition_watch.timeout.emit()
    status._definition_deadline.timeout.emit()

    assert status.jump_list.jumps == expected
    assert status.timer_go_to_definition is None
    assert not status._definition_watch.isActive()
    assert not status._definition_deadline.isActive()


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("destination_position", [0, 10])
def test_definition_tracking_survives_editor_switch(
    vim_bot, monkeypatch, asynchronous, destination_position
):
    """Spyder binds the destination editor before placing its definition cursor."""
    _, stack, _, vim, qtbot = vim_bot
    status = vim.vim_cmd.vim_status
    previous_index = stack.get_stack_index()
    stack.set_stack_index(0)
    vim._on_editor_focus_changed()
    reset_vim_state(status)
    status.cursor.set_cursor_pos(2)
    origin = status.get_current_location()
    destination_file = stack.get_filenames()[1]
    destination_editor = stack.data[1].editor
    previous_destination_text = destination_editor.toPlainText()
    destination_editor.set_text("definition target\n")
    destination = (destination_file, destination_position)

    def arrive():
        stack.set_current_filename(destination_file)
        vim._on_editor_focus_changed()
        status.cursor.set_cursor_pos(destination_position)

    def go_to_definition(self, cursor=None):
        if asynchronous:
            QTimer.singleShot(0, arrive)
        else:
            arrive()

    monkeypatch.setattr(
        type(status.get_editor()), "go_to_definition_from_cursor", go_to_definition
    )
    commandline = vim.vim_cmd.commandline
    try:
        qtbot.keyClicks(commandline, "gd")
        qtbot.waitUntil(lambda: len(status.jump_list.jumps) == 2, timeout=1000)

        assert [(jump.file, jump.pos) for jump in status.jump_list.jumps] == [
            origin,
            destination,
        ]
        assert status.timer_go_to_definition is None
        assert not status._definition_deadline.isActive()

        commandline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_O, Qt.ControlModifier)
        )
        vim._on_editor_focus_changed()
        assert status.get_current_location() == origin
        commandline.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_I, Qt.ControlModifier)
        )
        vim._on_editor_focus_changed()
        assert status.get_current_location() == destination
    finally:
        destination_editor.set_text(previous_destination_text)
        stack.set_stack_index(previous_index)
        vim._on_editor_focus_changed()
        reset_vim_state(status)


@pytest.mark.parametrize("destination_position", [0, 10])
def test_completed_definition_tracking_cannot_remove_destination(
    vim_bot, monkeypatch, destination_position
):
    """Returning to the origin must not trigger a completed request's fallback."""
    _, _, _, vim, _ = vim_bot
    status = vim.vim_cmd.vim_status
    reset_vim_state(status)
    origin = ("source.py", 20)
    destination = ("target.py", destination_position)
    location = [origin]
    monkeypatch.setattr(status, "get_current_location", lambda: location[0])
    status.push_jump()
    status.start_definition_tracking(origin)

    location[0] = destination
    status._definition_watch.timeout.emit()

    expected = [(jump.file, jump.pos) for jump in status.jump_list.jumps]
    assert expected == [origin, destination]
    assert status.timer_go_to_definition is None
    assert not status._definition_deadline.isActive()

    location[0] = origin
    status._definition_deadline.timeout.emit()
    assert [(jump.file, jump.pos) for jump in status.jump_list.jumps] == expected
