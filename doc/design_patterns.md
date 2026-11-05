# Architecture and maintenance

This guide describes the boundaries to preserve when changing commands, editor
integration or passive UI. See the [user guide](../README.md) for supported keys.
Source paths below are relative to `spyder_okvim/`.

## Ownership

| Area | Owner and responsibility |
| --- | --- |
| Spyder integration | [spyder/plugin.py](../spyder_okvim/spyder/plugin.py) binds the active editor stack and moves the shared Vim UI between host windows. [spyder/editor.py](../spyder_okvim/spyder/editor.py) supplies file, IDE and language-aware editor operations. |
| Command dispatch | [spyder/vim_widgets.py](../spyder_okvim/spyder/vim_widgets.py) assembles services and guards input dispatch. [vim/status.py](../spyder_okvim/vim/status.py) coordinates modes and creates per-executor services. |
| Vim grammar | [executor/](../spyder_okvim/executor) contains mode, operator and prefix executors. Commands use `CursorMotions`, `TextObjects` and `EditingActions` for ranges and edits. |
| Prompt and passive UI | [spyder/commandline_input.py](../spyder_okvim/spyder/commandline_input.py) owns input, IME and applied completion. Popup, which-key and preview controllers observe stable input and manage their own timers and views. |
| Editing state | [vim/insert_repeat.py](../spyder_okvim/vim/insert_repeat.py), [vim/registers.py](../spyder_okvim/vim/registers.py) and [utils/put.py](../spyder_okvim/utils/put.py) own insertion/repeat, registers and reversible put sessions. |
| Navigation | [utils/bookmark_manager.py](../spyder_okvim/utils/bookmark_manager.py) owns marks and persistence callbacks; [utils/jump_list.py](../spyder_okvim/utils/jump_list.py) owns jump navigation. Dialogs consume prepared rows or snapshots. |

`vim/state.py`, register rules and yank values remain importable without Qt or
Spyder. `vim/__init__.py` resolves exports lazily. Keep model imports independent
of editor services and import features from their owning modules.

## Commands and ranges

Discrete prefix executors declare ordered `CommandSpec` values in
[executor_base.py](../spyder_okvim/executor/executor_base.py). Accepted keys,
dispatch and default hints come from that declaration:

```python
command_specs = (
    CommandSpec("g", "g", "Go to line"),
    CommandSpec("d", "d", "Go to definition"),
    CommandSpec("~", "tilde", "Swap case"),
)
```

Add the specification and its method with `(self, count=1, count_text="")`.
`count` is the effective number; `count_text` preserves the typed prefix, since
an implicit count and an explicit `1` can have different repeat semantics.
Tuple order determines hint order. Commands with count, text or motion grammar
use their executor's parser instead of the discrete-key table.

Each mode gets its own stateful continuations. `DeferredAction` describes work
waiting for a motion; `ExecutorTransition` selects the next executor and whether
to clear the displayed input. Execute deferred edits only after the motion is
confirmed. Hint providers return key/description pairs and must remain read-only:
no register creation, clipboard access, cursor movement or document edits.

Range calculations use these units:

- Document offsets and Visual columns: Qt UTF-16 units; block numbers: zero-based.
- Ex line addresses and displayed line/column numbers: one-based.
- Prompt snapshots and `VimLineEdit.replace_input()`: Python string indices,
  converted at the QLineEdit boundary.
- Character text-object ranges: half-open. `MotionType` controls endpoint
  expansion for selection or editing, including linewise separators.

Keep conversions at API boundaries, especially for non-BMP characters. Shared
case policy and Qt matching live in `utils/search_helpers.py`.

## Stable input and view lifetimes

`VimWidget.input_processing()` emits `sig_input_started` at the outer entry and
`sig_input_finished` after the outer exit, including exception paths. Passive
controllers synchronize after this boundary. `PromptSnapshot` captures the
executor, text, Python cursor index and composition/replacement state; reject
transient snapshots before scheduling completion or regex work.

Use the input owner's `history_context()`, `replace_input()`, `browse_history()`
and `apply_path_completion()` APIs. An applied Tab cycle and an unaccepted popup
row are distinct states: preserve Tab/Shift-Tab cycling and two-Enter acceptance
when changing suggestions. See [path completion](commandline_completion_performance.md)
for worker ownership and cancellation.

`pending_hint()` excludes input dispatch, dot execution and macro playback.
Macro suppression lasts until the final queued GUI key completes, even after
the worker stops. Queued results and replayed keys must validate their generation
and editor context before taking effect.

The plugin binds commands to an explicit editor stack before restoring input
focus. Switching views cancels old requests; the same Vim widget and status UI
move between the main window, undocked editor and editor windows. Navigation
between panes uses live panes in the current host window.

