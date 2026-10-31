"""Debounced editor overlays for one disposable substitution input session."""

# Standard Libraries
import weakref
from dataclasses import dataclass, replace
from math import ceil

# Third Party Libraries
from qtpy.QtCore import QObject, QPoint, QTimer, Signal
from qtpy.QtGui import QColor, QTextCursor, QTextFormat
from qtpy.QtWidgets import QTextEdit
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.spyder.substitute_overlay import SubstituteOverlay
from spyder_okvim.utils.ex_parser import (
    ExError,
    is_substitute,
    scan_header,
    scan_substitute_preview,
)
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted
from spyder_okvim.utils.substitute import prepare_substitution
from spyder_okvim.utils.substitute_preview import (
    PreviewLimits,
    PreviewResult,
    SubstitutePreview,
)


@dataclass(frozen=True)
class PreviewKey:
    """All inputs whose equality permits reuse of a completed calculation."""

    text: str
    ignorecase: bool
    smartcase: bool
    read_only: bool
    limits: PreviewLimits
    preview_lines: tuple[int, ...]


class SubstitutePreviewController(QObject):
    """Calculate without touching the document or confirmed Vim records.

    A session starts explicitly on Ex entry, even with the option disabled.
    Suspending keeps that origin and its document watch; cancelling releases
    them, so an external edit cannot silently start another preview session.
    """

    sig_result_ready = Signal()

    DEBOUNCE_MS = 150
    TICK_MS = 8
    VIEW_BUFFER_LINES = 8

    def __init__(self, vim_widget):
        super().__init__(vim_widget)
        self._vim = weakref.ref(vim_widget)
        self._editor = None
        self._document = None
        self._window = None
        self._session = None
        self._revision = None
        self._origin_line = 0
        self._preview_lines = ()
        self._request = None
        self._job = None
        self._cache_key = None
        self._cache_result = None
        self._suspended = False
        self._closed = False
        self._document_connections = []
        self.enabled = True
        self._settings = None
        self.limits = PreviewLimits()
        self.result = None
        self.overlay = SubstituteOverlay(self)
        self.overlay.sig_view_changed.connect(self._schedule_view_sync)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.DEBOUNCE_MS)
        self._timer.timeout.connect(self._start)
        self._chunk_timer = QTimer(self)
        self._chunk_timer.setSingleShot(True)
        self._chunk_timer.timeout.connect(self._step)
        self._view_timer = QTimer(self)
        self._view_timer.setSingleShot(True)
        self._view_timer.timeout.connect(self._sync_view)
        self._connections = (
            (vim_widget.sig_input_started, self._invalidate),
            (vim_widget.sig_input_finished, self.sync),
            (vim_widget.sig_command_changed, self.sync),
            (vim_widget.sig_command_cancelled, self.cancel),
        )
        for signal, slot in self._connections:
            signal.connect(slot)
        self.apply_settings()

    def set_editor(self, editor):
        """Clear the previous editor before changing the active view."""
        if editor is not live_widget(self._editor):
            self.cancel()
            self._editor = weakref.ref(editor) if editor is not None else None
            self.overlay.set_editor(editor)

    def begin_session(self, executor):
        """Capture addresses at Ex entry, independently of later caret moves."""
        self.cancel()
        vim = live_widget(self._vim)
        if self._closed or vim is None:
            return
        editor = vim.vim_status.get_editor()
        if editor is None or widget_is_deleted(editor):
            return
        document = editor.document()
        self._editor = weakref.ref(editor)
        self._document = weakref.ref(document)
        self._window = weakref.ref(editor.window())
        self._session = executor
        self._revision = document.revision()
        self._origin_line = executor.origin_line
        self.overlay.set_editor(editor)
        self._document_connections = [
            (document.contentsChanged, self.cancel),
            (document.destroyed, self.cancel),
            (editor.destroyed, self.cancel),
            (editor.textChanged, self._check_document),
        ]
        for signal, slot in self._document_connections:
            signal.connect(slot)

    def _check_document(self):
        editor = live_widget(self._editor)
        document = live_widget(self._document)
        if (
            editor is None
            or document is None
            or editor.document() is not document
            or document.revision() != self._revision
        ):
            self.cancel()

    def _invalidate(self, *, clear_cache=False):
        self._timer.stop()
        self._chunk_timer.stop()
        self._view_timer.stop()
        self._request = self._job = None
        if clear_cache:
            self._cache_key = self._cache_result = None
        self.result = None
        self.overlay.clear()
        editor = live_widget(self._editor)
        if editor is not None:
            editor.clear_extra_selections("vim_substitute_preview")

    def cancel(self, *args):
        """End this session and disconnect all document lifetime observers."""
        self._invalidate(clear_cache=True)
        self._session = None
        self._document = None
        self._window = None
        self._revision = None
        self._preview_lines = ()
        self._suspended = False
        for signal, slot in self._document_connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._document_connections = []

    def suspend(self):
        """Dismiss work while retaining enough context to resume safely."""
        self._suspended = True
        self._invalidate()

    def resume(self):
        if not self._closed:
            self._suspended = False
            self.sync()

    def apply_settings(self):
        vim = live_widget(self._vim)
        if vim is None:
            return
        search_settings = vim.vim_status.settings
        settings = (
            bool(CONF.get(CONF_SECTION, "substitute_preview_enabled", True)),
            search_settings.ignorecase,
            search_settings.smartcase,
        )
        if settings == self._settings:
            return
        self._settings = settings
        self.enabled = settings[0]
        self._invalidate(clear_cache=True)
        if self.enabled:
            self.sync()

    def _visible_lines(self, editor):
        """Hit-test visible paragraphs without walking hidden/folded blocks."""
        viewport = editor.viewport()
        numbers = []
        y = 0
        # One extra paragraph lets the calculator report a visible-output limit
        # instead of silently presenting a clipped request as complete.
        while y < viewport.height() and len(numbers) <= self.limits.max_preview_lines:
            block = editor.cursorForPosition(QPoint(0, y)).block()
            if not block.isValid() or block.blockNumber() in numbers:
                break
            numbers.append(block.blockNumber())
            bottom = (
                editor.blockBoundingGeometry(block)
                .translated(editor.contentOffset())
                .bottom()
            )
            y = max(y + 1, ceil(bottom))
        return tuple(numbers)

    def _ensure_view_coverage(self):
        """Keep a small buffer so layout-only changes reuse calculated rows."""
        editor = live_widget(self._editor)
        if self._session is None or editor is None:
            return False
        visible = self._visible_lines(editor)
        if set(visible).issubset(self._preview_lines) and (
            len(self._preview_lines) <= self.limits.max_preview_lines + 1
        ):
            return False
        requested = list(visible)
        if visible:
            document = editor.document()
            # Actual visible paragraphs come first, so small scan budgets do
            # not get consumed by a buffer above the viewport.
            for distance in range(1, self.VIEW_BUFFER_LINES + 1):
                for number in (visible[-1] + distance, visible[0] - distance):
                    if len(requested) >= self.limits.max_preview_lines:
                        break
                    if (
                        0 <= number < document.blockCount()
                        and number not in requested
                        and document.findBlockByNumber(number).isVisible()
                    ):
                        requested.append(number)
        self._preview_lines = tuple(requested)
        return True

    def _schedule_view_sync(self):
        """Coalesce geometry events; painting never prepares a regex."""
        if self._session is not None and not self._closed:
            self._view_timer.start(0)

    def _sync_view(self):
        vim = live_widget(self._vim)
        if vim is None or vim.is_processing_input or self._closed:
            return
        if self._current_key() is None:
            return
        if self._ensure_view_coverage():
            self.sync()
            if self._timer.isActive():
                self._timer.start(0)

    def _current_key(self):
        """Check identities and input guards before each document read/show."""
        vim = live_widget(self._vim)
        editor = live_widget(self._editor)
        document = live_widget(self._document)
        if self._closed or vim is None or self._session is None:
            return None
        status = vim.vim_status
        if (
            editor is None
            or document is None
            or status.get_editor() is not editor
            or editor.document() is not document
            or editor.window() is not live_widget(self._window)
            or document.revision() != self._revision
            or status.sub_mode is not self._session
        ):
            self.cancel()
            return None
        line = vim.commandline
        snapshot = line.snapshot()
        if (
            snapshot is None
            or not self.enabled
            or self._suspended
            or vim.is_processing_input
            or snapshot.is_replacing
            or snapshot.is_composing
            or not line.hasFocus()
            or not line.isActiveWindow()
            or not editor.viewport().isVisible()
            or editor.window() is not line.window()
            or vim.is_playing_macro
            or status.is_recording_macro()
            or status.running_dot_cmd
            or status.substitute_confirm is not None
        ):
            return None
        return PreviewKey(
            snapshot.text,
            status.settings.ignorecase,
            status.settings.smartcase,
            editor.isReadOnly(),
            self.limits,
            self._preview_lines,
        )

    def sync(self):
        """Schedule only stable whole-command input, never textChanged work."""
        vim = live_widget(self._vim)
        if vim is None or self._closed or vim.is_processing_input:
            return
        # Ending an Ex context is independent of whether calculation is enabled.
        # Incomplete ranges can still be repaired inside the same prompt.
        text = vim.commandline.text()
        try:
            header = scan_header(text[1:]) if text.startswith(":") else None
        except ExError:
            header = None
        if header is not None and header.command and not is_substitute(header.command):
            self.cancel()
            return
        key = self._current_key()
        if key is None:
            self._invalidate()
            return
        self._ensure_view_coverage()
        key = replace(key, preview_lines=self._preview_lines)
        text = key.text
        try:
            # Bound scanner/tokenizer input before regex preparation as well as
            # bounding the document scan. A long replacement needs no expansion.
            context = scan_substitute_preview(
                text[: self.limits.max_command_chars],
                vim.vim_status.last_substitute,
            )
        except ExError:
            context = None
        if context is None:
            self._invalidate(clear_cache=True)
            return
        if key == self._cache_key:
            self._show(self._cache_result, key)
            return
        if self._request is not None and self._request[0] == key:
            return
        self._invalidate()
        self._request = key, context
        self._timer.start()

    def _start(self):
        if self._request is None:
            return
        key, context = self._request
        if self._current_key() != key:
            self._invalidate()
            return
        vim = live_widget(self._vim)
        document = live_widget(self._document)
        try:
            if len(key.text) > self.limits.max_command_chars:
                result = PreviewResult(
                    spans=(),
                    match_count=0,
                    matched_lines=0,
                    partial=True,
                    reasons=("command length limit",),
                    count_only=False,
                    confirm=False,
                    read_only=key.read_only,
                    first_line=self._origin_line + 1,
                    last_line=self._origin_line + 1,
                )
                self._cache_key, self._cache_result = key, result
                self._request = None
                self._show(result, key)
                return

            pattern = context.spec.pattern
            if not pattern:
                if not context.pattern_closed:
                    self._request = None
                    return
                pattern = vim.vim_status.search.txt_searched
                if not pattern:
                    raise ExError("No previous search pattern")
            prepared = prepare_substitution(
                context.header,
                replace(context.spec, pattern=pattern),
                self._origin_line,
                document.blockCount(),
                prepare_replacement=context.pattern_closed,
                ignorecase=vim.vim_status.settings.ignorecase,
                smartcase=vim.vim_status.settings.smartcase,
            )
            self._job = SubstitutePreview(
                document,
                prepared,
                limits=self.limits,
                preview_lines=key.preview_lines,
            )
            self._step()
        except (ExError, ValueError):
            self._invalidate(clear_cache=True)

    def _step(self):
        job = self._job
        if job is None or self._request is None:
            return
        key, _ = self._request
        if self._current_key() != key:
            self._invalidate()
            return
        try:
            done = job.step(max_milliseconds=self.TICK_MS)
        except (ExError, ValueError):
            self._invalidate(clear_cache=True)
            return
        if self._current_key() != key or job is not self._job:
            return
        if done:
            result = replace(job.result, read_only=key.read_only)
            self._cache_key, self._cache_result = key, result
            self._job = self._request = None
            self._show(result, key)
        else:
            self._chunk_timer.start(0)

    def _show(self, result, key):
        if result is None or self._current_key() != key:
            return
        editor = live_widget(self._editor)
        document = live_widget(self._document)
        selections = []
        for start, end in result.spans:
            cursor = QTextCursor(document)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setBackground(QColor("#9b6723"))
            selection.format.setForeground(QColor("#ffffff"))
            if not cursor.hasSelection():
                selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selections.append(selection)
        editor.set_extra_selections("vim_substitute_preview", selections)
        self.result = result
        self.overlay.set_result(result)
        self.sig_result_ready.emit()

    def cleanup(self):
        if self._closed:
            return
        self.cancel()
        self.overlay.cleanup()
        for signal, slot in self._connections:
            signal.disconnect(slot)
        self._connections = ()
        self._closed = True
