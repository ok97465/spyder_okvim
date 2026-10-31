"""Bounded background path lookups, independent of input-widget lifetime."""

from __future__ import annotations

# Standard Libraries
import logging
from dataclasses import dataclass
from threading import Event

# Third Party Libraries
from qtpy.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from qtpy.QtWidgets import QApplication

# Project Libraries
from spyder_okvim.utils.commandline import PathCompletionRequest, path_completion_items


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _LookupJob:
    generation: int
    request: PathCompletionRequest
    cancelled: Event


class _PathLookupTask(QRunnable):
    """Read immutable request data and emit a result without reading widgets."""

    def __init__(self, job, finished):
        super().__init__()
        self._job = job
        self._finished = finished

    def run(self):
        job = self._job
        try:
            candidates = path_completion_items(job.request, job.cancelled.is_set)
        except Exception:
            # Always release the active slot, including unexpected backend
            # failures; an exception must not strand the latest pending input.
            logger.exception("Path completion lookup failed")
            candidates = []
        try:
            self._finished(job, candidates)
        except RuntimeError:
            # QApplication may already have destroyed the service at shutdown.
            # The pool still owns this runnable until its filesystem call ends.
            pass


class PathLookupService(QObject):
    """Keep one running lookup and one replaceable latest pending request.

    The application owns this object so a blocked filesystem call cannot retain
    an input widget or deliver into a destroyed controller. Cancellation is
    cooperative between entries; it cannot interrupt an individual I/O call.
    """

    completed = Signal(int, object)
    _finished = Signal(object, object)

    def __init__(self):
        application = QApplication.instance()
        if application is None:
            raise RuntimeError("PathLookupService requires a QApplication")
        super().__init__(application)
        self._pool = QThreadPool.globalInstance()
        self._active_job = None
        self._pending_job = None
        self._closed = False
        self._finished.connect(self._finish, Qt.QueuedConnection)
        application.aboutToQuit.connect(self.close)

    @property
    def busy(self):
        """Whether active I/O or a queued latest request still needs handling."""
        return self._active_job is not None or self._pending_job is not None

    def submit(self, generation, request):
        """Cancel older work and retain only this latest request."""
        if self._closed:
            return
        self._pending_job = _LookupJob(generation, request, Event())
        if self._active_job is not None:
            self._active_job.cancelled.set()
        else:
            self._start_pending()

    def _start_pending(self):
        if self._closed or self._active_job is not None or self._pending_job is None:
            return
        job = self._pending_job
        self._pending_job = None
        self._active_job = job
        self._pool.start(_PathLookupTask(job, self._finished.emit))

    @Slot(object, object)
    def _finish(self, job, candidates):
        """Receive worker results on the GUI thread before notifying clients."""
        if job is not self._active_job:
            return
        self._active_job = None
        if not self._closed and not job.cancelled.is_set():
            self.completed.emit(job.generation, candidates)
        if self._closed:
            self.deleteLater()
        else:
            self._start_pending()

    def cancel(self):
        """Discard pending input without waiting for active filesystem I/O."""
        self._pending_job = None
        if self._active_job is not None:
            self._active_job.cancelled.set()

    @Slot()
    def close(self):
        """Release clients immediately; delete after an active task returns."""
        if self._closed:
            return
        self._closed = True
        self.cancel()
        if self._active_job is None:
            self.deleteLater()
