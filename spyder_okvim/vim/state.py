# -*- coding: utf-8 -*-
"""Vim modes, command snapshots and register/key values without Qt imports.

Document positions and Visual columns are Qt UTF-16 offsets; block numbers
are zero-based. Live document edits belong to insert_repeat.py.
"""

# Standard Libraries
from enum import IntEnum


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

    def __init__(self, count_text: str = "", cmd: str = "", *, num_str=None):
        """Create a new instance.

        Args:
            count_text: Original count spelling, empty when no prefix was typed.
            cmd: Command string.
            num_str: Historical keyword alias for count_text.
        """
        self.count_text: str = count_text if num_str is None else num_str
        self.cmd: str = cmd

    def clear(self):
        """Reset both number and command strings."""
        self.count_text = ""
        self.cmd = ""

    def set(self, input_cmd_info):
        """Copy the fields from another ``InputCmdInfo``.

        Args:
            input_cmd_info: Source command info to copy from.
        """
        self.count_text = input_cmd_info.count_text
        self.cmd = input_cmd_info.cmd

    @property
    def num_str(self):
        """Historical alias for the original, possibly empty count text."""
        return self.count_text

    @num_str.setter
    def num_str(self, value):
        self.count_text = value


class DotCmdInfo:
    """Snapshot of a change for dot replay, including its Visual shape.

    ``count_text`` preserves an implicit count versus explicit digits. Visual
    blocks are zero-based and columns are Qt UTF-16 offsets with the saved
    selection endpoint excluded. Live editor recording is owned by the session.
    """

    def __init__(self):
        self.vim_state = None
        self.sel_block_no_start = None
        self.sel_block_no_end = None
        self.sel_col_start = None
        self.sel_col_end = None
        self.count_text: str = ""
        self.cmd: str = ""
        self.cmd_list_insertmode = None
        self.register_name = None
        self.put_payload = None
        self.editor_connected = None
        self.key_list_from_editor = []
        self.key_list_to_cmd_line = []

    def clear_key_list(self):
        """Remove any stored key events."""
        self.key_list_from_editor.clear()
        self.key_list_to_cmd_line.clear()

    def selection_to_cmd_string(self):
        """Reconstruct the saved Visual shape before replaying a change."""
        if self.vim_state == VimState.VLINE:
            n_lines = self.sel_block_no_end - self.sel_block_no_start
            return "V" + (f"{n_lines}j" if n_lines > 0 else "")
        if self.vim_state == VimState.VISUAL:
            cmd_str = "v"
            n_lines = self.sel_block_no_end - self.sel_block_no_start
            if n_lines > 0:
                cmd_str += f"{n_lines}j0"
                if self.sel_col_end > 1:
                    cmd_str += f"{self.sel_col_end - 1}l"
            else:
                n = self.sel_col_end - self.sel_col_start - 1
                if n > 0:
                    cmd_str += f"{n}l"
            return cmd_str
        return ""

    def to_cmd_string(self, count, count_text):
        """Return the textual representation of this dot command.

        Args:
            count: Numeric prefix used for the command.
            count_text: Original numeric string typed by the user.
        """
        register_prefix = f'"{self.register_name}' if self.register_name else ""
        selection = self.selection_to_cmd_string()
        if selection:
            # Select the register after reconstructing the Visual selection.
            return selection + register_prefix + self.cmd

        if count_text:
            return register_prefix + str(count) + self.cmd
        else:
            return register_prefix + self.count_text + self.cmd

    @property
    def num_str(self):
        """Historical alias for the original, possibly empty count text."""
        return self.count_text

    @num_str.setter
    def num_str(self, value):
        self.count_text = value


class InputSource(IntEnum):
    """Destination of a recorded key, preserving historical numeric values."""

    COMMAND_LINE = 0
    EDITOR = 1


class KeyInfo:
    """Recorded key values and their command-line/editor input destination.

    Native Qt key/modifier identities are retained without importing Qt here.
    Event construction happens on demand through the Qt key boundary.
    """

    def __init__(
        self,
        key_code: int,
        text: str,
        modifiers: int,
        source: InputSource = InputSource.EDITOR,
        *,
        identifier=None,
    ):
        self.key_code = key_code
        self.text = text
        self.modifiers = modifiers
        self.source = InputSource(source if identifier is None else identifier)

    @property
    def identifier(self):
        """Historical integer alias; new code uses ``source``."""
        return int(self.source)

    @identifier.setter
    def identifier(self, value):
        self.source = InputSource(value)

    def to_event(self):
        """Create an ignored Qt KeyPress event on the GUI thread."""
        # Project Libraries
        from spyder_okvim.utils.key_helpers import key_event_from_info

        return key_event_from_info(self)


class RegisterInfo:
    """One register's name, text and Vim character/line selection kind.

    Values are copied when rotating automatic registers, so mutation cannot
    alias another register or a previously recorded immutable yank entry.
    """

    def __init__(self):
        """Initialize an empty register."""
        self.name = ""
        self.content = ""
        self.type = VimState.NORMAL


def __getattr__(name):
    """Keep the old InsertCmdInfo import without loading Qt for pure values."""
    if name == "InsertCmdInfo":
        from .insert_repeat import InsertEdit

        return InsertEdit
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
