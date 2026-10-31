# -*- coding: utf-8 -*-
"""Apply Vim editing actions using explicit document and text-object context.

The command layer owns count parsing and undo grouping. This module owns range
selection, text changes and their register/dot side effects; host-specific
indentation and comment operations retain their existing editor semantics.
"""

# Standard Libraries
import re

# Third Party Libraries
from qtpy.QtGui import QTextCursor

# Project Libraries
from spyder_okvim.utils.motion import MotionInfo, MotionType
from spyder_okvim.vim.state import VimState


class EditingActions:
    """Apply edits on the GUI thread using explicit state and motion services.

    Text-object calculation is read-only; edit methods update the document and,
    where applicable, dot/register/yank state through the supplied session.
    Positions are Qt UTF-16 offsets and line numbers are zero-based blocks.
    """

    def __init__(self, vim_status, motions):
        """Receive state directly instead of retrieving it through motions."""
        self.vim_status = vim_status
        self.text_objects = motions.text_objects

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
            start = self.vim_status.get_pos_start_in_selection()
            end = self.vim_status.get_pos_end_in_selection()
            is_linewise = self.vim_status.vim_state == VimState.VLINE
            return start, end, is_linewise

        if motion_info is None:
            return None, None, False

        if motion_info.motion_type == MotionType.BlockWise:
            return motion_info.sel_start, motion_info.sel_end, False
        if (
            motion_info.motion_type == MotionType.LineWise
            and motion_info.sel_start is not None
            and motion_info.sel_end is not None
        ):
            return motion_info.sel_start, motion_info.sel_end, True

        cursor = self.vim_status.get_cursor()
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

        editor = self.vim_status.get_editor()
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

        self.vim_status.cursor.set_cursor_pos(pos)

        editor.document_did_change()

    def replace_with_character(self, start: int, end: int, character: str) -> None:
        """Replace selected text with a given character.

        Args:
            start: Inclusive Qt UTF-16 start of the range to replace.
            end: Exclusive Qt UTF-16 end of the range to replace.
            character: Character used for replacement.
        """
        self.vim_status.update_dot_cmd(connect_editor=False)

        if self.vim_status.is_normal() and start == end:
            self.vim_status.cursor.set_cursor_pos(start)
            return

        cursor = self.vim_status.get_cursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        text = cursor.selectedText().replace("\u2029", "\n")
        replacement = re.sub(r".", character, text)
        cursor.insertText(replacement)

        if self.vim_status.is_normal():
            self.vim_status.cursor.set_cursor_pos(end - 1)

        editor = self.vim_status.get_editor()
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

        cursor = self.vim_status.get_cursor()
        cursor.setPosition(pos_start)
        cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        text = cursor.selectedText().replace("\u2029", "\n")
        text_sub = self._add_surrounding(ch, text)
        cursor.insertText(text_sub)

        editor = self.vim_status.get_editor()
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
            motion_info = self.text_objects.inner_quote(ch)
            if motion_info.sel_start and motion_info.sel_end:
                motion_info.sel_start -= 1
                motion_info.sel_end += 1
        else:
            motion_info = self.text_objects.around_bracket(1, ch)

        if motion_info.sel_start is None:
            return motion_info

        cursor = self.vim_status.get_cursor()
        cursor.setPosition(motion_info.sel_start)
        cursor.setPosition(motion_info.sel_end, QTextCursor.KeepAnchor)
        text = cursor.selectedText().replace("\u2029", "\n")
        text_sub = self._delete_surrounding(ch, text)
        cursor.insertText(text_sub)

        editor = self.vim_status.get_editor()
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
            motion_info = self.text_objects.inner_quote(ch_delete)
            if motion_info.sel_start and motion_info.sel_end:
                motion_info.sel_start -= 1
                motion_info.sel_end += 1
        else:
            motion_info = self.text_objects.around_bracket(1, ch_delete)

        if motion_info.sel_start is None:
            return motion_info

        cursor = self.vim_status.get_cursor()
        cursor.setPosition(motion_info.sel_start)
        cursor.setPosition(motion_info.sel_end, QTextCursor.KeepAnchor)
        text = cursor.selectedText().replace("\u2029", "\n")
        text_sub = self._delete_surrounding(ch_delete, text)
        text_sub = self._add_surrounding(ch_insert, text_sub)
        cursor.insertText(text_sub)

        editor = self.vim_status.get_editor()
        editor.document_did_change()

        return motion_info

    def change_case(self, motion_info: MotionInfo, operation) -> None:
        """Apply case transformation to text determined by ``motion_info``.

        Args:
            motion_info: Motion describing the range to transform.
            operation: One of ``"swap"``, ``"lower"`` or ``"upper"``.
        """
        self.vim_status.update_dot_cmd(connect_editor=False)

        if not self.vim_status.is_normal():
            sel_start = self.vim_status.get_pos_start_in_selection()
            sel_end = self.vim_status.get_pos_end_in_selection()
            self._apply_case(sel_start, sel_end, operation)
            self.vim_status.to_normal()
            self.vim_status.cursor.set_cursor_pos(sel_start)
        elif motion_info.motion_type == MotionType.BlockWise:
            self._apply_case(motion_info.sel_start, motion_info.sel_end, operation)
            self.vim_status.cursor.set_cursor_pos(motion_info.sel_start)
        else:
            cursor = self.vim_status.get_cursor()
            cursor_pos_cur = cursor.position()
            cursor_pos_new = motion_info.cursor_pos
            if cursor_pos_new is None:
                return
            pos_start, pos_end = sorted([cursor_pos_cur, cursor_pos_new])

            if motion_info.motion_type == MotionType.CharWise:
                self._apply_case(pos_start, pos_end, operation)
            elif motion_info.motion_type == MotionType.CharWiseIncludingEnd:
                self._apply_case(pos_start, pos_end + 1, operation)
            elif motion_info.motion_type == MotionType.LineWise:
                block_start, _ = self.vim_status.cursor.get_block(pos_start)
                block_end, _ = self.vim_status.cursor.get_block(pos_end)
                sel_start = block_start.position()
                sel_end = block_end.position() + block_end.length() - 1
                self._apply_case(sel_start, sel_end, operation)

                # Exception case, guu, gUU, g~~
                if pos_start == pos_end:
                    pos_start = sel_start
            self.vim_status.cursor.set_cursor_pos(pos_start)

    def _apply_case(self, pos_start: int, pos_end: int, operation) -> None:
        """Perform case transformation on the given range."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        cursor = self.vim_status.get_cursor()

        cursor.setPosition(pos_start)
        cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        text = cursor.selectedText()
        if operation == "swap":
            cursor.insertText(text.swapcase())
        elif operation == "lower":
            cursor.insertText(text.lower())
        else:
            cursor.insertText(text.upper())

        editor = self.vim_status.get_editor()
        editor.document_did_change()

    def reindent(self, motion_info: MotionInfo) -> None:
        """Reindent the resolved block range using the host's language context.

        Characterwise ranges exclude their end. Dot state is recorded before
        the host performs one undo group and restores its indentation settings.
        """
        start, end, linewise = self._get_selection_range(motion_info)
        if start is None or end is None:
            return
        if not linewise and end > start:
            end -= 1
        first_block, last_block, _, _ = self._get_block_range(start, end)
        self.vim_status.update_dot_cmd(connect_editor=False)
        self.vim_status.host.reindent_lines(first_block, last_block)

    def indent(self, motion_info: MotionInfo | None) -> None:
        """Shift the given lines to the right."""
        pos_start, pos_end, _ = self._get_selection_range(motion_info)
        if pos_start is None or pos_end is None:
            return
        self._shift_indentation(pos_start, pos_end, forward=True)

    def unindent(self, motion_info: MotionInfo | None) -> None:
        """Shift the given lines to the left."""
        pos_start, pos_end, _ = self._get_selection_range(motion_info)
        if pos_start is None or pos_end is None:
            return
        self._shift_indentation(pos_start, pos_end, forward=False)

    def _shift_indentation(self, pos_start: int, pos_end: int, forward: bool) -> None:
        """Shift leading whitespace by one level using the document settings."""
        self.vim_status.update_dot_cmd(connect_editor=False)

        editor = self.vim_status.get_editor()
        cursor = self.vim_status.get_cursor()

        block_no_start, block_no_end, pos_start, pos_end = self._get_block_range(
            pos_start, pos_end
        )

        document = editor.document()

        indent = self.vim_status.indent
        tab_width = editor.tab_stop_width_spaces
        shift_width = tab_width if indent == "\t" else len(indent)
        text_list_shifted = []
        for block_no in range(block_no_start, block_no_end + 1):
            text = document.findBlockByNumber(block_no).text()
            if not text:
                text_list_shifted.append("")
                continue

            n_blank = len(text) - len(text.lstrip(" \t"))
            # Measure tabs before shifting so mixed whitespace keeps its width.
            width = len(text[:n_blank].expandtabs(tab_width))
            width = width + shift_width if forward else max(0, width - shift_width)
            if indent == "\t":
                prefix = "\t" * (width // tab_width) + " " * (width % tab_width)
            else:
                prefix = " " * width
            text_list_shifted.append(prefix + text[n_blank:])

        cursor.setPosition(pos_start)
        cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        cursor.insertText("\n".join(text_list_shifted))

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

        cursor = self.vim_status.get_cursor()
        cursor.setPosition(sel_start)
        cursor.setPosition(sel_end, QTextCursor.KeepAnchor)
        txt = cursor.selectedText().replace("\u2029", "\n")
        if register_type == VimState.VLINE:
            txt += "\n"

        # These operator motions also use numbered history for a small delete.
        force_numbered = self.vim_status.is_normal() and bool(
            re.match(r"^[dc]\d*[%()`/?nN{}]", self.vim_status.input_cmd.cmd)
        )

        # Register updates can replace this count with a history limit warning.
        doc = cursor.document()
        nb_start = doc.findBlock(sel_start).blockNumber()
        nb_end = doc.findBlock(sel_end).blockNumber()
        if nb_start != nb_end:
            self.vim_status.set_message(f"{nb_end - nb_start + 1} lines yanked")

        self.vim_status.update_registers(
            register_name,
            txt,
            register_type,
            is_yank=is_explicit,
            force_numbered=force_numbered,
        )

        # highlight yank
        if is_explicit and not self.vim_status.running_dot_cmd:
            self.vim_status.cursor.highlight_yank(sel_start, sel_end)

        return sel_start, sel_end

    def delete(self, motion_info: MotionInfo, is_insert, replace_txt=""):
        """Delete text defined by ``motion_info``.

        Args:
            motion_info: Motion describing the range to delete.
            is_insert: If ``True`` delete while in insert mode.
            replace_txt: Optional replacement text.
        """
        self.vim_status.update_dot_cmd(
            connect_editor=is_insert, register_name=self.vim_status.get_register_name()
        )

        if self.vim_status.is_normal():
            if motion_info.motion_type == MotionType.BlockWise:
                if motion_info.sel_start is None or motion_info.sel_end is None:
                    return
            elif motion_info.cursor_pos is None:
                return

        cursor = self.vim_status.get_cursor()
        editor = self.vim_status.get_editor()
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
                self.vim_status.cursor.set_cursor_pos(cursor_pos_new + len(replace_txt))
            else:
                self.vim_status.cursor.set_cursor_pos_without_end(cursor_pos_new)

        editor.document_did_change()

    def toggle_comment(self, motion_info: MotionInfo) -> None:
        """Toggle the host's comments and finish in Normal mode at the first line.

        Resolve the motion before passing a UTF-16 selection to the host. Dot
        recording, mode changes and Vim cursor display remain owned here.
        """
        self.vim_status.update_dot_cmd(connect_editor=False)
        start, end, _ = self._get_selection_range(motion_info)
        if start is None or end is None:
            return
        _, _, start, end = self._get_block_range(start, end)
        position = self.vim_status.host.toggle_comments(start, end)
        self.vim_status.to_normal()
        self.vim_status.cursor.set_cursor_pos(position)
        self.vim_status.get_editor().document_did_change()
