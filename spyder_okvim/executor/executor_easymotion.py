# -*- coding: utf-8 -*-
"""Support for EasyMotion-like navigation.

EasyMotion highlights possible jump targets in the editor and lets the user
select one with a short key sequence.  This executor provides helper methods
used by the normal and visual mode executors to implement those jumps.
"""

# Third Party Libraries
from qtpy.QtCore import QPoint
from qtpy.QtGui import QTextCursor, QTextDocument

# Project Libraries
from spyder_okvim.executor.executor_base import (
    RETURN_EXECUTOR_METHOD_INFO,
    ExecutorSubBase,
)
from spyder_okvim.utils.motion import MotionInfo, MotionType


class ExecutorSelectMarkerEasymotion(ExecutorSubBase):
    """Submode for selecting marker of easymotion."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self.motion_info = MotionInfo()

    def _set_motion_info(
        self,
        cur_pos: int | None,
        sel_start: int | None = None,
        sel_end: int | None = None,
        motion_type: int = MotionType.LineWise,
    ):
        """Set motion info.

        Args:
            cur_pos: the position of cursor.
            sel_start: the start position of selection.
            sel_end: the end position of selection.
            motion_type: motion type

        Returns:
            MotionInfo

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
            return self.process_return(self.execute_func_deferred(self.motion_info))


class ExecutorSearchCharEasymotion(ExecutorSubBase):
    """Submode for searching character in easymotion."""

    def __init__(self, vim_status, executor_select_maker):
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self.executor_select_maker = executor_select_maker
        self.n_input_required = 1
        self.search_method = None

    def __call__(self, txt: str):
        if len(txt) < self.n_input_required:
            return False

        self.vim_status.sub_mode = None
        ret = None
        if self.search_method:
            ret = self.search_method(txt)

        if ret:
            self.vim_status.sub_mode = ret.sub_mode
            return ret.clear_command_line
        else:
            self.vim_status.sub_mode = None
            return True

    def get_cursor_pos_of_viewport(self) -> tuple[int, int]:
        """Get the cursor position of viewport of editor."""
        editor = self.vim_status.get_editor()
        start_pos = editor.cursorForPosition(QPoint(0, 0)).position()
        bottom_right = QPoint(
            editor.viewport().width() - 1, editor.viewport().height() - 1
        )
        end_pos = editor.cursorForPosition(bottom_right).position()

        return start_pos, end_pos

    def set_search_method(self, method_name: str):
        "Set search method."
        self.search_method = {
            "ch_forwards": self.forwards_find_char,
            "ch_backwards": self.backwards_find_char,
        }.get(method_name, None)

    def set_position_result_to_vim_status(self, positions, motion_type):
        """Set positions to vim status for easymotion."""
        executor_sub = self.executor_select_maker
        if positions:
            executor_sub.set_func_list_deferred(
                self.func_list_deferred, self.return_deferred
            )
            self.vim_status.set_marker_for_easymotion(positions, motion_type)
            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def forwards_find_char(self, characters: str):
        """Find characters forwards."""
        editor = self.vim_status.get_editor()

        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = self.get_cursor_pos_of_viewport()
        start_pos = min([view_end_pos, cur_pos]) + 1

        positions = []
        while view_start_pos <= start_pos <= view_end_pos:
            cursor = editor.document().find(characters, start_pos)
            if cursor.isNull():
                break
            positions.append(cursor.position() - len(characters))
            start_pos = cursor.position()

        return self.set_position_result_to_vim_status(
            positions, MotionType.CharWiseIncludingEnd
        )

    def backwards_find_char(self, characters: str):
        """Find characters backwards."""
        editor = self.vim_status.get_editor()

        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = self.get_cursor_pos_of_viewport()
        start_pos = max([view_start_pos, cur_pos]) - 1

        positions = []
        while view_start_pos <= start_pos <= view_end_pos:
            cursor = editor.document().find(
                characters, start_pos, QTextDocument.FindBackward
            )
            if cursor.isNull():
                break
            positions.append(cursor.position() - len(characters))
            start_pos = cursor.position() - len(characters)

        return self.set_position_result_to_vim_status(positions, MotionType.CharWise)


class ExecutorEasymotion(ExecutorSubBase):
    """Submode of easymotion."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

        self.dispatcher = {
            "w": self.forward_words,
            "b": self.backward_words,
            "j": self.forward_start_of_line,
            "k": self.backward_start_of_line,
            "f": self.forwards_find_char,
            "F": self.backwards_find_char,
        }
        self.executor_select_maker = ExecutorSelectMarkerEasymotion(vim_status)
        self.executor_search_char = ExecutorSearchCharEasymotion(
            vim_status, self.executor_select_maker
        )

    def __call__(self, txt: str):
        if txt.isdigit():
            return False
        num = 1
        num_str = ""
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

    def get_cursor_pos_of_viewport(self) -> tuple[int, int]:
        """Get the cursor position of viewport of editor."""
        editor = self.vim_status.get_editor()
        start_pos = editor.cursorForPosition(QPoint(0, 0)).position()
        bottom_right = QPoint(
            editor.viewport().width() - 1, editor.viewport().height() - 1
        )
        end_pos = editor.cursorForPosition(bottom_right).position()

        return start_pos, end_pos

    def set_position_result_to_vim_status(self, positions, motion_type):
        """Set positions to vim status for easymotion."""
        executor_sub = self.executor_select_maker
        if positions:
            executor_sub.set_func_list_deferred(
                self.func_list_deferred,
                self.return_deferred,
            )
            self.vim_status.set_marker_for_easymotion(positions, motion_type)
            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def forward_words(self, num=1, num_str=""):
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

        return self.set_position_result_to_vim_status(positions, MotionType.CharWise)

    def backward_words(self, num=1, num_str=""):
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

        return self.set_position_result_to_vim_status(positions, MotionType.CharWise)

    def forward_start_of_line(self, num=1, num_str=""):
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

        return self.set_position_result_to_vim_status(positions, MotionType.LineWise)

    def backward_start_of_line(self, num=1, num_str=""):
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

        return self.set_position_result_to_vim_status(positions, MotionType.LineWise)

    def forwards_find_char(self, num=1, num_str=""):
        """Find characters forwards."""
        executor_sub = self.executor_search_char
        executor_sub.set_search_method("ch_forwards")
        executor_sub.n_input_required = num
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def backwards_find_char(self, num=1, num_str=""):
        """Find characters forwards."""
        executor_sub = self.executor_search_char
        executor_sub.set_search_method("ch_backwards")
        executor_sub.n_input_required = num
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
