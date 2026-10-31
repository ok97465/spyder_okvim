"""Opt-in path completion measurements: invoke this filename with pytest -s.

The diagnostic pass materializes the same DirEntry objects before feeding them
to the production scanner, isolating enumeration, filtering/building, and sort.
The unmodified production scan is timed separately. These are warm local-disk
measurements; they do not predict network or cold-cache filesystem latency.
"""

# ruff: noqa: F811 - imported pytest fixtures are injected by parameter name

# Standard Libraries
import json
import os
import platform
from contextlib import nullcontext
from statistics import median
from time import perf_counter

# Third Party Libraries
from qtpy import API_NAME
from qtpy.QtCore import QCoreApplication, qVersion

# Project Libraries
from spyder_okvim.spyder import commandline_path_lookup
from spyder_okvim.utils import commandline
from tests.commandline_support import history_popup as history_popup

REPETITIONS = 7


def _scan_times(request, monkeypatch):
    """Time production lookup, then isolate its phases using a saved listing."""
    started = perf_counter()
    candidates = commandline.path_completion_items(request)
    scan_ms = (perf_counter() - started) * 1000

    started = perf_counter()
    with os.scandir(request.directory) as stream:
        entries = list(stream)
    enumeration_ms = (perf_counter() - started) * 1000
    sort_ms = 0

    def timed_sorted(*args, **kwargs):
        nonlocal sort_ms
        started = perf_counter()
        result = sorted(*args, **kwargs)
        sort_ms += (perf_counter() - started) * 1000
        return result

    with monkeypatch.context() as isolated:
        isolated.setattr(os, "scandir", lambda directory: nullcontext(iter(entries)))
        isolated.setattr(commandline, "sorted", timed_sorted, raising=False)
        started = perf_counter()
        diagnostic = commandline.path_completion_items(request)
        filter_sort_ms = (perf_counter() - started) * 1000
    assert diagnostic == candidates
    return candidates, {
        "scan_total_ms": scan_ms,
        "enumeration_ms": enumeration_ms,
        "filter_build_ms": filter_sort_ms - sort_ms,
        "sort_ms": sort_ms,
    }


def _popup_times(state, candidates):
    """Publish a complete lookup through the controller, then process paint."""
    controller = state.controller
    controller._path_timer.stop()
    controller._path_context = controller._current_context(directory=True)
    controller._path_candidates = tuple(candidates)
    controller.clear_candidates()
    started = perf_counter()
    controller.sync()
    sync_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    QCoreApplication.processEvents()
    paint_ms = (perf_counter() - started) * 1000
    assert controller.candidates == candidates
    assert controller.popup.isVisible()
    assert controller.selected_index is None
    return {"popup_sync_ms": sync_ms, "event_processing_ms": paint_ms}


def test_measure_commandline_completion(history_popup, tmp_path, monkeypatch):
    state = history_popup
    measurements = []
    for entry_count in (100, 1000, 10000, 30000):
        directory = tmp_path / str(entry_count)
        directory.mkdir()
        # Descending names force a real sort. Mix supported and excluded files
        # with directories, preserving a high but realistic candidate ratio.
        for index in range(entry_count):
            name = "entry_{:05d}".format(entry_count - index)
            extension = (".py", ".json", ".toml", ".txt", ".pyc")[index % 5]
            path = directory / (name + extension)
            if index % 20 == 0:
                path.mkdir()
            else:
                path.touch()
        monkeypatch.chdir(directory)
        state.line.esc_pressed()
        state.line.setFocus()
        state.qtbot.keyClicks(state.line, ":e ")
        state.controller._path_timer.stop()
        request = commandline.parse_path_completion(":e ", 3, ("e",), str(directory))
        samples = []
        for repetition in range(REPETITIONS + 1):
            candidates, timings = _scan_times(request, monkeypatch)
            timings.update(_popup_times(state, candidates))
            if repetition:  # Exclude first listing and popup initialization.
                samples.append(timings)
        measurements.append(
            dict(
                entries=entry_count,
                candidates=len(candidates),
                median_ms={
                    key: round(median(sample[key] for sample in samples), 3)
                    for key in samples[0]
                },
                max_scan_total_ms=round(
                    max(sample["scan_total_ms"] for sample in samples), 3
                ),
            )
        )

    # Measure timer latency independently of enumeration and popup publication.
    state.line.esc_pressed()
    monkeypatch.chdir(tmp_path / "100")
    state.line.setFocus()
    scan_started = []
    original_lookup = commandline_path_lookup.path_completion_items

    def timed_lookup(request, cancelled=None):
        scan_started.append(perf_counter())
        return original_lookup(request, cancelled)

    monkeypatch.setattr(commandline_path_lookup, "path_completion_items", timed_lookup)
    state.qtbot.keyClicks(state.line, ":e ")
    input_finished = perf_counter()
    state.qtbot.waitUntil(lambda: bool(scan_started), timeout=5000)
    state.qtbot.waitUntil(lambda: not state.controller._path_lookup.busy, timeout=5000)
    print(
        json.dumps(
            dict(
                environment=dict(
                    platform=platform.platform(),
                    python=platform.python_version(),
                    qt_api=API_NAME,
                    qt=qVersion(),
                ),
                repetitions=REPETITIONS,
                configured_debounce_ms=state.controller.PATH_LOOKUP_DELAY_MS,
                observed_debounce_ms=round(
                    (scan_started[0] - input_finished) * 1000, 3
                ),
                measurements=measurements,
            ),
            indent=2,
        )
    )
