# -*- coding: utf-8 -*-
"""."""
# %% Import
# Local imports
from spyder_okvim.executor.executor_base import ExecutorBase


class ExecutorLeaderKey(ExecutorBase):
    """Executor for leader key."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.dispatcher = {
                'i': self.auto_import,
                'b': self.toggle_breakpoint,
                '\r': self.run_cell_and_advance,
                'r': self.run_selection,
                'f': self.formatting,
                'p': self.open_switcher
                }

        self.set_selection_to_editor_using_vim_selection = \
            self.vim_status.cursor.set_selection_to_editor_using_vim_selection

    def __call__(self, txt):
        """Parse txt and executor command.

        Returns
        -------
        bool
            if return is True, Clear command line

        """
        method = self.dispatcher.get(txt, None)
        if method:
            method(1, None)

        self.vim_status.sub_mode = None
        return True

    def auto_import(self, num=1, num_str=''):
        """Insert import statements from user defined list(for personal)."""
        editor = self.get_editor()
        try:
            editor.auto_import.auto_import()
            self.vim_status.set_focus_to_vim()
        except AttributeError:
            pass

    def toggle_breakpoint(self, num=1, num_str=""):
        """Toggle break."""
        self.get_editorstack().set_or_clear_breakpoint()

    def run_cell_and_advance(self, num=1, num_str=""):
        """Run cell and advance."""
        editor = self.get_editor()
        editor.sig_run_cell_and_advance.emit()
        self.vim_status.set_focus_to_vim()

    def run_selection(self, num=1, num_str=""):
        """Run selected text or current line in console."""
        editor = self.get_editor()
        old_cursor = self.set_selection_to_editor_using_vim_selection()
        editor.sig_run_selection.emit()
        if old_cursor:
            editor.setTextCursor(old_cursor)
        self.vim_status.set_focus_to_vim()

    def formatting(self, num=1, num_str=''):
        """Format document automatically."""
        editor = self.get_editor()
        old_cursor = self.set_selection_to_editor_using_vim_selection()
        try:
            editor.format_document_or_range()
            if old_cursor:
                editor.setTextCursor(old_cursor)
            self.vim_status.set_focus_to_vim()
        except AttributeError:
            pass

    def open_switcher(self, num=1, num_str=''):
        """Open switcher for buffers."""
        self.vim_status.main.open_switcher()

