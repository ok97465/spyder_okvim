# Command dispatch, input and editor lifetimes

Command execution, input observation, and hint rendering have separate owners.
Executors update Vim state; which-key observes completed input and displays
available continuations without executing commands or taking keyboard focus.

## Module grouping and state ownership

The existing packages stay in place. Related handlers and small collaborators
share a file; separate files represent distinct behavior or lifetimes rather
than one class each.

| Location | Responsibility |
| --- | --- |
| `executor/executor_normal.py`, `executor_visual.py`, `executor_vline.py` | `NormalModeExecutor`, `VisualModeExecutor` and `VisualLineModeExecutor` interpret their mode's input and apply its selection policy. |
| `executor/operators.py` | Pending d/c/y operators and inner/around text-object input stay together so count and word-rule differences can be read side by side. |
| `executor/prefixes.py` | Small g/register/character/structure/window handlers and `ModeSubmodes` share the continuation contract. Every mode receives its own instances. |
| `executor/search_prompt.py`, `executor/leap_input.py` | Search preview/confirmation and Leap target selection have independent input sessions. |
| `utils/motions.py`, `utils/text_objects.py`, `utils/editing.py` | Motion computation, read-only text-object ranges and document edits have explicit collaborators. Basic, line and word motions remain together. |
| `vim/insert_repeat.py`, `vim/registers.py` | Insert/count/undo and dot recording have one owner; register rules and bounded yank history have another. |
| `spyder/commandline_input.py`, `spyder/macro_playback.py` | Prompt/IME/navigation state and queued macro playback each have a cohesive owner. |
| `spyder/vim_widgets.py`, `spyder/editor.py` | Small pane/label/shortcut classes stay with screen assembly; host file, IDE and language-aware editor operations go through `EditorCommands`. |

`VimStatus` coordinates modes and exposes the feature owners. Its legacy accessors
delegate to those owners rather than maintain duplicate register or insertion
state. `VimWidget` supplies command services through the session's
`create_command_services()` assembly point. Each executor receives its own
`CursorMotions` and `EditingActions(status, motions)` as `motions` and `edits`;
stateful Leap/search continuations are never global singletons.

`CursorMotions.text_objects` is a `TextObjects` calculator bound to a cursor
provider. Both operators and edits use its named methods such as `inner_word()`
and `around_bracket()`. Editing actions receive session state directly instead
of obtaining it indirectly through a motion helper. Search motions still live
with cursor motions, while `utils/search_helpers.py` supplies explicit case
policy and Qt matching shared with substitution.

Document offsets and Visual columns use Qt UTF-16 units, and block numbers are
zero-based. Ex line addresses and dialog display coordinates are one-based.
Character text-object ranges are half-open. Linewise ranges can end at the last
block's content end, with the applying policy adding its separator as needed.
`MotionType` determines how endpoints expand for an edit or selection. Keep
these contracts in value and API docstrings when adding a range calculation.

`vim/state.py`, register rules and yank values can be imported without Qt or
Spyder. `vim/__init__.py` resolves its public exports lazily; importing a model
must not eagerly load editor services. `KeyInfo.source` uses the named
`InputSource.COMMAND_LINE`/`EDITOR` routes while preserving recorded key values.
`KeyInfo.to_event()` performs Qt conversion only when replay needs it.

## Declaring commands

`executor/executor_base.py` defines `CommandSpec(key, method_name, description)`.
Discrete prefix executors declare an ordered `command_specs` tuple of raw
single-character keys. The base executor derives accepted keys, method dispatch,
and hint descriptions from it.
The `g`, operator-`g`, `z`, and leader executors use this mechanism.

For example, `GPrefixExecutor` in `executor/prefixes.py` includes:

```python
command_specs = (
    CommandSpec("g", "g", "Go to line"),
    CommandSpec("d", "d", "Go to definition"),
    CommandSpec("~", "tilde", "Swap case"),
    # Add another CommandSpec here when implementing a new g command.
)
```

