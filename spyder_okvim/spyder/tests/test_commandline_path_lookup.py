"""Background completion scheduling stays bounded and independent of widgets."""

# Standard Libraries
import os
import subprocess
import sys
import textwrap
from threading import Event, get_ident
from types import SimpleNamespace

import pytest
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication

from spyder_okvim.spyder import commandline_path_lookup
from spyder_okvim.spyder.commandline_path_lookup import PathLookupService
from spyder_okvim.utils.commandline import parse_path_completion


@pytest.fixture
def lookup(qtbot):
    service = PathLookupService()
    releases = []
    state = SimpleNamespace(service=service, releases=releases)
    try:
        yield state
    finally:
        for release in releases:
            release.set()
        service.close()
        qtbot.waitUntil(lambda: not service.busy, timeout=5000)


def request_for(tmp_path, prefix):
    text = ":e " + prefix
    return parse_path_completion(text, len(text), ("e",), str(tmp_path))


def test_running_lookup_keeps_only_latest_pending_request(
    lookup, qtbot, tmp_path, monkeypatch
):
    service = lookup.service
    started, release = Event(), Event()
    lookup.releases.append(release)
    calls, results, result_threads = [], [], []
    gui_thread = get_ident()

    def scan(request, cancelled):
        calls.append((request.prefix, get_ident()))
        if request.prefix == "first":
            started.set()
            assert release.wait(5)
        return [request.prefix]

    def completed(generation, candidates):
        results.append((generation, candidates))
        result_threads.append(get_ident())

    monkeypatch.setattr(commandline_path_lookup, "path_completion_items", scan)
    service.completed.connect(completed)
    service.submit(1, request_for(tmp_path, "first"))
    qtbot.waitUntil(started.is_set, timeout=5000)
    service.submit(2, request_for(tmp_path, "superseded"))
    service.submit(3, request_for(tmp_path, "latest"))
    qtbot.wait(10)
    assert service.busy
    assert [prefix for prefix, _ in calls] == ["first"]
    release.set()
    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    assert [prefix for prefix, _ in calls] == ["first", "latest"]
    assert results == [(3, ["latest"])]
    assert all(thread != gui_thread for _, thread in calls)
    assert result_threads == [gui_thread]
    assert not service.busy


def test_cancel_discards_late_result_and_pending_request(
    lookup, qtbot, tmp_path, monkeypatch
):
    service = lookup.service
    started, release = Event(), Event()
    lookup.releases.append(release)
    calls, results = [], []

    def scan(request, cancelled):
        calls.append(request.prefix)
        if request.prefix == "blocked":
            started.set()
            assert release.wait(5)
            assert cancelled()
        return [request.prefix]

    monkeypatch.setattr(commandline_path_lookup, "path_completion_items", scan)
    service.completed.connect(
        lambda generation, rows: results.append((generation, rows))
    )
    service.submit(1, request_for(tmp_path, "blocked"))
    qtbot.waitUntil(started.is_set, timeout=5000)
    service.submit(2, request_for(tmp_path, "pending"))
    service.cancel()
    release.set()
    qtbot.waitUntil(lambda: not service.busy, timeout=5000)
    assert calls == ["blocked"]
    assert results == []
    service.submit(3, request_for(tmp_path, "fresh"))
    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    assert results == [(3, ["fresh"])]


def test_close_keeps_service_alive_until_io_returns_without_blocking_gui(
    lookup, qtbot, tmp_path, monkeypatch
):
    service = lookup.service
    started, release = Event(), Event()
    lookup.releases.append(release)
    destroyed, delivered, gui_events = [], [], []

    def scan(request, cancelled):
        started.set()
        assert release.wait(5)
        return [request.prefix]

    monkeypatch.setattr(commandline_path_lookup, "path_completion_items", scan)
    service.completed.connect(lambda *args: delivered.append(args))
    service.destroyed.connect(lambda: destroyed.append(True))
    assert service.parent() is QApplication.instance()
    service.submit(1, request_for(tmp_path, "blocked"))
    qtbot.waitUntil(started.is_set, timeout=5000)
    service.close()
    QTimer.singleShot(0, lambda: gui_events.append(True))
    qtbot.waitUntil(lambda: bool(gui_events), timeout=5000)
    assert service.busy
    assert destroyed == []
    release.set()
    qtbot.waitUntil(lambda: bool(destroyed), timeout=5000)
    assert delivered == []
    assert not service.busy


def test_worker_failure_releases_active_slot(lookup, qtbot, tmp_path, monkeypatch):
    service = lookup.service
    results = []

    def scan(request, cancelled):
        if request.prefix == "bad":
            raise OSError("unavailable backend")
        return [request.prefix]

    monkeypatch.setattr(commandline_path_lookup, "path_completion_items", scan)
    service.completed.connect(
        lambda generation, rows: results.append((generation, rows))
    )
    service.submit(1, request_for(tmp_path, "bad"))
    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    assert results == [(1, [])]
    assert not service.busy
    service.submit(2, request_for(tmp_path, "good"))
    qtbot.waitUntil(lambda: len(results) == 2, timeout=5000)
    assert results[-1] == (2, ["good"])


def test_application_quit_cancels_running_io_without_waiting():
    """Exercise the actual quit signal without ending the shared test app."""
    script = textwrap.dedent(
        """
        from threading import Event
        from time import monotonic, sleep

        from qtpy.QtCore import QThreadPool, QTimer
        from qtpy.QtWidgets import QApplication

        from spyder_okvim.spyder import commandline_path_lookup
        from spyder_okvim.utils.commandline import parse_path_completion

        app = QApplication([])
        service = commandline_path_lookup.PathLookupService()
        started, release = Event(), Event()
        results = []

        def scan(request, cancelled):
            started.set()
            assert release.wait(5)
            assert cancelled()
            return []

        commandline_path_lookup.path_completion_items = scan
        service.completed.connect(lambda *args: results.append(args))
        request = parse_path_completion(':e ', 3, ('e',), '.')
        service.submit(1, request)
        assert started.wait(2)
        QTimer.singleShot(0, app.quit)
        execute = getattr(app, 'exec', None) or app.exec_
        execute()
        # Quit returns while I/O remains blocked. The app-owned service and
        # runnable remain alive until the cooperative cancellation can finish.
        assert service._closed
        assert service.busy
        assert service._active_job.cancelled.is_set()
        assert not release.is_set()
        release.set()
        deadline = monotonic() + 3
        while service.busy and monotonic() < deadline:
            app.processEvents()
            sleep(.001)
        assert not service.busy
        assert not results
        assert QThreadPool.globalInstance().waitForDone(2000)
        """
    )
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    completed = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