Hiding or deactivating a window suspends substitution preview while retaining
its draft and origin. Permanent focus loss, editor replacement and shutdown
cancel the relevant work. `cancel_pending_input()` and
`VimStatus.cancel_pending_work()` are the shared cleanup boundaries; controllers
also release their timers, signals and viewport children in `cleanup()`.

Use `live_widget()` and `widget_is_deleted()` from `utils/qtcompat.py` when
following weak Qt references. A live Python wrapper can refer to a deleted C++
object. Async callbacks must also recheck document identity/revision where their
result depends on captured text, and must not refocus an obsolete editor.

## Edits, undo and registers

[utils/undo.py](../spyder_okvim/utils/undo.py) provides `undo_block()` for
synchronous changes and `UndoGroup` for one logical change spanning events.
It handles Spyder's custom undo stack, native Qt undo and the actual undo owner
of a document shared by cloned views. Use its `editor_undo()`, `editor_redo()`
and `notify_document_change()` helpers rather than assuming the active view owns
the history or issuing duplicate language-server notifications.

`Registers.update_registers()` records each logical yank/deletion once.
Individual register writes, puts and history reads do not add yank entries.
Clipboard access is injected into `Registers`; bookmark persistence uses
callbacks supplied to `BookmarkManager`. Stored entries and dialog snapshots
contain values rather than Qt widgets.

`PutController` captures the original mode, selection, placement and count.
Cycling uses a fixed history snapshot and joins replacements to the initial
put's undo group. It validates both document state and the exact reversible
patch, since Qt can defer change notifications inside edit blocks. Preserve the
session's size budget and invalidate it on unrelated edits, navigation or undo.
Dot repetition retains the put payload and Visual selection shape separately.

## Substitution preview and execution

| Layer | Responsibility |
| --- | --- |
| `utils/ex_parser.py`, `utils/substitute.py` | Parse addresses/flags and share matching, replacement expansion and paragraph assembly. |
| `executor/executor_colon.py`, `utils/substitute_confirm.py` | Execute against the current document; manage interactive approval and one logical undo change. |
| `utils/substitute_preview.py` | Calculate bounded candidate spans and requested visible paragraph results. |
| `spyder/substitute_preview.py` | Own the Ex preview session, debounce/chunk timers, result validation and publication. |
| `spyder/substitute_overlay.py` | Lay out and paint a passive viewport child using editor geometry and syntax formats. |

Preview preserves document text, cursor/selection, scrolling, undo history and
confirmed Vim records. Enter executes the normal substitution path against the
current document; it does not apply a cached preview. Cancelling confirmation
keeps approved replacements in their undo group.

The overlay stays inside each original paragraph's height. Longer or additionally
wrapped results are clipped, with an ellipsis and **Partial preview** indicator.
Unchanged fragments retain syntax formats. Omitted output leaves source text
visible; paint callbacks never run regex matching or replacement expansion.

Count-only (`n`) input highlights candidates. Confirmation (`c`) previews the
all-approved result before execution enters interactive approval. Read-only
documents can show preview without permitting edits. Prompt guidance can coexist
with the overlay. Scan/output budgets, viewport priority and the single-regex-call
limit are documented in [preview performance](substitute_preview_performance.md).

## Settings, themes and geometry

`spyder/config.py` reads an immutable `PluginSettings` snapshot;
`VimWidget.apply_settings()` distributes it to feature owners. Calculations use
the applied values. Tests that change `CONF` must apply settings explicitly.

Editor highlights and jump labels use the editor's palette; the mode indicator
follows its parent/app palette. Which-key, history and guide panels use Spyder's
UI palette. [utils/theme.py](../spyder_okvim/utils/theme.py) prefers theme colors
and repairs low foreground contrast: 4.5:1 for its text and 3:1 for deletion
markers. Appearance changes recolor existing ranges or invalidate paint layouts
without recalculating matches, moving the cursor or restarting highlight timers.

`CommandlinePopupHost` positions completion/history and guide sections; sections
measure content and report changes. Which-key wraps and scrolls its own rows.
Passive popups keep keyboard focus in the command input. Theme regressions cover
discovered installed variants and synthetic low-contrast palettes.

## Shared picker

`utils/picker.py` owns immutable targets/candidate snapshots and bounded search.
`spyder/picker_dialog.py` renders only values and emits intent; it never reads a
file or navigates the host. `picker_providers.py` captures GUI values and checks
live targets before using existing bookmark/jump/editor owners. Blocks are
zero-based, offsets and columns are Qt UTF-16, and displayed coordinates are
one-based. `picker_preview.py` shares bounded content/indexes between metadata
and the independent read-only preview document. Open buffers take precedence;
GUI validity checks inspect document revision without recopying text. The host
reuses one bounded open-document snapshot until its document or revision changes.
Metadata rows retain at most 1,024 source characters per location, and report
partial text search when that limit is reached. Preview language highlighters
are reused, with only the current code or diff highlighter attached.

