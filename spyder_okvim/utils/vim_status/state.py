# -*- coding: utf-8 -*-
"""Core data structures for Vim status handling."""

from qtpy.QtCore import QEvent
from qtpy.QtGui import QKeyEvent


class VimState:
    """Vim state constants."""

    VISUAL = 0
    VLINE = 1
    NORMAL = 3
    INSERT = 4
    SUBMODE = 5


class FindInfo:
    """Metadata for ``f``, ``F``, ``t`` and ``T`` commands."""

    def __init__(self):
        self.cmd_name: str = ""
        self.ch: str = ""

    def set(self, cmd_name: str, ch: str):
        """Update this command information.

        Args:
            cmd_name: Command name (``f``/``F``/``t``/``T``).
            ch: Character used with the command.
        """
        self.cmd_name = cmd_name
        self.ch = ch


class InputCmdInfo:
    """Container for the command currently being typed."""

    def __init__(self, num_str: str, cmd: str):
        """Create a new instance.

        Args:
            num_str: Number prefix for the command.
            cmd: Command string.
        """
        self.num_str: str = num_str
        self.cmd: str = cmd

    def clear(self):
        """Reset both number and command strings."""
        self.num_str = ""
        self.cmd = ""

    def set(self, input_cmd_info):
        """Copy the fields from another ``InputCmdInfo``.

        Args:
            input_cmd_info: Source command info to copy from.
        """
        self.num_str = input_cmd_info.num_str
        self.cmd = input_cmd_info.cmd


class DotCmdInfo:
    """Information about the last ``.`` command."""

    def __init__(self):
        self.vim_state = None
        self.sel_block_no_start = None
        self.sel_block_no_end = None
        self.sel_col_start = None
        self.sel_col_end = None
        self.num_str: str = ""
        self.cmd: str = ""
        self.cmd_list_insertmode = None
        self.register_name = None
        self.editor_connected = None
        self.key_list_from_editor = []
        self.key_list_to_cmd_line = []

    def clear_key_list(self):
        """Remove any stored key events."""
        self.key_list_from_editor.clear()
        self.key_list_to_cmd_line.clear()

    def to_cmd_string(self, num, num_str):
        """Return the textual representation of this dot command.

        Args:
            num: Numeric prefix used for the command.
            num_str: Original numeric string typed by the user.
        """
        # TODO : apply register name.
        cmd_str = ""

        if self.vim_state == VimState.VLINE:
            cmd_str += "V"
            n_lines = self.sel_block_no_end - self.sel_block_no_start
            if n_lines > 0:
                cmd_str += f"{n_lines}j"
            cmd_str += self.cmd
            return cmd_str

        if self.vim_state == VimState.VISUAL:
            cmd_str += "v"
            n_lines = self.sel_block_no_end - self.sel_block_no_start
            if n_lines > 0:
                cmd_str += f"{n_lines}j0"

                if self.sel_col_end > 1:
                    cmd_str += f"{self.sel_col_end - 1}l"
            else:
                n = self.sel_col_end - self.sel_col_start - 1
                if n > 0:
                    cmd_str += f"{n}l"
            cmd_str += self.cmd
            return cmd_str

        if num_str:
            return str(num) + self.cmd
        else:
            return self.num_str + self.cmd



class KeyInfo:
    """Serializable representation of a :class:`QKeyEvent`."""

    def __init__(self, key_code: int, text: str, modifiers: int, identifier: int = 1):
        self.key_code = key_code
        self.text = text
        self.modifiers = modifiers
        #: 0 if coming from the Vim command line, 1 if from the editor
        self.identifier = identifier

    def to_event(self):
        """Return a :class:`QKeyEvent` created from this info."""
        event = QKeyEvent(QEvent.KeyPress, self.key_code, self.modifiers, self.text)
        event.ignore()
        return event


class RegisterInfo:
    """Simple register structure used by macros and yank/put."""

    def __init__(self):
        """Initialize an empty register."""
        self.name = ""
        self.content = ""
        self.type = VimState.NORMAL


