"""Coordinate Vim modes and the owners of editing, search and input sessions."""

# Standard Libraries

# Third Party Libraries
from qtpy.QtCore import QObject, QTimer, Signal, Slot
from qtpy.QtGui import QKeyEvent, QTextCursor
from qtpy.QtWidgets import QApplication, QLabel, QWidget

# Project Libraries
from spyder_okvim.spyder.config import read_settings, register_selection_layers
from spyder_okvim.spyder.editor import EditorCommands
from spyder_okvim.utils.bookmark_manager import BookmarkManager
from spyder_okvim.utils.cell_helpers import CellRegion
from spyder_okvim.utils.easymotion import EasyMotionMarkerManager, EasyMotionPainter
from spyder_okvim.utils.jump_list import JumpList
from spyder_okvim.utils.qtcompat import text_width

from .cursor import VimCursor
from .insert_repeat import InsertRepeatSession
from .label import ANNOTATION_STYLE, InlineLabel
from .macro import MacroManager
from .registers import Registers
from .search import SearchInfo
from .state import (
    FindInfo,
    InputCmdInfo,
    VimState,
)


class VimStatus(QObject):
    """Coordinate mode changes and services for one plugin instance.

    Insert/repeat and register rules have their own owners. Public forwarding
    methods preserve command integrations without duplicating their state.
    """

    change_label = Signal(int)
    input_cancelled = Signal()

    def __init__(
        self,
        editor_widget: QWidget,
        main: QWidget,
        msg_label: QLabel,
        *,
        command_services_factory=None,
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
        self._command_services_factory = command_services_factory
        self.settings = read_settings()
        register_selection_layers()
        self.cursor: VimCursor = VimCursor(editor_widget, self.settings)
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
        # Input UI binds these public callbacks after constructing its owners.
        self.cancel_pending_input = lambda: None
        self.show_yank_history = lambda: None
        self.clear_yank_history = lambda: None
        self.cancel_macro = lambda: None
        self.is_playing_macro = lambda: False

        self.sub_mode = None

        # command
        self.find_info = FindInfo()
        self.input_cmd = InputCmdInfo("", "")
        self.input_cmd_prev = InputCmdInfo("", "")
        self.insert_repeat = InsertRepeatSession(self)

        # register
        self.registers = Registers(
            lambda: QApplication.clipboard().text(),
            lambda text: QApplication.clipboard().setText(text),
            self.set_message,
        )
        # VimWidget supplies the controller during initialization.
        self.put_controller = None

        # search
        self.search = SearchInfo(self.cursor, self, settings=self.settings)
        self.last_substitute = None
        self.substitute_confirm = None

        # message
        self.msg_label = msg_label
        self.msg_prefix = ""

        # Macro
        self.manager_macro = MacroManager()

        # bookmarks
        self.host = EditorCommands(
            editor_widget, self.cursor, main, self.set_focus_to_vim
        )
        # Project Libraries
        from spyder_okvim.spyder.config import bookmarks_path

        bookmarks_file = bookmarks_path()
        self.bookmark_manager = BookmarkManager(
            bookmarks_file,
            self.host.open_file,
            self.get_editorstack,
            self.get_editor,
            self.cursor.set_cursor_pos,
        )

        # jumplist
        self.jump_list = JumpList()
        self.timer_go_to_definition = None
        self._definition_watch = QTimer(self)
        self._definition_generation = 0
        self._definition_connections = ()
        self._focus_timer = QTimer(self)
        self._focus_timer.setSingleShot(True)
        self._focus_timer.timeout.connect(self._restore_input_focus)
        self._definition_deadline = QTimer(self)
        self._definition_deadline.setSingleShot(True)

        # easymotion
        self.painter_easymotion = EasyMotionPainter()
        self.manager_marker_easymotion = EasyMotionMarkerManager()
        self.editor_connected_easymotion = None

        # Leap
        self.n_annotate_max = 50
        self.labels_for_annotate = [
            InlineLabel(self.editor_widget.get_widget())
            for _ in range(self.n_annotate_max)
        ]
        self.hide_annotate_on_txt()

    @property
    def indent(self) -> str:
        """Return one indentation level from the active document settings."""
        return self.get_editor().indent_chars

    def clear_state(self):
        """Return to Normal state and remove active Visual/annotation display."""
        self.is_visual_mode = False
        self.vim_state = VimState.NORMAL
        editor = self.get_editor()
        if editor:
            editor.clear_extra_selections("vim_selection")
            editor.clear_extra_selections("vim_cursor")
        self.hide_annotate_on_txt()

    def is_normal(self):
        """Check that vim state is normal mode."""
        return self.vim_state == VimState.NORMAL

    def to_normal(self):
        """Change vim state to normal mode."""
        self.finish_insert()
        self.clear_state()
        cursor = self.get_cursor()
        if cursor.atBlockEnd() and not cursor.atBlockStart():
            pos = cursor.position()
            self.cursor.set_cursor_pos(pos - 1)
        try:
            self.change_label.emit(VimState.NORMAL)
        except RuntimeError:
            pass

    def get_cells(self) -> list[CellRegion]:
        """Return the cell regions for the active editor."""
        return self.host.get_cells()

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
        """Schedule input focus in milliseconds for the current editor only."""
        # Standard Libraries
        import weakref

        # Project Libraries
        from spyder_okvim.utils.qtcompat import widget_is_deleted

        editor = self.get_editor()
        if (
            self.cmd_line is None
            or widget_is_deleted(self.cmd_line)
            or editor is None
            or widget_is_deleted(editor)
        ):
            self._focus_timer.stop()
            return
        self._focus_editor = weakref.ref(editor)
        self._focus_timer.start(delay)

    def _restore_input_focus(self):
        """Reject a delayed focus request after its editor has changed."""
        # Project Libraries
        from spyder_okvim.utils.qtcompat import live_widget

        editor = live_widget(getattr(self, "_focus_editor", None))
        if editor is not None and editor is self.get_editor():
            self.set_focus_to_vim()
            self.cursor.draw_vim_cursor()

    def get_register_name(self):
        """Get register name from previous command."""
        txt = self.input_cmd_prev.cmd

        if len(txt) == 2 and txt[0] == '"':
            return txt[1]
        else:
            return '"'  # default register name

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
        """Watch for a gd destination with the existing two-second origin fallback.

        Arrival stops the watch; the deadline retains the existing origin
        bookkeeping policy. One watch/deadline pair belongs to this session.
        Replacing or cancelling
        the request disconnects prior callbacks, so no closed view is revisited.
        """
        self._definition_generation += 1
        generation = self._definition_generation
        timer = self._definition_watch
        timer.stop()
        self._definition_deadline.stop()
        for signal, callback in self._definition_connections:
            signal.disconnect(callback)
        self.timer_go_to_definition = timer

        def stop():
            timer.stop()
            self.timer_go_to_definition = None

        def check():
            if generation != self._definition_generation:
                return
            current = self.get_current_location()
            if previous is not None and current and current != previous:
                if current[1] < 1:
                    # Spyder can briefly report zero before a destination exists.
                    return
                self.push_jump()
                stop()

        def finalize():
            if generation != self._definition_generation:
                return
            stop()
            current = self.get_current_location()
            if previous is not None and current == previous:
                self.jump_list.pop_last()

        self._definition_connections = (
            (timer.timeout, check),
            (self._definition_deadline.timeout, finalize),
        )
        for signal, callback in self._definition_connections:
            signal.connect(callback)
        timer.start(100)
        self._definition_deadline.start(2000)

    def jump_backward(self) -> None:
        """Jump to the previous location in the jump list."""
        jump = self.jump_list.back()
        if not jump:
            return
        if self.get_editorstack().is_file_opened(jump.file) is None:
            self.host.open_file(jump.file)
        self.get_editorstack().set_current_filename(jump.file)
        self.cursor.set_cursor_pos(jump.pos)

    def jump_forward(self) -> None:
        """Jump to the next location in the jump list."""
        jump = self.jump_list.forward()
        if not jump:
            return
        if self.get_editorstack().is_file_opened(jump.file) is None:
            self.host.open_file(jump.file)
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

    def annotate_on_txt(self, info: dict[int, str]):
        """Annotate the editor with temporary inline labels.

        Args:
            info: Mapping of cursor positions to text labels.
            timeout: Milliseconds before labels are cleared.
        """
        editor = self.get_editor()
        tc = editor.textCursor()
        font = editor.viewport().font()
        fm = editor.fontMetrics()
        ch_width = text_width(fm, "H")
        ch_height = fm.height()

        padding_h = (
            ANNOTATION_STYLE["padding_h"] * 2 + ANNOTATION_STYLE["border_width"] * 2
        )
        padding_v = (
            ANNOTATION_STYLE["padding_v"] * 2 + ANNOTATION_STYLE["border_width"] * 2
        )

        for idx, (pos, data) in enumerate(info.items()):
            if idx >= self.n_annotate_max:
                break

            label = self.labels_for_annotate[idx]
            label.set_style(font.family(), font.pointSize())
            text_width_px = max(text_width(fm, data), ch_width)
            label_width = text_width_px + padding_h
            label_height = ch_height + padding_v
            label.setFixedSize(label_width, label_height)
            label.setText(data)

            tc.setPosition(pos)
            rect_in_local = editor.cursorRect(tc)
            pos_in_parent = editor.viewport().mapTo(
                label.parent(), rect_in_local.topLeft()
            )
            label.move(pos_in_parent)
            label.raise_()
            label.show()

    def refresh_settings(self):
        """Read applied options at the plugin boundary and return the snapshot."""
        self.settings = read_settings()
        return self.settings

    @property
    def dot_cmd(self):
        """Recorded change owned by the Insert/repeat session."""
        return self.insert_repeat.dot_command

    @dot_cmd.setter
    def dot_cmd(self, value):
        self.insert_repeat.dot_command = value

    @property
    def insert_cmd(self):
        """Current insertion; retained for existing command integrations."""
        return self.insert_repeat.insertion

    @property
    def running_dot_cmd(self):
        """Whether dot input is replaying rather than recording a new change."""
        return self.insert_repeat.is_replaying

    @running_dot_cmd.setter
    def running_dot_cmd(self, value):
        self.insert_repeat.is_replaying = value

    @property
    def register_dict(self):
        """Register values owned by the register service."""
        return self.registers.values

    @register_dict.setter
    def register_dict(self, values):
        self.registers.values = values

    @property
    def yank_history(self):
        """Immutable-entry history owned by the register service."""
        return self.registers.history

    @property
    def yanky_enabled(self):
        """Whether logical edits should be added to yank history."""
        return self.registers.enabled

    @yanky_enabled.setter
    def yanky_enabled(self, enabled):
        self.registers.enabled = enabled

    def set_register(self, name, content, register_type):
        """Write one register without adding a logical history entry."""
        return self.registers.set_register(name, content, register_type)

    def update_registers(
        self, name, content, register_type, *, is_yank, force_numbered=False
    ):
        """Apply one logical yank/delete and its automatic register updates."""
        return self.registers.update_registers(
            name, content, register_type, is_yank=is_yank, force_numbered=force_numbered
        )

    def get_register(self):
        """Read the register selected by the preceding command prefix."""
        return self.registers.get_register(self.get_register_name())

    def start_insert(self, command, count):
        """Begin one counted insertion before changing the document."""
        self.insert_repeat.start_insert(command, count)

    def finish_insert(self, apply_count=True):
        """Finish the active insertion, optionally suppressing count expansion."""
        self.insert_repeat.finish_insert(apply_count=apply_count)

    def handle_insert_key(self, event):
        """Notify the insertion owner about navigation that stops count expansion."""
        self.insert_repeat.handle_insert_key(event)

    def send_insert_event(self, editor, event):
        """Deliver replay input through the active insertion's undo group."""
        self.insert_repeat.send_insert_event(editor, event)

    def set_insert_start(self):
        """Anchor the insertion after a command has positioned its cursor."""
        self.insert_repeat.set_insert_start()

    def disconnect_from_editor(self):
        """Release the editor connection used to record dot input."""
        self.insert_repeat.disconnect_from_editor()

    def update_dot_cmd(
        self, connect_editor, register_name=None, key_list_to_cmd_line=None
    ):
        """Snapshot the next change through the Insert/repeat owner."""
        self.insert_repeat.update_dot_cmd(
            connect_editor, register_name, key_list_to_cmd_line
        )

    def cancel_pending_work(self):
        """Release view-bound work before a switch or shutdown; safe to repeat."""
        self.cancel_pending_input()
        self.finish_insert(apply_count=False)
        self.disconnect_from_editor()
        self._focus_timer.stop()
        self._definition_deadline.stop()
        self._definition_generation += 1
        self._definition_watch.stop()
        self.timer_go_to_definition = None
        self.cursor.clear_highlights()
        self.remove_marker_of_easymotion()

    def create_command_services(self):
        """Compose independent motion/edit services for one executor lifetime.

        Stateful Leap input must not leak between modes or pending operators.
        All executors use this one assembly point and receive explicit state.
        """
        if self._command_services_factory is not None:
            return self._command_services_factory(self)
        # Compatibility for integrations constructing VimStatus directly.
        # Project Libraries
        from spyder_okvim.utils.editing import EditingActions
        from spyder_okvim.utils.motions import CursorMotions

        motions = CursorMotions(self)
        return motions, EditingActions(self, motions)
