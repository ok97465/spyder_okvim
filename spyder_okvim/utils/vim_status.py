# -*- coding: utf-8 -*-
"""Container for the state shared by all executors."""

# Standard library imports
import os.path as osp
from collections import defaultdict

# Third party imports
from qtpy.QtCore import QEvent, QObject, QRegularExpression, Qt, QTimer, Signal, Slot
from qtpy.QtGui import (
    QBrush,
    QColor,
    QKeyEvent,
    QRegularExpressionValidator,
    QTextBlock,
    QTextCursor,
    QValidator,
)
from qtpy.QtWidgets import QApplication, QLabel, QTextEdit
from spyder.config.manager import CONF
from spyder.plugins.editor.api.decoration import DRAW_ORDERS

# Local imports
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.bookmark_manager import BookmarkManager
from spyder_okvim.utils.easymotion import ManageMarkerEasymotion, PainterEasyMotion
from spyder_okvim.utils.helper_motion import MotionInfo, MotionType


class VimState:
    """Vim state constants."""

    VISUAL = 0
    VLINE = 1
    NORMAL = 3
    INSERT = 4
    SUBMODE = 5


class FindInfo:
    """f,F,t,T command Info."""

    def __init__(self):
        self.cmd_name: str = ""
        self.ch: str = ""

    def set(self, cmd_name: str, ch: str):
        """Set infomation of find commmand."""
        self.cmd_name = cmd_name
        self.ch = ch


class InputCmdInfo:
    """Info for input command."""

    def __init__(self, num_str: str, cmd: str):
        self.num_str: str = num_str
        self.cmd: str = cmd

    def clear(self):
        """Clear."""
        self.num_str = ""
        self.cmd = ""

    def set(self, input_cmd_info):
        """Set the information of input command."""
        self.num_str = input_cmd_info.num_str
        self.cmd = input_cmd_info.cmd


class DotCmdInfo:
    """Dot command info."""

    def __init__(self):
        self.vim_state = None
        self.sel_block_no_start = None
        self.sel_block_no_end = None
        self.sel_col_start = None
        self.sel_col_end = None
        self.num_str: str = ""
        self.cmd: str = ""
        self.cmd_list_insertmode = None
        self.register_name = None
        self.editor_connected = None
        self.key_list_from_editor = []
        self.key_list_to_cmd_line = []

    def clear_key_list(self):
        """Clear key list from editor."""
        self.key_list_from_editor.clear()
        self.key_list_to_cmd_line.clear()

    def cmd2string(self, num, num_str):
        """Convert cmd info to string of vim command."""
        # TODO : apply register name.
        cmd_str = ""

        if self.vim_state == VimState.VLINE:
            cmd_str += "V"
            n_lines = self.sel_block_no_end - self.sel_block_no_start
            if n_lines > 0:
                cmd_str += f"{n_lines}j"
            cmd_str += self.cmd
            return cmd_str

        if self.vim_state == VimState.VISUAL:
            cmd_str += "v"
            n_lines = self.sel_block_no_end - self.sel_block_no_start
            if n_lines > 0:
                cmd_str += f"{n_lines}j0"

                if self.sel_col_end > 1:
                    cmd_str += f"{self.sel_col_end - 1}l"
            else:
                n = self.sel_col_end - self.sel_col_start - 1
                if n > 0:
                    cmd_str += f"{n}l"
            cmd_str += self.cmd
            return cmd_str

        if num_str:
            return str(num) + self.cmd
        else:
            return self.num_str + self.cmd


class KeyInfo:
    """Save the info of QKeyEvent."""

    def __init__(self, key_code: int, text: str, modifiers: int, identifier: int = 1):
        self.key_code = key_code
        self.text = text
        self.modifiers = modifiers
        self.identifier = identifier  # 0: from vim, 1: from editor

    def to_event(self):
        """Convert key info to qkeyevent."""
        event = QKeyEvent(QEvent.KeyPress, self.key_code, self.modifiers, self.text)
        event.ignore()
        return event


class RegisterInfo:
    """Info of register."""

    def __init__(self):
        self.name = ""
        self.content = ""
        self.type = VimState.NORMAL


