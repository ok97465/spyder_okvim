"""Offer command history only at stable, interactive prompt boundaries."""

# Standard Libraries
import weakref

# Third Party Libraries
from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtWidgets import QApplication
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.commandline_history import HistoryPopup, history_candidates
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted


class CommandlineHistoryController(QObject):
    """Keep candidate selection separate from command text and execution."""

    def __init__(self, vim_widget):
        super().__init__(vim_widget)
        self._vim = weakref.ref(vim_widget)
        self._editor = None
        self._viewport = None
        self._window = None
        self._session = None
        self._context = None
        self._suppressed = False
        self._closed = False
        self.enabled = False
        self.popup = None
        self.candidates = []
        self.selected_index = None
        self._connections = (
            (vim_widget.sig_input_started, self._hide),
            (vim_widget.sig_input_finished, self.sync),
            (vim_widget.sig_command_changed, self.sync),
            (vim_widget.sig_command_cancelled, self.cancel),
            (vim_widget.commandline.textEdited, self._edited),
            (vim_widget.commandline.textChanged, self._text_changed),
            (vim_widget.commandline.cursorPositionChanged, self.sync),
        )
        for signal, slot in self._connections:
            signal.connect(slot)
        self.apply_settings()

    def apply_settings(self):
        """Apply an explicit preference change, including immediate dismissal."""
        if self._closed:
            return
        enabled = bool(CONF.get(CONF_SECTION, "commandline_history_enabled", True))
        if enabled != self.enabled:
            self.cancel()
            self.enabled = enabled
            self.sync()

    def set_editor(self, editor):
        """Follow the active viewport without retaining a deleted editor."""
        if self._closed:
            return
        if editor is not None and widget_is_deleted(editor):
            editor = None
        viewport = editor.viewport() if editor is not None else None
        if viewport is live_widget(self._viewport):
            self._set_window(editor.window() if editor is not None else None)
            return
        self.cancel()
        previous = live_widget(self._viewport)
        if previous is not None:
            previous.removeEventFilter(self)
            try:
                previous.destroyed.disconnect(self._viewport_destroyed)
            except (TypeError, RuntimeError):
                pass
        self._set_window(None)
        if self.popup is not None and not widget_is_deleted(self.popup):
            self.popup.deleteLater()
        self.popup = None
        self._editor = weakref.ref(editor) if editor is not None else None
        self._viewport = weakref.ref(viewport) if viewport is not None else None
        self._set_window(editor.window() if editor is not None else None)
        if viewport is not None:
            viewport.installEventFilter(self)
            viewport.destroyed.connect(self._viewport_destroyed)

    def _set_window(self, window):
        previous = live_widget(self._window)
        if window is previous:
            return
        self.cancel()
        if previous is not None:
            previous.removeEventFilter(self)
        self._window = weakref.ref(window) if window is not None else None
        if window is not None:
            window.installEventFilter(self)

    def _viewport_destroyed(self, *args):
        self.cancel()
        self._set_window(None)
        self._editor = self._viewport = self._window = None
        self.popup = None

    def _hide(self):
        if self.popup is not None and not widget_is_deleted(self.popup):
            self.popup.hide()

    def _clear_candidates(self):
        self._hide()
        if self.popup is not None and not widget_is_deleted(self.popup):
            self.popup.select(None)
        self.candidates = []
        self.selected_index = None
        self._context = None

    def cancel(self):
        """Release all state when a prompt or its editor is left."""
        self._clear_candidates()
        self._session = None
        self._suppressed = False

    def suppress(self):
        """Keep recalled/completed text quiet until a real edit or new prompt."""
        self._suppressed = True
        self._clear_candidates()

    def _edited(self):
        self._suppressed = False
        self.selected_index = None
        self._context = None

    def _text_changed(self):
        self._clear_candidates()
        self.sync()

    def _current_context(self):
        vim = live_widget(self._vim)
        editor = live_widget(self._editor)
        viewport = live_widget(self._viewport)
        if vim is None or self._closed or not self.enabled:
            return None
        line = vim.commandline
        status = vim.vim_status
        if (
            widget_is_deleted(line)
            or not line.hasFocus()
            or not line.isActiveWindow()
            or line.is_composing
            or line._updating_commandline
            or vim.is_playing_macro
            or status.is_recording_macro()
            or status.running_dot_cmd
            or status.substitute_confirm is not None
            or editor is None
            or viewport is None
            or not viewport.isVisible()
            or status.get_editor() is not editor
            or editor.window() is not line.window()
        ):
            return None
        context = line._history_context(line.text())
        if context is None:
            return None
        # QLineEdit positions count UTF-16 units, including surrogate pairs.
        if line.cursorPosition() != len(line.text().encode("utf-16-le")) // 2:
            return None
        return status.sub_mode, *context

    def sync(self):
        """Read candidates after recursive input and IME updates have settled."""
        vim = live_widget(self._vim)
        if self._closed or vim is None or vim.is_processing_input:
            return
        line = vim.commandline
        if line._history_context(line.text()) is None:
            self.cancel()
            return
        session = vim.vim_status.sub_mode
        editor = live_widget(self._editor)
        if editor is not None:
            self._set_window(editor.window())
        if session is not self._session:
            self.cancel()
            self._session = session
        context = self._current_context()
        if context is None or self._suppressed:
            self._clear_candidates()
            return
        _, kind, _, body = context
        candidates = history_candidates(line.histories[kind], body)
        if not candidates:
            self._clear_candidates()
            return
        changed = context != self._context or candidates != self.candidates
        self._context = context
        self.candidates = candidates
        if self.popup is None or widget_is_deleted(self.popup):
            self.popup = HistoryPopup(live_widget(self._viewport))
            changed = True
        if changed:
            self.selected_index = None
            self.popup.set_candidates(candidates)
        appearance_changed = self.popup.refresh_appearance(line.font())
        if changed or appearance_changed:
            self.popup.update_geometry()
        self.popup.select(self.selected_index)
        self.popup.raise_()
        self.popup.show()

    def key_action(self, event):
        """Reserve only keys that a visible, current panel will actually use."""
        vim = live_widget(self._vim)
        if (
            vim is None
            or vim.is_processing_input
            or not self.candidates
            or self.popup is None
            or widget_is_deleted(self.popup)
            or not self.popup.isVisible()
            or self._current_context() != self._context
        ):
            return None
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_N:
                return "next"
            if event.key() == Qt.Key_P:
                return "previous"
        if (
            event.key() in (Qt.Key_Return, Qt.Key_Enter)
            and event.modifiers() == Qt.NoModifier
            and self.selected_index is not None
        ):
            return "accept"
        return None

    def handle_key(self, action, event):
        """Handle an action captured before the outer input guard hid the panel."""
        # Input-start observers can change the prompt before this handler runs.
        # Consume the reserved key without accepting stale text or executing it.
        if (
            not self.candidates
            or self._current_context() != self._context
            or (action == "accept" and self.selected_index is None)
        ):
            self._clear_candidates()
            event.accept()
            return
        if action == "accept":
            self._accept()
        else:
            step = 1 if action == "next" else -1
            if self.selected_index is None:
                self.selected_index = 0 if step == 1 else len(self.candidates) - 1
            else:
                self.selected_index = (self.selected_index + step) % len(
                    self.candidates
                )
        event.accept()

    def _accept(self):
        vim = live_widget(self._vim)
        line = vim.commandline
        context = self._context
        candidate = self.candidates[self.selected_index]
        # Some native IMEs deliver a final commit synchronously here. That
        # commit may change the prefix, so it must never accept a stale row or
        # turn this same Return into command execution.
        QApplication.inputMethod().commit()
        if self._current_context() != context:
            self._clear_candidates()
            return
        self.suppress()
        line._reset_navigation()
        _, _, prompt, _ = context
        line._replace_commandline(prompt + candidate)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Hide, QEvent.Close, QEvent.WindowDeactivate):
            self.cancel()
        elif watched is live_widget(self._viewport) and event.type() == QEvent.Resize:
            if self.popup is not None and not widget_is_deleted(self.popup):
                self.popup.update_geometry()
        return super().eventFilter(watched, event)

    def cleanup(self):
        """Disconnect observers and dispose of the viewport child on shutdown."""
        if self._closed:
            return
        self.set_editor(None)
        for signal, slot in self._connections:
            signal.disconnect(slot)
        self._connections = ()
        self._closed = True
