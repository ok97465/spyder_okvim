"""Command-line input, immutable observations and applied navigation state.

This module owns QLineEdit/IME behavior and the prompt's history/Tab state.
Popup selection and preview rendering remain with their existing controllers.
"""

from __future__ import annotations

# Standard Libraries
import os
import os.path as osp
import re
import weakref
from dataclasses import dataclass

# Third Party Libraries
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QFocusEvent, QInputMethodEvent, QKeyEvent
from qtpy.QtWidgets import QApplication, QLineEdit, QStyle
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION, KEYCODE2STR
from spyder_okvim.utils.commandline import completion_items, substitute_field_candidates
from spyder_okvim.utils.commandline_history import (
    HISTORY_LIMIT,
    load_history,
    save_history,
)
from spyder_okvim.utils.ex_parser import ExError, is_substitute, scan_header
from spyder_okvim.utils.key_helpers import latin_command_key
from spyder_okvim.utils.qtcompat import (
    python_cursor_position,
    qt_cursor_position,
    text_width,
)


@dataclass(frozen=True)
class PromptSnapshot:
    """An input observation tied to an executor, using a Python cursor index.

    ``prompt`` includes a search count and direction when present. Composing
    or replacing snapshots are observations only and must not start passive
    completion or regex work. Applied Tab candidates stay with the widget.
    """

    session: object
    kind: str
    prompt: str
    text: str
    cursor: int
    is_composing: bool
    is_replacing: bool