class SearchInfo:
    """Result of search."""

    def __init__(self, vim_cursor):
        self.color_fg = QBrush(QColor("#A9B7C6"))
        self.color_bg = QBrush(QColor("#30652F"))
        self.txt_searched = ""
        self.selection_list = []
        self.vim_cursor = vim_cursor
        self.ignorecase = True

        self.set_color()

    def set_color(self):
        """Set the color of search results."""
        self.color_fg = QBrush(QColor(CONF.get(CONF_SECTION, "search_fg_color")))
        self.color_bg = QBrush(QColor(CONF.get(CONF_SECTION, "search_bg_color")))

        for sel in self.selection_list:
            sel.format.setForeground(self.color_fg)
            sel.format.setBackground(self.color_bg)

    def get_sel_start_list(self):
        """Get the start position of selection."""
        cursor = self.vim_cursor.get_cursor()
        validator = QRegularExpressionValidator(
            QRegularExpression(self.txt_searched), None
        )

        tmp = []
        for sel in self.selection_list:
            cursor.setPosition(sel.cursor.selectionStart())
            cursor.setPosition(sel.cursor.selectionEnd(), QTextCursor.KeepAnchor)
            txt_sel = cursor.selectedText()

            if (validator.validate(txt_sel, 0)[0] == QValidator.Acceptable) or (
                self.ignorecase is True and txt_sel.lower() == self.txt_searched.lower()
            ):
                tmp.append(sel)
        self.selection_list = tmp

        self.vim_cursor.set_extra_selections(
            "vim_search", [i for i in self.selection_list]
        )

        return [i.cursor.selectionStart() for i in self.selection_list]


class ManagerMacro:
    """Manage macros."""

    def __init__(self):
        self.registers = defaultdict(list)
        self.is_recording = False
        self.reg_name_for_record = ""
        #: Editor currently connected to receive key events during recording
        self.editor_connected = None
        self.reg_name_for_execute = ""
        self.num_execute = 0

    def set_info_for_execute(self, ch, num):
        """Set info for executing contents of register."""
        self.reg_name_for_execute = ch
        self.num_execute = num

    def start_record(self, ch):
        """Start recording to register ``ch``."""
        self.reg_name_for_record = ch
        self.is_recording = True

        if ch.lower() == ch:
            self.registers[ch] = list()

    def stop_record(self):
        """Stop recording."""
        # Remove the trailing ``q`` when finishing recording
        self.remove_last_key("q")
        self.reg_name_for_record = ""
        self.is_recording = False

    def remove_last_key(self, ch):
        """Remove last key."""
        key_list = self.registers[self.reg_name_for_record]
        if len(key_list) > 0:
            last_key = key_list[-1]
            if last_key.text == ch:
                self.registers[self.reg_name_for_record] = key_list[:-1]

    def add_vim_keyevent(self, event):
        """Add keyevent from vim."""
        if self.is_recording:
            self.registers[self.reg_name_for_record].append(
                KeyInfo(event.key(), event.text(), event.modifiers(), 0)
            )

    def add_editor_keyevent(self, event):
        """Add keyevent from editor."""
        self.registers[self.reg_name_for_record].append(
            KeyInfo(event.key(), event.text(), event.modifiers(), 1)
        )

    def connect_to_editor(self, editor, slot):
        """Connect ``slot`` to ``editor`` for recording events."""
        self.editor_connected = editor
        editor.sig_key_pressed.connect(slot)

    def disconnect_from_editor(self, slot):
        """Disconnect previously connected editor from ``slot``."""
        editor = self.editor_connected
        if editor:
            try:
                editor.sig_key_pressed.disconnect(slot)
            except (TypeError, RuntimeError):
                # Already disconnected or editor deleted
                pass
        self.editor_connected = None

class LabelOnTxt(QLabel):
    """Label on txt."""

    def __init__(self, parent=None):
        """Initialize the label used to display text annotations."""
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

    def set_style(self, font_family: str, font_size_pt: int):
        """Set stylesheet."""
        self.setStyleSheet(
            f"""QLabel {{ 
            background-color : #222b35;
            color : #cd4340;
            border: 1px solid #cd4340;
            padding : 0px;
            text-indent : 1px; 
            margin : 0px;
            font-family: {font_family};
            font-size: {font_size_pt}pt;
            }}"""
        )