To add a command, implement its named method with the usual
`(self, count=1, count_text="")` signature and add its specification. `count`
is the effective number and `count_text` retains the original typed prefix:
an absent count and an explicit `1` differ for commands such as `gg` and dot.
There is no separate hint list or key expression to update. Raw keys preserve case and can
use method names such as `tilde` for punctuation. Tuple order controls hint order.

Leader commands follow the same declaration. For example,
`CommandSpec("f", "formatting", "Format document or selection")` binds the
existing `formatting` method. `ExecutorLeaderKey.set_easymotion_key()` rebuilds
the effective commands from the defaults and adds the configured leader as the
EasyMotion continuation. A collision replaces that key's default command;
changing the leader restores the previous default binding.

Other executors retain their existing parsers where counts, text input, or motion
grammar require them. The `submode` decorator carries parent counts and prepares
deferred actions without executing them. `DeferredAction` describes the callback
and whether it consumes a motion; `ExecutorTransition` selects the next executor
and whether to clear the displayed command line. That flag does not indicate
whether an edit succeeded. A pending operator's actions run after its motion is
confirmed, not during search or hint preview.

## Applied settings and host operations

`spyder/config.py` reads a `PluginSettings` snapshot at the configuration boundary.
Search, Leap and cursor code use the applied values rather than reading global
configuration during a calculation. `resolve_ignorecase()` receives explicit
ignorecase/smartcase values and an optional substitution i/I override.

`VimWidget.apply_settings()` refreshes that snapshot and applies cursor/search,
bindings, completion, preview and hint preferences. Tests that change `CONF`
must apply settings explicitly; the integration reset helper also refreshes the
session's applied values.

`EditorCommands` handles save/close/new/open, run/debug, formatting, language-aware
indentation/commenting and Python/cell metadata. Commands retain Vim parsing,
range selection and register/dot policy. File commands recheck document identity
after operations that can process events, preserving debugger close guards,
autosave cleanup and Save As cancellation. Run actions restore the original
selection and command-input focus after the host action.

## Dynamic hints

Every executor exposes `hint_prefix` and `get_hint_candidates()`. A `None` prefix
opts out. The default provider returns `(raw_key, description)` pairs from the
effective command specifications. Register and mark executors override it to
describe current state; register range labels can describe groups of keys.

Providers must be read-only: do not create registers, read the clipboard, move the
cursor, modify selections, or execute commands. Register previews use existing
dictionary entries. Mark hints reflect whether the pending motion can change
files. Dynamic candidates are evaluated when hints are about to be displayed,
after the wait has earned its display delay.

## Observing stable input

`VimWidget` in `spyder/vim_widgets.py` owns command dispatch and composes input
services; `MacroPlayback` in `spyder/macro_playback.py` owns macro playback.
The widget's `input_processing()` context encloses key events, text changes, and replayed
keys. Nested calls emit `sig_input_started` once at the outer entry and
`sig_input_finished` once after the outer exit, including exception paths.
`sig_command_changed` reports changes outside dispatch; `sig_command_cancelled`
invalidates pending hints on cancellation or focus loss.

`pending_hint()` returns an immutable `PendingHint` containing a weak editor
reference, the active executor, Vim mode, and prefix. It returns `None` during
input dispatch, dot execution, macro playback, or a mode without prefix hints.
Macro suppression lasts until the final queued GUI key finishes, even if the
worker thread has already stopped. `is_playing_macro` exposes the playback
owner's active generation. The worker emits captured key values and completion
in order; the GUI owner validates generation/editor identity and waits for any
outer input guard before releasing playback. Hint consumers do not inspect
worker or widget private execution flags.

## Prompt input and shared view lifetime