`PickerController` owns one nonmodal session and per-source/scope state. Its
application-owned `PickerWorkService` keeps one active plus one latest pending
request per collection/search/content lane across close/reopen. Operations
capture values and services only; cancellation leaves a blocked operation in its
slot until it returns. Session, scope, dataset, query and selection tokens reject
late publication. Search always starts from the candidate snapshot, never the
displayed top-N rows. Metadata batches by file and yields to selected preview.
Failed metadata work advances the queue and can be retried by refreshing;
background failures cannot replace another selection's preview.
Git uses a separate bounded `QProcess` lane with timeout, terminate/kill and
NUL-safe parsers. Patch previews display text; navigation uses the candidate's
original target rather than displayed patch row numbers.
Stashes retain a fixed object SHA for preview rather than a mutable reflog index.
Current-file history follows renames in that file's repository; repository history
uses the active project. Paging budgets belong to each source/scope, and commit
Back returns to the source that opened its changed files. The `<leader>t` submode
uses the existing prefix transition/WhichKey contract for m/j/s/S/c/C/b.

`picker_git_controller.py` owns Git execution intent and runtime prompts.
`picker_git_actions.py` builds explicit commands and serializes accepted writes in
an application-owned process service without a replaceable queue. Query/source
cancellation invalidates preflight intent; it never terminates an accepted write.
HEAD, symbolic HEAD and selected branch refs are checked before the mutation.
UI callbacks use session/query/selection identity; cleanup detaches observers and
lets already accepted execution finish. Open-document revisions protect edits
made during Git execution from being overwritten when clean buffers are reloaded.
Buffer snapshots are captured again after runtime prompts. Shared documents
reload once through a surviving view if another clone closes during execution.
Confirmation dialogs cover reset/delete/rebase/merge; normal Git refusal/conflict
messages remain visible without forcing, automatically stashing or aborting.
The Actions menu and source-specific keys share the same intent path.

Focus ownership lasts through `active → finishing → closed`. A replacement
invalidates a queued action and focus handoff. Accept closes first, then validates
and executes once on a later event-loop turn. `VimLineEdit` recognizes both active
and finishing ownership. The internal navigation guard permits only the captured
stack/window during explicit acceptance or Jumps Ctrl+O/I; external view/project
changes and shutdown cancel through the normal shared boundaries. ShortcutOverride
reserves keys, and KeyPress executes them once. Native preedit Enter/Esc completes
or cancels composition before picker acceptance. YankHistory keeps its separate
table popup and key contract. The former file/mark/jump dialogs and modal helper
have been removed.

The measured design and intentional limits are recorded in
[picker performance](picker_performance.md). Layout state belongs to the session;
no extra color settings, query cache, native sorter, permanent file index or
provider registry was introduced without evidence that it is needed.

Keep source adapters explicit: each validates and executes against its existing
file, bookmark or jump owner. Entries store one target and a preview kind; avoid
wrapping the same target in a second preview object. Content requests use object
identity to reject replaced work and retain only selection and buffer identity
for publication checks. Buffer snapshots name their fields so Git reload guards
can be read without remembering tuple positions. Fixed read and decoding limits
belong to the content service rather than each cache key.

## Verification

Run commands from the repository root in a development environment with the
package and [test requirements](../requirements/tests.txt) installed. The
[CI workflow](../.github/workflows/tests.yml) defines the dependency/Qt setup.
Use a separate process for each binding:

```sh
SPYDER_PYTEST=True QT_QPA_PLATFORM=offscreen \
QT_API=pyqt5 PYTEST_QT_API=pyqt5 python runtests.py

SPYDER_PYTEST=True QT_QPA_PLATFORM=offscreen \
QT_API=pyside6 PYTEST_QT_API=pyside6 python runtests.py
```

For a focused change, replace `python runtests.py` with `python -m pytest -q`
and the relevant test paths. Pure model/storage checks can run without loading
Qt or Spyder:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests
```

Native IME checks require a desktop backend (`cocoa` on macOS, `windows` on
Windows) instead of `offscreen`. Run `spyder/tests/test_commandline_ime.py` and
`utils/tests/test_key_helpers.py` under `spyder_okvim/` with that backend.
Real editor-window integration is opt-in and requires the paired Spyder fork:

```sh
SPYDER_PYTEST=True SPYDER_OKVIM_WINDOW_INTEGRATION=1 \
QT_QPA_PLATFORM=offscreen QT_API=pyside6 PYTEST_QT_API=pyside6 \
python -m pytest -q spyder_okvim/spyder/tests/test_editor_windows.py
```

Use the two linked performance guides for opt-in benchmarks. Record environment
and timing output with the run or review rather than accumulating dated results
in these design documents.
