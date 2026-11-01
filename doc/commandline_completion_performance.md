# Path completion performance

Path lookup separates filesystem work from GUI publication. The relevant code is
[the scanner](../spyder_okvim/utils/commandline.py),
[the worker service](../spyder_okvim/spyder/commandline_path_lookup.py) and
[the popup controller](../spyder_okvim/spyder/commandline_popup_controller.py).

## Work and cancellation

- The scanner enumerates one directory, filters names and supported extensions,
  then sorts candidates. It does not open file contents. The extension allowlist
  is `PATH_COMPLETION_EXTENSIONS`.
- Automatic lookup has a 100 ms debounce. Explicit Tab submits immediately and
  reuses completed results, including an empty result. Candidate reads and
  request validation do not enumerate directories.
- `PathLookupService` keeps one active worker and the latest pending request.
  Workers receive immutable request data; queued delivery and popup updates run
  on the GUI thread.
- The controller validates the input session, editor, text, caret, working
  directory and generation before applying a result. Input or context changes
  discard stale work. Results arriving during input processing wait until that
  input has finished.
- Cancellation is cooperative between filesystem entries and around sorting.
  One blocked filesystem call can delay the next lookup. Widget cleanup
  disconnects delivery without waiting; application thread-pool shutdown can
  still wait for outstanding I/O.

The candidate list has no fixed size cap. Filtering in a worker keeps input
responsive during enumeration, but building and laying out a large popup still
costs GUI time. Measure scan and display separately when investigating latency.

## Run the benchmark

From the repository root, with the test dependencies installed:

```sh
SPYDER_PYTEST=True QT_QPA_PLATFORM=offscreen \
QT_API=pyside6 PYTEST_QT_API=pyside6 \
python -m pytest -q -s spyder_okvim/spyder/tests/benchmark_commandline_completion.py
```

Use `pyqt5` for both Qt variables to compare bindings. This opt-in benchmark
creates temporary directories with 100, 1,000, 10,000 and 30,000 entries. Each
mixes supported and excluded extensions with subdirectories. It warms each
listing and popup, then reports seven repetitions as JSON.

| JSON field | Interpretation |
| --- | --- |
| `scan_total_ms`, `max_scan_total_ms` | Production scanner cost and its slowest observed repetition. |
| `enumeration_ms`, `filter_build_ms`, `sort_ms` | Diagnostic phases measured separately over the same directory entries. Their medians need not sum to the production scan median. |
| `popup_sync_ms` | Controller merging, row publication and popup geometry on the GUI thread. |
| `event_processing_ms` | Event processing after publication, reported separately from synchronous popup work. |
| `observed_debounce_ms` | Input-to-worker-start delay, separate from scan and display costs. |

Compare runs with the same directory sizes, candidate counts, Qt binding and
platform. Warm local-disk results do not predict cold-cache or network I/O.
Record the emitted environment with measurements; avoid treating one machine's
latency as a fixed performance guarantee.

For correctness regressions, run
[`test_commandline_path_lookup.py`](../spyder_okvim/spyder/tests/test_commandline_path_lookup.py)
and [`test_commandline_completion.py`](../spyder_okvim/spyder/tests/test_commandline_completion.py).
These cover pending-request replacement, cancellation, blocked-I/O cleanup,
late delivery and Tab-cycle context checks.