`VimLineEdit` in `spyder/commandline_input.py` owns prompt drafts, history/caret
navigation, applied Tab candidates and native IME handling. `snapshot()` returns
an immutable `PromptSnapshot` tied to the active executor, with a Python string
cursor index and composition/replacement flags. Passive consumers reject
transient snapshots before scheduling completion or regex work.

Controllers use `history_context()`, `replace_input()`, `browse_history()`,
`reset_navigation()` and `apply_path_completion()` instead of reading private
line-edit state. `replace_input()` accepts a Python cursor index and converts it
at the QLineEdit boundary; callers must not pass a Qt UTF-16 position.

An applied Tab cycle and the popup's unaccepted highlighted row are separate
states. `completion_result` exposes the input's immutable candidate tuple and
applied index. Two-Enter acceptance, Tab/Shift-Tab cycling, suffix preservation
and the need to reaccept a Ctrl+N/P selection after Tab remain input contracts.

`VimWidget.handle_prompt_event()` distributes shared view/focus policy without
popup and preview controllers controlling each other. App deactivation suspends
preview while retaining its draft/origin; permanent focus loss and view changes
invalidate the appropriate requests. External document edits end preview, while
confirmation cancellation keeps replacements already accepted. Public
`cancel_pending_input()` and `VimStatus.cancel_pending_work()` release view-bound
work and timers before editor replacement or shutdown.

## Display and Qt lifecycle

`WhichKeyController` in `spyder/which_key.py` subscribes to the input signals,
checks focus and editor visibility, and schedules one timer for each pending
snapshot. Repeated observations preserve the original deadline. Input hides
stale rows immediately; a surviving wait can reuse its elapsed delay.

The controller follows the active editor viewport through `set_editor()`.
View changes, viewport destruction, and shutdown cancel pending work and release
the old popup. `cleanup()` also disconnects input signals and the timer.
`VimWidget.apply_settings()` explicitly refreshes command bindings and which-key
preferences; `set_leader_key()` only updates bindings and reports a change.

`WhichKeyPopup` in `spyder/which_key_popup.py` owns labels, readable key names,
theme/font styling, and geometry. It wraps descriptions to fit the viewport and
adds scrolling for overflow. It does not interpret Vim state or handle commands.

`SwitcherNavigation` in `spyder/switcher.py` separately attaches Ctrl+P/N handling
to Spyder's file/symbol switcher. Plugin availability hooks attach and detach the
filter; the main plugin event filter remains responsible for editor lifecycle.

`utils/qtcompat.py` provides `widget_is_deleted()` and `live_widget()` for safe
access to weak Qt references across PyQt/PySide bindings. A live Python wrapper
can still refer to a deleted C++ widget, so weak references alone are insufficient.

## Yank history and put sessions

`VimStatus.registers` owns register values and one `YankHistory` for the plugin
instance; the status's `yank_history` accessor delegates to it. Immutable
`YankEntry` values contain text, explicit character/line type, source, and bounded
payload metadata, with no Qt references. Record each logical yank or deletion
once in `update_registers()` after the existing register updates; individual
`set_register()` writes, puts, and history reads do not record entries. Clipboard
read/write and message callbacks are supplied to `Registers`, keeping those
rules independent of Qt.

`VimWidget` owns the `PutController`; executors call it directly through
`VimStatus.put_controller`, without mode-specific forwarding helpers. The
controller plans puts from the original mode, selection, placement, and count,
and retains a reversible local patch.
Cycling joins replacements to the original put's undo group. It uses a fixed
entry snapshot and never changes register values or history order. Document,
view, cursor, command, and undo validity determine whether a session can cycle;
syntax-highlighter revision changes alone do not imply text edits.
Exact patch validation is still required because Qt can defer text-change
notifications until an outer edit block ends. Reversible patch capture is
skipped when cycling is disabled or the put exceeds the session budget. The
`after_cursor` argument describes p/P placement; Visual puts replace the captured
selection. Planning values, `plan_put()` and application/cycling remain together
in `utils/put.py` so this feature can be followed without extra forwarding files.

