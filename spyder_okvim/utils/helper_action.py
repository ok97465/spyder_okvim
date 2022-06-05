# -*- coding: utf-8 -*-
"""Module for action of vim."""
# %% Import
# Standard library imports
import re

# Third party imports
from qtpy.QtGui import QTextCursor

# Local imports
from spyder_okvim.utils.helper_motion import HelperMotion, MotionInfo, MotionType
from spyder_okvim.utils.vim_status import VimState


class HelperAction:
    """Helper for vim action."""

    def __init__(self, vim_status):
        self.vim_status = vim_status
        self.get_editor = vim_status.get_editor
        self.get_cursor = vim_status.get_cursor
        self.set_cursor = vim_status.set_cursor
        self.set_cursor_pos = vim_status.cursor.set_cursor_pos

        self.get_block_no_start_in_selection = (
            vim_status.get_block_no_start_in_selection
        )
        self.get_block_no_end_in_selection = vim_status.get_block_no_end_in_selection
        self.get_pos_start_in_selection = vim_status.get_pos_start_in_selection
        self.get_pos_end_in_selection = vim_status.get_pos_end_in_selection
        self.helper_motion = HelperMotion(vim_status)

    def join_lines(self, cursor_pos_start: int, block_no_start: int, block_no_end: int):
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
        text_list = [""]
        cursor.setPosition(cursor_pos_start)
        for _ in range(n_line - 1):
            cursor.movePosition(QTextCursor.NextBlock)
            text = cursor.block().text().lstrip()
            if text:
                text_list.append(text)

        # Replace text
        cursor.setPosition(cursor_pos_start)
        cursor.movePosition(QTextCursor.EndOfLine)
        cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor, n_line - 1)
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        cursor.insertText(" ".join(text_list))

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
        text = cursor.selectedText().replace("\u2029", "\n")
        text_sub = re.sub(r".", ch, text)
        cursor.insertText(text_sub)

        if self.vim_status.is_normal():
            self.vim_status.cursor.set_cursor_pos(pos_end - 1)

        editor = self.get_editor()
        editor.document_did_change()

    def _add_surrounding(self, ch: str, text: str) -> str:
        """Add surroundings."""
        prefix_dict = {
            "'": "'",
            '"': '"',
            "(": "( ",
            "{": "{ ",
            "[": "[ ",
            ")": "(",
            "}": "{",
            "]": "[",
        }

        suffix_dict = {
            "'": "'",
            '"': '"',
            "(": " )",
            "{": " }",
            "[": " ]",
            ")": ")",
            "}": "}",
            "]": "]",
        }

        return prefix_dict[ch] + text + suffix_dict[ch]

    def add_surrounding(self, pos_start: int, pos_end: int, ch: str):
        """Add surrouding."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        if self.vim_status.is_normal() and pos_start == pos_end:
            self.vim_status.cursor.set_cursor_pos(pos_start)
            return

        cursor = self.get_cursor()
        cursor.setPosition(pos_start)
        cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        text = cursor.selectedText().replace("\u2029", "\n")
        text_sub = self._add_surrounding(ch, text)
        cursor.insertText(text_sub)

        editor = self.get_editor()
        editor.document_did_change()

    def _delete_surrounding(self, ch: str, text: str) -> str:
        """Delete surroundings."""
        open_brackets = "([{"
        text_sub = text[1:-1]
        if ch in open_brackets:
            text_sub = text_sub.strip()
        return text_sub

    def delete_surrounding(self, ch: str) -> MotionInfo:
        """Delete surrouding."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        if ch in "'\"":
            motion_info = self.helper_motion.i_quote(ch)
            if motion_info.sel_start and motion_info.sel_end:
                motion_info.sel_start -= 1
                motion_info.sel_end += 1
        else:
            motion_info = self.helper_motion.a_bracket(1, ch)

        if motion_info.sel_start is None:
            return motion_info

        cursor = self.get_cursor()
        cursor.setPosition(motion_info.sel_start)
        cursor.setPosition(motion_info.sel_end, QTextCursor.KeepAnchor)
        text = cursor.selectedText().replace("\u2029", "\n")
        text_sub = self._delete_surrounding(ch, text)
        cursor.insertText(text_sub)

        editor = self.get_editor()
        editor.document_did_change()

        return motion_info

    def change_surrounding(self, ch_delete: str, ch_insert: str) -> MotionInfo:
        """Change surrouding."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        if ch_delete in "'\"":
            motion_info = self.helper_motion.i_quote(ch_delete)
            if motion_info.sel_start and motion_info.sel_end:
                motion_info.sel_start -= 1
                motion_info.sel_end += 1
        else:
            motion_info = self.helper_motion.a_bracket(1, ch_delete)

        if motion_info.sel_start is None:
            return motion_info

        cursor = self.get_cursor()
        cursor.setPosition(motion_info.sel_start)
        cursor.setPosition(motion_info.sel_end, QTextCursor.KeepAnchor)
        text = cursor.selectedText().replace("\u2029", "\n")
        text_sub = self._delete_surrounding(ch_delete, text)
        text_sub = self._add_surrounding(ch_insert, text_sub)
        cursor.insertText(text_sub)

        editor = self.get_editor()
        editor.document_did_change()

        return motion_info

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
            self._handle_case(motion_info.sel_start, motion_info.sel_end, method)
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
        if method == "swap":
            cursor.insertText(text.swapcase())
        elif method == "lower":
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
                text_list_indent.append("")
        texts_indent = "\n".join(text_list_indent)

        cursor.setPosition(pos_start)
        cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        cursor.insertText(texts_indent)

        block_start, _ = self.vim_status.cursor.get_block(pos_start)
        len_blank = len(block_start.text()) - len(block_start.text().lstrip())

        self.vim_status.cursor.set_cursor_pos(block_start.position() + len_blank)
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
        texts_unindent = "\n".join(text_list_unindent)

        cursor.setPosition(pos_start)
        cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        cursor.insertText(texts_unindent)

        block_start, _ = self.vim_status.cursor.get_block(pos_start)
        len_blank = len(block_start.text()) - len(block_start.text().lstrip())

        self.vim_status.cursor.set_cursor_pos(block_start.position() + len_blank)
        editor.document_did_change()

    def yank(self, motion_info: MotionInfo, is_explicit=False):
        """Yank text into register.

        Parameters
        ----------
        motion_info: MotionInfo
            motion_info
        is_explicit: Bool
            If this method is called explicitly, this arg is True.

        """
        if self.vim_status.is_normal():
            if motion_info.motion_type == MotionType.BlockWise:
                if motion_info.sel_start is None or motion_info.sel_end is None:
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
        txt = cursor.selectedText().replace("\u2029", "\n")
        if register_type == VimState.VLINE:
            txt += "\n"

        self.vim_status.set_register(register_name, txt, register_type)
        if is_explicit is True and register_name == '"':
            self.vim_status.set_register("0", txt, register_type)

        # Set message
        doc = cursor.document()
        nb_start = doc.findBlock(sel_start).blockNumber()
        nb_end = doc.findBlock(sel_end).blockNumber()
        if nb_start != nb_end:
            self.vim_status.set_message(f"{nb_end - nb_start + 1} lines yanked")

        # highlight yank
        if is_explicit is True and self.vim_status.is_normal():
            if self.vim_status.running_dot_cmd is False:
                self.vim_status.cursor.highlight_yank(sel_start, sel_end)

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
        reg = self.vim_status.get_register()
        self.vim_status.update_dot_cmd(connect_editor=False, register_name=reg.name)

        editor = self.get_editor()
        n_block_old = editor.blockCount()

        if reg.content:
            content = reg.content * num
        else:
            content = ""

        cursor = self.get_cursor()
        if reg.type != VimState.VLINE:
            if not cursor.atBlockEnd() and is_lower:
                cursor.movePosition(QTextCursor.Right)
            cursor.insertText(content)
            pos_end = cursor.selectionEnd()
            self.vim_status.to_normal()
            self.set_cursor_pos(pos_end - 1)
        elif is_lower is False:
            cursor.movePosition(QTextCursor.StartOfLine)
            block_number_old = cursor.block().blockNumber()
            cursor.insertText(content)
            block = self.get_editor().document().findBlockByNumber(block_number_old)
            cursor.setPosition(block.position())
            cursor = self._move_cursor_after_space(cursor)
            self.set_cursor_pos(cursor.position())
        else:
            cursor.movePosition(QTextCursor.EndOfLine)
            cursor_pos_old = cursor.position()
            if cursor.atEnd():
                cursor.insertText("\n" + content[:-1])
            else:
                cursor.movePosition(QTextCursor.Right)
                cursor.insertText(content)
            cursor.setPosition(cursor_pos_old)
            cursor.movePosition(QTextCursor.Down)
            cursor = self._move_cursor_after_space(cursor)
            self.set_cursor_pos(cursor.position())

        n_block_new = editor.blockCount()
        if n_block_new != n_block_old:
            self.vim_status.set_message(f"{n_block_new - n_block_old} more lines")

        editor = self.get_editor()
        editor.document_did_change()

    def paste_in_visual(self, num):
        """Put the text before the cursor."""
        editor = self.get_editor()
        reg = self.vim_status.get_register()
        self.vim_status.update_dot_cmd(connect_editor=False, register_name=reg.name)

        editor = self.get_editor()
        n_block_old = editor.blockCount()

        if reg.content:
            content = reg.content * num
            if reg.type == VimState.VLINE:
                content = "\n" + content
        else:
            content = ""

        cursor = self.get_cursor()
        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()
        block_no_start = self.get_block_no_start_in_selection()

        cursor.setPosition(sel_start)
        cursor.setPosition(sel_end, QTextCursor.KeepAnchor)
        cursor.insertText(content)

        if reg.type == VimState.VLINE:
            block = editor.document().findBlockByNumber(block_no_start + 1)
            cursor_pos_new = block.position()
        else:
            if "\n" in content:
                cursor_pos_new = sel_start
            else:
                cursor_pos_new = sel_start + len(content) - 1

        n_block_new = editor.blockCount()
        if n_block_new != n_block_old:
            self.vim_status.set_message(f"{n_block_new - n_block_old} more lines")

        editor.document_did_change()

        self.vim_status.to_normal()
        self.vim_status.cursor.set_cursor_pos(cursor_pos_new)

    def paste_in_vline(self, num):
        """Put the text before the cursor."""
        editor = self.get_editor()
        reg = self.vim_status.get_register()
        self.vim_status.update_dot_cmd(connect_editor=False, register_name=reg.name)

        editor = self.get_editor()
        n_block_old = editor.blockCount()

        if reg.content:
            if reg.type == VimState.VLINE:
                content = reg.content * num
                content = content[:-1]
            else:
                content = reg.content
                if num > 1:
                    content = (reg.content + "\n") * num
                    content = content[:-1]
        else:
            content = ""

        cursor = self.get_cursor()
        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()

        cursor.setPosition(sel_start)
        cursor.setPosition(sel_end, QTextCursor.KeepAnchor)
        cursor.insertText(content)

        n_block_new = editor.blockCount()
        if n_block_new != n_block_old:
            self.vim_status.set_message(f"{n_block_new - n_block_old} more lines")

        editor.document_did_change()

        self.vim_status.to_normal()
        self.vim_status.cursor.set_cursor_pos(sel_start)

    def delete(self, motion_info: MotionInfo, is_insert, replace_txt=""):
        """Delete selected text."""
        reg = self.vim_status.get_register()
        if is_insert:
            self.vim_status.update_dot_cmd(connect_editor=True, register_name=reg.name)
        else:
            self.vim_status.update_dot_cmd(connect_editor=False, register_name=reg.name)

        if self.vim_status.is_normal():
            if motion_info.motion_type == MotionType.BlockWise:
                if motion_info.sel_start is None or motion_info.sel_end is None:
                    return
            elif motion_info.cursor_pos is None:
                return

        cursor = self.get_cursor()
        editor = self.get_editor()
        n_block_old = editor.blockCount()
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

        # Set message
        n_block_new = editor.blockCount()
        if n_block_new != n_block_old:
            self.vim_status.set_message(f"{n_block_old - n_block_new} fewer lines")

        # Set cursor pos in normal
        if self.vim_status.is_normal():
            cursor_pos_new = sel_start
            if is_linewise and is_insert is False:
                n_block = editor.blockCount()
                block_no = min([block_no_start, n_block - 1])
                block = editor.document().findBlockByNumber(block_no)
                txt = block.text()
                cursor_pos_new = block.position() + len(txt) - len(txt.lstrip())
                cursor.setPosition(cursor_pos_new)

            if is_insert:
                self.set_cursor_pos(cursor_pos_new + len(replace_txt))
            else:
                self.vim_status.cursor.set_cursor_pos_without_end(cursor_pos_new)

        editor.document_did_change()

    def toggle_comment(self, motion_info: MotionInfo):
        """Toggle comment."""
        self.vim_status.update_dot_cmd(connect_editor=False)
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

        block_start, block_no_start = self.vim_status.cursor.get_block(pos_start)
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
