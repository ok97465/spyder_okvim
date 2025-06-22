# -*- coding: utf-8 -*-
"""Cursor handling utilities."""

# Third Party Libraries
from qtpy.QtCore import QTimer
from qtpy.QtGui import QBrush, QColor, QTextBlock, QTextCursor
from qtpy.QtWidgets import QTextEdit
from spyder.config.manager import CONF
from spyder.plugins.editor.api.decoration import DRAW_ORDERS

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.motion import MotionInfo, MotionType


class VimCursor:
    """Manage the Vim cursor."""

    def __init__(self, editor_widget):
        self.editor_widget = editor_widget

        self.vim_cursor = QTextEdit.ExtraSelection()
        self.vim_cursor.format.setForeground(QBrush(QColor("#000000")))
        self.vim_cursor.format.setBackground(QBrush(QColor("#BBBBBB")))

        self.selection = QTextEdit.ExtraSelection()
        self.selection.format.setForeground(QBrush(QColor("#A9B7C6")))
        self.selection.format.setBackground(QBrush(QColor("#214283")))

        self.yank_fg_color = QBrush(QColor("#B9C7D6"))
        self.yank_bg_color = QBrush(QColor("#7D7920"))
        self.hl_yank_dur = 400  # duration of highlight after yank
        self.hl_yank = True

        self.set_config_from_conf()

        # Order of Selections
        DRAW_ORDERS["vim_search"] = 6
        DRAW_ORDERS["hl_yank"] = 7
        DRAW_ORDERS["vim_selection"] = 8
        DRAW_ORDERS["vim_cursor"] = 9

    def set_config_from_conf(self):
        """Set config from conf."""
        self.vim_cursor.format.setForeground(
            QBrush(QColor(CONF.get(CONF_SECTION, "cursor_fg_color")))
        )
        self.vim_cursor.format.setBackground(
            QBrush(QColor(CONF.get(CONF_SECTION, "cursor_bg_color")))
        )

        self.selection.format.setForeground(
            QBrush(QColor(CONF.get(CONF_SECTION, "select_fg_color")))
        )
        self.selection.format.setBackground(
            QBrush(QColor(CONF.get(CONF_SECTION, "select_bg_color")))
        )

        self.yank_fg_color = QBrush(QColor(CONF.get(CONF_SECTION, "yank_fg_color")))
        self.yank_bg_color = QBrush(QColor(CONF.get(CONF_SECTION, "yank_bg_color")))
        self.hl_yank_dur = CONF.get(CONF_SECTION, "highlight_yank_duration")
        self.hl_yank = CONF.get(CONF_SECTION, "highlight_yank")

    def get_editor(self):
        """Get the editor focused."""
        editorstack = self.editor_widget.get_current_editorstack()
        return editorstack.get_current_editor()

    def get_editorstack(self):
        """Get the editorstack."""
        return self.editor_widget.get_current_editorstack()

    def get_cursor(self):
        """Get the cursor."""
        return self.get_editor().textCursor()

    def set_cursor(self, cursor):
        """Set the cursor to focused editor."""
        return self.get_editor().setTextCursor(cursor)

    def get_end_position(self):
        """Get the end position of document."""
        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.End)
        return cursor.position()

    def draw_vim_cursor(self):
        """Draw vim cursor."""
        vim_cursor = self.vim_cursor
        editor = self.get_editor()
        vim_cursor.cursor = editor.textCursor()
        vim_cursor.cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
        self.set_extra_selections("vim_cursor", [vim_cursor])

    def create_selection(self, start, end):
        """Create a text selection between two positions.

        Args:
            start: Starting position of the selection.
            end: End position of the selection.
        """
        end_document = self.get_end_position()
        if end > end_document:
            end = end_document

        sel = self.selection
        sel.cursor = QTextCursor(self.get_editor().document())
        sel.cursor.setPosition(start)
        sel.cursor.setPosition(end, QTextCursor.KeepAnchor)
        self.set_extra_selections("vim_selection", [sel])
        self.draw_vim_cursor()

    def set_cursor_pos_in_visual(self, pos_new):
        """Move the cursor while adjusting the current visual selection.

        Args:
            pos_new: Desired new cursor position.
        """
        if pos_new is None:
            return
        editor = self.get_editor()
        pos_cur = editor.textCursor().position()

        sel = editor.get_extra_selections("vim_selection")[0]
        start_old = sel.cursor.selectionStart()
        end_old = sel.cursor.selectionEnd()

        start = start_old
        end = end_old

        if abs(start_old - pos_cur) <= abs(end_old - 1 - pos_cur):
            if start_old >= pos_new:
                start = pos_new
            elif end_old > pos_new:
                start = pos_new
            else:
                start = end - 1
                end = pos_new + 1
        else:
            if end_old - 1 <= pos_new:
                end = pos_new + 1
            elif start_old < pos_new:
                end = pos_new + 1
            else:
                end = start_old + 1
                start = pos_new

        end_document = self.get_end_position()
        if end > end_document:
            end = end_document

        sel.cursor.setPosition(start)
        sel.cursor.setPosition(end, QTextCursor.KeepAnchor)
        self.set_extra_selections("vim_selection", [sel])
        self.set_cursor_pos(pos_new)

    def get_block(self, pos: int) -> tuple[QTextBlock, int]:
        """Get block number of cursor position."""
        cursor = self.get_cursor()
        cursor.setPosition(pos)
        return cursor.block(), cursor.blockNumber()

    def get_block_no_start_in_selection(self):
        """Get start block number of selection."""
        editor = self.get_editor()

        sel = editor.get_extra_selections("vim_selection")
        if not sel:
            return

        sel = sel[0]

        sel_start = sel.cursor.selectionStart()

        _, block_no_start = self.get_block(sel_start)

        return block_no_start

    def get_block_no_end_in_selection(self):
        """Get the last block number of selection."""
        editor = self.get_editor()

        sel = editor.get_extra_selections("vim_selection")
        if not sel:
            return

        sel = sel[0]

        sel_end = sel.cursor.selectionEnd()

        _, block_no_end = self.get_block(sel_end)

        return block_no_end

    def get_pos_start_in_selection(self):
        """Get start position of selection."""
        editor = self.get_editor()

        sel = editor.get_extra_selections("vim_selection")
        if not sel:
            return

        sel = sel[0]

        sel_start = sel.cursor.selectionStart()

        return sel_start

    def get_pos_end_in_selection(self):
        """Get end position of selection."""
        editor = self.get_editor()

        sel = editor.get_extra_selections("vim_selection")
        if not sel:
            return

        sel = sel[0]

        sel_end = sel.cursor.selectionEnd()

        return sel_end

    def set_selection_to_editor_using_vim_selection(self):
        """Set the selection to editor by referring the selection of vim."""
        editor = self.get_editor()
        old_cursor = editor.textCursor()
        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()
        if sel_start:
            new_cursor = editor.textCursor()
            new_cursor.setPosition(sel_start, QTextCursor.MoveAnchor)
            new_cursor.setPosition(sel_end, QTextCursor.KeepAnchor)
            editor.setTextCursor(new_cursor)
            return old_cursor

    def set_cursor_pos_in_vline(self, pos_new):
        """Move the cursor while updating the visual line selection.

        Args:
            pos_new: Desired new cursor position.
        """
        if pos_new is None:
            return
        editor = self.get_editor()
        block_no_cur = editor.textCursor().blockNumber()

        sel = editor.get_extra_selections("vim_selection")[0]
        sel_start = sel.cursor.selectionStart()
        sel_end = sel.cursor.selectionEnd()

        block_start, block_no_start = self.get_block(sel_start)
        block_end, block_no_end = self.get_block(sel_end)
        block_new, block_no_new = self.get_block(pos_new)

        if block_no_start == block_no_cur:
            if block_no_new <= block_no_end:
                block_start = block_new
            else:
                block_start = block_end
                block_end = block_new
        else:
            if block_no_new >= block_no_start:
                block_end = block_new
            else:
                block_end = block_start
                block_start = block_new

        start = block_start.position()
        end = block_end.position() + block_end.length() - 1
        sel.cursor.setPosition(start)
        sel.cursor.setPosition(end, QTextCursor.KeepAnchor)
        self.set_extra_selections("vim_selection", [sel])
        self.set_cursor_pos(pos_new)

    def set_block_selection_in_visual(self, motion_info: MotionInfo):
        """Update block-wise visual selection from ``motion_info``.

        Args:
            motion_info: Motion information computed by a helper.
        """
        editor = self.get_editor()
        sel = editor.get_extra_selections("vim_selection")[0]
        sel.cursor.setPosition(motion_info.sel_start)
        sel.cursor.setPosition(motion_info.sel_end, QTextCursor.KeepAnchor)
        self.set_extra_selections("vim_selection", [sel])
        self.set_cursor_pos(motion_info.sel_end - 1)

    def set_cursor_pos(self, pos):
        """Place the editor cursor at ``pos``.

        Args:
            pos: New absolute position for the cursor.
        """
        if pos is None:
            return
        editor = self.get_editor()
        pos = max(0, min(pos, editor.document().characterCount() - 1))
        cursor = editor.textCursor()
        cursor.setPosition(pos)
        self.set_cursor(cursor)
        self.draw_vim_cursor()

    def set_cursor_pos_without_end(self, pos):
        """Set the cursor avoiding the final block boundary.

        Args:
            pos: Desired cursor position.
        """
        if pos is None:
            return
        editor = self.get_editor()
        cursor = editor.textCursor()
        cursor.setPosition(pos)
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            cursor.movePosition(QTextCursor.Left)
        self.set_cursor(cursor)
        self.draw_vim_cursor()

    def apply_motion_info_in_normal(self, motion_info: MotionInfo):
        """Apply motion info in normal mode."""
        self.set_cursor_pos(motion_info.cursor_pos)

    def apply_motion_info_in_yank(self, motion_info: MotionInfo):
        """Apply motion info after yank in normal mode."""
        cursor_pos = self.get_cursor().position()
        if motion_info.motion_type == MotionType.BlockWise:
            self.set_cursor_pos(motion_info.sel_start)
        else:
            if motion_info.cursor_pos is None:
                return
            pos = min([cursor_pos, motion_info.cursor_pos])
            self.set_cursor_pos(pos)

    def apply_motion_info_in_visual(self, motion_info: MotionInfo):
        """Apply motion info in visual mode."""
        self.set_cursor_pos_in_visual(motion_info.cursor_pos)

    def apply_motion_info_in_vline(self, motion_info: MotionInfo):
        """Apply motion info in visual mode."""
        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def set_extra_selections(
        self, key: str, sels: list[QTextEdit.ExtraSelection]
    ) -> None:
        """Set extra selections on the editor.

        Args:
            key: Name of the selection group.
            sels: List of selections to apply.
        """
        editor = self.get_editor()
        editor.set_extra_selections(key, sels)

    def highlight_yank(self, pos_start: int, pos_end: int) -> None:
        """Highlight yanked text.

        Args:
            pos_start: Starting position of the yanked text.
            pos_end: End position of the yanked text.
        """
        if self.hl_yank is False:
            return

        cursor = self.get_cursor()
        editor = self.get_editor()

        sel = QTextEdit.ExtraSelection()
        sel.format.setForeground(self.yank_fg_color)
        sel.format.setBackground(self.yank_bg_color)
        sel.cursor = cursor

        sel.cursor.setPosition(pos_start)
        sel.cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
        self.set_extra_selections("hl_yank", [sel])

        def clear():
            try:
                editor.clear_extra_selections("hl_yank")
            except RuntimeError:
                pass

        QTimer.singleShot(self.hl_yank_dur, clear)
