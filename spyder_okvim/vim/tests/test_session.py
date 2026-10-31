"""Cancelled session timers cannot refocus or alter a closed/switched view."""

# Standard Libraries
from unittest.mock import Mock

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


def test_cancelled_definition_callbacks_leave_jump_history_unchanged(vim_bot):
    """Late watch/deadline events must not add or remove navigation entries."""
    _, _, _, vim, _ = vim_bot
    status = vim.vim_cmd.vim_status
    reset_vim_state(status)
    previous = status.get_current_location()
    status.push_jump()
    expected = list(status.jump_list.jumps)
    status.start_definition_tracking(previous)
    status.cancel_pending_work()

    status._definition_watch.timeout.emit()
    status._definition_deadline.timeout.emit()

    assert status.jump_list.jumps == expected
    assert status.timer_go_to_definition is None
