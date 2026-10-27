# Command dispatch and prefix hints

Command execution, input observation, and hint rendering have separate owners.
Executors update Vim state; which-key observes completed input and displays
available continuations without executing commands or taking keyboard focus.

## Declaring commands

`executor/executor_base.py` defines `CommandSpec(key, method_name, description)`.
Discrete prefix executors declare an ordered `command_specs` tuple of raw
single-character keys. The base executor derives accepted keys, method dispatch,
and hint descriptions from it.
The `g`, operator-`g`, `z`, and leader executors use this mechanism.

For example, `ExecutorSubCmd_g` includes:

```python
command_specs = (
    CommandSpec("g", "g", "Go to line"),
    CommandSpec("d", "d", "Go to definition"),
    CommandSpec("~", "tilde", "Swap case"),
    # Add another CommandSpec here when implementing a new g command.
)
```

To add a command, implement its named method with the usual
`(self, num=1, num_str="")` signature and add its specification. There is no
separate hint list or key expression to update. Raw keys preserve case and can
use method names such as `tilde` for punctuation. Tuple order controls hint order.

Leader commands follow the same declaration. For example,
`CommandSpec("f", "formatting", "Format document or selection")` binds the
existing `formatting` method. `ExecutorLeaderKey.set_easymotion_key()` rebuilds
the effective commands from the defaults and adds the configured leader as the
EasyMotion continuation. A collision replaces that key's default command;
changing the leader restores the previous default binding.

Other executors retain their existing parsers where counts, text input, or motion
grammar require them. The `submode` decorator manages executor transitions;
`MotionHelper` and `ActionHelper` own movement and text operations.

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

`VimWidget` in `spyder/vim_widgets.py` owns command dispatch and macro playback.
Its `input_processing()` context encloses key events, text changes, and replayed
keys. Nested calls emit `sig_input_started` once at the outer entry and
`sig_input_finished` once after the outer exit, including exception paths.
`sig_command_changed` reports changes outside dispatch; `sig_command_cancelled`
invalidates pending hints on cancellation or focus loss.

`pending_hint()` returns an immutable `PendingHint` containing a weak editor
reference, the active executor, Vim mode, and prefix. It returns `None` during
input dispatch, dot execution, macro playback, or a mode without prefix hints.
Macro suppression lasts until the final queued GUI key finishes, even if the
worker thread has already stopped. `is_playing_macro` derives this state from the
active playback generation. Hint consumers do not inspect these private execution
flags themselves.

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
