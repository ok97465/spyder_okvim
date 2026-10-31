"""Insert undo grouping and dot recording for one Vim input session.

The session owns the live insertion and recorded change. It observes Qt events
only while inserting and disconnects the captured editor before cancellation.
Pure replay values remain in state.py; no UI widget is traversed from here.
"""

# Standard Libraries
from contextlib import contextmanager

# Third Party Libraries
from qtpy.QtCore import QCoreApplication, QEvent, QObject, Qt
from qtpy.QtGui import QKeySequence, QTextCursor

from .state import DotCmdInfo, InputSource, KeyInfo


class InsertEdit:
    """One insertion, including its count and shared undo block."""

    def __init__(self, editor, command: str, count: int):
        self.editor = editor
        self.command = command
        self.count = count
        self.edit_cursor = editor.textCursor()
        self.has_edit = False
        self.initial_revision = self.edit_cursor.document().revision()
        self.start_cursor = QTextCursor(self.edit_cursor)
        self.start_cursor.setKeepPositionOnInsert(True)
        self.end_cursor = QTextCursor(self.edit_cursor)

    @contextmanager
    def edit_block(self):
        """Join edits while delivering document signals after every event."""
        document = self.edit_cursor.document()
        revision = document.revision()
        if self.has_edit or revision != self.initial_revision:
            self.edit_cursor.joinPreviousEditBlock()
        else:
            self.edit_cursor.beginEditBlock()
        try:
            yield
        finally:
            self.edit_cursor.endEditBlock()
            self.has_edit = self.has_edit or document.revision() != revision


# Historical public name; the implementation now lives with its edit lifetime.
InsertCmdInfo = InsertEdit


