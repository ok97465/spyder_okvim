# -*- coding: utf-8 -*-
"""Executor handling leader-key sequences."""

# Third Party Libraries
from qtpy.QtCore import QTimer
from spyder.api.plugins import Plugins

# Project Libraries
from spyder_okvim.executor.executor_base import ExecutorBase


class ExecutorLeaderKey(ExecutorBase):
    """Executor for leader key."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.dispatcher = {
            "i": self.auto_import,
            "b": self.toggle_breakpoint,
            "\r": self.run_cell_and_advance,
            "r": self.run_selection,
            "f": self.formatting,
            "p": self.open_switcher,
            "s": self.open_symbol_swicher,
        }

        self.set_selection_to_editor_using_vim_selection = (
            self.vim_status.cursor.set_selection_to_editor_using_vim_selection
        )
        self.prev_executor = None

    def set_easymotion_key(self, key):
        "Set key for easymotion."
        self.dispatcher[key] = self.execute_easymotion

    def __call__(self, txt):
        """Dispatch leader-key command ``txt`` and return execution info."""
        method = self.dispatcher.get(txt, None)

        ret = None
        if method:
            ret = method(1, "")

        if ret:
            self.vim_status.sub_mode = ret.sub_mode
            return ret.clear_command_line
        else:
            self.vim_status.sub_mode = None
            return True

    def auto_import(self, num=1, num_str=""):
        """Insert import statements from user defined list(for personal)."""
        editor = self.get_editor()
        try:
            editor.auto_import.auto_import()
            self.vim_status.set_focus_to_vim()
        except AttributeError:
            pass

    def toggle_breakpoint(self, num=1, num_str=""):
        """Toggle break."""
        editor = self.get_editor()
        editor.breakpoints_manager.toogle_breakpoint()

    def run_cell_and_advance(self, num=1, num_str=""):
        """Run cell and advance."""
        editor_stack = self.get_editorstack()
        editor_stack.sig_trigger_action.emit("run cell and advance", Plugins.Run)
        self.vim_status.set_focus_to_vim()

    def run_selection(self, num=1, num_str=""):
        """Run selected text or current line in console."""
        editor_stack = self.get_editorstack()
        editor = self.get_editor()
        old_cursor = self.set_selection_to_editor_using_vim_selection()
        editor_stack.sig_trigger_action.emit("run selection and advance", Plugins.Run)
        if old_cursor:
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
