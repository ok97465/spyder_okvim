"""Show history or substitution guidance at stable command-line boundaries."""

# Standard Libraries
import weakref

# Third Party Libraries
from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtWidgets import QApplication
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.commandline_history import HistoryPopup, history_candidates
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.spyder.substitute_guide import SubstituteGuidePopup
from spyder_okvim.utils.ex_parser import (
    ExError,
    has_substitute_delimiter,
    scan_substitute_guide,
    scan_substitute_preview,
)
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted


class CommandlinePopupController(QObject):
    """Share prompt and editor lifetimes while keeping history selection local."""

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
        self.history_enabled = False
        self.guide_enabled = False
        self.preview_enabled = False
        self._layout_signature = None
        self.popup = None
        self.guide_popup = None
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
        vim_widget.commandline.installEventFilter(self)
        self.apply_settings()

    def apply_settings(self):
        """Apply an explicit preference change, including immediate dismissal."""
        if self._closed:
            return
        history = bool(CONF.get(CONF_SECTION, "commandline_history_enabled", True))
        guide = bool(CONF.get(CONF_SECTION, "substitute_guide_enabled", True))
        preview = bool(CONF.get(CONF_SECTION, "substitute_preview_enabled", True))
        if (history, guide, preview) != (
            self.history_enabled,
            self.guide_enabled,
            self.preview_enabled,
        ):
            self.history_enabled, self.guide_enabled, self.preview_enabled = (
                history,
                guide,
                preview,
            )
            self._clear_candidates()
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
        for popup in self._popups():
            if popup is not None and not widget_is_deleted(popup):
                popup.deleteLater()
        self.popup = self.guide_popup = None
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
            vim = live_widget(self._vim)
            preview = (
                getattr(vim, "substitute_preview", None) if vim is not None else None
            )
            if preview is not None:
                preview.cancel()
        self._window = weakref.ref(window) if window is not None else None
        if window is not None:
            window.installEventFilter(self)

    def _viewport_destroyed(self, *args):
        self.cancel()
        self._set_window(None)
        self._editor = self._viewport = self._window = None
        self.popup = self.guide_popup = None

    def _popups(self):
        return self.popup, self.guide_popup

    def _hide(self):
        for popup in self._popups():
            if popup is not None and not widget_is_deleted(popup):
                popup.hide()

    def _clear_candidates(self):
        if self.popup is not None and not widget_is_deleted(self.popup):
            self.popup.hide()
            self.popup.select(None)
        self.candidates = []
        self.selected_index = None
        self._context = None

    def cancel(self):
        """Release all state when a prompt or its editor is left."""
        self._hide()
        self._clear_candidates()
        self._session = None
        self._suppressed = False
        self._layout_signature = None

    def suppress_history(self):
        """Keep recalled/completed text quiet until a real edit or new prompt."""
        self._suppressed = True
        self._clear_candidates()

    def _edited(self):
        self._suppressed = False
        self.selected_index = None
        self._context = None

    def _text_changed(self):
        self._hide()
        self._clear_candidates()
        self.sync()

    def _current_context(self, *, history=False):
        """Read an interactive prompt, optionally requiring history selection."""
        vim = live_widget(self._vim)
        editor = live_widget(self._editor)
        viewport = live_widget(self._viewport)
        if vim is None or self._closed or (history and not self.history_enabled):
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
        if (
            history
            and line.cursorPosition() != len(line.text().encode("utf-16-le")) // 2
        ):
            return None
        return status.sub_mode, *context

    def _layout_guide(self):
        """Refit changed guidance without retaining closed Qt widgets."""
        viewport = live_widget(self._viewport)
        popup = self.guide_popup
        if (
            viewport is None
            or popup is None
            or widget_is_deleted(popup)
            or not popup.isVisible()
        ):
            return
        signature = (
            viewport.width(),
            viewport.height(),
            id(popup),
            popup._content,
            popup.font().toString(),
            popup.styleSheet(),
        )
        if signature == self._layout_signature:
            return
        self._layout_signature = signature
        popup.update_geometry()

    def sync(self):
        """Show guidance before considering selectable history."""
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
        if context is None:
            self._hide()
            self._clear_candidates()
            return
        guide_shown = False
        preview = getattr(vim, "substitute_preview", None)
        preview_prompt = self.preview_enabled and has_substitute_delimiter(line.text())
        showing_overlay = False
        if preview_prompt and preview is not None:
            try:
                command = scan_substitute_preview(
                    line.text()[: preview.limits.max_command_chars],
                    vim.vim_status.last_substitute,
                )
            except ExError:
                command = None
            # Keep field help out of the way while previewing replacement text.
            showing_overlay = preview.has_overlay or (
                command is not None
                and command.pattern_closed
                and "n" not in command.spec.flags
            )
        if self.guide_enabled and context[1] == "ex":
            # QLineEdit counts UTF-16 code units; the parser uses Python indices.
            cursor = len(
                line.text()
                .encode("utf-16-le")[: line.cursorPosition() * 2]
                .decode("utf-16-le", errors="ignore")
            )
            guide = scan_substitute_guide(
                line.text(), cursor, vim.vim_status.last_substitute
            )
            if guide is not None and guide.stage == "replacement":
                self._hide()
                self._clear_candidates()
                return
            # Options must remain discoverable after the final delimiter, even
            # while the replacement preview is pending or already displayed.
            if guide is not None and (
                not showing_overlay or guide.stage in ("flags", "count", "unsupported")
            ):
                self._clear_candidates()
                if self.guide_popup is None or widget_is_deleted(self.guide_popup):
                    self.guide_popup = SubstituteGuidePopup(live_widget(self._viewport))
                self.guide_popup.set_context(guide)
                self.guide_popup.refresh_appearance(line.font())
                self.guide_popup.raise_()
                self.guide_popup.show()
                guide_shown = True
        if (
            not guide_shown
            and self.guide_popup is not None
            and not widget_is_deleted(self.guide_popup)
        ):
            self.guide_popup.hide()
        if guide_shown or preview_prompt:
            self._clear_candidates()
            self._layout_guide()
            return
        if (
            not self.history_enabled
            or self._suppressed
            or line.cursorPosition() != len(line.text().encode("utf-16-le")) // 2
        ):
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
            or (
                self.preview_enabled
                and has_substitute_delimiter(vim.commandline.text())
            )
            or not self.candidates
            or self.popup is None
            or widget_is_deleted(self.popup)
            or not self.popup.isVisible()
            or self._current_context(history=True) != self._context
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
            or self._current_context(history=True) != self._context
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
        if self._current_context(history=True) != context:
            self._clear_candidates()
            return
        self.suppress_history()
        line._reset_navigation()
        _, _, prompt, _ = context
        line._replace_commandline(prompt + candidate)

    def eventFilter(self, watched, event):
        vim = live_widget(self._vim)
        preview = getattr(vim, "substitute_preview", None) if vim is not None else None
        event_type = event.type()
        if event_type in (QEvent.Hide, QEvent.WindowDeactivate):
            self._hide()
            self._clear_candidates()
            if preview is not None:
                preview.suspend()
        elif event_type == QEvent.Close or (
            event_type == QEvent.FocusOut
            and vim is not None
            and watched is vim.commandline
        ):
            self.cancel()
            if preview is not None:
                if (
                    event_type == QEvent.FocusOut
                    and vim.commandline._transient_prompt_focus_loss(event)
                ):
                    preview.suspend()
                else:
                    preview.cancel()
        elif watched is live_widget(self._viewport) and event_type == QEvent.Wheel:
            # The passive guide forwards only wheels within its own bounds.
            popup = self.guide_popup
            if (
                popup is not None
                and not widget_is_deleted(popup)
                and popup.isVisible()
                and popup.geometry().contains(event.position().toPoint())
            ):
                scrollbar = popup.scroll_area.verticalScrollBar()
                if scrollbar.maximum() > scrollbar.minimum():
                    scrollbar.event(event)
                    event.accept()
                    return True
        elif watched is live_widget(self._viewport) and event_type == QEvent.Resize:
            if self.popup is not None and not widget_is_deleted(self.popup):
                self.popup.update_geometry()
            self._layout_guide()
        elif event_type in (
            QEvent.Show,
            QEvent.WindowActivate,
            QEvent.FontChange,
            QEvent.PaletteChange,
            QEvent.StyleChange,
        ):
            self.sync()
            if preview is not None and event_type in (
                QEvent.Show,
                QEvent.WindowActivate,
            ):
                preview.resume()
        return super().eventFilter(watched, event)

    def cleanup(self):
        """Disconnect observers and dispose of the viewport child on shutdown."""
        if self._closed:
            return
        self.set_editor(None)
        vim = live_widget(self._vim)
        if vim is not None and not widget_is_deleted(vim.commandline):
            vim.commandline.removeEventFilter(self)
        for signal, slot in self._connections:
            signal.disconnect(slot)
        self._connections = ()
        self._closed = True
