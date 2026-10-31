# -*- coding: utf-8 -*-
"""Executor handling leader-key sequences."""

# Project Libraries
from spyder_okvim.executor.executor_base import CommandSpec, ExecutorBase


class ExecutorLeaderKey(ExecutorBase):
    """Executor for leader key."""

    command_specs = (
        CommandSpec("i", "auto_import", "Auto import"),
        CommandSpec("I", "search_imports", "Search imports"),
        CommandSpec("b", "toggle_breakpoint", "Toggle breakpoint"),
        CommandSpec("d", "debug_cell", "Debug cell"),
        CommandSpec("D", "debug_selection", "Debug selection or line"),
        CommandSpec("\r", "run_cell_and_advance", "Run cell and advance"),
        CommandSpec("r", "run_selection", "Run selection or line"),
        CommandSpec("f", "formatting", "Format document or selection"),
        CommandSpec("p", "open_switcher", "Switch file"),
        CommandSpec("s", "open_symbol_switcher", "Switch symbol"),
        CommandSpec("y", "show_yank_history", "Yank history"),
    )

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.prev_executor = None

    def set_easymotion_key(self, key):
        """Restore default commands and bind the current EasyMotion key."""
        self.hint_prefix = key
        commands = {command.key: command for command in self.command_specs}
        # Replacing an existing key preserves its position; a new key appends.
        commands[key] = CommandSpec(key, "execute_easymotion", "EasyMotion")
        self._set_command_specs(commands.values())

    def on_escape(self):
        """Discard the pending leader without executing its previous executor."""
        self.prev_executor = None

    def __call__(self, txt):
        """Dispatch leader-key command ``txt`` and return execution info."""
        method = self.dispatcher.get(txt)

        ret = None
        if method:
            ret = method(1, "")

        return self.process_return(ret)

    def auto_import(self, count=1, count_text=""):
        """Ask the host to insert imports and restore command input focus."""
        self.vim_status.host.auto_import()

    def search_imports(self, count=1, count_text=""):
        """Browse host import candidates without filtering by the cursor word."""
        self.vim_status.host.search_imports()

    def toggle_breakpoint(self, count=1, count_text=""):
        """Toggle the host editor's breakpoint at the current line."""
        self.vim_status.host.toggle_breakpoint()

    def run_cell_and_advance(self, count=1, count_text=""):
        """Run cell and advance."""
        self._trigger_run_action("run cell and advance")

    def run_selection(self, count=1, count_text=""):
        """Run selected text or current line in console."""
        self._trigger_run_action("run selection and advance", use_selection=True)

    def debug_cell(self, count=1, count_text=""):
        """Debug the current cell without advancing to the next cell."""
        self._trigger_run_action("run cell in debugger")

    def debug_selection(self, count=1, count_text=""):
        """Debug selected text or the current line without advancing."""
        self._trigger_run_action("run selection in debugger", use_selection=True)

    def _trigger_run_action(self, action, use_selection=False):
        """Run or debug through the host, restoring Vim selection and focus."""
        self.vim_status.host.trigger_run_action(action, use_selection=use_selection)

    def formatting(self, count=1, count_text=""):
        """Format the current document or selected range through the host."""
        self.vim_status.host.format_document()

    def open_switcher(self, count=1, count_text=""):
        """Open the host's file switcher."""
        self.vim_status.host.open_switcher()

    def open_symbol_switcher(self, count=1, count_text=""):
        """Open the host's symbol switcher."""
        self.vim_status.host.open_switcher(symbol=True)

    def execute_easymotion(self, count=1, count_text=""):
        """Execute easymotion."""
        return self.prev_executor.run_easymotion()

    def show_yank_history(self, count=1, count_text=""):
        """Request the active view's yank picker through the session callback."""
        self.vim_status.show_yank_history()
