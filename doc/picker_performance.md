# Picker performance measurements

Measured on 2026-11-05 with Python 3.13.9, macOS 27.0.1 arm64,
PyQt5 / Qt 5.15.2, and `QT_QPA_PLATFORM=offscreen`. Each timing uses 21
repetitions after warming the measured code path. p95 is the nearest-rank
95th percentile. These measurements cover the production sorter, content reader,
and worker service; they do not establish native macOS window, IME, or network
filesystem latency.

Reproduce from the repository root:

```sh
QT_QPA_PLATFORM=offscreen python -m spyder_okvim.spyder.tests.benchmark_picker
```

## Search

The synthetic candidates have paths such as `src/package_99/file_99999.py`.
Every query searches the complete immutable snapshot; at most 1,000 ranked rows
are returned for display. Candidate allocation is measured separately with
`tracemalloc`, which is disabled during timing.

| Candidates | Query | Matching candidates | p50 (ms) | p95 (ms) |
| ---: | --- | ---: | ---: | ---: |
| 10,000 | empty | 10,000 | 2.829 | 2.968 |
| 10,000 | `file1` | 3,439 | 10.123 | 10.311 |
| 10,000 | `package99file9` | 100 | 5.790 | 6.021 |
| 10,000 | `no-match` | 0 | 1.918 | 1.979 |
| 100,000 | empty | 100,000 | 18.721 | 19.027 |
| 100,000 | `file1` | 40,951 | 65.297 | 66.143 |
| 100,000 | `package99file9` | 1,000 | 57.954 | 60.724 |
| 100,000 | `no-match` | 0 | 18.755 | 19.492 |

The 10,000-candidate dataset retains 6,408,488 Python bytes, with a build peak
of 6,428,088 bytes. The 100,000-candidate dataset retains 64,517,984 bytes, with
a build peak of 64,646,704 bytes. The 32 MiB candidate-string collection limit
is a separate limit from total Python object memory.

The sorter uses a bounded heap rather than retaining all matches or query
results. Exact substring matches short-circuit repeated-character input;
nonempty queries and search fields have length limits. Cancellation is checked
at least every 64 candidates, within window refinement, and before publishing a
result. A cancelled search returns no selectable partial matches.

An adversarial field (`a_b_` repeated 2,048 times) and a 256-character query
(`ab` repeated 128 times) exposed a real refinement bottleneck: 100 candidates
took 7,748.8 ms before bounding refinement. The updated implementation processes
the same 100 candidates in 65.161 ms p50 / 67.666 ms p95. Matching remains exact;
minimum-window ranking is approximate after 64 valid-window refinements. Fields
longer than 2,048 characters or queries longer than 64 characters use one linear
greedy window. Exact substring matches still get their optimal span immediately.
This trades a small ranking difference on pathological input for bounded work
and simple cancellation, without adding a native sorter dependency.

## Shared content and preview

The source contains 990,000 characters over 90,000 lines. Compact newline and
UTF-16 indexes are shared by all locations in the immutable content snapshot.
The timing below excludes initial index construction; a separate initial run
including index construction and 1,000 lookups took 8.92 ms.

| Operation | p50 (ms) | p95 (ms) |
| --- | ---: | ---: |
| 1,000 metadata location lookups | 1.495 | 1.554 |
| Selected preview window | 0.003 | 0.008 |

The preview displays 2,000 lines / 21,999 characters. Twenty different files
leave 8,115,054 bytes in the content cache, below the 8,388,608-byte bound.
The cache accounts for text and compact indexes. Disk stat changes replace old
versions; metadata and previews reuse the same content. Content reads are
limited to 1 MiB, independently of the 2,000-line / 200,000-character display
limits. Unreachable locations beyond a truncated prefix produce a limitation
message and preserve the navigation target.

## Worker ownership and event-loop responsiveness

A deliberately blocked candidate-collection operation remains active through
100 simulated close/reopen requests. Observed maxima are one active slot, one
latest pending slot, and one concurrent blocked operation. The old operation's
result is discarded and only the newest request publishes. This exercises a
non-interruptible I/O boundary without pretending cancellation frees its slot.

During 21 production worker searches over 100,000 candidates, a Qt timer with
a configured 1 ms interval produced 124 samples. Observed event-loop gaps were
13.710 ms p50, 20.062 ms p95, and 26.289 ms maximum. This includes GIL contention
and the benchmark's event-processing loop. It is not a native key-to-paint
measurement. Search debounce is separately configured at 40 ms in the
controller; preview debounce is 50 ms.

The measured data supports retaining the small Python worker design for this
release. Native sorters, permanent indexes, additional configuration, and query
caches add complexity without a demonstrated requirement here. Native cocoa
IME, undocked-window focus, multi-monitor DPI, cold-disk collection, and large
Git patch rendering still require their own measurements.
