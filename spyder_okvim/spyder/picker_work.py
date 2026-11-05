"""Application-owned bounded worker lanes for picker values and filesystem I/O."""

from __future__ import annotations

import logging
from threading import Event

from qtpy.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from qtpy.QtWidgets import QApplication


logger = logging.getLogger(__name__)


class _Task(QRunnable):
    def __init__(self, lane, token, operation, finished):
        super().__init__()
        self.lane = lane
        self.token = token
        self.operation = operation
        self.cancelled = Event()
        self.finished = finished

    def run(self):
        try:
            result = self.operation(self.cancelled.is_set)
        except Exception as error:
            logger.exception("Picker %s failed", self.lane)
            result = error
        try:
            self.finished(self, result)
        except RuntimeError:
            pass


class PickerWorkService(QObject):
    """One active and one latest pending task per lane, across popup sessions.

    Submitted operations capture values and services, never editors or dialogs.
    Cancellation does not free an active slot before its filesystem call exits.
    """

    completed = Signal(str, object, object)
    _finished = Signal(object, object)
    LANES = ("collect", "search", "content")

    def __init__(self):
        application = QApplication.instance()
        super().__init__(application)
        self.active = dict.fromkeys(self.LANES)
        self.pending = dict.fromkeys(self.LANES)
        self.closed = False
        self._finished.connect(self._finish, Qt.QueuedConnection)
        application.aboutToQuit.connect(self.close)

    def submit(self, lane, token, operation):
        if self.closed:
            return
        self.cancel(lane)
        self.pending[lane] = _Task(lane, token, operation, self._finished.emit)
        self._start(lane)

    def _start(self, lane):
        if self.closed or self.active[lane] is not None:
            return
        task, self.pending[lane] = self.pending[lane], None
        if task is not None:
            self.active[lane] = task
            QThreadPool.globalInstance().start(task)

    def _finish(self, task, result):
        lane = task.lane
        if task is not self.active[lane]:
            return
        self.active[lane] = None
        if not self.closed and not task.cancelled.is_set():
            self.completed.emit(lane, task.token, result)
        if self.closed:
            if not any(self.active.values()):
                self.deleteLater()
        else:
            self._start(lane)

    def cancel(self, lane=None):
        for name in (self.LANES if lane is None else (lane,)):
            self.pending[name] = None
            if self.active[name] is not None:
                self.active[name].cancelled.set()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.cancel()
        if not any(self.active.values()):
            self.deleteLater()
