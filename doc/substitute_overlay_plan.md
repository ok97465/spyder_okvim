# Editor substitution overlay

## Intended behavior

Typing an explicit `:s` command highlights its candidates. Once the pattern
delimiter is closed, the editor paints the expected changed paragraphs over
their original text. A separate results window is not used. The document,
cursor, selection, scroll position, undo history and confirmed Vim records stay
unchanged until Enter executes the normal synchronous substitution path.

The overlay retains the source document's line positions and heights. It clips
longer or additionally wrapped results to that space, with an overflow marker,
instead of covering the next source line. Replacement spans receive an accent;
deletions receive a small marker. Count-only input keeps source highlighting.
Confirmation input previews the result assuming approval of every candidate.

## Implementation tasks

- [x] Extend the bounded candidate scanner with optional paragraph results,
  UTF-16 replacement/deletion spans, and calculation-time output budgets. Reuse
  execution's replacement expansion and paragraph assembly. Prioritize requested
  viewport paragraphs so a partial global scan still previews the current view.
- [x] Add one mouse-transparent viewport overlay. Use Qt text layout and editor
  block geometry for tabs, Unicode and wrapping; clip each paragraph into its
  source bounds. Repaint on scroll, resize, font and theme changes without doing
  regex work in paint callbacks. Preserve unchanged syntax formats. Keep
  calltip widgets above it; guidance yields while entering replacements and
  returns for search-only or count-only input.
- [x] Connect the overlay to the existing debounced Ex session controller.
  Reuse results while their document/revision/input/settings and requested
  viewport coverage are current. Invalidate calculation and display on every
  existing cancel/reset/editor-switch/cleanup path; Enter never applies a
  stored preview plan.
- [x] Extend pure calculation, renderer and real input lifecycle tests. Cover
  exact execution parity, deletion/no-op/captures, NBSP/emoji/combining text,
  scrolling and wrapping, clipped output, partial limits, state preservation,
  late callbacks, IME and confirmation. Run regression suites in both Qt
  bindings and document a 10,000-line measurement and visual inspection.

## Responsibility boundaries

- `utils/substitute.py`: shared preparation, expansion and paragraph assembly.
- `utils/substitute_preview.py`: finite candidate scan and optional results.
- `spyder/substitute_preview.py`: session, scheduling, validation and publication.
- `spyder/substitute_overlay.py`: placement and painting only.

Global scan counts and visible results can be partial. Omitted output leaves
the original editor text and candidate highlighting intact, with a partial
preview indicator. No hard timeout for one Qt regular expression call is added.


## Validation (2026-10-30)

- Full regression suite: 3,350 passed in each of PyQt5 and PySide6/Qt 6.8.3
  on macOS; 101 optional tests skipped in each ordinary run.
- Native Cocoa input and overlay integration: 109 passed, 42 conditional skips.
- Opt-in editor window routing, popup and overlay lifetime: 21 passed. This
  includes a new painted-preview switch/close test against real Editor windows.
- Both bindings pass renderer tests; pure calculation tests cover output parity,
  UTF-16 mapping, viewport priority and calculation-time budgets. Integrated
  tests cover folding without scrolling and help suppression during debounce.
- Formatting, Ruff F checks and `git diff --check` pass.
- The 10,000-line benchmark and screenshot were rerun against final code. See
  [performance measurements](substitute_preview_performance.md) for timings,
  retained buffers and clipping/timeout limits.
