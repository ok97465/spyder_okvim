# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""Spyder pane, shortcuts and the composition of OkVim input services.

Small presentation classes stay with the widget that assembles them. Prompt
input and queued macro playback have their own cohesive modules and lifetimes.
"""

from __future__ import annotations

# Standard Libraries
import os.path as osp
import re
import weakref
from contextlib import contextmanager

# Third Party Libraries
from qtpy.QtCore import QEvent, QObject, QSize, Qt, Signal, Slot
from qtpy.QtGui import QColor, QKeySequence, QPainter, QPalette, QTextCursor
from qtpy.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget
from spyder.api.config.decorators import on_conf_change
from spyder.api.plugins import Plugins
from spyder.api.widgets.main_widget import PluginMainWidget
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.executor import (
    ExecutorLeaderKey,
    NormalModeExecutor,
    VisualLineModeExecutor,
    VisualModeExecutor,
)
from spyder_okvim.executor.prefixes import WindowPrefixExecutor
from spyder_okvim.spyder.commandline_input import VimLineEdit
from spyder_okvim.spyder.commandline_popup_controller import (
    CommandlinePopupController,
)
from spyder_okvim.spyder.config import CONF_SECTION, KEYCODE2STR
from spyder_okvim.spyder.macro_playback import (
    MacroPlayback,
    MacroPlaybackWorker,
)
from spyder_okvim.spyder.substitute_preview import SubstitutePreviewController
from spyder_okvim.spyder.which_key import PendingHint, WhichKeyController
from spyder_okvim.utils.file_search import FileSearchDialog
from spyder_okvim.utils.put import PutController
from spyder_okvim.utils.qtcompat import (
    exec_dialog,
    text_width,
    widget_is_deleted,
)
from spyder_okvim.utils.testing_env import running_in_pytest
from spyder_okvim.utils.yank_dialog import YankHistoryPicker
from spyder_okvim.vim import InputCmdInfo, KeyInfo, VimState, VimStatus
from spyder_okvim.vim.state import InputSource


class VimPane(PluginMainWidget):
    """Invisible pane used to host the Vim command widget."""

    def __init__(self, name=None, plugin=None, parent=None):
        """Create the pane and its underlying Vim widget."""
        super().__init__(name, plugin, parent)
        layout = QHBoxLayout()
        layout.addWidget(QLabel("Please hide this pane."))
        self.setLayout(layout)

        self.main = parent
        self.vim_cmd = VimWidget(self.main.editor, self.main)

    def get_title(self):
        """Return the localized title for the pane."""
        return "Okvim"

    def get_focus_widget(self):
        """Return the widget that should receive focus."""
        return self.vim_cmd

    def setup(self):
        """Perform initial setup after the plugin is created."""
        pass

    def update_actions(self):
        """Update actions exposed by the plugin."""
        pass

    @on_conf_change
    def apply_plugin_settings(self, options):
        """Apply the config settings."""
        self.vim_cmd.apply_settings()


class VimShortcut(QObject):
    """Translate editor shortcuts into Vim commands and explicit host actions."""

    signal_cmd = Signal(str)

    def __init__(self, main, vim_status: VimStatus):
        super().__init__()
        self.main = main
        self.vim_status = vim_status
        self.get_editor = self.vim_status.get_editor
        self.cmd_line = None
        self.executor_window = WindowPrefixExecutor(vim_status)

    def _scroll(self, half: bool, up: bool) -> None:
        """Scroll the editor window.

        Args:
            half: If ``True`` scroll half the visible lines.
            up: Scroll up when ``True`` otherwise scroll down.
        """
        lines = self.vim_status.get_number_of_visible_lines()
        if half:
            lines //= 2
        if lines < 1:
            lines = 1

        command = "k" if up else "j"
        self.signal_cmd.emit(f"{lines}{command}")
        self.signal_cmd.emit("^")

    def pg_half_up(self):
        """Scroll half page up."""
        self._scroll(True, True)

    def pg_up(self):
        """Scroll one page up."""
        self._scroll(False, True)

    def pg_half_down(self):
        """Scroll half page down."""
        self._scroll(True, False)

    def pg_down(self):
        """Scroll one page down."""
        self._scroll(False, False)

    def _extract_number(self) -> tuple[int | None, int, int]:
        """Return the number under the cursor.

        Returns:
            tuple[int | None, int, int]: Extracted number and its start and end
            Qt UTF-16 positions. The end position is exclusive.
        """
        cursor = self.get_editor().textCursor()

        val = None
        block_start = cursor.block().position()
        block_end = block_start + cursor.block().length()
        pos_start = cursor.position()
        pos_end = pos_start

        for index_end in range(pos_start + 1, block_end):
            cursor.setPosition(pos_start)
            cursor.setPosition(index_end, QTextCursor.KeepAnchor)
            try:
                text_selected = cursor.selectedText()
                if text_selected == "-":
                    continue
                val_ = int(text_selected)
                if text_selected.isdigit() or text_selected[0] == "-":
                    val = val_
                    pos_end = index_end
                else:
                    break
            except ValueError:
                break

        for index_start in range(pos_start, block_start - 1, -1):
            cursor.setPosition(index_start)
            cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
            try:
                val_ = int(cursor.selectedText())
                text_selected = cursor.selectedText()
                if text_selected.isdigit() or text_selected[0] == "-":
                    val = val_
                    pos_start = index_start
                else:
                    break
            except ValueError:
                break

        return val, pos_start, pos_end

    def _change_number(self, delta: int, key: int) -> None:
        """Change the number at the cursor.

        Args:
            delta: Increment or decrement value.
            key: Qt key code used for dot command updates.
        """
        val, start, end = self._extract_number()
        if val is None:
            return
        if self.vim_status.sub_mode:
            self.cmd_line.esc_pressed()
            return

        count_text = self.cmd_line.text()
        count = 1 if not count_text else int(count_text)

        cursor = self.get_editor().textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.insertText(str(val + delta * count))
        self.signal_cmd.emit("h")

        cmd_info = InputCmdInfo(str(count), "")
        self.vim_status.input_cmd.set(cmd_info)
        key_info = KeyInfo(key, "", Qt.ControlModifier, source=InputSource.COMMAND_LINE)
        self.vim_status.update_dot_cmd(False, key_list_to_cmd_line=[key_info])

    def add_num(self) -> None:
        """Add to the number at the cursor."""
        self._change_number(1, Qt.Key_A)

    def subtract_num(self) -> None:
        """Subtract from the number at the cursor."""
        self._change_number(-1, Qt.Key_X)

    def redo(self) -> None:
        """Redo [count] changes which were undone."""
        if self.vim_status.sub_mode:
            self.cmd_line.esc_pressed()
            return

        if not self.vim_status.is_normal():
            return

        editor = self.vim_status.get_editor()
        n_block_old = editor.blockCount()

        count_text = self.cmd_line.text()
        count = 1 if not count_text else int(count_text)

        editor = self.get_editor()
        for _ in range(count):
            editor.redo()

        n_block_new = editor.blockCount()
        if n_block_new != n_block_old:
            if n_block_new > n_block_old:
                self.vim_status.set_message(f"{n_block_new - n_block_old} more lines")
            else:
                self.vim_status.set_message(f"{n_block_old - n_block_new} fewer lines")
        else:
            self.vim_status.set_message(f"{count} changes")

        self.cmd_line.esc_pressed()

    def open_file_search(self) -> None:
        """Open the file search dialog."""
        root_folder = self.main.projects.get_active_project_path()

        dlg = FileSearchDialog(root_folder, self.get_editor())
        exec_dialog(dlg)
        path = dlg.get_selected_path()

        if osp.isfile(path):
            self.vim_status.push_jump()
            application = self.main.get_plugin(Plugins.Application)
            application.open_file_in_plugin(path)
            self.vim_status.jump_list.push(path, 0)
        self.vim_status.set_focus_to_vim()

    def clear_tip_search(self) -> None:
        """Clear tooltip, search highlight."""
        self.get_editor().hide_tooltip()
        self.vim_status.search.clear_highlights()

    def jump_backward(self) -> None:
        """Jump to previous location in the jumplist."""
        if self.vim_status.sub_mode:
            self.cmd_line.esc_pressed()
            return
        self.vim_status.jump_backward()
        self.vim_status.set_focus_to_vim()

    def jump_forward(self) -> None:
        """Jump to next location in the jumplist."""
        if self.vim_status.sub_mode:
            self.cmd_line.esc_pressed()
            return
        self.vim_status.jump_forward()
        self.vim_status.set_focus_to_vim()

    def window_command(self) -> None:
        """Wait for an editor split command after Ctrl+w."""
        if self.vim_status.sub_mode:
            self.cmd_line.esc_pressed()
            return
        if not self.vim_status.is_normal():
            return
        count_text = self.cmd_line.text()
        self.vim_status.input_cmd.set(InputCmdInfo(count_text, "<C-w>"))
        self.executor_window.parent_counts = [int(count_text) if count_text else 1]
        self.vim_status.sub_mode = self.executor_window
        self.cmd_line.clear()


class VimStateLabel(QLabel):
    """Display state of vim."""

    def __init__(self, parent):
        super().__init__(parent)
        self._applying_appearance = False
        self.setObjectName("vimStateLabel")
        self.setAccessibleName("Vim mode")
        self.setAlignment(Qt.AlignCenter)
        self.change_state(VimState.INSERT)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

    @Slot(int)
    def change_state(self, state):
        """Display the state of vim."""
        if widget_is_deleted(self):
            return
        self._state = state
        text = {
            VimState.VISUAL: "VISUAL",
            VimState.NORMAL: "NORMAL",
            VimState.VLINE: "V-LINE",
            VimState.INSERT: "INSERT",
        }.get(state, "")
        self.setText(text)
        self.setAccessibleDescription(f"Current Vim mode: {text}")
        self.refresh_appearance()

    def refresh_appearance(self):
        """Keep mode text legible using the host palette or explicit overrides."""
        if self._applying_appearance:
            return
        self._applying_appearance = True
        try:
            self._apply_palette()
        finally:
            self._applying_appearance = False

    def _apply_palette(self):
        """Guard stylesheet-induced palette events during window reparenting."""
        palette = self.palette()
        colors = []
        for option, role in (
            ("mode_fg_color", QPalette.HighlightedText),
            ("mode_bg_color", QPalette.Highlight),
        ):
            configured = QColor(CONF.get(CONF_SECTION, option, ""))
            colors.append(configured if configured.isValid() else palette.color(role))
        foreground, background = (color.name() for color in colors)
        stylesheet = (
            "QLabel#vimStateLabel {"
            f"color: {foreground}; background-color: {background};"
            "border: 1px solid palette(mid); border-radius: 3px;"
            "padding: 1px 5px; font-weight: bold; }"
        )
        if stylesheet != self.styleSheet():
            self.setStyleSheet(stylesheet)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.PaletteChange, QEvent.ApplicationPaletteChange):
            self.refresh_appearance()


class VimMessageLabel(QLabel):
    """Show bounded plain status text while retaining the full accessible message."""

    def __init__(self, parent):
        super().__init__("", parent)
        self.setTextFormat(Qt.PlainText)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setAccessibleName("Vim status message")
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)

    def setText(self, text):
        super().setText(text)
        self.setToolTip(text)
        self.setAccessibleDescription(text)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(min(hint.width(), text_width(self.fontMetrics(), "M" * 30)))
        return hint

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, event):
        painter = QPainter(self)
        text = self.fontMetrics().elidedText(
            self.text(), Qt.ElideRight, self.contentsRect().width()
        )
        self.style().drawItemText(
            painter,
            self.contentsRect(),
            self.alignment(),
            self.palette(),
            self.isEnabled(),
            text,
            QPalette.WindowText,
        )


class VimWidget(QWidget):
    """Own command dispatch and report its stable input boundaries."""

    sig_input_started = Signal()
    sig_input_finished = Signal()
    sig_command_changed = Signal()
    sig_command_cancelled = Signal()

    def __init__(self, editor_widget, main):
        super().__init__(main)
        self.editor_widget = editor_widget
        self.main = main
        self._input_depth = 0
        self._closed = False
        self._yank_picker = None
        self.status_label = VimStateLabel(main)
        self.msg_label = VimMessageLabel(main)

        self.vim_status = VimStatus(
            editor_widget,
            main,
            self.msg_label,
        )
        self.sig_command_cancelled.connect(self.vim_status.input_cancelled.emit)
        self.put_controller = PutController(self.vim_status)
        self.vim_status.put_controller = self.put_controller
        self.vim_status.change_label.connect(self.status_label.change_state)

        self.vim_shortcut = VimShortcut(self.main, self.vim_status)

        self.commandline = VimLineEdit(self, self.vim_status, self.vim_shortcut)
        self.commandline.textChanged.connect(self.on_text_changed)

        self.vim_status.cmd_line = self.commandline
        self.vim_shortcut.cmd_line = self.commandline

        self.executor_normal_cmd = NormalModeExecutor(self.vim_status)
        self.executor_visual_cmd = VisualModeExecutor(self.vim_status)
        self.executor_vline_cmd = VisualLineModeExecutor(self.vim_status)
        self.executors = {
            VimState.NORMAL: self.executor_normal_cmd,
            VimState.VISUAL: self.executor_visual_cmd,
            VimState.VLINE: self.executor_vline_cmd,
        }

        # leader key
        self.executor_leader_key = ExecutorLeaderKey(self.vim_status)
        self.leader_key = " "

        self.macro_playback = MacroPlayback(self)
        # Public worker alias retained for callers that wait for shutdown.
        self.worker_macro = self.macro_playback.worker
        self.which_key = WhichKeyController(self)
        self.commandline_popup = CommandlinePopupController(self)
        self.substitute_preview = SubstitutePreviewController(self)
        self.substitute_preview.sig_result_ready.connect(self.commandline_popup.sync)
        self.vim_status.cancel_pending_input = lambda: self.cancel_pending_input()
        self.vim_status.cancel_macro = lambda: self.cancel_macro()
        self.vim_status.is_playing_macro = lambda: self.is_playing_macro
        self.vim_status.show_yank_history = lambda: self.show_yank_history()
        self.vim_status.clear_yank_history = lambda: self.clear_yank_history()
        self.apply_settings()

    @property
    def is_processing_input(self):
        """Whether recursive input dispatch still has unfinished work."""
        return self._input_depth > 0

    @property
    def is_playing_macro(self):
        """Whether a macro still has queued GUI input to finish."""
        return self.macro_playback.is_active

    def pending_hint(self):
        """Expose a stable prefix wait independently of the display controller."""
        status = self.vim_status
        executor = status.sub_mode
        if (
            self.is_processing_input
            or self.is_playing_macro
            or status.running_dot_cmd
            or status.vim_state not in self.executors
            or executor is None
            or executor.hint_prefix is None
        ):
            return None
        editor = status.get_editor()
        if editor is None or widget_is_deleted(editor):
            return None
        return PendingHint(
            weakref.ref(editor), executor, status.vim_state, executor.hint_prefix
        )

    def apply_settings(self):
        """Apply command bindings and hint preferences explicitly."""
        status = self.vim_status
        status.refresh_settings()
        self.set_leader_key()
        self.which_key.apply_settings()
        self.commandline_popup.apply_settings()
        self.substitute_preview.apply_settings()
        enabled = bool(CONF.get(CONF_SECTION, "yanky_enabled", True))
        length = CONF.get(CONF_SECTION, "yank_history_length", 100)
        if not isinstance(length, int) or isinstance(length, bool) or length < 1:
            length = 100
        if enabled != status.yanky_enabled or length != status.yank_history.length:
            self.cancel_yank_picker()
            self.put_controller.cancel()
        status.yanky_enabled = enabled
        status.yank_history.resize(length)
        status.cursor.apply_settings(status.settings)
        status.search.apply_settings(status.settings)
        self.status_label.refresh_appearance()

    @property
    def has_yank_picker(self):
        """Whether an active history request still owns popup focus restoration."""
        return self._yank_picker is not None

    def is_current_yank_picker(self, picker):
        """Validate a picker callback without exposing the owning field."""
        return self._yank_picker is picker

    def bind_editor(self, editor):
        """Bind view observers together after the host selects an editor stack.

        Cancel requests against the old view before installing observers on a
        replacement. Rebinding the same editor preserves its active prompt.
        Passing None releases the view without retaining deleted Qt wrappers.
        """
        if self._closed:
            return
        if editor is not self.put_controller.editor:
            self.cancel_pending_input()
        self.which_key.set_editor(editor)
        self.substitute_preview.set_editor(editor)
        self.commandline_popup.set_editor(editor)
        self.put_controller.bind_editor(editor)

    def finish_yank_picker(self, picker):
        """Release only the request that completed, preserving a newer picker."""
        if self.is_current_yank_picker(picker):
            self._yank_picker = None

    def handle_prompt_event(self, event_type, *, transient_focus_loss=False):
        """Apply prompt visibility policy at the shared input/view owner.

        Hiding or deactivating retains the Ex draft and preview origin. A
        permanent focus loss or close discards preview requests; accepted
        replacements remain in the document. Repeated events are harmless.
        """
        if self._closed or not hasattr(self, "substitute_preview"):
            return
        if event_type in (QEvent.Hide, QEvent.WindowDeactivate):
            self.substitute_preview.suspend()
        elif event_type in (QEvent.Close, QEvent.FocusOut):
            if transient_focus_loss:
                self.substitute_preview.suspend()
            else:
                self.substitute_preview.cancel()
        elif event_type in (QEvent.Show, QEvent.WindowActivate):
            self.substitute_preview.resume()

    def cancel_pending_input(self):
        """Cancel view-owned pending work while leaving text and mode to the caller."""
        self.substitute_preview.cancel()
        self.cancel_substitute()
        self.cancel_yank_picker()
        self.put_controller.cancel()
        self.cancel_macro()

    def clear_yank_history(self):
        """Clear memory explicitly, including while Yanky is disabled."""
        self.cancel_yank_picker()
        self.put_controller.cancel()
        self.vim_status.yank_history.clear()
        self.vim_status.set_message("Yanky: history cleared")

    def cancel_yank_picker(self):
        """Invalidate callbacks before closing a popup that may delete itself."""
        picker, self._yank_picker = self._yank_picker, None
        if picker is not None:
            picker.cancel()

    def cancel_substitute(self):
        """End a pending confirmation without undoing accepted replacements."""
        confirmation = self.vim_status.substitute_confirm
        if confirmation is not None:
            confirmation.cancel()

    def show_yank_history(self):
        """Pick one immutable history entry against a captured editor context."""
        status = self.vim_status
        self.cancel_yank_picker()
        self.put_controller.cancel()
        if not status.yanky_enabled:
            status.set_message("Yanky is disabled")
            return
        if self.is_playing_macro or status.is_recording_macro():
            status.set_message("Yanky: history picker is unavailable in macros")
            return
        editor = status.get_editor()
        if editor is None or widget_is_deleted(editor) or editor.isReadOnly():
            return
        entries = status.yank_history.snapshot()
        if not entries:
            status.set_message("Yanky: history is empty")
            return
        self.put_controller.bind_editor(editor)
        self._yank_picker = YankHistoryPicker(
            self,
            editor,
            entries,
            is_current=self.is_current_yank_picker,
            on_finished=self.finish_yank_picker,
        )
        self._yank_picker.show()

    @contextmanager
    def input_processing(self):
        """Synchronize hints once, after recursive command processing finishes."""
        self._input_depth += 1
        if self._input_depth == 1:
            self.sig_input_started.emit()
        try:
            yield
        except BaseException:
            self.put_controller.cancel()
            raise
        finally:
            self._input_depth -= 1
            if self._input_depth == 0:
                self.macro_playback.finish_pending()
                self.sig_input_finished.emit()

    def cancel_macro(self) -> None:
        """Invalidate queued playback when its editor is left or closed."""
        self.macro_playback.cancel()

    def send_key_event(self, key_info: KeyInfo, generation=None) -> None:
        """Replay a recorded key on the GUI thread through the input guard."""
        self.macro_playback.deliver_key(key_info, generation)

    def set_leader_key(self) -> None:
        """Set leader key from CONF."""
        leader_key = CONF.get(CONF_SECTION, "leader_key")
        key_sequence = QKeySequence.fromString(leader_key)
        try:
            key = key_sequence[0]
        except (IndexError, TypeError):
            key = None
        if hasattr(key, "key"):
            # PySide6 returns QKeyCombination objects; extract the raw key.
            key = key.key()
        command_key = KEYCODE2STR.get(key)
        if command_key:
            leader_key = command_key
        changed = self.leader_key != leader_key
        self.leader_key = leader_key
        self.executor_leader_key.set_easymotion_key(leader_key)
        if changed:
            self.sig_command_changed.emit()

    def on_text_changed(self, text: str) -> None:
        """Dispatch visible command text within one stable input observation boundary."""
        with self.input_processing():
            self._process_text(text)

    def _process_text(self, text: str) -> None:
        """Run existing executors while recursive clears stay inside the guard."""
        if not text:
            sub_mode = self.vim_status.sub_mode
            if sub_mode and sub_mode.accepts_input_method:
                self.commandline.esc_pressed()
            self.commandline.sync_input_method()
            return

        confirmation = self.vim_status.substitute_confirm
        if confirmation is not None:
            confirmation(text)
            self.commandline.clear()
            self.commandline.sync_input_method()
            return

        if not (
            self.vim_status.is_normal()
            and self.vim_status.sub_mode is None
            and re.fullmatch(r"[1-9][0-9]*", text)
        ):
            self.put_controller.cancel()

        executor = self.executors[self.vim_status.vim_state]
        if self.vim_status.sub_mode:
            executor = self.vim_status.sub_mode

        # workaround for easymotion (press leader, leader)
        if text == self.leader_key and executor != self.executor_leader_key:
            sub_mode = self.vim_status.sub_mode
            if sub_mode and sub_mode.allow_leaderkey is False:
                pass
            else:
                self.executor_leader_key.prev_executor = executor
                self.vim_status.sub_mode = self.executor_leader_key
                self.commandline.clear()
                return

        if text.endswith("\r"):
            self.substitute_preview.cancel()
            self.commandline.remember_command(text[:-1])
        if executor(text):
            self.commandline.clear()

        # Visual ':' captures rows before leaving Visual mode. Install its
        # executor first: setText emits textChanged synchronously and otherwise
        # re-enters the previous executor with the numeric range.
        sub_mode = self.vim_status.sub_mode
        if sub_mode is not executor and getattr(sub_mode, "history_kind", None) == "ex":
            sub_mode.begin_input()
            self.substitute_preview.begin_session(sub_mode)
        pending_range = getattr(sub_mode, "pending_range_text", None)
        if pending_range is not None:
            sub_mode.pending_range_text = None
            self.commandline.setText(pending_range)

        self.commandline.sync_input_method()

        if self.vim_status.manager_macro.reg_name_for_execute:
            self.put_controller.cancel()
            macro_manager = self.vim_status.manager_macro
            register = macro_manager.reg_name_for_execute
            self.macro_playback.start(
                macro_manager.registers[register], macro_manager.num_execute
            )
            macro_manager.set_info_for_execute("", 0)

    def cleanup(self) -> None:
        """Clean up resources used by the widget."""
        if self._closed:
            return
        self._closed = True
        self.vim_status.cancel_pending_work()
        self.substitute_preview.cleanup()
        self.put_controller.cleanup()
        self.which_key.cleanup()
        self.commandline_popup.cleanup()
        if self.vim_status.is_recording_macro():
            self.vim_status.stop_recording_macro()
        self.vim_status.search.close()
        try:
            self.vim_status.change_label.disconnect(self.status_label.change_state)
        except Exception:
            pass
        self.macro_playback.cleanup()
        if running_in_pytest():
            self.worker_macro.deleteLater()
            self.commandline.deleteLater()
            self.status_label.deleteLater()
            self.msg_label.deleteLater()


# Historical public imports retained after implementation extraction.
__all__ = [
    "VimPane",
    "VimShortcut",
    "VimStateLabel",
    "VimLineEdit",
    "VimWidget",
    "MacroPlaybackWorker",
]
