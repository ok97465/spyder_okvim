# -*- coding: utf-8 -*-
"""Executor for ":" command-line input."""

# Third Party Libraries
from qtpy.QtWidgets import QDialog

# Project Libraries
from spyder_okvim.executor.executor_base import ExecutorSubBase
from spyder_okvim.utils.jump_dialog import JumpListDialog
from spyder_okvim.utils.mark_dialog import MarkListDialog
from spyder_okvim.vim import VimState


class ExecutorColon(ExecutorSubBase):
    """Interpreter for ``:`` commands entered in the command line."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.editor_widget = vim_status.editor_widget

    def __call__(self, txt: str) -> bool:
        """Parse ``txt`` and execute the corresponding ex command.

        Args:
            txt: Command string typed by the user, including the trailing ``\r``.

        Returns:
            if return is True, Clear command line.

        """
        if txt[-1] == "\b":
            cmd_line = self.vim_status.cmd_line
            if len(txt) <= 2:
                self.vim_status.sub_mode = None
                return True
            else:
                cmd_line.setText(txt[:-2])
        if txt[-1] != "\r":
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

        if cmd.isdigit():
            self.goto_line(int(cmd))
        else:
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
        self.save_current_file()
        self.vim_status.cursor.draw_vim_cursor()

    def q(self, arg=""):
        """Close current file."""
        self.close_current_file()
        self.vim_status.set_focus_to_vim()

    def qexclamation(self, arg=""):
        """Close current file without saving."""
        # TODO :
        self.close_current_file()
        self.vim_status.set_focus_to_vim()

    def wq(self, arg=""):
        """Save and close current file."""
        self.w(arg)
        self.q()

    def n(self, args=""):
        """Create new file."""
        self.create_new_file()
        self.vim_status.set_focus_to_vim()

    def marks(self, arg=""):
        """Show bookmarks and jump to the selected one."""
        vs = self.vim_status
        marks = vs.bookmark_manager.list_bookmarks()

        dlg = MarkListDialog(marks, vs.main)
        result = dlg.exec_()
        # When running tests ``exec_`` is patched to return ``None`` so the
        # selected mark must be retrieved regardless of the returned value.
        # Only reject the action explicitly when ``QDialog.Rejected`` (0) is
        # returned.
        mark = (
            dlg.get_selected_mark()
            if result is None or result == QDialog.Accepted
            else None
        )
        if mark:
            vs.push_jump()
            vs.jump_to_bookmark(mark)
            vs.push_jump()

        vs.set_focus_to_vim()

    def jumps(self, arg=""):
        """Display the jumplist in a popup dialog."""
        vs = self.vim_status

        dlg = JumpListDialog(vs, vs.main)
        dlg.exec_()

        vs.set_focus_to_vim()

    def goto_line(self, num):
        """Move cursor according to :number command."""
        vs = self.vim_status
        vs.push_jump()
        if vs.vim_state == VimState.NORMAL:
            motion_info = self.helper_motion.G(num, True)
            vs.cursor.apply_motion_info_in_normal(motion_info)
        elif vs.vim_state in (VimState.VISUAL, VimState.VLINE):
            motion_info = self.helper_motion.j(num)
            if vs.vim_state == VimState.VISUAL:
                vs.cursor.apply_motion_info_in_visual(motion_info)
            else:
                vs.cursor.apply_motion_info_in_vline(motion_info)
            vs.to_normal()
        vs.push_jump()
