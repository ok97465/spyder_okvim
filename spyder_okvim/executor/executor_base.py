# -*- coding: utf-8 -*-
"""Base classes for OkVim command executors.

This module provides :class:`ExecutorBase` and :class:`ExecutorSubBase`, which
handle the parsing of command strings and delegation of actions to the
motion and editing services. Executors interpret user
keystrokes, update the shared :class:`~spyder_okvim.vim.VimStatus` object and
decide whether submodes should be entered.
"""

# Standard Libraries
import re
from dataclasses import dataclass
from typing import Any, Callable, NamedTuple


class DeferredAction(NamedTuple):
    """A pending operator callback and whether it consumes the resulting motion."""

    callback: Callable
    accepts_argument: bool


class ExecutorTransition(NamedTuple):
    """Enter a submode and state whether the displayed input must be cleared."""

    sub_mode: Any
    clear_command_line: bool


@dataclass(frozen=True)
class CommandSpec:
    """A raw command key, its executor method and its hint description."""

    key: str
    method_name: str
    description: str


class ExecutorBase:
    """Interpret command/count input and return the next input transition.

    Concrete modes own their pending subexecutors. Motion/edit services are
    supplied by the session's composition function, never global singletons.
    """

    accepts_input_method = False
    hint_prefix = None
    command_specs = ()

    SYMBOLS_REPLACEMENT = {
        "!": "exclamation",
        "?": "question",
        "<": "less",
        ">": "greater",
        "=": "equal",
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
        self.motions, self.edits = vim_status.create_command_services()
        # Existing integrations may still access the former attribute names.
        self.helper_motion = self.motions
        self.helper_action = self.edits

        self.has_zero_cmd = True
        self.pattern_cmd = None
        self.allow_leaderkey = True
        self._command_specs = ()
        if self.command_specs:
            self._set_command_specs(self.command_specs)

    def _set_command_specs(self, commands):
        """Build accepted keys, dispatch and hints from one command declaration.

        Other executors can keep their existing parsers. Discrete prefix
        commands opt in by declaring ``command_specs``; descriptive ranges and
        context-dependent hints belong in ``get_hint_candidates`` instead.
        """
        self._command_specs = tuple(commands)
        keys = "".join(re.escape(command.key) for command in self._command_specs)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(keys))
        self.dispatcher = {
            command.key: getattr(self, command.method_name)
            for command in self._command_specs
        }

    def get_hint_candidates(self):
        """Return read-only descriptions of the next supported keys."""
        return [(command.key, command.description) for command in self._command_specs]

    def update_input_cmd_info(self, count_text, cmd, input_txt):
        """Save the prior input and record the explicit count text and command key."""
        self.vim_status.input_cmd_prev.set(self.vim_status.input_cmd)
        self.vim_status.input_cmd.count_text = count_text
        self.vim_status.input_cmd.cmd = cmd

    def set_parent_info_to_submode(self, submode, count, count_text):
        """Start a submode with this request's count and its original spelling."""
        submode.parent_counts = [count]
        submode.parent_count_texts = [count_text]

    def __call__(self, txt: str) -> bool:
        """Interpret pending input, retaining an incomplete numeric prefix.

        Return True when the command line should clear, including unsupported
        input; False means more input is needed. The empty count text and an
        explicit "1" have different semantics even though both execute once.
        """
        if self.has_zero_cmd and txt == "0":
            # Special case to simplify regexp
            key = "0"
            count_text = "1"
        else:
            match = self.pattern_cmd.match(txt)
            if not match:
                if txt.isdigit():
                    return False
                else:
                    self.vim_status.sub_mode = None
                    return True

            count_text, key = match.groups()

        count = int(count_text) if count_text else 1
        self.update_input_cmd_info(count_text, key, txt)

        ret = None
        if self._command_specs:
            method = self.dispatcher.get(key)
        else:
            method_name = self.SYMBOLS_REPLACEMENT.get(key, key)
            method = getattr(self, method_name, None)
        if method is None:
            print("unknown key", key)
        else:
            ret = method(count=count, count_text=count_text)

        return self.process_return(ret)

    def process_return(self, ret: Any):
        """Apply a handler transition, defaulting to finished input when absent."""
        if ret:
            self.vim_status.sub_mode = ret.sub_mode
            return ret.clear_command_line
        else:
            self.vim_status.sub_mode = None
            return True


class ExecutorSubBase(ExecutorBase):
    """Accumulate operator counts and run deferred actions for pending input."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.has_zero_cmd = False
        self.parent_counts = []
        self.parent_count_texts = []
        self.func_list_deferred: list[DeferredAction] = []
        self.return_deferred: Any = None

    def set_parent_info_to_submode(self, submode, count, count_text):
        """Copy ancestor counts before adding the current pending operator count."""
        submode.parent_counts = self.parent_counts.copy()
        submode.parent_count_texts = self.parent_count_texts.copy()

        submode.parent_counts.append(count)
        submode.parent_count_texts.append(count_text)

    def set_func_list_deferred(self, f_list: list[DeferredAction], ret: Any = None):
        """Replace the pending callbacks and their eventual transition result."""
        self.func_list_deferred = f_list
        self.return_deferred = ret

    def execute_func_deferred(self, arg=None):
        """Execute method passed in from previous executor."""
        for func_info in self.func_list_deferred:
            if func_info.accepts_argument:
                func_info.callback(arg)
            else:
                func_info.callback()
        return self.return_deferred

    def update_input_cmd_info(self, count_text, cmd, input_txt):
        """Append submode input to the command being recorded for dot replay."""
        self.vim_status.input_cmd.cmd += input_txt

    def on_escape(self) -> None:
        """Handle ``Esc`` key while in this submode."""
        return

    def close_current_file(self, force=False):
        """Delegate file closure and debugger/autosave guards to the host."""
        self.vim_status.host.close_current_file(force=force)

    def save_current_file(self):
        """Return the host's explicit save success result."""
        return self.vim_status.host.save_current_file()

    def save_and_close_current_file(self):
        """Close only when the originally active document was saved."""
        self.vim_status.host.save_and_close_current_file()

    def create_new_file(self):
        """Create a document using the host editor action."""
        self.vim_status.host.create_new_file()
