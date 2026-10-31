"""Opt-in measurements; invoke this filename explicitly with pytest -s."""

# ruff: noqa: F811 - imported pytest fixtures are injected by parameter name

# Standard Libraries
import json
import os
import platform
from time import perf_counter

# Third Party Libraries
from qtpy import API_NAME
from qtpy.QtCore import Qt, QTimer, qVersion

# Project Libraries
from spyder_okvim.utils.substitute_preview import SubstitutePreview
from tests.commandline_support import (
    enter_command,
)
from tests.commandline_support import history_popup as history_popup
from tests.commandline_support import preview as preview


def test_measure_preview(preview, monkeypatch, request):
    state = preview
    previous_size = state.main.size()
    request.addfinalizer(lambda: state.main.resize(previous_size))
    state.main.resize(900, 600)
    state.editor.set_text("\n".join(["foo alpha beta foo gamma foo"] * 10000))
    state.preview._timer.setInterval(150)
    step_times, publish_times, paint_times = [], [], []
    original_step = SubstitutePreview.step
    original_show = state.preview._show
    original_paint = state.preview.overlay._paint
    cancel_after_chunk = False
    cancel_times = []

    def cancel_input():
        started = perf_counter()
        state.qtbot.keyPress(state.line, Qt.Key_Escape)
        cancel_times.append((perf_counter() - started) * 1000)

    def step(job, *args, **kwargs):
        nonlocal cancel_after_chunk
        started = perf_counter()
        done = original_step(job, *args, **kwargs)
        step_times.append((perf_counter() - started) * 1000)
        if cancel_after_chunk:
            cancel_after_chunk = False
            QTimer.singleShot(0, cancel_input)
        return done

    def publish(*args, **kwargs):
        started = perf_counter()
        original_show(*args, **kwargs)
        publish_times.append((perf_counter() - started) * 1000)

    def paint(*args, **kwargs):
        started = perf_counter()
        original_paint(*args, **kwargs)
        paint_times.append((perf_counter() - started) * 1000)

    monkeypatch.setattr(state.preview.overlay, "_paint", paint)
    monkeypatch.setattr(SubstitutePreview, "step", step)
    monkeypatch.setattr(state.preview, "_show", publish)
    measurements = []
    for command in (
        ":%s/foo/bar/g",
        ":%s/absent/bar/g",
        ":%s/foo/" + "X" * 10000 + "/g",
    ):
        state.line.esc_pressed()
        step_times.clear()
        publish_times.clear()
        paint_times.clear()
        started = perf_counter()
        enter_command(state, command)
        input_ms = (perf_counter() - started) * 1000
        state.qtbot.waitUntil(lambda: state.preview.result is not None, timeout=5000)
        latency_ms = (perf_counter() - started) * 1000
        value = state.preview.result
        if state.preview.overlay.widget is not None:
            state.preview.overlay.widget.grab()
        assert not hasattr(state.controller, "preview_popup")
        assert state.editor.toPlainText() == "\n".join(
            ["foo alpha beta foo gamma foo"] * 10000
        )
        screenshot = os.environ.get("SPYDER_OKVIM_PREVIEW_SCREENSHOT")
        if screenshot and command == ":%s/foo/bar/g":
            state.main.grab().save(screenshot)
        measurements.append(
            dict(
                command="large replacement" if len(command) > 100 else command,
                input_ms=round(input_ms, 3),
                result_latency_ms=round(latency_ms, 3),
                scan_ms=round(sum(step_times), 3),
                max_tick_ms=round(max(step_times), 3),
                publication_ms=round(sum(publish_times), 3),
                paint_ms=round(sum(paint_times), 3),
                paint_calls=len(paint_times),
                chunks=len(step_times),
                candidates=value.match_count,
                scanned_lines=value.scanned_lines,
                highlights=len(value.spans),
                rows=len(value.rows),
                output_chars=sum(
                    len(row.before) + len(row.after) for row in value.rows
                ),
                output_truncated=value.output_truncated,
                partial=value.partial,
                reasons=value.reasons,
            )
        )
    state.line.esc_pressed()
    step_times.clear()
    cancel_after_chunk = True
    enter_command(state, ":%s/absent/bar/g")
    state.qtbot.waitUntil(lambda: bool(cancel_times), timeout=5000)
    state.qtbot.wait(30)
    assert len(step_times) == 1
    assert state.preview.result is None
    assert state.preview._job is None
    assert not state.preview._chunk_timer.isActive()
    print(
        json.dumps(
            dict(
                environment=dict(
                    platform=platform.platform(),
                    python=platform.python_version(),
                    qt_api=API_NAME,
                    qt=qVersion(),
                ),
                document_lines=10000,
                document_chars=len(state.editor.toPlainText()),
                measurements=measurements,
                esc_handling_ms=round(cancel_times[0], 3),
                cancelled_after_chunks=len(step_times),
            ),
            indent=2,
        )
    )
