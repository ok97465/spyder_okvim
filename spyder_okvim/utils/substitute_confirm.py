"""A short-lived submode for approving precomputed substitutions."""

# Standard Libraries
import weakref

# Third Party Libraries
from qtpy.QtGui import QColor, QTextCursor, QTextFormat
from qtpy.QtWidgets import QTextEdit

# Project Libraries
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted


class SubstituteConfirm:
    """Approve ordered original-document targets without holding an edit block."""

    accepts_input_method = False
    allow_leaderkey = False
    hint_prefix = None
    history_kind = None

    def __init__(self, vim_status, editor, targets, on_finish):
        self.status = vim_status
        self._editor_ref = weakref.ref(editor)
        self.document = editor.document()
        self.targets = tuple(targets)
        self.on_finish = on_finish
        self.active = True
        self._edited = False
        self.replacement_count = 0
        self.last_line = None
        self._lines = set()
        self._index = self._delta = 0
        self._revision = self.document.revision()
        self._editing = self._context_lost = False
        self._connections = []

    @property
    def editor(self):
        return live_widget(self._editor_ref)

    @property
    def line_count(self):
        return len(self._lines)

    def valid(self):
        """Whether the captured document is still current and unchanged."""
        editor = self.editor
        if self._context_lost or editor is None or widget_is_deleted(self.document):
            return False
        return (
            self.status.get_editor() is editor
            and editor.document() is self.document
            and self.document.revision() == self._revision
            and not editor.isReadOnly()
        )

    def start(self):
        """Observe cancellation and show the first target after installing submode."""
        if not self.valid():
            self.cancel()
            return
        for signal, callback in (
            (self.document.contentsChanged, self._document_changed),
            (self.document.destroyed, self._destroyed),
            (self.editor.destroyed, self._destroyed),
            (self.status.input_cancelled, self.cancel),
        ):
            signal.connect(callback)
            self._connections.append((signal, callback))
        if not self.targets:
            self._finish()
        else:
            self._show_target()

    def __call__(self, text):
        """Consume confirmation input without changing Normal command records."""
        if not self.active:
            return True
        if not self.valid():
            self.cancel()
            return True
        if text in ("q", "\x1b"):
            self.cancel()
            return True
        if text not in ("y", "n", "a", "l"):
            return True
        try:
            while self._index < len(self.targets):
                if text != "n":
                    self._replace_target()
                self._index += 1
                if text != "a":
                    break
            if text == "l" or self._index == len(self.targets):
                # A final n keeps the cursor on the skipped match. Finishing
                # with y/l goes to column zero; a uses normal :s positioning.
                if text != "n":
                    block = self.document.findBlockByNumber(self.last_line)
                    position = block.position()
                    if text == "a":
                        line = block.text()
                        position += len(line) - len(line.lstrip(" \t"))
                    self.status.cursor.set_cursor_pos_without_end(position)
                self._finish()
            else:
                self._show_target()
        except Exception:
            self.cancel()
            raise
        return True

    def _show_target(self):
        start, end, _ = self.targets[self._index]
        cursor = QTextCursor(self.document)
        cursor.setPosition(start + self._delta)
        cursor.setPosition(end + self._delta, QTextCursor.KeepAnchor)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format.setBackground(QColor("#c05b3d"))
        selection.format.setForeground(QColor("#ffffff"))
        if not cursor.hasSelection():
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        self.editor.set_extra_selections("vim_substitute", [selection])
        self.status.cursor.set_cursor_pos_without_end(start + self._delta)
        self.status.set_message("replace? (y/n/a/l/q)")

    def _replace_target(self):
        editor = self.editor
        start, end, replacement = self.targets[self._index]
        start, end = start + self._delta, end + self._delta
        cursor = QTextCursor(self.document)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        self.last_line = cursor.blockNumber()
        self._lines.add(self.last_line)
        self.replacement_count += 1
        if cursor.selectedText() == replacement:
            return

        previous_skip_rstrip = editor.skip_rstrip
        editor.skip_rstrip = True
        self._editing = True
        try:
            if self._edited:
                cursor.joinPreviousEditBlock()
            else:
                cursor.beginEditBlock()
            try:
                cursor.insertText(replacement)
            finally:
                cursor.endEditBlock()
            self._edited = True
            self._delta += len(replacement.encode("utf-16-le")) // 2 - (end - start)
            self._revision = self.document.revision()
            editor.document_did_change()
        finally:
            self._editing = False
            editor.skip_rstrip = previous_skip_rstrip

    def _document_changed(self):
        if not self._editing:
            self._context_lost = True
            self.cancel()

    def _destroyed(self, *args):
        self._context_lost = True
        self.cancel()

    def on_escape(self):
        self.cancel()

    def cancel(self):
        """Keep approved edits and disconnect the pending confirmation session."""
        self._finish()

    def _finish(self):
        if not self.active:
            return
        self.active = False
        for signal, callback in self._connections:
            try:
                signal.disconnect(callback)
            except (TypeError, RuntimeError):
                pass
        self._connections.clear()
        if self.editor is not None:
            self.editor.clear_extra_selections("vim_substitute")
        if self.status.sub_mode is self:
            self.status.sub_mode = None
        if self.status.substitute_confirm is self:
            self.status.substitute_confirm = None
        self.status.cmd_line.sync_input_method()
        self.on_finish(self)
