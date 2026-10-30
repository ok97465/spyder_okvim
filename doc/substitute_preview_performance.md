# Incremental substitution overlay measurements

The opt-in benchmark uses the real command input lifecycle, editor candidate
highlights and replacement overlay. It does not run in the ordinary test suite:

```sh
SPYDER_PYTEST=True QT_QPA_PLATFORM=offscreen \
QT_API=pyside6 PYTEST_QT_API=pyside6 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m pytest -s -q -p pytestqt.plugin \
  spyder_okvim/spyder/tests/benchmark_substitute_preview.py
```

Set `SPYDER_OKVIM_PREVIEW_SCREENSHOT=/tmp/overlay.png` to capture the editor.
The command prints JSON with calculation, publication and paint timings and
retained buffer sizes. Timing is informational; source preservation, absence of
a separate result panel, cancellation and stale-job cleanup are asserted. The
substitution guide keeps its default enabled setting and yields while replacement
results are drawn, leaving the editor preview unobscured.

## Environment and sample

Measured on 2026-10-30 using Apple M4, macOS 27.0.1 ARM64, Python 3.13.9,
PySide6 / Qt 6.8.3 and the offscreen Qt platform. The document contains 10,000
lines and 289,999 characters: `foo alpha beta foo gamma foo` on each line.
The main window is 900 × 600 pixels. These are single-run observations, not
latency guarantees. Editor construction and loading the document occur before the timers start. Paint totals include
repaints requested by the test and screenshot capture; their call counts are
reported separately from the synchronous publication step.

| Input | Schedule input | Ready, including debounce | Total scan | Longest scan tick | Highlight + overlay publication | Paint total (calls) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `:%s/foo/bar/g` | 2.96 ms | 177.80 ms | 6.80 ms | 0.61 ms | 17.18 ms | 5.17 ms (3) |
| `:%s/absent/bar/g` | 1.11 ms | 171.41 ms | 13.61 ms | 0.76 ms | 0.07 ms | 0.29 ms (1) |
| `:%s/foo/` + 10,000 `X` characters + `/g` | 6.93 ms | 190.81 ms | 11.68 ms | 1.59 ms | 7.92 ms | 0.19 ms (2) |

Dense matches stopped at 2,000 candidates after examining 667 lines. The result
retained 2,000 highlight spans and 39 changed paragraphs for the visible view
and its small buffer: 2,184 original/result characters in total. The source still
contained `foo`; the screenshot showed `bar` directly at those editor locations,
with replacement spans tinted and a **Partial preview** badge for the scan cap.
Line numbers, original line positions and command-line focus remained intact.

The absent pattern examined 5,000 lines and retained no spans or output text.
The large replacement retained no result paragraphs: its expansion budget was
reached while producing the first requested paragraph. Original source and
candidate highlights remained visible, with a partial-preview indicator.

Escape dispatched after the first scan chunk took 0.71 ms to handle. No second
chunk ran, both calculation timers stopped and no result remained after
cancellation.

## Internal limits and rendering behavior

The implementation uses a 150 ms single-shot debounce, an 8 ms scan-tick target
and at most 128 yield points per tick. Scan limits are 5,000 lines, 2,000 matches,
20,000 characters per line, 500,000 cumulative source characters and 16,000 command
characters. Output limits are 100 requested preview paragraphs, 20,000 retained
original/result characters and 20,000 replacement-expansion characters. These
bounds apply during calculation. Enter executes the existing unrestricted,
synchronous substitution path.

Requested visible paragraphs are visited before the remaining range. Scrolling
beyond cached coverage computes the new view, including positions beyond the
global scan cap. Horizontal scrolling and appearance changes redraw cached rows; newly exposed
paragraphs can request additional bounded results. Painting never runs a regular expression or expands a replacement.

The overlay occupies the original source paragraphs' heights and does not
reflow the actual document. A result requiring more width or wrapped lines is
clipped to that paragraph's source area and receives an ellipsis and partial
indicator. Omitted output leaves source text visible. No-op paragraphs need no
replacement overlay. This avoids shifting or covering following source lines.

The tick target is checked **between** regular-expression matches and lines.
Skipping very long lines and yielding between chunks improves ordinary input
and cancellation responsiveness, but cannot bound one pathological Qt regular
expression call. There is no forced regex timeout or worker process in this
version. Highlight publication and painting are separate bounded operations;
their measured costs are distinct from the scan-tick target.
