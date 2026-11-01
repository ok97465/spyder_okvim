# Substitution preview performance

Substitution preview performs bounded calculation before publishing candidate
highlights and an editor overlay. Its components are
[the calculator](../spyder_okvim/utils/substitute_preview.py),
[the controller](../spyder_okvim/spyder/substitute_preview.py) and
[the renderer](../spyder_okvim/spyder/substitute_overlay.py).

## Work budgets

`SubstitutePreviewController` debounces input for 150 ms and requests scan ticks
with an 8 ms target. `SubstitutePreview.step()` yields after at most 128 line or
match steps per tick. The time target is checked between those steps; one Qt
regular-expression call has no hard timeout.

The current `PreviewLimits` defaults bound each calculation:

| Budget | Limit |
| --- | ---: |
| Scanned lines / matches | 5,000 / 2,000 |
| Characters per source line / cumulative scanned source | 20,000 / 500,000 |
| Command characters | 16,000 |
| Requested preview paragraphs | 100 |
| Retained original and result characters | 20,000 combined |
| Replacement-expansion characters | 20,000 |

Visible paragraphs are visited first, with up to eight neighboring lines on
either side requested as a buffer. Scrolling outside cached coverage requests
another bounded calculation. Appearance changes and horizontal scrolling reuse
calculated results; painting does not run regular expressions or expand text.

The overlay preserves the source document and its layout. Output that exceeds a
source paragraph's available width or height is clipped and marked as partial;
omitted paragraphs retain their source text. Preview limits do not limit the
normal synchronous substitution executed by Enter.

## Run the benchmark

From the repository root, with the test dependencies installed:

```sh
SPYDER_PYTEST=True QT_QPA_PLATFORM=offscreen \
QT_API=pyside6 PYTEST_QT_API=pyside6 \
python -m pytest -q -s spyder_okvim/spyder/tests/benchmark_substitute_preview.py
```

Use `pyqt5` for both Qt variables to compare bindings. Set
`SPYDER_OKVIM_PREVIEW_SCREENSHOT=/tmp/overlay.png` to save an optional screenshot.
The opt-in benchmark uses the real input lifecycle and a 10,000-line document.
It measures dense matches, an absent pattern, a large replacement and Escape
cancellation after the first scan chunk. Editor construction and loading occur
before timing starts.

| JSON field | Interpretation |
| --- | --- |
| `input_ms`, `result_latency_ms` | Scheduling cost and time until a result, including debounce. |
| `scan_ms`, `max_tick_ms`, `chunks` | Calculation total, longest tick and number of chunks. |
| `publication_ms` | Candidate-highlight and overlay publication, separate from scan time. |
| `paint_ms`, `paint_calls` | Cumulative repaint cost and call count; screenshot capture can trigger extra paints. |
| `highlights`, `rows`, `output_chars`, `reasons` | Retained work and the budgets that caused a partial result. |
| `esc_handling_ms`, `cancelled_after_chunks` | Cancellation response and whether another chunk ran. |

Compare timings using the same document, viewport size and Qt backend. An 8 ms
scan target does not bound publication, paint or a single regex call. Keep the
JSON environment and paint counts alongside results. The benchmark asserts
source preservation and stale-job cleanup; timings are informational.

For regression checks, run
[`test_substitute_preview.py`](../spyder_okvim/utils/tests/test_substitute_preview.py)
for calculation budgets, plus the controller's
[`preview tests`](../spyder_okvim/spyder/tests/test_substitute_preview.py) and
[`overlay tests`](../spyder_okvim/spyder/tests/test_substitute_overlay.py)
for cancellation, view changes and rendering preservation.
