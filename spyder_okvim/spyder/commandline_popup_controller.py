"""Coordinate passive completion, history, and substitution guidance."""

from __future__ import annotations

# Standard Libraries
import os
import weakref
from dataclasses import dataclass, replace

# Third Party Libraries
from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtWidgets import QApplication
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.commandline_history import history_candidates
from spyder_okvim.spyder.commandline_popup import CommandlinePopupHost
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.commandline import (
    CompletionCandidate,
    command_candidates,
    merge_candidates,
    substitute_field_candidates,
)
from spyder_okvim.utils.ex_parser import scan_substitute_guide
from spyder_okvim.utils.qtcompat import (
    live_widget,
    python_cursor_position,
    qt_cursor_position,
    widget_is_deleted,
)


@dataclass(frozen=True)
class PromptContext:
    """Snapshot the input and executor that a reserved key is allowed to use."""

    session: object
    editor_id: int
    kind: str
    prompt: str
    text: str
    cursor: int
    directory: str | None = None


@dataclass(frozen=True)
class PopupAction:
    name: str
    context: PromptContext
    candidates: tuple
    selected_index: int | None


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
        self.completion_enabled = False
        self.history_enabled = False
        self.guide_enabled = False
        self.host = None
        self._selection_applied = False
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
        completion = bool(
            CONF.get(CONF_SECTION, "commandline_completion_enabled", True)
        )
        history = bool(CONF.get(CONF_SECTION, "commandline_history_enabled", True))
        guide = bool(CONF.get(CONF_SECTION, "substitute_guide_enabled", True))
        if (completion, history, guide) != (
            self.completion_enabled,
            self.history_enabled,
            self.guide_enabled,
        ):
            (
                self.completion_enabled,
                self.history_enabled,
                self.guide_enabled,
            ) = (
                completion,
                history,
                guide,
            )
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
        if self.host is not None and not widget_is_deleted(self.host):
            self.host.deleteLater()
        self.host = None
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
        self.host = None
        self.popup = self.guide_popup = None

    def _hide(self):
        if self.host is not None and not widget_is_deleted(self.host):
            self.host.hide()

    def clear_candidates(self):
        """Dismiss the pending selection before editing or cycling the input."""
        self._hide()
        if self.popup is not None and not widget_is_deleted(self.popup):
            self.popup.select(None)
        self.candidates = []
        self.selected_index = None
        self._selection_applied = False
        self._context = None

    def cancel(self):
        """Release all state when a prompt or its editor is left."""
        self.clear_candidates()
        self._session = None
        self._suppressed = False

    def suppress_history(self):
        """Keep recalled/completed text quiet until a real edit or new prompt."""
        self._suppressed = True
        self.clear_candidates()

    def _edited(self):
        self._suppressed = False
        self.selected_index = None
        self._context = None

    def _text_changed(self):
        self.clear_candidates()
        self.sync()

    def _current_context(self, *, directory=False):
        """Read the final interactive input without changing any command state."""
        vim = live_widget(self._vim)
        editor = live_widget(self._editor)
        viewport = live_widget(self._viewport)
        if vim is None or self._closed:
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
        history_context = line._history_context(line.text())
        if history_context is None:
            return None
        kind, prompt, _ = history_context
        return PromptContext(
            status.sub_mode,
            id(editor),
            kind,
            prompt,
            line.text(),
            python_cursor_position(line.text(), line.cursorPosition()),
            os.getcwd() if directory else None,
        )

    def _automatic_candidates(self, context):
        """Only command names and in-memory histories participate while typing."""
        if self._suppressed:
            return []
        vim = live_widget(self._vim)
        line = vim.commandline
        fields = []
        histories = []
        commands = []
        if self.history_enabled:
            if context.kind == "ex":
                fields = substitute_field_candidates(
                    line.histories["ex"], context.text, context.cursor
                )
            if context.cursor == len(context.text):
                body = context.text[len(context.prompt) :]
                for entry in history_candidates(line.histories[context.kind], body):
                    text = context.prompt + entry
                    histories.append(
                        CompletionCandidate(
                            "history",
                            entry,
                            "full command" if context.kind == "ex" else "full search",
                            text,
                            len(text),
                        )
                    )
        if self.completion_enabled and context.kind == "ex":
            commands = [
                CompletionCandidate("command", text, "command", text, cursor)
                for text, cursor in command_candidates(
                    context.text, context.cursor, context.session.SUPPORTED_COMMANDS
                )
            ]
        return merge_candidates(fields, histories, commands)

    def _ensure_host(self):
        if self.host is None or widget_is_deleted(self.host):
            self.host = CommandlinePopupHost(live_widget(self._viewport))
            self.popup = self.host.popup
            self.guide_popup = self.host.guide_popup

    def _candidate_list(self, context):
        """Prefer the line edit's cached Tab list over automatic suggestions."""
        vim = live_widget(self._vim)
        tab = vim.commandline.completion_result
        if tab is not None:
            return list(tab[0]) if self.completion_enabled else [], tab
        return self._automatic_candidates(context), None

    def sync(self):
        """Read context, decide both sections independently, then update the host."""
        vim = live_widget(self._vim)
        if self._closed or vim is None or vim.is_processing_input:
            return
        line = vim.commandline
        session = vim.vim_status.sub_mode
        editor = live_widget(self._editor)
        if editor is not None:
            self._set_window(editor.window())
        if session is not self._session:
            self.cancel()
            self._session = session
        context = self._current_context()
        if context is None:
            if line._history_context(line.text()) is None:
                self.cancel()
            else:
                self.clear_candidates()
            return

        guide = None
        if self.guide_enabled and context.kind == "ex":
            guide = scan_substitute_guide(
                context.text, context.cursor, vim.vim_status.last_substitute
            )
        candidates, tab = self._candidate_list(context)
        if any(candidate.apply_scope == "path" for candidate in candidates):
            context = replace(context, directory=os.getcwd())
        changed = context != self._context or candidates != self.candidates
        self._context = context
        self.candidates = candidates
        if changed:
            self.selected_index = tab[1] if tab is not None and candidates else None
            self._selection_applied = tab is not None
        if not candidates:
            self.selected_index = None
            self._selection_applied = False
        if not candidates and guide is None:
            self._hide()
            return
        self._ensure_host()
        if candidates:
            if changed:
                self.popup.set_candidates(candidates)
            appearance_changed = self.popup.refresh_appearance(line.font())
            if changed or appearance_changed:
                self.host.invalidate_geometry()
            self.popup.select(self.selected_index)
        if guide is not None:
            guide_changed = self.guide_popup.set_context(guide)
            appearance_changed = self.guide_popup.refresh_appearance(line.font())
            if guide_changed or appearance_changed:
                self.host.invalidate_geometry()
        self.host.show_sections(candidates=bool(candidates), guide=guide is not None)

    def key_action(self, event):
        """Use the same side-effect-free decision for reservation and dispatch."""
        vim = live_widget(self._vim)
        if (
            vim is None
            or vim.is_processing_input
            or not self.candidates
            or self.popup is None
            or widget_is_deleted(self.popup)
            or not self.popup.isVisible()
        ):
            return None
        name = None
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_N:
                name = "next"
            elif event.key() == Qt.Key_P:
                name = "previous"
        elif (
            event.key() in (Qt.Key_Return, Qt.Key_Enter)
            and event.modifiers() == Qt.NoModifier
            and self.selected_index is not None
            and not self._selection_applied
        ):
            name = "accept"
        if name is not None:
            return PopupAction(
                name, self._context, tuple(self.candidates), self.selected_index
            )
        return None

    def _action_is_current(self, action):
        if action.context is None:
            return False
        context = self._current_context(directory=action.context.directory is not None)
        if (
            context != action.context
            or tuple(self.candidates) != action.candidates
            or self.selected_index != action.selected_index
        ):
            return False
        # Input-start observers can update history without editing the prompt.
        candidates, _ = self._candidate_list(context)
        return tuple(candidates) == action.candidates

    def handle_key(self, action, event):
        """Consume reserved keys even if input-start observers made them stale."""
        if not self._action_is_current(action):
            self.clear_candidates()
        elif action.name == "accept":
            self._accept(action)
        else:
            step = 1 if action.name == "next" else -1
            if self.selected_index is None:
                self.selected_index = 0 if step == 1 else len(self.candidates) - 1
            else:
                self.selected_index = (self.selected_index + step) % len(
                    self.candidates
                )
            self._selection_applied = False
        event.accept()

    def _accept(self, action):
        vim = live_widget(self._vim)
        line = vim.commandline
        candidate = action.candidates[action.selected_index]
        # A native IME can synchronously change the context while committing.
        QApplication.inputMethod().commit()
        if not self._action_is_current(action):
            self.clear_candidates()
            return
        self.suppress_history()
        line._reset_navigation()
        line._replace_commandline(
            candidate.text,
            qt_cursor_position(candidate.text, candidate.cursor_position),
        )

    def eventFilter(self, watched, event):
        vim = live_widget(self._vim)
        preview = getattr(vim, "substitute_preview", None) if vim is not None else None
        event_type = event.type()
        if event_type in (QEvent.Hide, QEvent.WindowDeactivate):
            self.clear_candidates()
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
            if self.host is not None and self.host.forward_wheel(event):
                return True
        elif watched is live_widget(self._viewport) and event_type == QEvent.Resize:
            if self.host is not None and not widget_is_deleted(self.host):
                self.host.update_geometry()
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
