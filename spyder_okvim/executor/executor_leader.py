# -*- coding: utf-8 -*-
"""Executor handling leader-key sequences."""

# Third Party Libraries
from qtpy.QtCore import QTimer
from spyder.api.plugins import Plugins

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
        CommandSpec("s", "open_symbol_swicher", "Switch symbol"),
    )

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.set_selection_to_editor_using_vim_selection = (
            self.vim_status.cursor.set_selection_to_editor_using_vim_selection
        )
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

    def auto_import(self, num=1, num_str=""):
        """Insert import statements from user defined list(for personal)."""
        editor = self.get_editor()
        try:
            editor.auto_import.auto_import()
            self.vim_status.set_focus_to_vim()
        except AttributeError:
            pass

    def search_imports(self, num=1, num_str=""):
        """Browse import candidates without filtering by the cursor word."""
        editor = self.get_editor()
        if editor is None or not editor.is_python() or editor.isReadOnly():
            return
        search = getattr(getattr(editor, "auto_import", None), "search_imports", None)
        if not callable(search):
            return
        try:
            search(query="")
        finally:
            # Spyder runs the picker modally; restore focus after it closes.
            self.vim_status.set_focus_to_vim()

    def toggle_breakpoint(self, num=1, num_str=""):
        """Toggle break."""
        editor = self.get_editor()
        editor.breakpoints_manager.toogle_breakpoint()

    def run_cell_and_advance(self, num=1, num_str=""):
        """Run cell and advance."""
        self._trigger_run_action("run cell and advance")

    def run_selection(self, num=1, num_str=""):
        """Run selected text or current line in console."""
        self._trigger_run_action("run selection and advance", use_selection=True)

    def debug_cell(self, num=1, num_str=""):
        """Debug the current cell without advancing to the next cell."""
        self._trigger_run_action("run cell in debugger")

    def debug_selection(self, num=1, num_str=""):
        """Debug selected text or the current line without advancing."""
        self._trigger_run_action("run selection in debugger", use_selection=True)

    def _trigger_run_action(self, action, use_selection=False):
        """Expose a Vim selection to Spyder and restore cursor and focus."""
        editor_stack = self.get_editorstack()
        editor = self.get_editor()
        old_cursor = (
            self.set_selection_to_editor_using_vim_selection()
            if use_selection
            else None
        )
        try:
            editor_stack.sig_trigger_action.emit(action, Plugins.Run)
        finally:
            if old_cursor is not None:
                editor.setTextCursor(old_cursor)
            self.vim_status.set_focus_to_vim()

    def retrieve_curosr_pos(self, pos: int, delay: int):
        """Retrieve the cursor position."""

        def _retrieve():
            self.vim_status.cursor.set_cursor_pos(pos)
            self.vim_status.set_focus_to_vim()
            self.vim_status.cursor.draw_vim_cursor()

        QTimer.singleShot(delay, _retrieve)

    def formatting(self, num=1, num_str=""):
        """Format document automatically."""
        editor = self.get_editor()
        editor.format_document_or_range()

    def open_switcher(self, num=1, num_str=""):
        """Open switcher for buffers."""
        main = self.vim_status.main
        switcher = main.get_plugin(Plugins.Switcher)
        switcher.open_switcher()

    def open_symbol_swicher(self, num=1, num_str=""):
        """Open switcher for symbol."""
        main = self.vim_status.main
        switcher = main.get_plugin(Plugins.Switcher)
        switcher.open_switcher(symbol=True)

    def execute_easymotion(self, num=1, num_str=""):
        """Execute easymotion."""
        return self.prev_executor.run_easymotion()
