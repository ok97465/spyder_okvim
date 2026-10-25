# -*- coding: utf-8 -*-
"""Utilities for searching within the editor."""

from dataclasses import dataclass

from qtpy.QtCore import QObject, QRegularExpression, QTimer, Signal
from qtpy.QtGui import QBrush, QColor, QTextCursor
from qtpy.QtWidgets import QTextEdit

from spyder.config.manager import CONF

from spyder_okvim.spyder.config import CONF_SECTION


@dataclass(frozen=True)
class SearchSnapshot:
    """Search settings to restore after an incremental search is cancelled."""

    text: str
    ignorecase: bool
    forward: bool
    highlight_enabled: bool


class SearchInfo(QObject):
    """Cache search results for the active document and refresh highlights."""

    closed = Signal()

    def __init__(self, vim_cursor, parent=None):
        """Initialize the search state.

        Args:
            vim_cursor: Cursor helper used to draw selections.
            parent: QObject that owns this search state.
        """
        super().__init__(parent)
        self.color_fg = QBrush(QColor("#A9B7C6"))
        self.color_bg = QBrush(QColor("#30652F"))
        self.txt_searched = ""
        self.selection_list = []
        self.vim_cursor = vim_cursor
        self.ignorecase = True
        self.forward = True
        self._pattern = QRegularExpression()
        self._editor = None
        self._document = None
        self._revision = None
        self._highlight_enabled = True
        self._closed = False
        self._editor_signals = []
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(150)
        self._refresh_timer.timeout.connect(self.refresh)

        self.set_color()
        source = vim_cursor.editor_widget.get_widget()
        if not hasattr(source, "sig_codeeditor_changed"):
            source = vim_cursor.get_editorstack()
        for name in ("sig_codeeditor_changed", "sig_editor_focus_changed"):
            signal = getattr(source, name, None)
            if signal is not None:
                signal.connect(self.refresh)
                self._editor_signals.append(signal)

    def set_color(self):
        """Refresh highlight colors from configuration."""
        self.color_fg = QBrush(QColor(CONF.get(CONF_SECTION, "search_fg_color")))
        self.color_bg = QBrush(QColor(CONF.get(CONF_SECTION, "search_bg_color")))

        for sel in self.selection_list:
            sel.format.setForeground(self.color_fg)
            sel.format.setBackground(self.color_bg)
        self._display_selections()

    def search(self, text, ignorecase=True, forward=True):
        """Start a search using one compiled expression for all matches."""
        self.txt_searched = text
        self.ignorecase = ignorecase
        self.forward = forward
        self._pattern = QRegularExpression(text)
        if ignorecase:
            self._pattern.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        self._revision = None
        self._highlight_enabled = True
        self.refresh()

    def snapshot(self):
        """Save the confirmed pattern, direction, and highlight visibility."""
        return SearchSnapshot(
            self.txt_searched,
            self.ignorecase,
            self.forward,
            self._highlight_enabled,
        )

    @property
    def is_closed(self):
        """Whether this search state has released its editor connections."""
        return self._closed

    def restore(self, snapshot):
        """Restore saved search settings and repaint their current matches."""
        self.search(
            snapshot.text,
            ignorecase=snapshot.ignorecase,
            forward=snapshot.forward,
        )
        if not snapshot.highlight_enabled:
            self.clear_highlights()

    def _display_selections(self):
        """Draw only on the editor that owns these results."""
        if self._editor is not None:
            selections = self.selection_list if self._highlight_enabled else []
            self._editor.set_extra_selections("vim_search", selections)

    def _disconnect_document(self):
        """Release the old document and remove its highlights."""
        if self._document is not None:
            try:
                self._document.contentsChanged.disconnect(self._document_changed)
            except (TypeError, RuntimeError):
                pass
        if self._editor is not None:
            try:
                self._editor.destroyed.disconnect(self._editor_destroyed)
                self._editor.clear_extra_selections("vim_search")
            except (TypeError, RuntimeError):
                pass
        self._document = None
        self._editor = None
        self._revision = None
        self.selection_list = []

    def _editor_destroyed(self, *args):
        """Cancel pending work before a closed editor can be accessed."""
        self._refresh_timer.stop()
        self._editor = None
        self._disconnect_document()

    def _document_changed(self):
        """Coalesce edits without delaying explicit search motions."""
        self._revision = None
        if self.txt_searched:
            self._refresh_timer.start()

    def refresh(self, *args):
        """Recompute matches when the active document or its text changes."""
        if self._closed:
            return
        self._refresh_timer.stop()
        stack = self.vim_cursor.get_editorstack()
        editor = stack.get_current_editor() if stack is not None else None
        document = editor.document() if editor is not None else None
        if editor is not self._editor or document is not self._document:
            self._disconnect_document()
            self._editor = editor
            self._document = document
            if editor is not None:
                document.contentsChanged.connect(self._document_changed)
                editor.destroyed.connect(self._editor_destroyed)
        if document is None or self._revision == document.revision():
            return

        selections = []
        if self.txt_searched and self._pattern.isValid():
            block = document.begin()
            while block.isValid():
                # Match each paragraph, treating NBSP as a space, just like
                # QTextDocument.find. Qt's iterator advances empty matches
                # safely and retains UTF-16 offsets and combining marks.
                matches = self._pattern.globalMatch(block.text().replace("\u00a0", " "))
                while matches.hasNext():
                    match = matches.next()
                    cursor = QTextCursor(document)
                    cursor.setPosition(block.position() + match.capturedStart())
                    cursor.setPosition(
                        block.position() + match.capturedEnd(), QTextCursor.KeepAnchor
                    )
                    selection = QTextEdit.ExtraSelection()
                    selection.format.setForeground(self.color_fg)
                    selection.format.setBackground(self.color_bg)
                    selection.cursor = cursor
                    selections.append(selection)
                block = block.next()

        self.selection_list = selections
        self._revision = document.revision()
        self._display_selections()

    def get_sel_start_list(self):
        """Return current match positions, flushing any pending edit refresh."""
        self.refresh()
        if not self._highlight_enabled:
            self._highlight_enabled = True
            self._display_selections()
        return list(
            dict.fromkeys(sel.cursor.selectionStart() for sel in self.selection_list)
        )

    def clear_highlights(self):
        """Hide highlights until the next explicit search or search motion."""
        self._highlight_enabled = False
        self._display_selections()

    def close(self):
        """Disconnect signals and cancel delayed work during reset or shutdown."""
        if self._closed:
            return
        self._closed = True
        self.closed.emit()
        self._refresh_timer.stop()
        for signal in self._editor_signals:
            try:
                signal.disconnect(self.refresh)
            except (TypeError, RuntimeError):
                pass
        self._editor_signals.clear()
        self._disconnect_document()