class VimLineEdit(QLineEdit):
    """Own prompt drafts, history navigation, Tab cycling and native IME input.

    Display selection stays with the popup controller; this widget owns only
    candidates that have already been applied. Public cursor positions use
    Python string indexes and are converted at the QLineEdit boundary.
    """

    def __init__(self, vim_widget, vim_status, vim_shortcut):
        super().__init__(vim_widget)
        self.vim_widget = vim_widget
        self.vim_status = vim_status
        self.vim_shortcut = vim_shortcut
        self._history_file = osp.join(
            CONF.get_plugin_config_path(CONF_SECTION), "commandline_history.json"
        )
        self.histories = load_history(self._history_file)
        self._history_dirty = False
        self._history_index = None
        self._history_draft = None
        self._completion_candidates = ()
        self._completion_index = -1
        self._completion_directory = None
        self._updating_commandline = False
        self._is_composing = False
        self._prompt_focus_window = None
        self.textChanged.connect(self.reset_navigation)
        self.cursorPositionChanged.connect(self._reset_completion)

        # Set size
        tw = text_width(self.fontMetrics(), " :%s/international/internationl/g ")
        fw = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        self.setFixedWidth(tw + (2 * fw) + 4)

        # Todo: Move setting shortcut to config file.
        vim_shortcut.signal_cmd.connect(self.setText)
        self.dispatcher = {
            Qt.Key_A: vim_shortcut.add_num,
            Qt.Key_X: vim_shortcut.subtract_num,
            Qt.Key_D: vim_shortcut.pg_half_down,
            Qt.Key_F: vim_shortcut.pg_down,
            Qt.Key_U: vim_shortcut.pg_half_up,
            Qt.Key_B: vim_shortcut.pg_up,
            Qt.Key_R: vim_shortcut.redo,
            Qt.Key_P: vim_shortcut.open_file_search,
            Qt.Key_C: vim_shortcut.clear_tip_search,
            Qt.Key_O: vim_shortcut.jump_backward,
            Qt.Key_I: vim_shortcut.jump_forward,
            Qt.Key_W: vim_shortcut.window_command,
        }
        self.setAttribute(Qt.WA_InputMethodEnabled, False)

    def reset_navigation(self, text="") -> None:
        """Discard history drafts and applied Tab candidates after a real edit.

        ``text`` accepts the textChanged signal payload. Recalled/completed
        input is guarded by replace_input() and keeps its navigation state.
        """
        if not self._updating_commandline:
            self._history_index = None
            self._history_draft = None
            self._clear_completion()

    def _reset_completion(self, old_position, new_position) -> None:
        """A manually moved caret starts a new completion at that position."""
        if not self._updating_commandline:
            self._clear_completion()

    def _clear_completion(self):
        """Release the cached Tab candidates and their selected row together."""
        self._completion_candidates = ()
        self._completion_index = -1
        self._completion_directory = None

    @property
    def completion_result(self):
        """Expose the current Tab list without giving the popup its ownership."""
        if not self._completion_candidates:
            return None
        text = self.text()
        current = (text, python_cursor_position(text, self.cursorPosition()))
        candidate = self._completion_candidates[self._completion_index]
        if (
            current != (candidate.text, candidate.cursor_position)
            or self._completion_directory != os.getcwd()
        ):
            return None
        return self._completion_candidates, self._completion_index

    def history_context(self, text: str | None = None) -> tuple[str, str, str] | None:
        """Return (kind, prompt/count, body), or None outside an active prompt."""
        if text is None:
            text = self.text()
        kind = getattr(self.vim_status.sub_mode, "history_kind", None)
        if kind == "ex" and text.startswith(":"):
            return kind, ":", text[1:]
        if kind == "search":
            match = re.fullmatch(r"(\d*[/?])(.*)", text, re.DOTALL)
            if match:
                return kind, *match.groups()
        return None

    def snapshot(self) -> PromptSnapshot | None:
        """Return immutable prompt input, or None outside Ex/search entry.

        The cursor is a Python string index, not a Qt UTF-16 position. A
        snapshot can describe a transient replacement or IME composition;
        passive consumers must reject those states before scheduling work.
        """
        text = self.text()
        context = self.history_context(text)
        if context is None:
            return None
        kind, prompt, _ = context
        return PromptSnapshot(
            self.vim_status.sub_mode,
            kind,
            prompt,
            text,
            python_cursor_position(text, self.cursorPosition()),
            self._is_composing,
            self._updating_commandline,
        )

    def remember_command(self, text) -> None:
        """Skip single-character Ex entries and consecutive duplicates."""
        context = self.history_context(text)
        if context is None:
            return
        kind, _, body = context
        if not body or (kind == "ex" and len(body.strip()) <= 1):
            return
        history = self.histories[kind]
        if not history or history[-1] != body:
            history.append(body)
            del history[:-HISTORY_LIMIT]
            self._history_dirty = True
        if self._history_dirty:
            self._history_dirty = not save_history(self._history_file, self.histories)

    def replace_input(self, text: str, cursor_position: int | None = None) -> None:
        """Replace input without discarding its history or Tab navigation.

        ``cursor_position`` is a Python string index; None places the caret at
        the end. Qt signals may dispatch recursively inside the shared input
        guard, and observers must wait for its outer finished notification.
        """
        with self.vim_widget.input_processing():
            was_replacing = self._updating_commandline
            self._updating_commandline = True
            try:
                self.setText(text)
                if cursor_position is not None:
                    self.setCursorPosition(qt_cursor_position(text, cursor_position))
            finally:
                self._updating_commandline = was_replacing

    def browse_history(self, backward: bool) -> None:
        """Recall entries and restore the exact draft after the newest one."""
        context = self.history_context(self.text())
        if context is None:
            return
        self.vim_widget.commandline_popup.suppress_history()
        kind, prompt, _ = context
        history = self.histories[kind]
        self._clear_completion()
        if not history:
            return
        if self._history_index is None:
            if not backward:
                return
            self._history_draft = (
                self.text(),
                python_cursor_position(self.text(), self.cursorPosition()),
            )
            self._history_index = len(history)
        if backward:
            self._history_index = max(0, self._history_index - 1)
        else:
            self._history_index += 1
        if self._history_index >= len(history):
            self.replace_input(*self._history_draft)
            self._history_index = None
            self._history_draft = None
        else:
            self.replace_input(prompt + history[self._history_index])

    def _complete_commandline(self, backward=False) -> None:
        """Apply and cycle the original command, field, or explicit path query."""
        context = self.history_context(self.text())
        if context is None:
            return
        controller = self.vim_widget.commandline_popup
        if context[0] != "ex":
            controller.suppress_history()
            return
        controller.clear_candidates()
        working_directory = os.getcwd()
        completion = self.completion_result
        if completion is not None:
            candidates, _ = completion
            candidate = candidates[0]
            # A single directory starts a fresh lookup on the next explicit Tab.
            enter_directory = (
                len(candidates) == 1
                and candidate.apply_scope == "path"
                and candidate.text[: candidate.cursor_position].endswith(os.sep)
            )
            if not enter_directory:
                step = -1 if backward else 1
                self._completion_index = (self._completion_index + step) % len(
                    candidates
                )
                self._apply_completion_candidate()
                return

        self._clear_completion()
        text = self.text()
        cursor = python_cursor_position(text, self.cursorPosition())
        self._completion_directory = working_directory
        candidates = substitute_field_candidates(self.histories["ex"], text, cursor)
        if not candidates:
            commands = self.vim_status.sub_mode.SUPPORTED_COMMANDS
            if controller.complete_paths(
                text, cursor, commands, working_directory, backward
            ):
                return
            candidates = completion_items(text, cursor, commands, working_directory)
        self._completion_candidates = tuple(candidates)
        self._completion_index = len(candidates) - 1 if backward else 0
        self._apply_completion_candidate()

    def apply_path_completion(self, candidates, directory, index):
        """Start the original Tab cycle after a cached or worker lookup."""
        self.vim_widget.commandline_popup.clear_candidates()
        self._completion_candidates = tuple(candidates)
        self._completion_directory = directory
        self._completion_index = index % len(candidates) if candidates else 0
        self._apply_completion_candidate()

    def _apply_completion_candidate(self):
        if not self._completion_candidates:
            return
        candidate = self._completion_candidates[self._completion_index]
        self.replace_input(
            candidate.text,
            candidate.cursor_position,
        )

    def event(self, event) -> bool:
        """Keep Tab in the prompt instead of letting QWidget move focus."""
        if (
            event.type() == QEvent.ShortcutOverride
            and self.vim_widget.commandline_popup.key_action(event) is not None
        ):
            event.accept()
            return True
        if self.vim_status.substitute_confirm is not None:
            if event.type() == QEvent.ShortcutOverride:
                event.accept()
                return True
            if event.type() == QEvent.KeyPress:
                self.keyPressEvent(event)
                return True
        if (
            event.type() == QEvent.ShortcutOverride
            and event.modifiers() == Qt.ControlModifier
            and event.key() in (Qt.Key_P, Qt.Key_N)
            and self._yank_cycle_context()
            and self.vim_widget.put_controller.can_cycle()
        ):
            # Reserve a valid cycle without editing during ShortcutOverride.
            event.accept()
            return True
        if (
            event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Tab, Qt.Key_Backtab)
            and self.history_context(self.text()) is not None
        ):
            self.keyPressEvent(event)
            return True
        return super().event(event)

    def inputMethodQuery(self, query):
        """Report mode-specific IME availability to the native input context."""
        if query == Qt.ImEnabled:
            # Qt 6 QLineEdit reports ImEnabled independently of this attribute.
            return (
                self.testAttribute(Qt.WA_InputMethodEnabled)
                and self.isEnabled()
                and not self.isReadOnly()
            )
        return super().inputMethodQuery(query)

    def sync_input_method(self) -> None:
        """Allow composition only while entering search or Ex text."""
        enabled = bool(
            self.vim_status.sub_mode and self.vim_status.sub_mode.accepts_input_method
        )
        if enabled == self.testAttribute(Qt.WA_InputMethodEnabled):
            return
        # Disable delivery before resetting: some IMEs commit on reset.
        self.setAttribute(Qt.WA_InputMethodEnabled, enabled)
        if not enabled:
            self._is_composing = False
            if self.hasFocus():
                QApplication.inputMethod().reset()
            super().inputMethodEvent(QInputMethodEvent())

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:
        """Keep late IME commits from being interpreted as Normal commands."""
        if self.testAttribute(Qt.WA_InputMethodEnabled):
            with self.vim_widget.input_processing():
                self._is_composing = bool(event.preeditString())
                super().inputMethodEvent(event)
        else:
            event.ignore()

    @property
    def is_composing(self):
        """Whether the native input method still owns uncommitted text."""
        return self._is_composing

    def to_normal(self) -> None:
        """Convert the state of vim to normal mode."""
        self.clear()
        self.vim_widget.vim_status.to_normal()
        self.vim_widget.vim_status.cursor.draw_vim_cursor()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        """Dispatch one native key inside the outer input observation guard."""
        history_action = self.vim_widget.commandline_popup.key_action(e)
        with self.vim_widget.input_processing():
            self._handle_key_press(e, history_action)

    def _handle_key_press(self, e: QKeyEvent, history_action=None) -> None:
        """Process a key before synchronizing hints at the outer input boundary."""
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape):
            self.vim_widget.commandline_popup.cancel_pending_tab()
        if history_action is not None:
            self.vim_widget.commandline_popup.handle_key(history_action, e)
            return
        if not self.testAttribute(Qt.WA_InputMethodEnabled):
            e = latin_command_key(e)
        confirmation = self.vim_status.substitute_confirm
        if confirmation is not None:
            if e.key() == Qt.Key_Escape or (
                e.key() == Qt.Key_C and e.modifiers() == Qt.ControlModifier
            ):
                self.esc_pressed()
            elif e.modifiers() in (Qt.NoModifier, Qt.ShiftModifier):
                confirmation(e.text())
            self.clear()
            self.sync_input_method()
            e.accept()
            return
        self.vim_status.manager_macro.add_vim_keyevent(e)

        key = e.key()
        pressed_ctrl = e.modifiers() == Qt.ControlModifier
        if self.try_handle_yank_cycle(e):
            return
        if key == Qt.Key_Escape:
            self.esc_pressed()
        elif pressed_ctrl and key == Qt.Key_C and self._substitute_input():
            self.vim_shortcut.clear_tip_search()
            self.esc_pressed()
        elif pressed_ctrl and key in self.dispatcher:
            self.vim_widget.put_controller.cancel()
            self.dispatcher[key]()
        elif self.testAttribute(Qt.WA_InputMethodEnabled):
            if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Tab, Qt.Key_Backtab):
                QApplication.inputMethod().commit()
                if key in (Qt.Key_Up, Qt.Key_Down):
                    self.browse_history(key == Qt.Key_Up)
                else:
                    self._complete_commandline(
                        key == Qt.Key_Backtab or bool(e.modifiers() & Qt.ShiftModifier)
                    )
                e.accept()
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                # Flush the final composing syllable before executing the text.
                QApplication.inputMethod().commit()
                self.setText(self.text() + "\r")
            else:
                super().keyPressEvent(e)
        elif KEYCODE2STR.get(key, None):
            self.setText(self.text() + KEYCODE2STR[key])
        else:
            super().keyPressEvent(e)

    def _substitute_input(self):
        """Cancel substitute prompts with Ctrl+C even when preview is disabled."""
        if getattr(self.vim_status.sub_mode, "history_kind", None) != "ex":
            return False
        if not self.text().startswith(":"):
            return False
        try:
            return is_substitute(scan_header(self.text()[1:]).command)
        except ExError:
            return False

    def _yank_cycle_context(self):
        """Only plain Normal input and an optional positive count can cycle."""
        text = self.text()
        return (
            self.vim_status.is_normal()
            and self.vim_status.sub_mode is None
            and not self.vim_widget.has_yank_picker
            and (not text or re.fullmatch(r"[1-9][0-9]*", text) is not None)
        )

    def try_handle_yank_cycle(self, event):
        """Consume valid cycles, including endpoints, before the file search."""
        if event.modifiers() != Qt.ControlModifier or event.key() not in (
            Qt.Key_P,
            Qt.Key_N,
        ):
            return False
        in_cycle_context = self._yank_cycle_context()
        handled = in_cycle_context and self.vim_widget.put_controller.cycle(
            1 if event.key() == Qt.Key_P else -1,
            int(self.text()) if self.text() else 1,
        )
        if not handled:
            if not self.vim_widget.is_playing_macro:
                return False
            self.vim_status.set_message("Yanky: no put to cycle in this macro")
        if in_cycle_context:
            self.clear()
            self.vim_status.input_cmd.clear()
        event.accept()
        return True

    def esc_pressed(self) -> None:
        """Cancel pending input and return to Normal without undoing accepted edits."""
        self._prompt_focus_window = None
        self.vim_widget.cancel_substitute()
        self.vim_widget.put_controller.cancel()
        self.vim_widget.sig_command_cancelled.emit()
        self.vim_status.input_cmd.clear()
        self.vim_status.remove_marker_of_easymotion()
        sub_mode = self.vim_status.sub_mode
        if sub_mode:
            try:
                sub_mode.on_escape()
            finally:
                self.vim_status.sub_mode = None
                self.sync_input_method()
                self.clear()
        else:
            self.to_normal()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Override Qt method."""
        self.vim_status.disconnect_from_editor()
        super().focusInEvent(event)
        preserve_prompt = (
            self._prompt_focus_window is not None
            and self._prompt_focus_window() is self.window()
        )
        self._prompt_focus_window = None
        if preserve_prompt and self.history_context(self.text()) is not None:
            self.vim_widget.handle_prompt_event(QEvent.WindowActivate)
            self.vim_widget.sig_command_changed.emit()
            return
        if self.vim_widget.has_yank_picker:
            return
        if self.vim_status.cursor.get_editor():
            self.to_normal()
        self.vim_status.set_message("")
        self.vim_widget.sig_command_changed.emit()

    def transient_prompt_focus_loss(self, event: QFocusEvent) -> bool:
        """Keep an Ex draft across application deactivation or temporary hide."""
        context = self.history_context(self.text())
        return bool(
            context is not None
            and context[0] == "ex"
            and (event.reason() == Qt.ActiveWindowFocusReason or not self.isVisible())
        )

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Override Qt method."""
        if self.transient_prompt_focus_loss(event):
            if self._prompt_focus_window is None:
                self._prompt_focus_window = weakref.ref(self.window())
            self.vim_widget.handle_prompt_event(QEvent.WindowDeactivate)
            super().focusOutEvent(event)
            return
        self._prompt_focus_window = None
        self.vim_widget.cancel_substitute()
        if self.vim_widget.has_yank_picker:
            super().focusOutEvent(event)
            return
        self.vim_widget.put_controller.cancel()
        self.vim_widget.sig_command_cancelled.emit()
        if self.testAttribute(Qt.WA_InputMethodEnabled):
            self.esc_pressed()
        super().focusOutEvent(event)
        self.clear()
        try:
            self.vim_widget.vim_status.to_insert()
        except RuntimeError:
            # The status may already be deleted when closing widgets
            pass