class InsertRepeatSession(QObject):
    """Own Insert/count/undo and dot recording on the active document's thread.

    ``status`` supplies mode, cursor and immutable command input values. The
    session never owns a command-line widget; replay delivery stays with input.
    """

    def __init__(self, status):
        super().__init__(status)
        self.status = status
        self.insertion = None
        self.dot_command = DotCmdInfo()
        self.is_replaying = False
        self._forwarding_event = False

    def record_editor_key(self, event):
        """Record an editor key for dot replay unless a replay is already active."""
        self.handle_insert_key(event)
        if self.status.running_dot_cmd:
            return
        self.status.dot_cmd.key_list_from_editor.append(
            KeyInfo(event.key(), event.text(), event.modifiers(), InputSource.EDITOR)
        )

    def disconnect_from_editor(self):
        """Disconnect from the editor."""
        # disconnect previous connection.
        editor = self.status.dot_cmd.editor_connected
        self.status.dot_cmd.editor_connected = None
        if editor:
            try:
                editor.sig_key_pressed.disconnect(self.record_editor_key)
            except (TypeError, RuntimeError):
                # The editor may already have been disconnected or closed.
                pass

    def handle_insert_key(self, event):
        """Cancel count expansion when Insert navigation interrupts typing."""
        if self.insertion is not None and event.key() in (
            Qt.Key_Left,
            Qt.Key_Right,
            Qt.Key_Up,
            Qt.Key_Down,
            Qt.Key_Home,
            Qt.Key_End,
            Qt.Key_PageUp,
            Qt.Key_PageDown,
        ):
            self.insertion.count = 1

    def start_insert(self, command: str, count: int):
        """Begin an insertion before changing the document, including ``o/O``."""
        self.finish_insert(apply_count=False)
        self.disconnect_from_editor()
        self.insertion = InsertEdit(self.status.get_editor(), command, count)
        self.insertion.editor.installEventFilter(self)

    def eventFilter(self, watched, event):
        """Group each Insert event without delaying editor updates until Esc."""
        info = self.insertion
        if (
            info is None
            or watched is not info.editor
            or self._forwarding_event
            or event.type() not in (QEvent.KeyPress, QEvent.InputMethod)
        ):
            return super().eventFilter(watched, event)
        if event.type() == QEvent.KeyPress and (
            event.matches(QKeySequence.Undo) or event.matches(QKeySequence.Redo)
        ):
            self.finish_insert(apply_count=False)
            return False
        self._forwarding_event = True
        try:
            with info.edit_block():
                # Forward through Qt so other editor filters still run.
                QCoreApplication.sendEvent(watched, event)
        finally:
            self._forwarding_event = False
        return True

    def send_insert_event(self, editor, event):
        """Group programmatic input from dot and macro playback as well."""
        info = self.insertion
        if info is not None and info.editor is editor:
            with info.edit_block():
                self.handle_insert_key(event)
                editor.keyPressEvent(event)
        else:
            editor.keyPressEvent(event)

    def set_insert_start(self):
        """Track the inserted range after positioning or opening a line."""
        info = self.insertion
        cursor = info.editor.textCursor()
        if info.command in ("o", "O"):
            cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.setKeepPositionOnInsert(True)
        info.start_cursor = cursor
        info.end_cursor = info.editor.textCursor()

    def finish_insert(self, apply_count=True):
        """Apply the insertion count once and close its undo block."""
        info = self.insertion
        if info is None:
            return
        self.insertion = None
        self.disconnect_from_editor()
        try:
            info.editor.removeEventFilter(self)
        except RuntimeError:
            return  # The editor has already been closed.
        editor = info.editor
        if not apply_count or editor is not self.status.get_editor():
            return
        cursor = editor.textCursor()
        start = info.start_cursor.position()
        end = cursor.position()
        if end != info.end_cursor.position():
            # Also guard cursor changes made with the mouse or editor APIs.
            info.count = 1
        if info.count > 1 and end >= start:
            inserted = QTextCursor(cursor)
            inserted.setPosition(start)
            inserted.setPosition(end, QTextCursor.KeepAnchor)
            text = inserted.selectedText().replace("\u2029", "\n")
            if info.command in ("o", "O"):
                text = "\n" + text
            if text:
                with info.edit_block():
                    cursor.insertText(text * (info.count - 1))
                editor.document_did_change()
        if info.count > 1 and not cursor.atBlockStart():
            cursor.movePosition(QTextCursor.PreviousCharacter)
        editor.setTextCursor(cursor)

    def update_dot_cmd(
        self, connect_editor, register_name=None, key_list_to_cmd_line=None
    ):
        """Snapshot the command, register and Visual shape before a change.

        Replace prior replay keys and optionally observe subsequent Insert keys.
        Visual block numbers are zero-based; columns use Qt UTF-16 offsets.
        """
        if self.status.running_dot_cmd is True:
            return
        dot_cmd = self.status.dot_cmd
        dot_cmd.put_payload = None
        dot_cmd.vim_state = self.status.vim_state
        dot_cmd.count_text = self.status.input_cmd.count_text
        dot_cmd.cmd = self.status.input_cmd.cmd
        dot_cmd.register_name = register_name
        dot_cmd.clear_key_list()
        if key_list_to_cmd_line:
            dot_cmd.key_list_to_cmd_line = key_list_to_cmd_line
        self.disconnect_from_editor()

        # For receiving key event from codeeditor
        if connect_editor:
            editor = self.status.get_editor()
            self.status.dot_cmd.editor_connected = editor
            editor.sig_key_pressed.connect(self.record_editor_key)

        # Get selection region.
        if self.status.is_normal():
            return

        sel_start = self.status.get_pos_start_in_selection()
        sel_end = self.status.get_pos_end_in_selection()

        block_start, block_no_start = self.status.cursor.get_block(sel_start)
        block_end, block_no_end = self.status.cursor.get_block(sel_end)

        dot_cmd.sel_block_no_start = block_no_start
        dot_cmd.sel_block_no_end = block_no_end
        dot_cmd.sel_col_start = sel_start - block_start.position()
        dot_cmd.sel_col_end = sel_end - block_end.position()
