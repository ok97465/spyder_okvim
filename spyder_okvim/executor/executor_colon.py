# -*- coding: utf-8 -*-
"""."""
# Local imports
from spyder_okvim.executor.executor_base import ExecutorSubBase


class ExecutorColon(ExecutorSubBase):
    """Execute the method by enter."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.editor_widget = vim_status.editor_widget

    def __call__(self, txt):
        """Parse txt and executor command.

        Returns
        -------
        bool
            if return is True, Clear command line

        """
        if txt[-1] == '\b':
            cmd_line = self.vim_status.cmd_line
            if len(txt) <= 2:
                self.vim_status.sub_mode = None
                return True
            else:
                cmd_line.setText(txt[:-2])
        if txt[-1] != '\r':
            return False

        if txt[0] != ":" or len(txt) <= 2:
            self.vim_status.sub_mode = None
            return True

        # ':' is saved to input cmd_info at ExecutorBase.
        # So we need only txt[1:].
        self.update_input_cmd_info(None, None, txt[1:])

        txt = txt[1:-1]  # remove :, \r
        cmd = txt.split(None, 1)
        args = cmd[1] if len(cmd) > 1 else ""
        cmd = cmd[0]

        for symbol, text in self.SYMBOLS_REPLACEMENT.items():
            cmd = cmd.replace(symbol, text)

        try:
            method = self.__getattribute__(cmd)
        except AttributeError:
            print("unknown command", cmd)
        else:
            method(args)

        self.vim_status.sub_mode = None

        return True

    def w(self, arg=""):
        """Save current file."""
        self.editor_widget.save_action.trigger()
        self.vim_status.cursor.draw_vim_cursor()

    def q(self, arg=""):
        """Close current file."""
        self.editor_widget.close_action.trigger()
        self.vim_status.set_focus_to_vim()

    def qexclamation(self, arg=""):
        """Close current file without saving."""
        # TODO :
        self.editor_widget.close_action.trigger()
        self.vim_status.set_focus_to_vim()

    def wq(self, arg=""):
        """Save and close current file."""
        self.w(arg)
        self.q()

    def n(self, args=""):
        """Create new file."""
        self.editor_widget.new_action.trigger()
        self.vim_status.set_focus_to_vim()


