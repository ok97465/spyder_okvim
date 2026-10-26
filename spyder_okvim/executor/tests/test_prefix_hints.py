"""Regression tests for context-sensitive prefix hints."""

# Standard Libraries
import os.path as osp

# Third Party Libraries
import pytest

# Project Libraries
from spyder_okvim.executor.executor_sub import ExecutorSubCmd_alnum
from spyder_okvim.vim.state import InputCmdInfo


@pytest.mark.parametrize(
    "command, parent_num, cross_file",
    [("'", [12], True), ("d'", [1, 1], False), ("gu'", [2, 3, 4], False)],
)
def test_mark_hints_respect_operator_file_boundary(
    vim_bot, monkeypatch, command, parent_num, cross_file
):
    """A direct counted jump can cross files, while an operator motion cannot."""
    _, stack, _, vim, _ = vim_bot
    status = vim.vim_cmd.vim_status
    current = stack.get_current_filename()
    other = current + ".other.py"
    manager = status.bookmark_manager
    local = {"file": current, "line": 2, "col": 0}
    same_file_global = {"file": current, "line": 3, "col": 0}
    other_file_global = {"file": other, "line": 4, "col": 0}
    monkeypatch.setattr(manager, "bookmarks", {current: {"a": local}})
    monkeypatch.setattr(
        manager,
        "bookmarks_global",
        {"A": same_file_global, "B": other_file_global},
    )
    monkeypatch.setattr(status, "input_cmd", InputCmdInfo("", command))
    executor = ExecutorSubCmd_alnum(status)
    executor.parent_num = parent_num

    candidates = executor.get_hint_candidates()

    expected = [
        ("a", f"{osp.basename(current)}:3"),
        ("A", f"{osp.basename(current)}:4"),
    ]
    if cross_file:
        expected.append(("B", f"{osp.basename(other)}:5"))
    assert executor.hint_prefix == "'"
    assert candidates == expected