The history picker receives immutable entries and returns a selected value.
`YankHistoryDialog` handles bounded display previews and table navigation only;
each row retains its original entry in `Qt.UserRole`. `YankHistoryPicker` reads
the result during the dialog's `finished` signal, before Qt deletes it, and owns target validation,
focus/mode restoration, and the eventual put. `VimWidget` holds only the current
picker; `is_current(picker)` and `on_finished(picker)` callbacks validate and
release that ownership without exposing its private field. An old completion
cannot release a replacement picker.
View changes and cleanup invalidate requests so callbacks cannot edit or refocus
an old editor.

Snapshot puts keep only their entry, direction, and count in `PutPayload`.
The Visual selection shape remains in `DotCmdInfo`, whose
`selection_to_cmd_string()` is shared by ordinary and snapshot dot repetition.
`InsertRepeatSession` owns that snapshot and the active `InsertEdit`, including
count expansion, event forwarding and shared undo grouping. Key delivery for
dot/macro uses the same insertion contract as actual editor input.

`VimLineEdit` owns an immutable tuple of Tab candidates, the selected row, and
the working directory. Observers reuse that tuple instead of copying the list.
The applied text and whether a unique directory needs another lookup are
derived from that row. `utils/commandline.py` supplies candidates to both Tab
completion and automatic suggestions; substitution fields reuse one cached,
immutable history snapshot without a separate history object.

Path completion uses one debounce timer connected for the controller's lifetime.
Its current request is cleared on invalidation; worker generations reject stale
results. The background runnable carries its request and cancellation event
directly, without a second job object.

Command-line popups own their content and appearance caches. Their setters
report changes so the controller can invalidate `CommandlinePopupHost` geometry.
The host alone positions both sections; the sections only measure their content.
`SubstituteOverlay` paints its passive viewport child through its existing event
filter.

## Navigation data and persistence

Bookmark callers use `vim_status.bookmark_manager` directly. The manager owns
local/global mark lookup and uses supplied load/persist callbacks. Default
`load_bookmarks()`/`save_bookmarks()` functions stay in the same feature module
and preserve existing paths and JSON keys. Tests can replace storage with an
in-memory implementation without changing mark rules or editor callbacks.

`build_mark_rows()` and `build_jump_snapshot()` prepare immutable display data
before constructing their dialogs. `MarkListDialog` returns a selected name;
`JumpListDialog` requests navigation through callbacks that return a fresh
snapshot. Neither dialog reads source files or knows `VimStatus`. Metadata
preparation stays near its feature rather than adding separate row/provider
modules. The existing jump metadata offset calculation is preserved; changing
its non-BMP display behavior is a separate fix.

## Compatibility and verification

New code imports each feature from its owning module. Historical mode class
names and `executor/executor_sub.py` remain import aliases.
`utils/motion_helpers.py` and `utils/action_helpers.py` retain small compatibility
wrappers for their former helpers and text-object/action names. `VimLineEdit`
and macro worker imports from `spyder/vim_widgets.py` still resolve through its
assembly imports. These are forwarding surfaces, not duplicate implementations;
internal code uses `DeferredAction`, `ExecutorTransition`, `count` and
`count_text`. Legacy imports do not guarantee every former internal NamedTuple
keyword constructor.

`python runtests.py` collects both existing feature tests under `spyder_okvim/`
and the pure model/storage tests under root `tests/`. Root `conftest.py`
imports GUI support lazily and creates the shared editor only when a test
requests `vim_bot`. Integration setup/reset lives in `tests/qt_support.py`;
product objects no longer expose a test-only reset method.

Pure boundary checks can run without loading Qt or Spyder:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests
```

Run existing feature regressions for the changed area and use a separate process
for each Qt binding. Native IME and opt-in paired-Spyder window tests cover
different environments from offscreen widget tests; see the README commands.
