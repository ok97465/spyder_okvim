# -*- coding: utf-8 -*-
"""."""
# %% Import
# Standard library imports
from typing import Tuple

# Third party imports
from qtpy.QtCore import QPoint
from qtpy.QtGui import QTextCursor

# Local imports
from spyder_okvim.executor.executor_base import (
        ExecutorSubBase, RETURN_EXECUTOR_METHOD_INFO)
from spyder_okvim.utils.helper_motion import MotionInfo, MotionType


class ExecutorSelectMarkerEasymotion(ExecutorSubBase):
    """Submode for selecting marker of easymotion."""
    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self.motion_info = MotionInfo()

    def _set_motion_info(self, cur_pos, sel_start=None, sel_end=None,
                         motion_type=MotionType.LineWise):
        """Set motion info.

        Parameters
        ----------
        cur_pos: int, optional
            the position of cursor.
        sel_start: int, optional
            the start position of selection.
        sel_end: int, optional
            the end position of selection.
        motion_type: int
            motion type

        Returns
        -------
        MotionInfo
            motion info

        """
        self.motion_info.cursor_pos = cur_pos
        self.motion_info.sel_start = sel_start
        self.motion_info.sel_end = sel_end
        self.motion_info.motion_type = motion_type

        return self.motion_info

    def __call__(self, txt: str):
        manager_marker = self.vim_status.manager_marker_easymotion
        manager_marker.handle_user_input(txt)

        motion_type = manager_marker.motion_type
        pos_list = manager_marker.position_list
        len_pos = len(pos_list)

        if len_pos > 1:
            self.vim_status.update_marker_for_easymotion()
            return True
        elif len_pos == 0:
            self.vim_status.remove_marker_of_easymotion()
            self.vim_status.sub_mode = None
            return True
        else:
            self.vim_status.remove_marker_of_easymotion()
            self.vim_status.sub_mode = None
            self._set_motion_info(pos_list[0], motion_type=motion_type)
            self.execute_func_deferred(self.motion_info)
            return True


class ExecutorEasymotion(ExecutorSubBase):
    """Submode of easymotion."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

        self.dispatcher = {
                'w': self.forward_words,
                'b': self.backward_words,
                'j': self.forward_start_of_line,
                'k': self.backward_start_of_line
                }
        self.executor_select_maker = ExecutorSelectMarkerEasymotion(vim_status)

    def __call__(self, txt: str):
        if txt.isdigit():
            return False
        num = 1
        num_str = ''
        if len(txt) > 1:
            num_str = txt[:-1]
            num = int(num_str)

        method = self.dispatcher.get(txt[-1], None)

        ret = None
        if method:
            ret = method(num, num_str)

        if ret:
            self.vim_status.sub_mode = ret.sub_mode
            return ret.clear_command_line
        else:
            self.vim_status.sub_mode = None
            return True

    def get_cursor_pos_of_viewport(self) -> Tuple[int, int]:
        """Get the cursor position of viewport of editor."""
        editor = self.vim_status.get_editor()
        start_pos = editor.cursorForPosition(QPoint(0, 0)).position()
        bottom_right = QPoint(
            editor.viewport().width() - 1, editor.viewport().height() - 1)
        end_pos = editor.cursorForPosition(bottom_right).position()

        return start_pos, end_pos

    def set_position_result_to_vim_status(self, positions, motion_type):
        """Set positions to vim status for easymotion."""
        executor_sub = self.executor_select_maker
        if positions:
            executor_sub.set_func_list_deferred(self.func_list_deferred)
            self.vim_status.set_marker_for_easymotion(positions, motion_type)
            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def forward_words(self, num=1, num_str=''):
        """Easymotion-w."""
        editor = self.vim_status.get_editor()
        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = self.get_cursor_pos_of_viewport()
        start_pos = max([view_start_pos, cur_pos])

        cursor = editor.textCursor()
        cursor.setPosition(start_pos)
        texts = editor.toPlainText()

        positions = []
        while 1:
            cursor.movePosition(QTextCursor.NextWord)
            if cursor.position() >= view_end_pos:
                break
            if cursor.atBlockEnd():
                continue
            ch = texts[cursor.position()]
            if not ch.isalnum():
                continue

            positions.append(cursor.position())

        return self.set_position_result_to_vim_status(positions,
                                                      MotionType.CharWise)

    def backward_words(self, num=1, num_str=''):
        """Easymotion-b."""
        editor = self.vim_status.get_editor()
        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = self.get_cursor_pos_of_viewport()
        start_pos = min([view_end_pos, cur_pos])

        cursor = editor.textCursor()
        cursor.setPosition(start_pos)
        texts = editor.toPlainText()

        positions = []
        while 1:
            if cursor.movePosition(QTextCursor.PreviousWord) is False:
                break
            if cursor.atBlockEnd():
                continue
            ch = texts[cursor.position()]
            if not ch.isalnum():
                continue

            positions.append(cursor.position())
            if cursor.position() <= view_start_pos:
                break

        return self.set_position_result_to_vim_status(positions,
                                                      MotionType.CharWise)

    def forward_start_of_line(self, num=1, num_str=''):
        """Easymotion-j."""
        editor = self.vim_status.get_editor()
        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = self.get_cursor_pos_of_viewport()
        start_pos = max([view_start_pos, cur_pos])

        cursor = editor.textCursor()
        cursor.setPosition(start_pos)

        positions = []
        while 1:
            if cursor.movePosition(QTextCursor.NextBlock) is False:
                break
            if cursor.position() >= view_end_pos:
                break
            pos = cursor.position()
            text = cursor.block().text()

            if text.strip():
                pos += len(text) - len(text.lstrip())

            positions.append(pos)

        return self.set_position_result_to_vim_status(positions,
                                                      MotionType.LineWise)

    def backward_start_of_line(self, num=1, num_str=''):
        """Easymotion-j."""
        editor = self.vim_status.get_editor()
        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = self.get_cursor_pos_of_viewport()
        start_pos = min([view_end_pos, cur_pos])

        cursor = editor.textCursor()
        cursor.setPosition(start_pos)

        positions = []
        while 1:
            if cursor.movePosition(QTextCursor.PreviousBlock) is False:
                break
            if cursor.position() < view_start_pos:
                break
            pos = cursor.position()
            text = cursor.block().text()

            if text.strip():
                pos += len(text) - len(text.lstrip())

            positions.append(pos)

        return self.set_position_result_to_vim_status(positions,
                                                      MotionType.LineWise)

