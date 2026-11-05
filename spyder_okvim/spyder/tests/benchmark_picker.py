"""Reproducible picker measurements; run as a module, outside the test suite.

QT_QPA_PLATFORM=offscreen python -m spyder_okvim.spyder.tests.benchmark_picker

Times are local warm-cache diagnostics, not native desktop interaction claims.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
from statistics import median
from tempfile import TemporaryDirectory
from threading import Event, Lock
from time import perf_counter, sleep
import tracemalloc

from spyder_okvim.spyder.picker_preview import (
    ContentService,
    from_text,
    locate,
    preview,
)
from spyder_okvim.utils.picker import (
    CandidateSnapshot,
    MAX_DISPLAY_RESULTS,
    PickerEntry,
    PickerTarget,
    search,
)


def summary(samples):
    ordered = sorted(samples)
    return {
        "p50_ms": round(median(ordered), 3),
        "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
    }


def dataset(count):
    return CandidateSnapshot(
        "files",
        "/project",
        1,
        tuple(
            PickerEntry(
                str(i),
                "files",
                f"file_{i}.py",
                f"src/package_{i % 100}",
                f"src/package_{i % 100}/file_{i}.py",
                i,
                PickerTarget(f"/project/src/package_{i % 100}/file_{i}.py"),
            )
            for i in range(count)
        ),
    )


def time_search(count, repetitions):
    tracemalloc.start()
    candidates = dataset(count)
    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    measurements = []
    for query in ("", "file1", "package99file9", "no-match"):
        search(candidates, query)  # Warm code paths and allocations.
        samples = []
        for _ in range(repetitions):
            started = perf_counter()
            result = search(candidates, query)
            samples.append((perf_counter() - started) * 1000)
        measurements.append(
            {
                "query": query,
                "matches": result.total_matches,
                "displayed": len(result.matches),
                **summary(samples),
            }
        )
    return {
        "candidates": count,
        "candidate_python_bytes": current_bytes,
        "candidate_build_peak_python_bytes": peak_bytes,
        "search": measurements,
    }


def time_adversarial(repetitions):
    candidates = CandidateSnapshot(
        "files",
        "/project",
        1,
        tuple(
            PickerEntry(str(index), "files", "a_b_" * 2048, ordinal=index)
            for index in range(100)
        ),
    )
    query = "ab" * 128
    samples = []
    for _ in range(repetitions):
        started = perf_counter()
        result = search(candidates, query)
        samples.append((perf_counter() - started) * 1000)
    return {
        "candidates": 100,
        "field_characters": 8192,
        "query_characters": 256,
        "matches": result.total_matches,
        **summary(samples),
    }


def time_content(repetitions):
    content = from_text("small line\n" * 90_000)
    target = PickerTarget("sample.py", offset_utf16=800_000)
    locate(content, target)  # Build the shared compact index once.
    locations, previews = [], []
    for _ in range(repetitions):
        started = perf_counter()
        for index in range(1000):
            locate(content, PickerTarget("sample.py", offset_utf16=index * 800))
        locations.append((perf_counter() - started) * 1000)
        started = perf_counter()
        display = preview(content, target)
        previews.append((perf_counter() - started) * 1000)
    service = ContentService()
    with TemporaryDirectory() as directory:
        for index in range(20):
            path = os.path.join(directory, f"sample-{index}.py")
            with open(path, "w") as stream:
                stream.write(content.text)
            service.read(path)
    return {
        "source_characters": len(content.text),
        "source_lines": 90_000,
        "locations_1000": summary(locations),
        "selected_preview": summary(previews),
        "displayed_characters": len(display.text),
        "displayed_lines": len(display.text.splitlines()),
        "cache_bytes_after_20_files": service.cache_bytes,
        "cache_limit_bytes": service.max_cache_bytes,
    }


def measure_workers(repetitions):
    # Import Qt only for this phase so pure tests need no QApplication.
    from qtpy import API_NAME
    from qtpy.QtCore import QTimer, qVersion
    from qtpy.QtWidgets import QApplication
    from spyder_okvim.spyder.picker_work import PickerWorkService

    application = QApplication.instance() or QApplication([])
    service = PickerWorkService()
    gate = Event()
    lock = Lock()
    actual_active = 0
    maximum_actual_active = 0
    completed = []
    service.completed.connect(lambda lane, token, result: completed.append(token))

    def blocked(cancel):
        nonlocal actual_active, maximum_actual_active
        with lock:
            actual_active += 1
            maximum_actual_active = max(actual_active, maximum_actual_active)
        gate.wait(5)
        with lock:
            actual_active -= 1
        return 0

    service.submit("collect", "old-session", blocked)
    active_task = service.active["collect"]
    maximum_active_slots = maximum_pending_slots = 0
    for session in range(100):
        service.cancel()  # Simulate closing the old popup.
        service.submit("collect", session, lambda cancel: "latest")
        maximum_active_slots = max(
            maximum_active_slots, int(service.active["collect"] is not None)
        )
        maximum_pending_slots = max(
            maximum_pending_slots, int(service.pending["collect"] is not None)
        )
        assert service.active["collect"] is active_task
    gate.set()
    deadline = perf_counter() + 5
    while completed != [99] and perf_counter() < deadline:
        application.processEvents()
        sleep(0.001)
    assert completed == [99]

    # Measure event-loop heartbeat gaps while the production worker searches.
    candidates = dataset(100_000)
    gaps = []
    last_tick = perf_counter()

    def tick():
        nonlocal last_tick
        now = perf_counter()
        gaps.append((now - last_tick) * 1000)
        last_tick = now

    timer = QTimer()
    timer.setInterval(1)
    timer.timeout.connect(tick)
    timer.start()
    for index in range(repetitions):
        token = f"search-{index}"
        service.submit(
            "search", token, lambda cancel: search(candidates, "file1", cancel)
        )
        deadline = perf_counter() + 5
        while token not in completed and perf_counter() < deadline:
            application.processEvents()
            sleep(0.001)
        assert token in completed
    timer.stop()
    service.close()
    application.processEvents()
    return {
        "qt_api": API_NAME,
        "qt_version": qVersion(),
        "close_reopen_requests": 100,
        "maximum_collect_active_slots": maximum_active_slots,
        "maximum_collect_pending_slots": maximum_pending_slots,
        "maximum_concurrent_blocked_operations": maximum_actual_active,
        "accepted_old_session_results": 0,
        "heartbeat_interval_ms": 1,
        "heartbeat_samples": len(gaps),
        "heartbeat_gap": summary(gaps),
        "heartbeat_max_gap_ms": round(max(gaps), 3),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=21)
    arguments = parser.parse_args()
    if arguments.repetitions < 1:
        parser.error("--repetitions must be positive")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    print(
        json.dumps(
            {
                "environment": {
                    "python": platform.python_version(),
                    "platform": platform.platform(),
                    "architecture": platform.machine(),
                    "qt_platform": os.environ["QT_QPA_PLATFORM"],
                },
                "repetitions": arguments.repetitions,
                "display_limit": MAX_DISPLAY_RESULTS,
                "datasets": [
                    time_search(count, arguments.repetitions)
                    for count in (10_000, 100_000)
                ],
                "adversarial_search": time_adversarial(arguments.repetitions),
                "content": time_content(arguments.repetitions),
                "workers": measure_workers(arguments.repetitions),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
