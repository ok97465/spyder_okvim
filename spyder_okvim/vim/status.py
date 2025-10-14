# -*- coding: utf-8 -*-
"""Main object storing global Vim state."""

# Standard Libraries
import os.path as osp
from collections import defaultdict

# Third Party Libraries
from qtpy.QtCore import QCoreApplication, QObject, QTimer, Signal, Slot
from qtpy.QtGui import QKeyEvent, QTextCursor
from qtpy.QtWidgets import QApplication, QLabel, QWidget
from spyder.api.plugins import Plugins
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.bookmark_manager import BookmarkManager
from spyder_okvim.utils.easymotion import EasyMotionMarkerManager, EasyMotionPainter
from spyder_okvim.utils.jump_list import JumpList

from .cursor import VimCursor
from .label import InlineLabel
from .macro import MacroManager
from .search import SearchInfo
from .state import DotCmdInfo, FindInfo, InputCmdInfo, KeyInfo, RegisterInfo, VimState


class VimStatus(QObject):
    """Track the global Vim emulation state."""

    change_label = Signal(int)

    def __init__(
        self, editor_widget: QWidget, main: QWidget, msg_label: QLabel
    ) -> None:
        """Initialize the status object.

        Args:
            editor_widget: Editor plugin used to access the current editor.
            main: Main Spyder window.
            msg_label: Label widget used to display status messages.
        """
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
        self.manager_macro = MacroManager()

        # bookmarks
        bookmarks_file = osp.join(
            CONF.get_plugin_config_path(CONF_SECTION), "bookmarks.json"
        )
        self._application_plugin = None
        self.bookmark_manager = BookmarkManager(
            bookmarks_file,
            self._open_file_in_application,
            self.get_editorstack,
            self.get_editor,
            self.cursor.set_cursor_pos,
        )
        # Expose dictionaries for backwards compatibility
        self.bookmarks = self.bookmark_manager.bookmarks
        self.bookmarks_global = self.bookmark_manager.bookmarks_global

        # jumplist
        self.jump_list = JumpList()
        self.timer_go_to_definition = None

        # easymotion
        self.painter_easymotion = EasyMotionPainter()
        self.manager_marker_easymotion = EasyMotionMarkerManager()
        self.editor_connected_easymotion = None

        # Sneak
        self.n_annotate_max = 50
        self.labels_for_annotate = [
            InlineLabel(self.main) for _ in range(self.n_annotate_max)
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
        try:
            self.change_label.emit(VimState.NORMAL)
        except RuntimeError:
            pass

    def reset_for_test(self):
        """Reset status for test."""
        # Remove any pending EasyMotion overlays before processing Qt events.
        self.remove_marker_of_easymotion()
        QCoreApplication.processEvents()
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
        self.manager_macro = MacroManager()

        self.msg_label.setText("")

        # bookmarks
        self.bookmark_manager.clear()
        self.bookmarks = self.bookmark_manager.bookmarks
        self.bookmarks_global = self.bookmark_manager.bookmarks_global

        # jumplist
        self.jump_list = JumpList()

        # Ensure EasyMotion overlays are removed between tests to avoid
        # accessing deleted widgets when reusing the session-scoped editor.
        self.remove_marker_of_easymotion()

        if self.timer_go_to_definition is not None:
            self.timer_go_to_definition.stop()
            self.timer_go_to_definition = None

        self.to_normal()

    def to_insert(self):
        """Change vim state to insert mode."""
        editor = self.get_editor()
        if editor is None:
            return
        self.is_visual_mode = False
        self.remove_marker_of_easymotion()
        editor.clear_extra_selections("vim_selection")
        editor.clear_extra_selections("vim_cursor")
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
        """Set focus to the Vim command line after ``delay`` milliseconds.

        Note: This is mainly used when the editor regains focus after external
        actions.

        Args:
            delay: Delay in milliseconds before focusing the command line.
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

    # ---- Application helpers ----------------------------------------
    def _get_application_plugin(self):
        """Return and cache Spyder's application plugin."""
        plugin = getattr(self, "_application_plugin", None)
        if plugin is None:
            try:
                plugin = self.main.get_plugin(Plugins.Application)
            except Exception:
                return None
            self._application_plugin = plugin
        return plugin

    def _open_file_in_application(self, file_path: str) -> None:
        """Open *file_path* through the application plugin when available."""
        if not file_path:
            return
        application = self._get_application_plugin()
        open_file = getattr(application, "open_file_in_plugin", None)
        if callable(open_file):
            open_file(file_path)

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

    # ---- Jump list ---------------------------------------------------
    def get_current_location(self):
        """Return the current file path and cursor position or ``None``."""
        stack = self.get_editorstack()
        editor = self.get_editor()
        if not stack or not editor or editor.textCursor().isNull():
            return None
        try:
            return stack.get_current_filename(), editor.textCursor().position()
        except Exception:
            return None

    # ---- Jump list ---------------------------------------------------
    def push_jump(self) -> None:
        """Record the current cursor position in the jump list."""
        location = self.get_current_location()
        if location is None:
            return
        file_path, pos = location
        self.jump_list.push(file_path, pos)

    def start_definition_tracking(self, previous):
        """Monitor cursor movement after ``gd`` and update the jump list."""
        timer = QTimer(self)
        self.timer_go_to_definition = timer

        def stop():
            timer.stop()
            self.timer_go_to_definition = None

        def check():
            current = self.get_current_location()
            if previous is not None and current and current != previous:
                pos = current[1]
                
                if pos < 1:
                    # The cursor may be set to 0 before it is created and positioned,
                    # but a definition never starts at cursor position 0.
                    return
                self.push_jump()
                stop()

        def finalize():
            stop()
            current = self.get_current_location()
            if previous is not None and current == previous:
                self.jump_list.pop_last()

        timer.timeout.connect(check)
        timer.start(100)
        QTimer.singleShot(2000, finalize)

    def jump_backward(self) -> None:
        """Jump to the previous location in the jump list."""
        jump = self.jump_list.back()
        if not jump:
            return
        if self.get_editorstack().is_file_opened(jump.file) is None:
            self._open_file_in_application(jump.file)
        self.get_editorstack().set_current_filename(jump.file)
        self.cursor.set_cursor_pos(jump.pos)

    def jump_forward(self) -> None:
        """Jump to the next location in the jump list."""
        jump = self.jump_list.forward()
        if not jump:
            return
        if self.get_editorstack().is_file_opened(jump.file) is None:
            self._open_file_in_application(jump.file)
        self.get_editorstack().set_current_filename(jump.file)
        self.cursor.set_cursor_pos(jump.pos)

    def set_message(self, msg, duration_ms=-1):
        """Display ``msg`` in the status bar."""
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

    def stop_recording_macro(self):
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
        """Set markers for EasyMotion.

        Args:
            positions: Character positions to annotate.
            motion_type: Kind of motion that triggered the annotation.
        """
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
        """Annotate the editor with temporary inline labels.

        Args:
            info: Mapping of cursor positions to text labels.
            timeout: Milliseconds before labels are cleared.
        """
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
