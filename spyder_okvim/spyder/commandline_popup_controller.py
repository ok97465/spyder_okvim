"""Coordinate passive completion, history, and substitution guidance."""

from __future__ import annotations

# Standard Libraries
import os
import weakref
from dataclasses import dataclass, replace

# Third Party Libraries
from qtpy.QtCore import QEvent, QObject, Qt, QTimer
from qtpy.QtWidgets import QApplication
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.commandline_history import history_candidates
from spyder_okvim.spyder.commandline_path_lookup import PathLookupService
from spyder_okvim.spyder.commandline_popup import CommandlinePopupHost
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.commandline import (
    CompletionCandidate,
    command_candidates,
    merge_candidates,
    parse_path_completion,
    substitute_field_candidates,
)
from spyder_okvim.utils.ex_parser import scan_substitute_guide
from spyder_okvim.utils.qtcompat import (
    live_widget,
    widget_is_deleted,
)


@dataclass(frozen=True)
class PromptContext:
    """Reserve input for one editor/executor; cursor uses Python string indexes."""

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


def _directory_completion_cursor(candidate):
    """Recognize a listed directory without querying the filesystem again."""
    if "path" not in candidate.source.split(", "):
        return None
    cursor = candidate.cursor_position
    separators = (os.sep,) if os.altsep is None else (os.sep, os.altsep)
    if candidate.text[:cursor].endswith(separators):
        return cursor
    # An intermediate component keeps its existing separator in the suffix.
    if candidate.text[cursor : cursor + 1] in separators:
        return cursor + 1
    return None


