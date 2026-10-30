"""Yank-history display and its asynchronous editor-context lifetime."""

from __future__ import annotations

# Standard Libraries
import weakref

# Third Party Libraries
from qtpy.QtCore import QEvent, Qt, QTimer
from qtpy.QtGui import QStandardItem
from qtpy.QtWidgets import QAbstractItemView, QDialog, QHeaderView

from .list_dialog import PopupTableDialog
from .qtcompat import live_widget, widget_is_deleted


class YankHistoryDialog(PopupTableDialog):
    """Display bounded previews while returning the original selected entry.

    Read ``selected_entry`` during ``finished`` before ``WA_DeleteOnClose`` can
    destroy the Qt dialog. Focus restoration and editing belong to the caller.
    """

    PREVIEW_LENGTH = 120

    def __init__(self, entries, parent=None):
        super().__init__(
            "Yank history",
            parent=parent,
            headers=["Type", "Lines", "Text"],
            min_width=560,
            max_height=360,
        )
        self.entries = tuple(entries)
        self._entries_by_id = {entry.id: entry for entry in self.entries}
        self.selected_entry = None
        self.list_viewer.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # Previews are bounded, and only the small metadata columns autosize.
        header = self.list_viewer.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self._populate()
        if self.entries:
            self.list_viewer.setCurrentIndex(self.list_model.index(0, 0))
            self.list_viewer.selectRow(0)
        self.list_viewer.installEventFilter(self)
        self.list_viewer.setFocus()

    @classmethod
    def preview(cls, text):
        """Build a single-line preview without copying the complete payload."""
        prefix = text[: cls.PREVIEW_LENGTH]
        prefix = prefix.replace("\n", " ↵ ").replace("\r", " ␍ ")
        prefix = prefix.replace("\t", " ⇥ ").replace("\u2029", " ↵ ")
        truncated = len(prefix) > cls.PREVIEW_LENGTH or len(text) > cls.PREVIEW_LENGTH
        return prefix[: cls.PREVIEW_LENGTH - 1] + "…" if truncated else prefix

    def _populate(self):
        for entry in self.entries:
            row = [
                QStandardItem("Line" if entry.kind == "linewise" else "Character"),
                QStandardItem(str(entry.line_count)),
                QStandardItem(self.preview(entry.text)),
            ]
            for item in row:
                item.setEditable(False)
                item.setData(entry.id, Qt.UserRole)
            row[1].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.list_model.appendRow(row)

    @staticmethod
    def _handles_key(event):
        key, modifiers = event.key(), event.modifiers()
        return (modifiers == Qt.ControlModifier and key in (Qt.Key_P, Qt.Key_N)) or (
            modifiers == Qt.NoModifier
            and key
            in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape)
        )

    def eventFilter(self, obj, event):
        """Reserve navigation shortcuts, and edit only on the KeyPress event."""
        if (
            obj is self.list_viewer
            and event.type()
            in (
                QEvent.ShortcutOverride,
                QEvent.KeyPress,
            )
            and self._handles_key(event)
        ):
            event.accept()
            if event.type() == QEvent.KeyPress:
                self.keyPressEvent(event)
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.NoModifier:
            if event.key() == Qt.Key_Up:
                self.prev_row()
                event.accept()
                return
            if event.key() == Qt.Key_Down:
                self.next_row()
                event.accept()
                return
        super().keyPressEvent(event)

    def accept(self):
        index = self.list_viewer.currentIndex()
        entry_id = index.data(Qt.UserRole) if index.isValid() else None
        self.selected_entry = self._entries_by_id.get(entry_id)
        super().accept()

    def reject(self):
        self.selected_entry = None
        super().reject()


class YankHistoryPicker:
    """One popup request, valid only while its captured view stays unchanged."""

    def __init__(self, widget, editor, entries):
        self.widget = widget
        self.status = widget.vim_status
        self.editor_ref = weakref.ref(editor)
        self.document_ref = weakref.ref(editor.document())
        self.generation = widget.put_controller.text_generation
        self.mode = self.status.vim_state
        cursor = editor.textCursor()
        self.cursor = (cursor.anchor(), cursor.position())
        self.selection = self._selection(editor)
        # Keep the wrapper alive until the Qt popup has finished.
        self.dialog = YankHistoryDialog(entries, editor.window())
        self.entry = None
        self._connections = []
        self._finishing = False
        self._restore_attempts = 0

    @staticmethod
    def _selection(editor):
        selections = editor.get_extra_selections("vim_selection")
        if selections:
            cursor = selections[0].cursor
            return cursor.anchor(), cursor.position()
        return None

    def show(self):
        editor = live_widget(self.editor_ref)
        self._connections = [
            (editor.document().contentsChange, self._text_changed),
            (editor.document().undoCommandAdded, self._invalidate),
            (editor.destroyed, self._invalidate),
            (editor.document().destroyed, self._invalidate),
        ]
        for signal, callback in self._connections:
            signal.connect(callback)
        self.dialog.finished.connect(self._finished)
        self.dialog.move(editor.mapToGlobal(editor.cursorRect().bottomLeft()))
        self.dialog.show()
        self.dialog.list_viewer.setFocus()

    def _disconnect(self):
        for signal, callback in self._connections:
            try:
                signal.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        self._connections.clear()

    def cancel(self):
        """Release observed targets after the owner has invalidated this request."""
        self._disconnect()
        if not widget_is_deleted(self.dialog):
            self.dialog.reject()

    def is_current(self):
        editor = live_widget(self.editor_ref)
        document = live_widget(self.document_ref)
        if (
            self.widget._yank_picker is not self
            or not self.status.yanky_enabled
            or editor is None
            or editor is not self.status.get_editor()
            or document is None
            or editor.document() is not document
            or editor.isReadOnly()
            or self.widget.put_controller.text_generation != self.generation
        ):
            return False
        cursor = editor.textCursor()
        return (
            (cursor.anchor(), cursor.position()) == self.cursor
            and self.status.vim_state == self.mode
            and self._selection(editor) == self.selection
        )

    def _invalidate(self, *args):
        if self.widget._yank_picker is self:
            self.widget.cancel_yank_picker()

    def _text_changed(self, position, removed, added):
        if removed or added:
            self._invalidate()

    def _finished(self, result):
        if self.widget._yank_picker is self and not self._finishing:
            self._finishing = True
            # Capture synchronously while the dialog still exists.
            self.entry = (
                self.dialog.selected_entry if result == QDialog.Accepted else None
            )
            # Popup deletion can post focus changes after ``finished``. Keep
            # the request active until those settle, then create the put.
            QTimer.singleShot(0, self._complete)

    def _complete(self):
        if self.widget._yank_picker is not self:
            return
        valid = self.is_current()
        editor = live_widget(self.editor_ref)
        line = self.widget.commandline
        # Check focus on a later event-loop turn after every restoration attempt.
        if valid and (self._restore_attempts == 0 or not line.hasFocus()):
            if self._restore_attempts < 5:
                self._restore_attempts += 1
                editor.window().activateWindow()
                line.setFocus()
                QTimer.singleShot(0, self._complete)
                return
            valid = False
        self._disconnect()
        try:
            if not valid:
                return
            # Focus handlers preserve state while this request is active, and
            # is_current() has verified the captured cursor and selection.
            self.status.change_label.emit(self.mode)
            if self.widget._yank_picker is not self:
                return
            self.status.cursor.draw_vim_cursor()
            if self.entry is not None:
                self.widget.put_controller.put(entry=self.entry)
        finally:
            if self.widget._yank_picker is self:
                self.widget._yank_picker = None
