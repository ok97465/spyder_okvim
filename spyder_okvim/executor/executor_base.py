# -*- coding: utf-8 -*-
"""Base classes for OkVim command executors.

This module provides :class:`ExecutorBase` and :class:`ExecutorSubBase`, which
handle the parsing of command strings and delegation of actions to the
``MotionHelper`` and ``ActionHelper`` utilities. Executors interpret user
keystrokes, update the shared :class:`~spyder_okvim.vim.VimStatus` object and
decide whether submodes should be entered.
"""

# Standard Libraries
from typing import Any, NamedTuple

# Project Libraries
from spyder_okvim.utils.action_helpers import ActionHelper
from spyder_okvim.utils.motion_helpers import MotionHelper

FUNC_INFO = NamedTuple("FUNC_INFO", [("func", Any), ("has_arg", bool)])
RETURN_EXECUTOR_METHOD_INFO = NamedTuple(
    "RETURN_EXECUTOR_METHOD_INFO", [("sub_mode", Any), ("clear_command_line", bool)]
)


class ExecutorBase:
    """Baseclass Executor."""

    SYMBOLS_REPLACEMENT = {
        "!": "exclamation",
        "?": "question",
        "<": "less",
        ">": "greater",
        "|": "pipe",
        " ": "space",
        "\b": "backspace",
        "\r": "enter",
        "@": "at",
        "$": "dollar",
        "0": "zero",
        "^": "caret",
        '"': "quote",
        "'": "apostrophe",
        "`": "backtick",
        "%": "percent",
        "~": "tilde",
        ":": "colon",
        "/": "slash",
        ";": "semicolon",
        ",": "comma",
        ".": "dot",
        "[": "opensquarebracket",
        "]": "closesquarebracket",
        "*": "asterisk",
        "#": "sharp",
        "{": "openbrace",
        "}": "closebrace",
    }

    def __init__(self, vim_status):
        """Initialize the executor with the shared :class:`VimStatus`.

        Args:
            vim_status: :class:`spyder_okvim.vim.VimStatus` instance providing
                editor and cursor helpers.

        """
        self.vim_status = vim_status
        self.get_cursor = vim_status.get_cursor
        self.set_cursor = vim_status.set_cursor
        self.get_editor = vim_status.get_editor
        self.get_editorstack = vim_status.get_editorstack
        self.get_block_no_start_in_selection = (
            vim_status.get_block_no_start_in_selection
        )
        self.get_block_no_end_in_selection = vim_status.get_block_no_end_in_selection
        self.get_pos_start_in_selection = vim_status.get_pos_start_in_selection
        self.get_pos_end_in_selection = vim_status.get_pos_end_in_selection
        self.set_cursor_pos = vim_status.cursor.set_cursor_pos
        self.helper_motion = MotionHelper(vim_status)
        self.helper_action = ActionHelper(vim_status)

        self.has_zero_cmd = True
        self.pattern_cmd = None
        self.allow_leaderkey = True

    def update_input_cmd_info(self, num_str, cmd, input_txt):
        """Update input cmd to vim_status."""
        self.vim_status.input_cmd_prev.set(self.vim_status.input_cmd)
        self.vim_status.input_cmd.num_str = num_str
        self.vim_status.input_cmd.cmd = cmd

    def set_parent_info_to_submode(self, submode, num, num_str):
        """Set info to submode."""
        submode.parent_num = [num]
        submode.parent_num_str = [num_str]

    def __call__(self, txt: str) -> bool:
        """Parse txt and executor command.

        Returns:
            if return is True, Clear command line.

        """
        if self.has_zero_cmd and txt == "0":
            # Special case to simplify regexp
            key = "0"
            num_str = "1"
        else:
            match = self.pattern_cmd.match(txt)
            if not match:
                if txt.isdigit():
                    return False
                else:
                    self.vim_status.sub_mode = None
                    return True

            num_str, key = match.groups()

        num = int(num_str) if num_str else 1
        self.update_input_cmd_info(num_str, key, txt)

        key = self.SYMBOLS_REPLACEMENT.get(key, key)

        ret = None
        try:
            method = self.__getattribute__(key)
        except AttributeError:
            print("unknown key", key)
        else:
            ret = method(num=num, num_str=num_str)

        return self.process_return(ret)

    def process_return(self, ret: Any):
        """Process return of method."""
        if ret:
            self.vim_status.sub_mode = ret.sub_mode
            return ret.clear_command_line
        else:
            self.vim_status.sub_mode = None
            return True


class ExecutorSubBase(ExecutorBase):
    """Baseclass for submode of executor."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.has_zero_cmd = False
        self.parent_num = []
        self.parent_num_str = []
        self.func_list_deferred: list[FUNC_INFO] = []
        self.return_deferred: Any = None

    def set_parent_info_to_submode(self, submode, num, num_str):
        """Set parent and self into to submode."""
        submode.parent_num = self.parent_num.copy()
        submode.parent_num_str = self.parent_num_str.copy()

        submode.parent_num.append(num)
        submode.parent_num_str.append(num_str)

    def set_func_list_deferred(self, f_list: list[FUNC_INFO], ret: Any = None):
        """Set func list."""
        self.func_list_deferred = f_list
        self.return_deferred = ret

    def execute_func_deferred(self, arg=None):
        """Execute method passed in from previous executor."""
        for func_info in self.func_list_deferred:
            if func_info.has_arg:
                func_info.func(arg)
            else:
                func_info.func()
        return self.return_deferred

    def update_input_cmd_info(self, num_str, cmd, input_txt):
        """Add input cmd to vim_status."""
        self.vim_status.input_cmd.cmd += input_txt

    # ------------------------------------------------------------------
    # Common editor actions
    # ------------------------------------------------------------------
    def close_current_file(self) -> None:
        """Close the current file using Spyder's editor API."""
        self.vim_status.editor_widget.close_file()

    def save_current_file(self) -> None:
        """Save the active file through Spyder's editor plugin."""
        self.vim_status.editor_widget.save()

    def create_new_file(self) -> None:
        """Create a new file using Spyder's editor plugin."""
        self.vim_status.editor_widget.new()
