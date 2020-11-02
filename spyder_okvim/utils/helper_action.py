# -*- coding: utf-8 -*-
"""Module for action of vim."""
# %% Import
# Standard library imports
import re

# Third party imports
from qtpy.QtGui import QTextCursor

# Local imports
from spyder_okvim.utils.helper_motion import MotionType, MotionInfo
from spyder_okvim.utils.vim_status import VimState


class HelperAction:
    """Helper for vim action."""

    def __init__(self, vim_status):
        self.vim_status = vim_status
        self.get_editor = vim_status.get_editor
        self.get_cursor = vim_status.get_cursor
        self.set_cursor = vim_status.set_cursor
        self.set_cursor_pos = vim_status.cursor.set_cursor_pos

        self.get_block_no_start_in_selection = \
            vim_status.get_block_no_start_in_selection
        self.get_block_no_end_in_selection = \
            vim_status.get_block_no_end_in_selection
        self.get_pos_start_in_selection = \
            vim_status.get_pos_start_in_selection
        self.get_pos_end_in_selection = \
            vim_status.get_pos_end_in_selection

    def join_lines(self,
                   cursor_pos_start: int,
                   block_no_start: int,
                   block_no_end: int):
        """Join lines."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        editor = self.get_editor()
        cursor = editor.textCursor()
        n_block = editor.blockCount()

        if block_no_end >= n_block - 1:
            block_no_end = n_block - 1

        if block_no_start == block_no_end:
            return

        n_line = block_no_end - block_no_start + 1
        text_list = ['']
        cursor.setPosition(cursor_pos_start)
        for _ in range(n_line - 1):
            cursor.movePosition(QTextCursor.NextBlock)
            text = cursor.block().text().lstrip()
            if text:
                text_list.append(text)

        # Replace text
        cursor.setPosition(cursor_pos_start)
        cursor.movePosition(QTextCursor.EndOfLine)
        cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor,
                            n_line - 1)
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        cursor.insertText(' '.join(text_list))

        # Move position of cursor
        cursor.movePosition(QTextCursor.EndOfBlock)
        cursor.movePosition(QTextCursor.Left, n=len(text_list[-1]) + 1)
        pos = cursor.position()

        self.set_cursor_pos(pos)

        editor.document_did_change()

    def replace_txt_with_ch(self, pos_start: int, pos_end: int, ch: str):
        """Replace selected text with character of argument."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        if self.vim_status.is_normal() and pos_start == pos_end:
            self.vim_status.cursor.set_cursor_pos(pos_start)
            return

        cursor = self.get_cursor()
        cursor.setPosition(pos_start)
        cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        text = cursor.selectedText().replace('\u2029', '\n')
        text_sub = re.sub(r'.', ch, text)
        cursor.insertText(text_sub)

        if self.vim_status.is_normal():
            self.vim_status.cursor.set_cursor_pos(pos_end - 1)

        editor = self.get_editor()
        editor.document_did_change()

    def handle_case(self, motion_info: MotionInfo, method):
        """Swap case."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        if not self.vim_status.is_normal():
            sel_start = self.get_pos_start_in_selection()
            sel_end = self.get_pos_end_in_selection()
            self._handle_case(sel_start, sel_end, method)
            self.vim_status.to_normal()
            self.vim_status.cursor.set_cursor_pos(sel_start)
        elif motion_info.motion_type == MotionType.BlockWise:
            self._handle_case(motion_info.sel_start, motion_info.sel_end,
                              method)
            self.vim_status.cursor.set_cursor_pos(motion_info.sel_start)
        else:
            cursor = self.get_cursor()
            cursor_pos_cur = cursor.position()
            cursor_pos_new = motion_info.cursor_pos
            if cursor_pos_new is None:
                return
            pos_start, pos_end = sorted([cursor_pos_cur, cursor_pos_new])

            if motion_info.motion_type == MotionType.CharWise:
                self._handle_case(pos_start, pos_end, method)
            elif motion_info.motion_type == MotionType.CharWiseIncludingEnd:
                self._handle_case(pos_start, pos_end + 1, method)
            elif motion_info.motion_type == MotionType.LineWise:
                block_start, _ = self.vim_status.cursor.get_block(pos_start)
                block_end, _ = self.vim_status.cursor.get_block(pos_end)
                sel_start = block_start.position()
                sel_end = block_end.position() + block_end.length() - 1
                self._handle_case(sel_start, sel_end, method)

                # Exception case, guu, gUU, g~~
                if pos_start == pos_end:
                    pos_start = sel_start
            self.vim_status.cursor.set_cursor_pos(pos_start)

    def _handle_case(self, pos_start: int, pos_end: int, method):
        """Swap case."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        cursor = self.get_cursor()

        cursor.setPosition(pos_start)
        cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        text = cursor.selectedText()
        if method == 'swap':
            cursor.insertText(text.swapcase())
        elif method == 'lower':
            cursor.insertText(text.lower())
        else:
            cursor.insertText(text.upper())

        editor = self.get_editor()
        editor.document_did_change()

    def indent(self, motion_info: MotionInfo):
        """Shift lines rightwards."""
        cursor = self.get_cursor()
        cursor_pos_cur = cursor.position()
        cursor_pos_new = motion_info.cursor_pos
        if cursor_pos_new is None:
            return
        pos_start, pos_end = sorted([cursor_pos_cur, cursor_pos_new])
        self._indent(pos_start, pos_end)

    def _indent(self, pos_start: int, pos_end: int):
        """Shift lines rightwards."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        editor = self.get_editor()
        cursor = self.get_cursor()

        get_block = self.vim_status.cursor.get_block
        block_start, block_no_start = get_block(pos_start)
        block_end, block_no_end = get_block(pos_end)

        pos_start = block_start.position()
        pos_end = block_end.position() + block_end.length() - 1

        text_list = []
        for no in range(block_no_start, block_no_end + 1):
            block = editor.document().findBlockByNumber(no)
            text_list.append(block.text())

        indent = self.vim_status.indent
        text_list_indent = []
        for text in text_list:
            if text:
                text_list_indent.append(indent + text)
            else:
                text_list_indent.append('')
        texts_indent = '\n'.join(text_list_indent)

        cursor.setPosition(pos_start)
        cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        cursor.insertText(texts_indent)

        block_start, _ = self.vim_status.cursor.get_block(pos_start)
        len_blank = len(block_start.text()) - len(block_start.text().lstrip())

        self.vim_status.cursor.set_cursor_pos(block_start.position()
                                              + len_blank)
        editor.document_did_change()

    def unindent(self, motion_info: MotionInfo):
        """Shift lines leftwards."""
        cursor = self.get_cursor()
        cursor_pos_cur = cursor.position()
        cursor_pos_new = motion_info.cursor_pos
        if cursor_pos_new is None:
            return
        pos_start, pos_end = sorted([cursor_pos_cur, cursor_pos_new])
        self._unindent(pos_start, pos_end)

    def _unindent(self, pos_start: int, pos_end: int):
        """Shift lines leftwards."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        editor = self.get_editor()
        cursor = self.get_cursor()

        get_block = self.vim_status.cursor.get_block
        block_start, block_no_start = get_block(pos_start)
        block_end, block_no_end = get_block(pos_end)

        pos_start = block_start.position()
        pos_end = block_end.position() + block_end.length() - 1

        text_list = []
        for no in range(block_no_start, block_no_end + 1):
            block = editor.document().findBlockByNumber(no)
            text_list.append(block.text())

        indent = self.vim_status.indent
        len_indent = len(indent)
        text_list_unindent = []
        for text in text_list:
            n_space = len(text) - len(text.lstrip())
            idx_discard = min([n_space, len_indent])
            text_list_unindent.append(text[idx_discard:])
        texts_unindent = '\n'.join(text_list_unindent)

        cursor.setPosition(pos_start)
        cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        cursor.insertText(texts_unindent)

        block_start, _ = self.vim_status.cursor.get_block(pos_start)
        len_blank = len(block_start.text()) - len(block_start.text().lstrip())

        self.vim_status.cursor.set_cursor_pos(block_start.position()
                                              + len_blank)
        editor.document_did_change()

    def yank(self, motion_info: MotionInfo):
        """Yank text into register."""
        if self.vim_status.is_normal():
            if motion_info.motion_type == MotionType.BlockWise:
                if (motion_info.sel_start is None
                        or motion_info.sel_end is None):
                    return None, None
            elif motion_info.cursor_pos is None:
                return None, None

        register_name = self.vim_status.get_register_name()
        register_type = VimState.NORMAL

        if not self.vim_status.is_normal():
            sel_start = self.get_pos_start_in_selection()
            sel_end = self.get_pos_end_in_selection()
            if self.vim_status.vim_state == VimState.VLINE:
                register_type = VimState.VLINE
        elif motion_info.motion_type == MotionType.BlockWise:
            sel_start = motion_info.sel_start
            sel_end = motion_info.sel_end
        else:
            cursor = self.get_cursor()
            cursor_pos_cur = cursor.position()
            cursor_pos_new = motion_info.cursor_pos
            sel_start, sel_end = sorted([cursor_pos_cur, cursor_pos_new])

            if motion_info.motion_type == MotionType.CharWiseIncludingEnd:
                sel_end += 1
            elif motion_info.motion_type == MotionType.LineWise:
                block_start, _ = self.vim_status.cursor.get_block(sel_start)
                block_end, _ = self.vim_status.cursor.get_block(sel_end)
                sel_start = block_start.position()
                sel_end = block_end.position() + block_end.length() - 1
                register_type = VimState.VLINE

        cursor = self.get_cursor()
        cursor.setPosition(sel_start)
        cursor.setPosition(sel_end, QTextCursor.KeepAnchor)
        txt = cursor.selectedText().replace('\u2029', '\n')
        if register_type == VimState.VLINE:
            txt += '\n'

        self.vim_status.set_register(register_name, txt, register_type)

        return sel_start, sel_end

    def _move_cursor_after_space(self, cursor):
        """Move cursor after white space."""
        txt = cursor.block().text()
        n_space = len(txt) - len(txt.lstrip())
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.movePosition(QTextCursor.Right, n=n_space)
        return cursor

    def paste_in_normal(self, num, is_lower):
        """Put the text before the cursor."""
        # TODO: apply num
        reg = self.vim_status.get_register()
        self.vim_status.update_dot_cmd(connect_editor=False,
                                       register_name=reg.name)

        cursor = self.get_cursor()
        if reg.type != VimState.VLINE:
            if not cursor.atBlockEnd() and is_lower:
                cursor.movePosition(QTextCursor.Right)
            cursor.insertText(reg.content)
            pos_end = cursor.selectionEnd()
            self.vim_status.to_normal()
            self.set_cursor_pos(pos_end - 1)
        elif is_lower is False:
            cursor.movePosition(QTextCursor.StartOfLine)
            block_number_old = cursor.block().blockNumber()
            cursor.insertText(reg.content)
            block = self.get_editor().document().findBlockByNumber(
                block_number_old)
            cursor.setPosition(block.position())
            cursor = self._move_cursor_after_space(cursor)
            self.set_cursor_pos(cursor.position())
        else:
            cursor.movePosition(QTextCursor.EndOfLine)
            cursor_pos_old = cursor.position()
            if cursor.atEnd():
                cursor.insertText('\n' + reg.content[:-1])
            else:
                cursor.movePosition(QTextCursor.Right)
                cursor.insertText(reg.content)
            cursor.setPosition(cursor_pos_old)
            cursor.movePosition(QTextCursor.Down)
            cursor = self._move_cursor_after_space(cursor)
            self.set_cursor_pos(cursor.position())

        editor = self.get_editor()
        editor.document_did_change()

    def delete(self, motion_info: MotionInfo, is_insert, replace_txt=''):
        """Delete selected text."""
        reg = self.vim_status.get_register()
        if is_insert:
            self.vim_status.update_dot_cmd(connect_editor=True,
                                           register_name=reg.name)
        else:
            self.vim_status.update_dot_cmd(connect_editor=False,
                                           register_name=reg.name)

        if self.vim_status.is_normal():
            if motion_info.motion_type == MotionType.BlockWise:
                if (motion_info.sel_start is None
                        or motion_info.sel_end is None):
                    return
            elif motion_info.cursor_pos is None:
                return

        cursor = self.get_cursor()
        editor = self.get_editor()
        is_linewise = False

        if not self.vim_status.is_normal():
            sel_start = self.get_pos_start_in_selection()
            sel_end = self.get_pos_end_in_selection()
            if self.vim_status.vim_state == VimState.VLINE:
                is_linewise = True
        elif motion_info.motion_type == MotionType.BlockWise:
            sel_start = motion_info.sel_start
            sel_end = motion_info.sel_end
        else:
            cursor = self.get_cursor()
            cursor_pos_cur = cursor.position()
            cursor_pos_new = motion_info.cursor_pos
            sel_start, sel_end = sorted([cursor_pos_cur, cursor_pos_new])

            if motion_info.motion_type == MotionType.CharWiseIncludingEnd:
                sel_end += 1
            elif motion_info.motion_type == MotionType.LineWise:
                is_linewise = True

        if is_linewise:
            n_block = editor.blockCount()
            get_block = self.vim_status.cursor.get_block
            block_start, block_no_start = get_block(sel_start)
            block_end, block_no_end = get_block(sel_end)
            if is_insert:
                sel_start = block_start.position()
                sel_end = block_end.position() + block_end.length() - 1
            else:
                if block_no_start == 0 and block_no_end == n_block - 1:
                    sel_start = block_start.position()
                    sel_end = block_end.position() + block_end.length() - 1
                elif block_no_start == 0:
                    sel_start = block_start.position()
                    sel_end = block_end.position() + block_end.length()
                else:
                    sel_start = block_start.position() - 1
                    sel_end = block_end.position() + block_end.length() - 1

        cursor.setPosition(sel_start)
        cursor.setPosition(sel_end, QTextCursor.KeepAnchor)
        cursor.insertText(replace_txt)

        # Set cursor pos in normal
        if self.vim_status.is_normal():
            cursor_pos_new = sel_start
            if is_linewise and is_insert is False:
                n_block = editor.blockCount()
                block_no = min([block_no_start, n_block - 1])
                block = editor.document().findBlockByNumber(block_no)
                txt = block.text()
                cursor_pos_new = (block.position()
                                  + len(txt) - len(txt.lstrip()))
                cursor.setPosition(cursor_pos_new)

            if is_insert:
                self.set_cursor_pos(cursor_pos_new + len(replace_txt))
            else:
                self.vim_status.cursor.set_cursor_pos_without_end(
                    cursor_pos_new)

        editor.document_did_change()

    def toggle_comment(self, motion_info: MotionInfo):
        """Toggle comment."""
        editor = self.get_editor()
        if not self.vim_status.is_normal():
            pos_start = self.get_pos_start_in_selection()
            pos_end = self.get_pos_end_in_selection()
        elif motion_info.motion_type == MotionType.BlockWise:
            pos_start = motion_info.sel_start
            pos_end = motion_info.sel_end
            if not pos_start or not pos_end:
                return
        else:
            cursor = editor.textCursor()
            cursor_pos_cur = cursor.position()
            cursor_pos_new = motion_info.cursor_pos
            if cursor_pos_new is None:
                return
            pos_start, pos_end = sorted([cursor_pos_cur, cursor_pos_new])

        block_start, block_no_start = self.vim_status.cursor.get_block(
                pos_start)
        block_end, _ = self.vim_status.cursor.get_block(pos_end)
        pos_start = block_start.position()
        pos_end = block_end.position() + block_end.length() - 1

        new_cursor = editor.textCursor()
        new_cursor.setPosition(pos_start, QTextCursor.MoveAnchor)
        new_cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        editor.setTextCursor(new_cursor)
        editor.toggle_comment()

        new_cursor = editor.textCursor()
        block = editor.document().findBlockByNumber(block_no_start)
        pos_start = block.position()
        new_cursor.setPosition(pos_start, QTextCursor.MoveAnchor)
        editor.setTextCursor(new_cursor)

        self.vim_status.to_normal()
        self.vim_status.cursor.set_cursor_pos(pos_start)

        editor.document_did_change()
