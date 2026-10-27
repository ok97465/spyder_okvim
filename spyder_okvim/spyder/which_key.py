"""Observe stable command waits and schedule read-only prefix hints."""

# Standard Libraries
import weakref
from dataclasses import dataclass

# Third Party Libraries
from qtpy.QtCore import QEvent, QObject, QTimer
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.spyder.which_key_popup import WhichKeyPopup
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted


@dataclass(frozen=True)
class PendingHint:
    """Identify a command wait without retaining its editor or reading candidates.

    Dynamic registers and marks are read only after the display delay expires.
    """

    editor: weakref.ReferenceType
    executor: object
    mode: int
    prefix: str


class WhichKeyController(QObject):
    """Observe completed input and schedule one hint for the current wait."""

    def __init__(self, vim_widget):
        super().__init__(vim_widget)
        self._vim = weakref.ref(vim_widget)
        self._editor = None
        self._viewport = None
        self._context = None
        self._closed = False
        self.popup = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._show_hints)
        self.enabled = None
        self.delay = None
        self._connections = (
            (vim_widget.sig_input_started, self._hide_popup),
            (vim_widget.sig_input_finished, self.sync),
            (vim_widget.sig_command_changed, self.sync),
            (vim_widget.sig_command_cancelled, self.cancel),
        )
        for signal, slot in self._connections:
            signal.connect(slot)
        self.apply_settings()

    def apply_settings(self):
        """Read preferences once on initialization or configuration apply."""
        if self._closed:
            return False
        enabled = bool(CONF.get(CONF_SECTION, "which_key_enabled", True))
        delay = max(0, min(2000, int(CONF.get(CONF_SECTION, "which_key_delay", 300))))
        if (enabled, delay) == (self.enabled, self.delay):
            return False
        self.cancel()
        self.enabled, self.delay = enabled, delay
        self.sync()
        return True

    def set_editor(self, editor):
        """Release the previous viewport before following the selected editor."""
        if self._closed:
            return
        if editor is not None and widget_is_deleted(editor):
            editor = None
        viewport = editor.viewport() if editor is not None else None
        if viewport is live_widget(self._viewport):
            self._editor = weakref.ref(editor) if editor is not None else None
            return
        self.cancel()
        previous = live_widget(self._viewport)
        if previous is not None:
            previous.removeEventFilter(self)
            try:
                previous.destroyed.disconnect(self._viewport_destroyed)
            except (TypeError, RuntimeError):
                pass
        popup = self.popup
        self.popup = None
        if popup is not None and not widget_is_deleted(popup):
            popup.hide()
            popup.deleteLater()
        self._editor = weakref.ref(editor) if editor is not None else None
        self._viewport = weakref.ref(viewport) if viewport is not None else None
        if viewport is not None:
            viewport.installEventFilter(self)
            viewport.destroyed.connect(self._viewport_destroyed)

    def _viewport_destroyed(self, *args):
        self.cancel()
        self._editor = None
        self._viewport = None
        self.popup = None

    def _current_context(self):
        vim = live_widget(self._vim)
        if vim is None or not self.enabled or self._closed:
            return None
        pending = vim.pending_hint()
        if pending is None:
            return None
        commandline = vim.commandline
        editor = live_widget(self._editor)
        viewport = live_widget(self._viewport)
        if (
            widget_is_deleted(commandline)
            or not commandline.hasFocus()
            or not commandline.isActiveWindow()
            or editor is None
            or viewport is None
            or live_widget(pending.editor) is not editor
            or not viewport.isVisible()
            or editor.window() is not commandline.window()
        ):
            return None
        return pending

    def sync(self):
        """Schedule only a new, valid wait; repeated observations keep its delay."""
        if self._closed:
            return
        vim = live_widget(self._vim)
        if vim is None:
            self.cancel()
            return
        if vim.is_processing_input:
            return
        context = self._current_context()
        if context is None:
            self.cancel()
        elif context != self._context:
            self.cancel()
            self._context = context
            self.timer.start(self.delay)
        elif not self.timer.isActive():
            # A displayed panel is hidden while handling input. If the same
            # wait survives, it has already earned its delay.
            self._show_hints()

    def _hide_popup(self):
        """Hide stale rows without moving a pending deadline."""
        popup = self.popup
        if popup is not None and not widget_is_deleted(popup):
            popup.hide()

    def cancel(self):
        """Idempotently stop pending hints and hide an existing panel."""
        self.timer.stop()
        self._context = None
        self._hide_popup()

    def _show_hints(self):
        vim = live_widget(self._vim)
        if vim is None or vim.is_processing_input:
            self.cancel()
            return
        context = self._current_context()
        if context is None or context != self._context:
            self.cancel()
            return
        candidates = context.executor.get_hint_candidates()
        if not candidates:
            self.cancel()
            return
        viewport = live_widget(self._viewport)
        if self.popup is None or widget_is_deleted(self.popup):
            self.popup = WhichKeyPopup(viewport)
        self.popup.set_candidates(context.prefix, candidates)
        self.popup.refresh_appearance(vim.commandline.font())
        self.popup.update_geometry()
        self.popup.raise_()
        self.popup.show()

    def eventFilter(self, watched, event):
        if watched is live_widget(self._viewport):
            if event.type() in (QEvent.Hide, QEvent.Close, QEvent.WindowDeactivate):
                self.cancel()
            elif event.type() == QEvent.Resize:
                popup = self.popup
                if popup is not None and not widget_is_deleted(popup):
                    popup.update_geometry()
        return super().eventFilter(watched, event)

    def cleanup(self):
        """Disconnect the timer and detach viewport UI before plugin shutdown."""
        if self._closed:
            return
        self.cancel()
        self.set_editor(None)
        self.timer.timeout.disconnect(self._show_hints)
        for signal, slot in self._connections:
            signal.disconnect(slot)
        self._connections = ()
        self._closed = True
