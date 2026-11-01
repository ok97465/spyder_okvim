"""Window prefixes preserve explicit counts and expose split navigation hints."""

# Standard Libraries
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt

# Project Libraries
from tests.qt_support import reset_vim_state


@pytest.mark.parametrize(
    "before, after, expected",
    [("", "w", None), ("2", "w", 2), ("", "3w", 3), ("2", "3w", 6)],
)
def test_cycle_split_counts(vim_bot, monkeypatch, before, after, expected):
    _, _, _, vim, qtbot = vim_bot
    status = vim.vim_cmd.vim_status
    line = vim.vim_cmd.commandline
    reset_vim_state(status)
    line.setFocus()
    cycle = Mock()
    monkeypatch.setattr("spyder_okvim.executor.prefixes.focus_cycle", cycle)

    qtbot.keyClicks(line, before)
    qtbot.keyClick(line, Qt.Key_W, Qt.ControlModifier)
    qtbot.keyClicks(line, after)

    cycle.assert_called_once_with(status, expected)
    assert line.text() == ""
    assert status.sub_mode is None


def test_previous_split_dispatch_and_hints(vim_bot, monkeypatch):
    _, _, _, vim, qtbot = vim_bot
    status = vim.vim_cmd.vim_status
    line = vim.vim_cmd.commandline
    reset_vim_state(status)
    line.setFocus()
    previous = Mock()
    monkeypatch.setattr("spyder_okvim.executor.prefixes.focus_previous", previous)

    qtbot.keyClick(line, Qt.Key_W, Qt.ControlModifier)
    candidates = dict(status.sub_mode.get_hint_candidates())
    assert candidates["w"] == "Focus next split"
    assert candidates["p"] == "Focus previous split"
    qtbot.keyClicks(line, "p")

    previous.assert_called_once_with(status)
    assert line.text() == ""
    assert status.sub_mode is None