class CommandlinePopupController(QObject):
    """Share prompt and editor lifetimes while keeping history selection local."""

    PATH_LOOKUP_DELAY_MS = 100

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
        # Display selection and filesystem lookup have independent lifetimes.
        # None means unqueried; an empty tuple is a completed, empty lookup.
        self._path_context = None
        self._path_candidates = None
        self._path_generation = 0
        self._path_loading = False
        self._path_deferred = None
        self._pending_tab_index = None
        self._path_lookup = PathLookupService()
        self._path_lookup.completed.connect(self._paths_ready)
        self._path_request = None
        self._path_timer = QTimer(self)
        self._path_timer.setSingleShot(True)
        self._path_timer.setInterval(self.PATH_LOOKUP_DELAY_MS)
        self._path_timer.timeout.connect(self._load_paths)
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
        if completion != self.completion_enabled:
            self._invalidate_paths()
        if (completion, history, guide) != (
            self.completion_enabled,
            self.history_enabled,
            self.guide_enabled,
        ):
            self.completion_enabled = completion
            self.history_enabled = history
            self.guide_enabled = guide
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
            if vim is not None:
                vim.handle_prompt_event(QEvent.Close)
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
        self._invalidate_paths()
        self.clear_candidates()
        self._session = None
        self._suppressed = False

    def suppress_history(self):
        """Keep recalled/completed text quiet until a real edit or new prompt."""
        self._suppressed = True
        self._invalidate_paths()
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
        if widget_is_deleted(line):
            return None
        status = vim.vim_status
        snapshot = line.snapshot()
        if (
            snapshot is None
            or not line.hasFocus()
            or not line.isActiveWindow()
            or snapshot.is_composing
            or snapshot.is_replacing
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
        return PromptContext(
            snapshot.session,
            id(editor),
            snapshot.kind,
            snapshot.prompt,
            snapshot.text,
            snapshot.cursor,
            os.getcwd() if directory else None,
        )

    def _invalidate_paths(self):
        """Cancel pending work and reject callbacks from an earlier request."""
        self._path_timer.stop()
        self._path_generation += 1
        self._path_context = None
        self._path_request = None
        self._path_candidates = None
        self._path_loading = False
        self._path_deferred = None
        self._pending_tab_index = None
        self._path_lookup.cancel()

    @property
    def path_tab_pending(self):
        """Whether an explicit Tab is waiting for its path lookup."""
        return self._pending_tab_index is not None

    def cancel_pending_tab(self):
        """Enter and Escape cancel a delayed application before dispatch."""
        if self.path_tab_pending:
            self._invalidate_paths()

    def _schedule_paths(self, context, request):
        """Debounce a new lookup without restarting unchanged pending work."""
        if context != self._path_context:
            self._invalidate_paths()
            self._path_context = context
        if (
            self._path_candidates is not None
            or self._path_timer.isActive()
            or self._path_loading
        ):
            return
        self._path_request = request
        self._path_timer.start()

    def _load_paths(self):
        """Submit only a still-current final input to the filesystem worker."""
        vim = live_widget(self._vim)
        request = self._path_request
        if self._closed or vim is None or request is None:
            return
        # A nested event loop can deliver a single-shot timeout mid-input.
        # Leave this request unqueried; input-finished sync will rearm it.
        if vim.is_processing_input:
            return
        if self._path_context != self._current_context(directory=True):
            self._invalidate_paths()
            self.sync()
            return
        self._start_path_lookup(request)

    def _start_path_lookup(self, request):
        self._path_timer.stop()
        self._path_request = None
        if not self._path_loading:
            self._path_loading = True
            self._path_lookup.submit(self._path_generation, request)

    def _paths_ready(self, generation, candidates):
        """Keep worker results in memory until the outer input boundary."""
        vim = live_widget(self._vim)
        if self._closed or vim is None or generation != self._path_generation:
            return
        self._path_deferred = tuple(candidates)
        if not vim.is_processing_input:
            self.sync()

    def _finish_path_lookup(self, context):
        """Publish a valid result, optionally applying the requested Tab once."""
        if self._path_deferred is None:
            return False
        if replace(context, directory=os.getcwd()) != self._path_context:
            self._invalidate_paths()
            return False
        self._path_candidates = self._path_deferred
        self._path_deferred = None
        self._path_loading = False
        if self.path_tab_pending:
            self._apply_path_tab(
                self._path_context,
                self._path_generation,
                self._path_candidates,
                self._pending_tab_index,
            )
            return True
        return False

    def _apply_path_tab(self, context, generation, candidates, index):
        vim = live_widget(self._vim)
        with vim.input_processing():
            # Input-start observers can change or cancel the prompt before a
            # delayed Tab is applied. Recheck after that notification as well.
            current = self._current_context(directory=True)
            if generation != self._path_generation or context != current:
                self._invalidate_paths()
                return
            self._pending_tab_index = None
            vim.commandline.apply_path_completion(candidates, context.directory, index)

    def complete_paths(self, text, cursor, commands, directory, backward=False):
        """Apply a cached Tab result or queue its application without blocking."""
        request = parse_path_completion(text, cursor, commands, directory)
        if request is None:
            return False
        context = self._current_context(directory=True)
        if context is None:
            return True
        if context != self._path_context:
            self._invalidate_paths()
            self._path_context = context
        if self._path_candidates is not None:
            self._apply_path_tab(
                context,
                self._path_generation,
                self._path_candidates,
                -1 if backward else 0,
            )
        else:
            # Preserve all requested directions while one lookup is in flight.
            if self._pending_tab_index is None:
                self._pending_tab_index = -1 if backward else 0
            else:
                self._pending_tab_index += -1 if backward else 1
            self._start_path_lookup(request)
        return True

    def _sync_path_lookup(self, context):
        """Schedule only interactive :e arguments; keep candidate reads pure."""
        vim = live_widget(self._vim)
        if context.kind != "ex" or vim.commandline.completion_result is not None:
            self._invalidate_paths()
            return context
        directory = os.getcwd()
        path_context = replace(context, directory=directory)
        # Explicit Tab can also cache an empty lookup for other commands or
        # while suggestions are disabled/suppressed. Do not rescan that input.
        if path_context == self._path_context and (
            self._path_candidates is not None or self.path_tab_pending
        ):
            return path_context
        if not self.completion_enabled or self._suppressed:
            self._invalidate_paths()
            return context
        request = parse_path_completion(
            context.text, context.cursor, context.session.SUPPORTED_COMMANDS, directory
        )
        if request is None or request.command != "e" or request.explicit_range:
            self._invalidate_paths()
            return context
        self._schedule_paths(path_context, request)
        return path_context

    def _automatic_candidates(self, context):
        """Merge in-memory suggestions with a completed matching path lookup."""
        if self._suppressed:
            return []
        vim = live_widget(self._vim)
        line = vim.commandline
        candidates = []
        if self.history_enabled:
            if context.kind == "ex":
                candidates.extend(
                    substitute_field_candidates(
                        line.histories["ex"], context.text, context.cursor
                    )
                )
            if context.cursor == len(context.text):
                body = context.text[len(context.prompt) :]
                for entry in history_candidates(line.histories[context.kind], body):
                    text = context.prompt + entry
                    candidates.append(
                        CompletionCandidate(
                            "history",
                            entry,
                            "full command" if context.kind == "ex" else "full search",
                            text,
                            len(text),
                        )
                    )
        if self.completion_enabled and context.kind == "ex":
            candidates.extend(
                CompletionCandidate("command", text, "command", text, cursor)
                for text, cursor in command_candidates(
                    context.text, context.cursor, context.session.SUPPORTED_COMMANDS
                )
            )
            if context == self._path_context and self._path_candidates is not None:
                candidates.extend(self._path_candidates)
        return merge_candidates(candidates)

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
            self._invalidate_paths()
            if line.history_context() is None:
                self.cancel()
            else:
                self.clear_candidates()
            return

        if self._finish_path_lookup(context):
            return
        context = self._sync_path_lookup(context)
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
        directory_cursor = _directory_completion_cursor(candidate)
        request = (
            parse_path_completion(
                candidate.text,
                directory_cursor,
                action.context.session.SUPPORTED_COMMANDS,
                os.getcwd(),
            )
            if directory_cursor is not None
            else None
        )
        continue_path = (
            request is not None
            and request.command == "e"
            and not request.explicit_range
        )
        cursor = directory_cursor if continue_path else candidate.cursor_position
        self.suppress_history()
        line.reset_navigation()
        line.replace_input(
            candidate.text,
            cursor,
        )
        if continue_path:
            # Accepting a directory continues browsing; file acceptance and
            # recalled history retain their quiet-until-edited behavior.
            self._suppressed = False
            self.sync()

    def eventFilter(self, watched, event):
        vim = live_widget(self._vim)
        event_type = event.type()
        if event_type in (QEvent.Hide, QEvent.WindowDeactivate):
            self._invalidate_paths()
            self.clear_candidates()
            if vim is not None:
                vim.handle_prompt_event(event_type)
        elif event_type == QEvent.Close or (
            event_type == QEvent.FocusOut
            and vim is not None
            and watched is vim.commandline
        ):
            self.cancel()
            if vim is not None:
                vim.handle_prompt_event(
                    event_type,
                    transient_focus_loss=(
                        event_type == QEvent.FocusOut
                        and vim.commandline.transient_prompt_focus_loss(event)
                    ),
                )
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
            if vim is not None:
                vim.handle_prompt_event(event_type)
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
        self._path_lookup.completed.disconnect(self._paths_ready)
        self._path_lookup.close()
