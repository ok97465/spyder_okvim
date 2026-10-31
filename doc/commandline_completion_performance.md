# Command-line path completion: implementation and measurements

Measured on 2026-10-31, macOS 27.0.1 arm64, Python 3.13.9, PyQt5 / Qt 5.15.2.

## Structure

`utils/commandline.py` keeps path parsing separate from directory enumeration.
`PathCompletionRequest` is immutable; the scanner only reads one directory and
filters file extensions without opening file contents. The extension allowlist
is `PATH_COMPLETION_EXTENSIONS`.

`CommandlinePopupController` owns the debounce timer, request generation, and
one completed-result cache. Its key includes the prompt session, editor,
complete input, Python cursor position, and working directory. An empty tuple
is a completed empty result; `None` means no completed lookup. Candidate reads
and key validation never enumerate directories.

`PathLookupService` runs filesystem work through `QThreadPool`. The application
owns the service, so it survives input-widget cleanup. It keeps at most one
running job and the latest pending job. Cancellation uses an event checked
between entries and around sorting. The worker reads immutable request data;
a queued QObject slot delivers its result on the GUI thread. This follows
[Qt's QObject and thread rules](https://doc.qt.io/qt-6/threads-qobject.html).

Automatic lookups wait 100ms after input settles. A missing Tab result uses the
same worker immediately and applies only if the original context is current.
Further pending Tab / Shift-Tab presses accumulate their direction and count.
Input changes, Enter, Esc, focus/session changes, and cleanup cancel application.
Once applied, the original cycle belongs to `VimLineEdit`; no automatic lookup
is scheduled for its replacement text. A single directory descends only on the
next explicit Tab. Accepting an `:e` directory with popup Enter instead clears
its old cycle and automatically queries children with no selected row. Existing
suffix separators are reused, including when the cursor is in an intermediate
component; file acceptance and history recall remain quiet until edited.
Completed empty Tab results are also reused for explicit-only
commands and while automatic suggestions are disabled.

When a timeout fires inside `input_processing()`, final-input synchronization
rearms it. When a worker result arrives there, the controller holds the result
until the outer input finishes and validates its generation/context again.
It does not repeat the lookup. `QTimer` only schedules submissions; it does not
perform filesystem work on the GUI thread. The timer remains in its owning
thread, as required by the [QTimer documentation](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QTimer.html).

## Reproduce

```sh
python -m pytest -q -s spyder_okvim/spyder/tests/benchmark_commandline_completion.py
```

The benchmark creates 100, 1,000, 10,000, and 30,000 entries, mixing supported
and excluded extensions with directories. It warms the listing and popup once,
then records seven repetitions. Directory enumeration and filter/build/sort
phases use a diagnostic pass over the same entries; their medians do not need
to sum exactly to the separately measured production scanner. Popup timing
includes controller merging, row replacement, and geometry; event processing
is measured separately. These are warm local-disk measurements, not guarantees.

| Entries | Candidates | Scan total | Enumeration | Filter/build | Sort | Popup sync | Events |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 60 | 0.113ms | 0.049ms | 0.053ms | 0.005ms | 0.265ms | 0.367ms |
| 1,000 | 600 | 1.010ms | 0.363ms | 0.509ms | 0.068ms | 1.809ms | 0.411ms |
| 10,000 | 6,000 | 10.899ms | 3.654ms | 5.242ms | 1.310ms | 17.596ms | 0.576ms |
| 30,000 | 18,000 | 32.874ms | 11.298ms | 16.192ms | 4.391ms | 52.326ms | 0.647ms |

Maximum scan times were 0.125ms, 1.080ms, 41.607ms, and 73.758ms respectively.
The configured debounce was 100ms; observed time until worker scan start was
96.193ms. Qt's default coarse timer may fire slightly early. Debounce latency
is separate from the scan and popup costs above.

The ordinary small-directory case is below the initial 16ms target. The
30,000-entry scanner repeatedly exceeded 30ms, so the final implementation
includes the conditional worker stage from `todo.md`. The scan-total column
measures the scanner's own work; production executes that work in the worker.

## Limits and verification

Popup construction remains GUI work: 18,000 suggestions took about 52ms to
publish. Moving enumeration to a worker does not remove that display cost.
A future large-list model can address it separately without changing the
path request/cache boundary. Network and external-volume paths were not measured in this environment;
slow I/O behavior was tested with controlled worker barriers.

An individual filesystem call cannot be interrupted. A blocked old lookup can
delay the newest queued lookup, even though input and cancellation remain
responsive. Cleanup disconnects result delivery and never waits for the pool.
The application owns the service until the active job returns; global-pool
shutdown may still wait for uninterruptible I/O. Tests cover queued replacement,
cooperative cancellation, thread affinity, cleanup while blocked, and actual
application quit in an isolated process with a controlled I/O release.

Integration tests also cover no-selection automatic display, two-Enter
acceptance, generation invalidation, IME/Unicode, nested event loops, settings,
working-directory changes, empty-cache reuse, and the existing Tab cycle.
