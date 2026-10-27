"""Regression tests for context-sensitive prefix hints."""

# Standard Libraries
import os.path as osp

# Third Party Libraries
import pytest

# Project Libraries
from spyder_okvim.executor.executor_base import CommandSpec, ExecutorSubBase
from spyder_okvim.executor.executor_sub import ExecutorSubCmd_alnum
from spyder_okvim.vim.state import InputCmdInfo


def test_declared_command_supports_custom_method_and_special_key(vim_bot):
    """A new prefix command supplies its parser, handler and hint in one place."""
    _, _, _, vim, _ = vim_bot
    calls = []

    class PrefixExecutor(ExecutorSubBase):
        command_specs = (CommandSpec("]", "perform_action", "Custom action"),)

        def perform_action(self, num=1, num_str=""):
            calls.append((num, num_str))

    executor = PrefixExecutor(vim.vim_cmd.vim_status)

    assert executor.get_hint_candidates() == [("]", "Custom action")]
    assert executor("12") is False
    assert calls == []
    assert executor("12]") is True
    assert calls == [(12, "12")]
    assert executor("[") is True
    assert calls == [(12, "12")]


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