class VimCursor:
    """Manange the cursor in vim."""

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
        # editor.update()

    def create_selection(self, start, end):
        """Create selection."""
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
        """Set cursor position and redraw selection in visual mode."""
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
        """Get block number of cursor position.

        Returns:
            QTextBlock: The QTextBlock class provides a container for text fragments.
            int: Block number.

        """
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
        """Set cursor position and redraw selection in vline mode."""
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
        """Set block selection in visual."""
        editor = self.get_editor()
        sel = editor.get_extra_selections("vim_selection")[0]
        sel.cursor.setPosition(motion_info.sel_start)
        sel.cursor.setPosition(motion_info.sel_end, QTextCursor.KeepAnchor)
        self.set_extra_selections("vim_selection", [sel])
        self.set_cursor_pos(motion_info.sel_end - 1)

    def set_cursor_pos(self, pos):
        """Set position cursor of editor."""
        if pos is None:
            return
        editor = self.get_editor()
        cursor = editor.textCursor()
        cursor.setPosition(pos)
        self.set_cursor(cursor)
        self.draw_vim_cursor()

    def set_cursor_pos_without_end(self, pos):
        """Set position cursor of editor.

        If the new position is the end of the block, cusor moves to left.
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

    def set_extra_selections(self, key, sels):
        """Set the selection info to editor."""
        editor = self.get_editor()
        editor.set_extra_selections(key, sels)

    def highlight_yank(self, pos_start, pos_end):
        """Highlight after yank."""
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

        QTimer.singleShot(
            self.hl_yank_dur, lambda: editor.clear_extra_selections("hl_yank")
        )


class VimStatus(QObject):
    """Status of vim."""

    change_label = Signal(int)

    def __init__(self, editor_widget, main, msg_label):
        super().__init__()
        self.is_visual_mode = False
        self.vim_state = VimState.NORMAL
        self.editor_widget = editor_widget
        self.cursor: VimCursor = VimCursor(editor_widget)
        self.main = main

        # method mapping
        self.set_cursor = self.cursor.set_cursor
        self.get_cursor = self.cursor.get_cursor
        self.get_editor = self.cursor.get_editor
        self.get_editorstack = self.cursor.get_editorstack
        self.get_block_no_start_in_selection = (
            self.cursor.get_block_no_start_in_selection
        )
        self.get_block_no_end_in_selection = self.cursor.get_block_no_end_in_selection
        self.get_pos_start_in_selection = self.cursor.get_pos_start_in_selection
        self.get_pos_end_in_selection = self.cursor.get_pos_end_in_selection

        self.cmd_line = None

        self.sub_mode = None

        # command
        self.find_info = FindInfo()
        self.input_cmd = InputCmdInfo("", "")
        self.input_cmd_prev = InputCmdInfo("", "")
        self.dot_cmd = DotCmdInfo()
        self.running_dot_cmd = False

        # register
        self.register_dict = defaultdict(RegisterInfo)

        # config
        self.indent = "    "

        # search
        self.search = SearchInfo(self.cursor)

        # message
        self.msg_label = msg_label
        self.msg_prefix = ""

        # Macro
        self.manager_macro = ManagerMacro()

        # bookmarks
        bookmarks_file = osp.join(
            CONF.get_plugin_config_path(CONF_SECTION), "bookmarks.json"
        )
        self.bookmark_manager = BookmarkManager(
            bookmarks_file,
            self.main.open_file,
            self.get_editorstack,
            self.get_editor,
            self.cursor.set_cursor_pos,
        )
        # Expose dictionaries for backwards compatibility
        self.bookmarks = self.bookmark_manager.bookmarks
        self.bookmarks_global = self.bookmark_manager.bookmarks_global

        # easymotion
        self.painter_easymotion = PainterEasyMotion()
        self.manager_marker_easymotion = ManageMarkerEasymotion()
        self.editor_connected_easymotion = None

        # Sneak
        self.n_annotate_max = 50
        self.labels_for_annotate = [
            LabelOnTxt(self.main) for _ in range(self.n_annotate_max)
        ]
        self.hide_annotate_on_txt()

    def clear_state(self):
        """Clear."""
        self.is_visual_mode = False
        self.vim_state = VimState.NORMAL
        editor = self.get_editor()
        if editor:
            editor.clear_extra_selections("vim_selection")
            editor.clear_extra_selections("vim_cursor")

    def is_normal(self):
        """Check that vim state is normal mode."""
        return self.vim_state == VimState.NORMAL

    def to_normal(self):
        """Change vim state to normal mode."""
        self.clear_state()
        cursor = self.get_cursor()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            pos = cursor.position()
            self.cursor.set_cursor_pos(pos - 1)
        self.change_label.emit(VimState.NORMAL)

    def reset_for_test(self):
        """Reset status for test."""
        self.clear_state()

        self.find_info = FindInfo()
        self.input_cmd = InputCmdInfo("", "")
        self.input_cmd_prev = InputCmdInfo("", "")
        self.dot_cmd.clear_key_list()
        self.running_dot_cmd = False

        self.get_editor().clear_extra_selections("hl_yank")

        # register
        self.register_dict = defaultdict(RegisterInfo)

        # config
        self.indent = "    "

        # search
        self.search = SearchInfo(self.cursor)

        # Macro
        self.manager_macro = ManagerMacro()

        self.msg_label.setText("")

        # bookmarks
        self.bookmark_manager.clear()
        self.bookmarks = self.bookmark_manager.bookmarks
        self.bookmarks_global = self.bookmark_manager.bookmarks_global

        self.to_normal()

    def to_insert(self):
        """Change vim state to insert mode."""
        self.is_visual_mode = False
        self.remove_marker_of_easymotion()
        self.get_editor().clear_extra_selections("vim_selection")
        self.get_editor().clear_extra_selections("vim_cursor")
        self.change_label.emit(VimState.INSERT)

    def to_visual_char(self):
        """Change vim state to visual mode."""
        self.clear_state()
        self.is_visual_mode = True
        self.vim_state = VimState.VISUAL

        pos = self.get_cursor().position()
        self.cursor.create_selection(pos, pos + 1)

        self.change_label.emit(VimState.VISUAL)

    def to_visual_line(self):
        """Change vim state to vline mode."""
        self.clear_state()
        self.is_visual_mode = True
        self.vim_state = VimState.VLINE

        cursor = self.get_cursor()
        cursor.movePosition(QTextCursor.StartOfBlock)

        pos_start = cursor.position()

        cursor.movePosition(QTextCursor.EndOfBlock)
        pos_end = cursor.position()

        self.cursor.create_selection(pos_start, pos_end)

        self.change_label.emit(VimState.VLINE)

    def get_number_of_visible_lines(self):
        """Get the number of visible lines in editor."""
        editor = self.get_editor()
        num_lines = editor.viewport().height() // editor.fontMetrics().height()
        return num_lines

    def set_focus_to_vim(self):
        """Set focus to vim command line."""
        if self.cmd_line:
            self.cmd_line.setFocus()

    def set_focus_to_vim_after_delay(self, delay=300):
        """Set focus to vim command line after delay.

        Spyder is focused after receiving the result of pyls.
        So set_focus_to_vim method is useless.
        """

        def focus():
            self.set_focus_to_vim()
            self.cursor.draw_vim_cursor()

        if self.cmd_line:
            QTimer.singleShot(delay, focus)

    @Slot(QKeyEvent)
    def rcv_key_from_editor(self, event):
        """Add key event from editor to list."""
        self.dot_cmd.key_list_from_editor.append(
            KeyInfo(event.key(), event.text(), event.modifiers(), 1)
        )

    def disconnect_from_editor(self):
        """Disconnect from the editor."""
        # disconnect previous connection.
        editor = self.dot_cmd.editor_connected
        if editor:
            editor.sig_key_pressed.disconnect(self.rcv_key_from_editor)
        self.dot_cmd.editor_connected = None

    def update_dot_cmd(
        self, connect_editor, register_name=None, key_list_to_cmd_line=None
    ):
        """Update input command info to dot command info."""
        if self.running_dot_cmd is True:
            return
        dot_cmd = self.dot_cmd
        dot_cmd.vim_state = self.vim_state
        dot_cmd.num_str = self.input_cmd.num_str
        dot_cmd.cmd = self.input_cmd.cmd
        dot_cmd.register_name = register_name
        dot_cmd.clear_key_list()
        if key_list_to_cmd_line:
            dot_cmd.key_list_to_cmd_line = key_list_to_cmd_line
        self.disconnect_from_editor()

        # For receiving key event from codeeditor
        if connect_editor:
            editor = self.get_editor()
            self.dot_cmd.editor_connected = editor
            editor.sig_key_pressed.connect(self.rcv_key_from_editor)

        # Get selection region.
        if self.is_normal():
            return

        sel_start = self.get_pos_start_in_selection()
        sel_end = self.get_pos_end_in_selection()

        block_start, block_no_start = self.cursor.get_block(sel_start)
        block_end, block_no_end = self.cursor.get_block(sel_end)

        dot_cmd.sel_block_no_start = block_no_start
        dot_cmd.sel_block_no_end = block_no_end
        dot_cmd.sel_col_start = sel_start - block_start.position()
        dot_cmd.sel_col_end = sel_end - block_end.position()

    def get_register_name(self):
        """Get register name from previous command."""
        txt = self.input_cmd_prev.cmd

        if len(txt) == 2 and txt[0] == '"':
            return txt[1]
        else:
            return '"'  # default register name

    def set_register(self, name, content, register_type):
        """Set content into register_dict."""
        if name == "+":
            QApplication.clipboard().setText(content)
        else:
            info = self.register_dict[name]
            info.name = name
            info.content = content
            info.type = register_type
            self.register_dict[name] = info

    def get_register(self):
        """Get content from register_dict."""
        name = self.get_register_name()
        if name == "+":
            info = RegisterInfo()
            info.name = "+"
            info.content = QApplication.clipboard().text()
            info.type = VimState.NORMAL
            return info
        else:
            return self.register_dict[name]

    # ---- Bookmarks ----------------------------------------------------
    def _load_persistent_bookmarks(self) -> None:
        """Load persistent bookmarks from disk."""
        self.bookmark_manager._load_persistent_bookmarks()

    def _save_persistent_bookmarks(self) -> None:
        """Save persistent bookmarks to disk."""
        self.bookmark_manager._save_persistent_bookmarks()

    def set_bookmark(self, name: str) -> None:
        """Set bookmark at current cursor position."""
        self.bookmark_manager.set_bookmark(name)

    def get_bookmark(self, name: str):
        """Return bookmark information for *name* or None."""
        return self.bookmark_manager.get_bookmark(name)

    def jump_to_bookmark(self, name: str) -> None:
        """Move cursor to bookmark *name* if it exists."""
        self.bookmark_manager.jump_to_bookmark(name)

    def set_message(self, msg, duration_ms=-1):
        """Display the massage."""
        self.msg_label.setText(f"{self.msg_prefix}{msg}")

    def start_recording_macro(self, reg_name):
        """Start recording macro."""
        self.msg_prefix = f"recording @{reg_name}... "

        editor = self.get_editor()
        self.manager_macro.start_record(reg_name)
        self.manager_macro.connect_to_editor(
            editor, self.add_key_from_editor_to_macro_manager
        )

    def is_recording_macro(self):
        """Return is_recording."""
        return self.manager_macro.is_recording

    def stop_recoding_macro(self):
        """Stop recording macro."""
        self.msg_prefix = ""
        self.manager_macro.stop_record()
        self.manager_macro.disconnect_from_editor(
            self.add_key_from_editor_to_macro_manager
        )

    @Slot(QKeyEvent)
    def add_key_from_editor_to_macro_manager(self, event):
        """Add key event from editor to list to macro_manager."""
        self.manager_macro.add_editor_keyevent(event)

    def set_marker_for_easymotion(self, positions: list[int], motion_type):
        """Set marker for easymotion."""
        if not positions:
            return
        self.remove_marker_of_easymotion()
        editor = self.get_editor()
        self.manager_marker_easymotion.set_positions(positions, motion_type)
        self.painter_easymotion.editor = editor
        self.painter_easymotion.positions = positions
        self.painter_easymotion.names = self.manager_marker_easymotion.name_list
        self.editor_connected_easymotion = editor
        editor.viewport().installEventFilter(self.painter_easymotion)
        editor.viewport().update()

    def update_marker_for_easymotion(self):
        """Update marker of easymotion."""
        self.remove_marker_of_easymotion()
        editor = self.get_editor()
        self.painter_easymotion.editor = editor
        self.painter_easymotion.positions = self.manager_marker_easymotion.position_list
        self.painter_easymotion.names = self.manager_marker_easymotion.name_list
        self.editor_connected_easymotion = editor
        editor.viewport().installEventFilter(self.painter_easymotion)
        editor.viewport().update()

    def remove_marker_of_easymotion(self):
        """Remove marker of easymotion."""
        editor = self.editor_connected_easymotion
        self.editor_connected_easymotion = None
        if editor:
            editor.viewport().removeEventFilter(self.painter_easymotion)
            editor.viewport().update()

    @Slot()
    def hide_annotate_on_txt(self):
        """Hide Labels for annotate on txt."""
        for idx in range(self.n_annotate_max):
            self.labels_for_annotate[idx].hide()

    def annotate_on_txt(self, info: dict[int, str], timeout: int = -1):
        """Annotate on txt."""
        editor = self.get_editor()
        tc = editor.textCursor()
        font = editor.viewport().font()
        fm = editor.fontMetrics()
        ch_width = fm.width("H")
        ch_height = fm.height()

        for idx, (pos, data) in enumerate(info.items()):
            label = self.labels_for_annotate[idx]
            label.set_style(font.family(), font.pointSize())
            label.setFixedSize(ch_width * len(data), ch_height)
            label.setText(data)

            tc.setPosition(pos)
            rect_in_local = editor.cursorRect(tc)
            pos_in_parent = editor.viewport().mapTo(
                label.parent(), rect_in_local.topLeft()
            )
            print(pos_in_parent)
            label.move(pos_in_parent)
            label.raise_()
            label.show()

            if idx > self.n_annotate_max - 1:
                break

        QTimer.singleShot(timeout, self.hide_annotate_on_txt)
