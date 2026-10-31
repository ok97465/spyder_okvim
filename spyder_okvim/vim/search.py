# -*- coding: utf-8 -*-
"""Utilities for searching within the editor."""

# Standard Libraries
from bisect import bisect_right
from dataclasses import dataclass

# Third Party Libraries
from qtpy.QtCore import QEvent, QObject, QRegularExpression, QTimer, Signal
from qtpy.QtGui import QBrush, QColor, QFont, QPalette, QTextCharFormat, QTextCursor
from qtpy.QtWidgets import QTextEdit

# Project Libraries
from spyder_okvim.spyder.config import PluginSettings
from spyder_okvim.utils.qtcompat import python_cursor_position
from spyder_okvim.utils.search_helpers import compile_pattern, iter_block_matches


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

    def __init__(self, vim_cursor, parent=None, *, settings=None):
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
        self._match_starts = []
        self._positions = []
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

        self.apply_settings(settings or PluginSettings())
        source = vim_cursor.editor_widget.get_widget()
        if not hasattr(source, "sig_codeeditor_changed"):
            source = vim_cursor.get_editorstack()
        for name in ("sig_codeeditor_changed", "sig_editor_focus_changed"):
            signal = getattr(source, name, None)
            if signal is not None:
                signal.connect(self.refresh)
                self._editor_signals.append(signal)

    def apply_settings(self, settings):
        """Apply explicit colors to cached matches without recompiling a search."""
        self.color_fg = QBrush(QColor(settings.search_fg_color))
        self.color_bg = QBrush(QColor(settings.search_bg_color))
        for selection in self.selection_list:
            selection.format.setForeground(self.color_fg)
            selection.format.setBackground(self.color_bg)
        self._display_selections()

    def set_color(self):
        """Compatibility refresh; plugin code passes an explicit snapshot."""
        # Project Libraries
        from spyder_okvim.spyder.config import read_settings

        self.apply_settings(read_settings())

    def search(self, text, ignorecase=True, forward=True, pattern=None):
        """Start a search using one compiled expression for all matches."""
        self.txt_searched = text
        self.ignorecase = ignorecase
        self.forward = forward
        self._pattern = (
            pattern if pattern is not None else compile_pattern(text, ignorecase)
        )
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
            self._display_current_match()

    def _display_current_match(self):
        """Distinguish the match at the cursor using color, weight and underline."""
        if self._editor is None:
            return
        selections = []
        if (
            self._highlight_enabled
            and self.selection_list
            and self._revision == self._editor.document().revision()
        ):
            position = self._editor.textCursor().position()
            index = bisect_right(self._match_starts, position) - 1
            if index >= 0:
                match = self.selection_list[index]
                start = match.cursor.selectionStart()
                end = match.cursor.selectionEnd()
                if start == position or start < position < end:
                    current = QTextEdit.ExtraSelection()
                    current.cursor = QTextCursor(match.cursor)
                    palette = self._editor.palette()
                    current.format.setBackground(palette.brush(QPalette.Highlight))
                    current.format.setForeground(
                        palette.brush(QPalette.HighlightedText)
                    )
                    current.format.setFontWeight(QFont.Bold)
                    current.format.setUnderlineStyle(QTextCharFormat.SingleUnderline)
                    selections.append(current)
        self._editor.set_extra_selections("vim_search_current", selections)

    def result_message(self, index=None, *, forward=None, wrapped=False):
        """Describe a motion's result, keeping invalid patterns distinct from misses."""
        if not self.txt_searched:
            return "No previous search"
        forward = self.forward if forward is None else forward
        pattern_text = ("/" if forward else "?") + self.txt_searched
        if not self._pattern.isValid():
            offset = (
                python_cursor_position(
                    self.txt_searched, self._pattern.patternErrorOffset()
                )
                + 1
            )
            return f"Regex error at {offset}: {self._pattern.errorString()} · {pattern_text}"
        total = len(self._positions)
        if not total:
            return f"No results · {pattern_text}"
        position = "–" if index is None else str(index + 1)
        message = f"{position}/{total}"
        if wrapped:
            message += " · Wrapped to top" if forward else " · Wrapped to bottom"
        return f"{message} · {pattern_text}"

    def eventFilter(self, watched, event):
        """Refresh the current target's palette without recompiling the pattern."""
        if watched is self._editor and event.type() in (
            QEvent.PaletteChange,
            QEvent.StyleChange,
        ):
            self._display_current_match()
        return super().eventFilter(watched, event)

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
                self._editor.cursorPositionChanged.disconnect(
                    self._display_current_match
                )
                self._editor.removeEventFilter(self)
                self._editor.clear_extra_selections("vim_search")
                self._editor.clear_extra_selections("vim_search_current")
            except (TypeError, RuntimeError):
                pass
        self._document = None
        self._editor = None
        self._revision = None
        self.selection_list = []
        self._match_starts = []
        self._positions = []

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
                editor.cursorPositionChanged.connect(self._display_current_match)
                editor.installEventFilter(self)
        if document is None or self._revision == document.revision():
            return

        selections = []
        if self.txt_searched and self._pattern.isValid():
            block = document.begin()
            while block.isValid():
                # Match each paragraph, treating NBSP as a space, just like
                # QTextDocument.find. Qt's iterator advances empty matches
                # safely and retains UTF-16 offsets and combining marks.
                for match in iter_block_matches(self._pattern, block.text()):
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
        self._match_starts = [sel.cursor.selectionStart() for sel in selections]
        self._positions = list(dict.fromkeys(self._match_starts))
        self._revision = document.revision()
        self._display_selections()

    def get_sel_start_list(self):
        """Return current match positions, flushing any pending edit refresh."""
        self.refresh()
        if not self._highlight_enabled:
            self._highlight_enabled = True
            self._display_selections()
        return self._positions.copy()

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
