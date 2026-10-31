"""Recorded-key delivery and the lifetime of one queued macro playback.

The worker only emits captured key values. Its completion signal shares the
sender and queue with those keys; the GUI owner keeps playback active until
both queued delivery and recursive input handling have finished.
"""

from __future__ import annotations

# Standard Libraries
import sys
import threading
import weakref

# Third Party Libraries
from qtpy.QtCore import QObject, QThread, Signal, Slot

# Project Libraries
from spyder_okvim.utils.qtcompat import live_widget
from spyder_okvim.vim.state import InputSource, KeyInfo


class MacroPlaybackWorker(QThread):
    """Queue recorded key values without accessing any GUI editor objects."""

    sig_focus_vim = Signal(int)
    sig_send_key_info = Signal(object, int)
    sig_playback_finished = Signal(int)

    def __init__(self, parent: QObject | None) -> None:
        super().__init__(parent)
        self.key_infos = ()
        self.repeat_count = 0
        self.generation = 0

    def set_key_infos(self, key_infos: list[KeyInfo], count: int) -> None:
        """Capture keys for a new generation before starting the stopped worker."""
        self.generation += 1
        self.key_infos = tuple(key_infos)
        self.repeat_count = count

    def run(self) -> None:
        """Emit keys and completion in order; interruption discards remaining keys."""
        if "coverage" in sys.modules:
            sys.settrace(getattr(threading, "_trace_hook", None))
        generation = self.generation
        commandline_has_focus = True
        for _ in range(self.repeat_count):
            if self.isInterruptionRequested():
                return
            for key_info in self.key_infos:
                if self.isInterruptionRequested():
                    return
                if key_info.source == InputSource.EDITOR:
                    commandline_has_focus = False
                elif not commandline_has_focus:
                    commandline_has_focus = True
                    self.sig_focus_vim.emit(generation)
                self.sig_send_key_info.emit(key_info, generation)
        if not commandline_has_focus:
            self.sig_focus_vim.emit(generation)
        self.sig_playback_finished.emit(generation)


class MacroPlayback(QObject):
    """Own worker, target identity and deferred GUI completion for one widget.

    A generation is active after worker start and remains active through its
    last queued key. Cancellation invalidates already queued signals before
    interrupting the worker, so they cannot edit or focus a replacement view.
    All methods except the worker's run() execute on the GUI thread.
    """

    def __init__(self, vim_widget):
        super().__init__(vim_widget)
        self._vim = weakref.ref(vim_widget)
        self.generation = -1
        self.editor_ref = None
        self.completion_generation = None
        self._closed = False
        self.worker = MacroPlaybackWorker(self)
        self.worker.sig_send_key_info.connect(self.deliver_key)
        self.worker.sig_focus_vim.connect(self.focus_input)
        self.worker.sig_playback_finished.connect(self.finish)

    @property
    def is_active(self):
        """Whether this generation still owns worker or queued GUI input."""
        return self.generation >= 0

    def is_current(self, generation):
        """Reject old generations and editor changes, including deleted wrappers."""
        vim = live_widget(self._vim)
        editor = live_widget(self.editor_ref)
        return (
            not self._closed
            and vim is not None
            and generation == self.generation
            and editor is not None
            and editor is vim.vim_status.get_editor()
        )

    def start(self, key_infos, count):
        """Start a snapshot against the active editor, invalidating older delivery."""
        vim = live_widget(self._vim)
        if vim is None or self._closed:
            return
        self.generation = -1
        self.editor_ref = None
        self.completion_generation = None
        vim.put_controller.cancel()
        if self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait()
        self.worker.set_key_infos(key_infos, count)
        self.generation = self.worker.generation
        self.editor_ref = weakref.ref(vim.vim_status.get_editor())
        vim.sig_command_cancelled.emit()
        self.worker.start()

    def cancel(self):
        """Invalidate queued work before requesting interruption; keep edits made."""
        if self._closed:
            return
        self.generation = -1
        self.editor_ref = None
        self.completion_generation = None
        self.worker.requestInterruption()
        vim = live_widget(self._vim)
        if vim is not None:
            vim.put_controller.cancel()
            vim.sig_command_cancelled.emit()

    @Slot(int)
    def focus_input(self, generation):
        """Restore command-line focus only for the captured live editor."""
        if self.is_current(generation):
            live_widget(self._vim).commandline.setFocus()

    @Slot(int)
    def finish(self, generation):
        """Release playback after its queued keys and outer input guard finish."""
        if not self.is_current(generation):
            return
        vim = live_widget(self._vim)
        if vim.is_processing_input:
            self.completion_generation = generation
            return
        self.completion_generation = None
        self.generation = -1
        self.editor_ref = None
        vim.put_controller.cancel()
        vim.sig_command_changed.emit()

    def finish_pending(self):
        """Complete a generation deferred by nested input or event-loop reentry."""
        if self.completion_generation is not None:
            self.finish(self.completion_generation)

    @Slot(object, int)
    def deliver_key(self, key_info, generation=None):
        """Deliver one recorded key through the same GUI input guard as real keys."""
        if generation is not None and not self.is_current(generation):
            return
        vim = live_widget(self._vim)
        if vim is None or self._closed:
            return
        with vim.input_processing():
            event = key_info.to_event()
            if key_info.source == InputSource.COMMAND_LINE:
                vim.commandline.keyPressEvent(event)
            else:
                editor = vim.vim_status.get_editor()
                vim.vim_status.send_insert_event(editor, event)

    def cleanup(self):
        """Cancel queued work and wait only for the finite key-emitting worker."""
        if self._closed:
            return
        self.cancel()
        if self.worker.isRunning():
            self.worker.wait()
        self._closed = True
