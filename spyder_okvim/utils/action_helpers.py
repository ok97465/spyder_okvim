# -*- coding: utf-8 -*-
"""Utility functions that implement Vim-style editing actions."""

# Standard Libraries
import re

# Third Party Libraries
from qtpy.QtGui import QTextCursor

# Project Libraries
from spyder_okvim.utils.motion import MotionInfo, MotionType
from spyder_okvim.utils.motion_helpers import MotionHelper
from spyder_okvim.vim import VimState


def _get_block_texts(editor, start_block: int, end_block: int) -> list[str]:
    """Return the text of blocks between two numbers inclusive."""

    return [
        editor.document().findBlockByNumber(no).text()
        for no in range(start_block, end_block + 1)
    ]


class ActionHelper:
    """Perform editing actions driven by Vim commands."""

    def __init__(self, vim_status):
        """Initialize helper with the shared Vim status.

        Args:
            vim_status: Object managing editor and cursor state.
        """
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
        self.helper_motion = MotionHelper(vim_status)

    def _get_block_range(
        self, pos_start: int, pos_end: int
    ) -> tuple[int, int, int, int]:
        """Return block numbers and adjusted positions for a range."""

        get_block = self.vim_status.cursor.get_block
        block_start, block_no_start = get_block(pos_start)
        block_end, block_no_end = get_block(pos_end)
        pos_start = block_start.position()
        pos_end = block_end.position() + block_end.length() - 1
        return block_no_start, block_no_end, pos_start, pos_end

    def _get_selection_range(
        self, motion_info: MotionInfo | None
    ) -> tuple[int | None, int | None, bool]:
        """Return selection start, end and linewise flag for an action."""

        if not self.vim_status.is_normal():
            start = self.get_pos_start_in_selection()
            end = self.get_pos_end_in_selection()
            is_linewise = self.vim_status.vim_state == VimState.VLINE
            return start, end, is_linewise

        if motion_info is None:
            return None, None, False

        if motion_info.motion_type == MotionType.BlockWise:
            return motion_info.sel_start, motion_info.sel_end, False

        cursor = self.get_cursor()
        cur_pos = cursor.position()
        new_pos = motion_info.cursor_pos
        if new_pos is None:
            return None, None, False

        start, end = sorted([cur_pos, new_pos])
        if motion_info.motion_type == MotionType.CharWiseIncludingEnd:
            end += 1
        elif motion_info.motion_type == MotionType.LineWise:
            block_start, _ = self.vim_status.cursor.get_block(start)
            block_end, _ = self.vim_status.cursor.get_block(end)
            start = block_start.position()
            end = block_end.position() + block_end.length() - 1
            return start, end, True

        return start, end, False

    def join_lines(
        self, cursor_pos_start: int, block_no_start: int, block_no_end: int
    ) -> None:
        """Join lines between two blocks.

        Args:
            cursor_pos_start: Cursor position at the start of the first line.
            block_no_start: Number of the first block to join.
            block_no_end: Number of the last block to join.
        """
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

    def replace_txt_with_ch(self, pos_start: int, pos_end: int, ch: str) -> None:
        """Replace selected text with a given character.

        Args:
            pos_start: Start position of the range to replace.
            pos_end: End position of the range to replace.
            ch: Character used for replacement.
        """
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
        """Return *text* wrapped by the given character."""
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

    def add_surrounding(self, pos_start: int, pos_end: int, ch: str) -> None:
        """Insert a surrounding character around the given range.

        Args:
            pos_start: Start position of the text to wrap.
            pos_end: End position of the text to wrap.
            ch: Surrounding character to add.
        """
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
        """Return ``text`` without its surrounding character."""
        open_brackets = "([{"
        text_sub = text[1:-1]
        if ch in open_brackets:
            text_sub = text_sub.strip()
        return text_sub

    def delete_surrounding(self, ch: str) -> MotionInfo:
        """Remove surrounding characters around the current selection.

        Args:
            ch: Character used to locate the surroundings.

        Returns:
            Information about the motion that located the text.
        """
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
        """Replace one surrounding character with another.

        Args:
            ch_delete: Character defining the surrounding to remove.
            ch_insert: Character to wrap around the text.

        Returns:
            Information about the motion that located the text.
        """
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

    def handle_case(self, motion_info: MotionInfo, method) -> None:
        """Apply case transformation to text determined by ``motion_info``.

        Args:
            motion_info: Motion describing the range to transform.
            method: One of ``"swap"``, ``"lower"`` or ``"upper"``.
        """
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

    def _handle_case(self, pos_start: int, pos_end: int, method) -> None:
        """Perform case transformation on the given range."""
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

    def indent(self, motion_info: MotionInfo) -> None:
        """Shift the given lines to the right."""
        pos_start, pos_end, _ = self._get_selection_range(motion_info)
        if pos_start is None or pos_end is None:
            return
        self._indent(pos_start, pos_end)

    def _indent(self, pos_start: int, pos_end: int) -> None:
        """Indent lines between ``pos_start`` and ``pos_end``."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        editor = self.get_editor()
        cursor = self.get_cursor()

        block_no_start, block_no_end, pos_start, pos_end = self._get_block_range(
            pos_start, pos_end
        )

        text_list = _get_block_texts(editor, block_no_start, block_no_end)

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

    def unindent(self, motion_info: MotionInfo) -> None:
        """Shift the given lines to the left."""
        pos_start, pos_end, _ = self._get_selection_range(motion_info)
        if pos_start is None or pos_end is None:
            return
        self._unindent(pos_start, pos_end)

    def _unindent(self, pos_start: int, pos_end: int) -> None:
        """Remove one level of indentation from the given range."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        editor = self.get_editor()
        cursor = self.get_cursor()

        block_no_start, block_no_end, pos_start, pos_end = self._get_block_range(
            pos_start, pos_end
        )

        text_list = _get_block_texts(editor, block_no_start, block_no_end)

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

    def yank(self, motion_info: MotionInfo, is_explicit: bool = False):
        """Copy text into the active register.

        Args:
            motion_info: Motion information for the yank range.
            is_explicit: When ``True`` the yank was explicitly requested.

        """
        if self.vim_status.is_normal():
            if motion_info.motion_type == MotionType.BlockWise:
                if motion_info.sel_start is None or motion_info.sel_end is None:
                    return None, None
            elif motion_info.cursor_pos is None:
                return None, None

        register_name = self.vim_status.get_register_name()
        sel_start, sel_end, is_linewise = self._get_selection_range(motion_info)
        if sel_start is None or sel_end is None:
            return None, None

        register_type = VimState.VLINE if is_linewise else VimState.NORMAL

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
        """Return ``cursor`` positioned after leading spaces."""
        txt = cursor.block().text()
        n_space = len(txt) - len(txt.lstrip())
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.movePosition(QTextCursor.Right, n=n_space)
        return cursor

    def paste_in_normal(self, num, is_lower):
        """Paste register content in normal mode."""
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
        """Paste over the current visual selection."""
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
        """Paste register content in visual line mode."""
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
        """Delete text defined by ``motion_info``.

        Args:
            motion_info: Motion describing the range to delete.
            is_insert: If ``True`` delete while in insert mode.
            replace_txt: Optional replacement text.
        """
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
        sel_start, sel_end, is_linewise = self._get_selection_range(motion_info)
        if sel_start is None or sel_end is None:
            return

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
        """Toggle comments for the selected lines."""
        self.vim_status.update_dot_cmd(connect_editor=False)
        editor = self.get_editor()
        pos_start, pos_end, _ = self._get_selection_range(motion_info)
        if pos_start is None or pos_end is None:
            return

        block_no_start, _, pos_start, pos_end = self._get_block_range(
            pos_start, pos_end
        )

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
