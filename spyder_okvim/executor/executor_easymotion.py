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
    ExecutorSubBase,
    ExecutorTransition,
)
from spyder_okvim.utils.motion import MotionInfo, MotionType


def _viewport_positions(editor):
    """Return the document offsets at the visible viewport corners."""
    start = editor.cursorForPosition(QPoint(0, 0)).position()
    bottom_right = QPoint(editor.viewport().width() - 1, editor.viewport().height() - 1)
    return start, editor.cursorForPosition(bottom_right).position()


def _show_marker_state(status):
    """Report remaining targets and the finite label budget."""
    manager = status.manager_marker_easymotion
    message = f"EasyMotion: select label · {len(manager.position_list)} candidates"
    if manager.total_count > manager.visible_count:
        message += f" · showing {manager.visible_count}/{manager.total_count}; scroll and retry"
    status.set_message(message + " · Backspace undo label · Esc cancel")


def _starts_with_letter_or_number(cursor):
    """Inspect one Unicode character without scanning the document prefix."""
    character_cursor = QTextCursor(cursor)
    character_cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
    character = character_cursor.selectedText()
    return bool(character) and character[0].isalnum()


class ExecutorSelectMarkerEasymotion(ExecutorSubBase):
    """Submode for selecting marker of easymotion."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

    def __call__(self, txt: str):
        if txt == "\x1b":
            self.on_escape()
            return True
        manager_marker = self.vim_status.manager_marker_easymotion
        manager_marker.handle_user_input(txt)

        motion_type = manager_marker.motion_type
        pos_list = manager_marker.position_list
        len_pos = len(pos_list)

        if txt == "\b" or len_pos > 1:
            self.vim_status.update_marker_for_easymotion()
            _show_marker_state(self.vim_status)
            return True
        elif len_pos == 0:
            self.vim_status.remove_marker_of_easymotion()
            self.vim_status.sub_mode = None
            self.vim_status.set_message("EasyMotion: no target for that label")
            return True
        else:
            self.vim_status.remove_marker_of_easymotion()
            self.vim_status.sub_mode = None
            self.vim_status.set_message("")
            motion_info = MotionInfo(pos_list[0], motion_type=motion_type)
            return self.process_return(self.execute_func_deferred(motion_info))

    def on_escape(self):
        """Release overlays and stage feedback on cancellation."""
        self.vim_status.remove_marker_of_easymotion()
        self.vim_status.set_message("")
        self.vim_status.sub_mode = None


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
            remaining = self.n_input_required - len(txt)
            self.vim_status.set_message(
                f"EasyMotion: enter {remaining} more characters · Esc cancel"
            )
            return False

        self.vim_status.sub_mode = None
        ret = None
        if self.search_method:
            ret = self.search_method(txt)

        return self.process_return(ret)

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
            _show_marker_state(self.vim_status)
            return ExecutorTransition(executor_sub, True)
        self.vim_status.set_message("EasyMotion: no matching target in this view")

    def on_escape(self):
        self.vim_status.set_message("")

    def forwards_find_char(self, characters: str):
        """Find characters forwards."""
        editor = self.vim_status.get_editor()

        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = _viewport_positions(editor)
        start_pos = max(view_start_pos, cur_pos + 1)

        positions = []
        while start_pos <= view_end_pos:
            cursor = editor.document().find(characters, start_pos)
            if cursor.isNull() or cursor.selectionStart() > view_end_pos:
                break
            positions.append(cursor.selectionStart())
            start_pos = cursor.position()

        return self.set_position_result_to_vim_status(
            positions, MotionType.CharWiseIncludingEnd
        )

    def backwards_find_char(self, characters: str):
        """Find characters backwards."""
        editor = self.vim_status.get_editor()

        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = _viewport_positions(editor)
        # Qt's backward search excludes its offset. Keep the last visible
        # character eligible even when scrolling has moved the cursor offscreen.
        start_pos = min(view_end_pos + 1, cur_pos)

        positions = []
        while start_pos > view_start_pos:
            cursor = editor.document().find(
                characters, start_pos, QTextDocument.FindBackward
            )
            if cursor.isNull() or cursor.selectionStart() < view_start_pos:
                break
            positions.append(cursor.selectionStart())
            start_pos = cursor.selectionStart()

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
        count = 1
        count_text = ""
        if len(txt) > 1:
            count_text = txt[:-1]
            count = int(count_text)

        method = self.dispatcher.get(txt[-1], None)

        ret = None
        if method:
            ret = method(count, count_text)

        return self.process_return(ret)

    def set_position_result_to_vim_status(self, positions, motion_type):
        """Set positions to vim status for easymotion."""
        executor_sub = self.executor_select_maker
        if positions:
            executor_sub.set_func_list_deferred(
                self.func_list_deferred,
                self.return_deferred,
            )
            self.vim_status.set_marker_for_easymotion(positions, motion_type)
            _show_marker_state(self.vim_status)
            return ExecutorTransition(executor_sub, True)
        self.vim_status.set_message("EasyMotion: no matching target in this view")

    def forward_words(self, count=1, count_text=""):
        """Easymotion-w."""
        editor = self.vim_status.get_editor()
        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = _viewport_positions(editor)
        start_pos = max([view_start_pos, cur_pos])

        cursor = editor.textCursor()
        cursor.setPosition(start_pos)

        positions = []
        while 1:
            cursor.movePosition(QTextCursor.NextWord)
            if cursor.position() >= view_end_pos:
                break
            if cursor.atBlockEnd():
                continue
            if not _starts_with_letter_or_number(cursor):
                continue

            positions.append(cursor.position())

        return self.set_position_result_to_vim_status(positions, MotionType.CharWise)

    def backward_words(self, count=1, count_text=""):
        """Easymotion-b."""
        editor = self.vim_status.get_editor()
        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = _viewport_positions(editor)
        start_pos = min([view_end_pos, cur_pos])

        cursor = editor.textCursor()
        cursor.setPosition(start_pos)

        positions = []
        while 1:
            if cursor.movePosition(QTextCursor.PreviousWord) is False:
                break
            if cursor.position() < view_start_pos:
                break
            if cursor.atBlockEnd():
                continue
            if not _starts_with_letter_or_number(cursor):
                continue

            positions.append(cursor.position())
            if cursor.position() <= view_start_pos:
                break

        return self.set_position_result_to_vim_status(positions, MotionType.CharWise)

    def forward_start_of_line(self, count=1, count_text=""):
        """Easymotion-j."""
        editor = self.vim_status.get_editor()
        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = _viewport_positions(editor)
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

    def backward_start_of_line(self, count=1, count_text=""):
        """Easymotion-j."""
        editor = self.vim_status.get_editor()
        cur_pos = editor.textCursor().position()
        view_start_pos, view_end_pos = _viewport_positions(editor)
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

    def forwards_find_char(self, count=1, count_text=""):
        """Find characters forwards."""
        executor_sub = self.executor_search_char
        executor_sub.set_search_method("ch_forwards")
        executor_sub.n_input_required = count
        self.vim_status.set_message(
            f"EasyMotion: enter {count} characters · Esc cancel"
        )
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )
        return ExecutorTransition(executor_sub, True)

    def backwards_find_char(self, count=1, count_text=""):
        """Find characters forwards."""
        executor_sub = self.executor_search_char
        executor_sub.set_search_method("ch_backwards")
        executor_sub.n_input_required = count
        self.vim_status.set_message(
            f"EasyMotion: enter {count} characters · Esc cancel"
        )
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )
        return ExecutorTransition(executor_sub, True)
