"""History picker integration with modes, dispatch, and asynchronous lifetime."""

# Standard Libraries
import weakref
from types import SimpleNamespace

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtWidgets import QDialog
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.spyder.vim_widgets import VimWidget
from spyder_okvim.utils.qtcompat import widget_is_deleted
from spyder_okvim.vim.state import VimState
from tests.qt_support import reset_vim_state


@pytest.fixture
def picker(vim_bot):
    main, stack, _, vim, qtbot = vim_bot
    widget = vim.vim_cmd
    status = widget.vim_status
    commandline = widget.commandline
    index = stack.get_stack_index()
    enabled = CONF.get(CONF_SECTION, "yanky_enabled", True)
    leader = CONF.get(CONF_SECTION, "leader_key")
    widget.cancel_yank_picker()
    widget.cancel_macro()
    commandline.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    vim._use_stack(stack)
    editor = stack.get_current_editor()
    original = editor.toPlainText()
    reset_vim_state(status)
    editor.set_text("alpha beta\nsecond line\nthird line")
    status.cursor.set_cursor_pos(0)
    CONF.set(CONF_SECTION, "yanky_enabled", True)
    CONF.set(CONF_SECTION, "leader_key", "Space")
    widget.apply_settings()
    status.yank_history.clear()
    entry = status.yank_history.record("한글\n😀\tend", "charwise")
    status.set_register('"', "register value", VimState.NORMAL)
    main.activateWindow()
    commandline.setFocus()
    QCoreApplication.processEvents()
    state = SimpleNamespace(
        main=main,
        stack=stack,
        vim=vim,
        widget=widget,
        status=status,
        line=commandline,
        editor=editor,
        bot=qtbot,
        entry=entry,
    )
    yield state
    widget.cancel_yank_picker()
    widget.cancel_macro()
    if status.is_recording_macro():
        status.stop_recording_macro()
    commandline.esc_pressed()
    status.disconnect_from_editor()
    reset_vim_state(status)
    stack.set_stack_index(0)
    vim._use_stack(stack)
    editor.set_text(original)
    status.yank_history.clear()
    CONF.set(CONF_SECTION, "yanky_enabled", enabled)
    CONF.set(CONF_SECTION, "leader_key", leader)
    widget.apply_settings()
    stack.set_stack_index(index)
    vim._use_stack(stack)
    main.activateWindow()
    commandline.setFocus()


def _open(state, trigger="direct"):
    if trigger == "direct":
        state.widget.show_yank_history()
    elif trigger == "leader":
        state.bot.keyClicks(state.line, " y")
    else:
        state.bot.keyClicks(state.line, ":YankyRingHistory")
        state.bot.keyClick(state.line, Qt.Key_Return)
    request = state.widget._yank_picker
    assert request is not None
    dialog = request.dialog
    # Keep it alive long enough to model a queued stale Qt completion.
    dialog.setAttribute(Qt.WA_DeleteOnClose, False)
    state.bot.addWidget(dialog)
    return dialog, request


def test_test_reset_closes_picker_and_stops_highlight_timers(picker):
    state = picker
    dialog, _ = _open(state)
    state.status.cursor.hl_put = True
    state.status.cursor.hl_yank_dur = 1000
    state.status.cursor.highlight_put(0, 1)
    assert state.status.cursor._highlight_timers
    reset_vim_state(state.status)
    assert state.widget._yank_picker is None
    assert not dialog.isVisible()
    assert not state.status.cursor._highlight_timers
    assert not state.editor.get_extra_selections("hl_put")


def _selection(state):
    return tuple(
        (item.cursor.anchor(), item.cursor.position())
        for item in state.editor.get_extra_selections("vim_selection")
    )


def _registers(state):
    return {
        name: (register.content, register.type)
        for name, register in state.status.register_dict.items()
    }


def _dot(state):
    dot = state.status.dot_cmd
    return (
        dot.vim_state,
        dot.num_str,
        dot.cmd,
        dot.register_name,
        dot.put_payload,
        dot.sel_block_no_start,
        dot.sel_block_no_end,
        dot.sel_col_start,
        dot.sel_col_end,
    )


@pytest.mark.parametrize("trigger", ["direct", "leader", "ex"])
def test_picker_put_keeps_original_entry_and_starts_cycle(picker, trigger):
    state = picker
    registers, history = _registers(state), state.status.yank_history.snapshot()
    dialog, _ = _open(state, trigger)
    assert dialog.list_viewer.currentIndex().row() == 0
    assert not dialog.list_model.item(0, 2).isEditable()
    state.bot.keyClick(dialog.list_viewer, Qt.Key_Return)
    state.bot.waitUntil(lambda: state.widget._yank_picker is None)
    QCoreApplication.processEvents()
    assert state.widget._yank_picker is None
    assert (
        state.editor.toPlainText() == "a한글\n😀\tendlpha beta\nsecond line\nthird line"
    )
    assert state.widget.put_controller.can_cycle()
    assert state.status.dot_cmd.put_payload.entry is state.entry
    assert _registers(state) == registers
    assert state.status.yank_history.snapshot() == history
    assert state.line.window().focusWidget() is state.line


def test_picker_captures_entry_before_dialog_deletion(picker):
    state = picker
    state.widget.show_yank_history()
    dialog = state.widget._yank_picker.dialog
    assert dialog.testAttribute(Qt.WA_DeleteOnClose)
    state.bot.keyClick(dialog.list_viewer, Qt.Key_Return)
    state.bot.waitUntil(lambda: state.widget._yank_picker is None)
    state.bot.waitUntil(lambda: widget_is_deleted(dialog))
    assert state.widget.put_controller.can_cycle()
    assert state.status.dot_cmd.put_payload.entry is state.entry


@pytest.mark.parametrize("selection", ["v3l", "3lv2h", "Vj"])
def test_picker_escape_restores_visual_selection_mode_and_focus(picker, selection):
    state = picker
    state.status.dot_cmd.cmd = "sentinel"
    state.bot.keyClicks(state.line, selection)
    original = state.editor.toPlainText()
    mode, selected = state.status.vim_state, _selection(state)
    cursor = state.editor.textCursor()
    registers, dot = _registers(state), _dot(state)
    dialog, _ = _open(state, "leader")
    state.bot.keyClick(dialog.list_viewer, Qt.Key_Escape)
    state.bot.waitUntil(lambda: state.widget._yank_picker is None)
    QCoreApplication.processEvents()
    assert state.editor.toPlainText() == original
    assert state.status.vim_state == mode
    assert _selection(state) == selected
    assert state.editor.textCursor().position() == cursor.position()
    assert state.editor.textCursor().anchor() == cursor.anchor()
    assert _registers(state) == registers
    assert _dot(state) == dot
    assert not state.widget.put_controller.can_cycle()
    assert state.line.window().focusWidget() is state.line


@pytest.mark.parametrize(
    "selection,expected",
    [
        ("v3l", "한글\n😀\tenda beta\nsecond line\nthird line"),
        ("Vj", "한글\n😀\tend\nthird line"),
    ],
)
@pytest.mark.parametrize("trigger", ["direct", "leader"])
def test_picker_put_uses_captured_visual_context(picker, selection, expected, trigger):
    state = picker
    original = state.editor.toPlainText()
    state.bot.keyClicks(state.line, selection)
    dialog, _ = _open(state, trigger)
    state.bot.keyClick(dialog.list_viewer, Qt.Key_Return)
    state.bot.waitUntil(lambda: state.widget._yank_picker is None)
    QCoreApplication.processEvents()
    assert state.editor.toPlainText() == expected
    assert state.status.is_normal()
    assert state.widget.put_controller.can_cycle()
    state.editor.undo()
    assert state.editor.toPlainText() == original


@pytest.mark.parametrize("selection, range_text", [("v3l", ":1,1"), ("Vj", ":1,2")])
def test_visual_colon_rejects_yanky_range_and_erasing_it_opens_normal_picker(
    picker, selection, range_text
):
    """Visual ':' fixes rows and leaves Visual mode for every Ex command."""
    state = picker
    original = state.editor.toPlainText()
    undo_available = state.editor.document().isUndoAvailable()
    history = state.status.yank_history.snapshot()
    state.bot.keyClicks(state.line, selection + ":")
    assert state.line.text() == range_text
    assert state.status.is_normal()
    assert not _selection(state)
    state.bot.keyClicks(state.line, "YankyRingHistory")
    state.bot.keyClick(state.line, Qt.Key_Return)

    assert state.widget._yank_picker is None
    assert "Range is not supported" in state.status.msg_label.text()
    assert state.editor.toPlainText() == original
    assert state.editor.document().isUndoAvailable() == undo_available
    assert state.status.yank_history.snapshot() == history

    state.status.cursor.set_cursor_pos(0)
    state.bot.keyClicks(state.line, selection + ":")
    state.line.setText(":YankyRingHistory")
    state.bot.keyClick(state.line, Qt.Key_Return)
    request = state.widget._yank_picker
    assert request is not None
    assert request.mode == VimState.NORMAL
    assert request.selection is None
    dialog = request.dialog
    dialog.setAttribute(Qt.WA_DeleteOnClose, False)
    state.bot.addWidget(dialog)
    position = request.cursor[1] + 1
    state.bot.keyClick(dialog.list_viewer, Qt.Key_Return)
    state.bot.waitUntil(lambda: state.widget._yank_picker is None)
    assert state.editor.toPlainText() == (
        original[:position] + state.entry.text + original[position:]
    )


@pytest.mark.parametrize("reason", ["clear", "disable", "view", "edit"])
def test_invalidated_picker_cannot_apply_late_result(picker, reason):
    state = picker
    original = state.editor.toPlainText()
    dialog, request = _open(state)
    dot, registers = _dot(state), _registers(state)
    if reason == "clear":
        state.widget.clear_yank_history()
    elif reason == "disable":
        CONF.set(CONF_SECTION, "yanky_enabled", False)
        state.widget.apply_settings()
    elif reason == "view":
        state.stack.set_stack_index(1)
        state.vim._use_stack(state.stack)
        state.stack.set_stack_index(0)
        state.vim._use_stack(state.stack)
    else:
        cursor = state.editor.textCursor()
        cursor.insertText("external")
        original = state.editor.toPlainText()
    assert state.widget._yank_picker is None
    assert not request.is_current()
    # A previously queued completion must not resurrect the request.
    dialog.selected_entry = state.entry
    dialog.finished.emit(QDialog.Accepted)
    assert state.editor.toPlainText() == original
    assert _dot(state) == dot
    assert _registers(state) == registers
    assert not state.widget.put_controller.can_cycle()


def test_old_picker_callback_cannot_close_or_refocus_new_request(picker):
    state = picker
    old, _ = _open(state)
    current, request = _open(state)
    old.selected_entry = state.entry
    old.finished.emit(QDialog.Accepted)
    assert state.widget._yank_picker is request
    assert current.isVisible()
    assert state.editor.toPlainText() == "alpha beta\nsecond line\nthird line"
    current.reject()


@pytest.mark.parametrize("accepted", [False, True])
def test_focus_completion_preserves_reentrant_picker(picker, accepted):
    state = picker
    dialog, _ = _open(state)
    original = state.editor.toPlainText()
    replacements = []

    def reopen(mode):
        state.status.change_label.disconnect(reopen)
        replacements.append(_open(state)[1])

    state.status.change_label.connect(reopen)
    if accepted:
        dialog.accept()
    else:
        dialog.reject()
    state.bot.waitUntil(lambda: bool(replacements))
    assert state.widget._yank_picker is replacements[0]
    assert replacements[0].dialog.isVisible()
    assert state.editor.toPlainText() == original


def test_clear_after_accept_invalidates_queued_focus_and_put(picker):
    state = picker
    dialog, _ = _open(state)
    original, dot = state.editor.toPlainText(), _dot(state)
    dialog.accept()
    state.widget.clear_yank_history()
    QCoreApplication.processEvents()
    QCoreApplication.processEvents()
    assert state.widget._yank_picker is None
    assert state.editor.toPlainText() == original
    assert _dot(state) == dot
    assert not state.widget.put_controller.can_cycle()


def test_picker_allows_rehighlight_without_text_change(picker):
    """Syntax formatting revisions do not invalidate a captured text context."""
    state = picker
    dialog, request = _open(state)
    state.editor.highlighter.rehighlight()
    QCoreApplication.processEvents()
    assert state.widget._yank_picker is request
    state.bot.keyClick(dialog.list_viewer, Qt.Key_Return)
    state.bot.waitUntil(lambda: state.widget._yank_picker is None)
    QCoreApplication.processEvents()
    assert state.widget.put_controller.can_cycle()
    assert state.status.dot_cmd.put_payload.entry is state.entry


def test_picker_accept_after_readonly_change_does_not_edit(picker):
    state = picker
    dialog, _ = _open(state)
    original, dot = state.editor.toPlainText(), _dot(state)
    state.editor.setReadOnly(True)
    try:
        dialog.accept()
        state.bot.waitUntil(lambda: state.widget._yank_picker is None)
        QCoreApplication.processEvents()
        assert state.widget._yank_picker is None
        assert state.editor.toPlainText() == original
        assert _dot(state) == dot
        assert not state.widget.put_controller.can_cycle()
    finally:
        state.editor.setReadOnly(False)


@pytest.mark.parametrize("macro", ["recording", "playing"])
def test_picker_is_unavailable_in_macro(picker, macro):
    state = picker
    if macro == "recording":
        state.status.manager_macro.start_record("a")
    else:
        state.widget.macro_playback.generation = 123
        state.widget.macro_playback.editor_ref = weakref.ref(state.editor)
    original = state.editor.toPlainText()
    state.widget.show_yank_history()
    assert state.widget._yank_picker is None
    assert "unavailable in macros" in state.status.msg_label.text()
    assert state.editor.toPlainText() == original


def test_cleanup_invalidates_picker_before_late_callback(picker):
    state = picker
    widget = VimWidget(state.main.editor, state.main)
    state.bot.addWidget(widget)
    widget.put_controller.bind_editor(state.editor)
    widget.vim_status.yank_history.record("late", "charwise")
    widget.show_yank_history()
    request = widget._yank_picker
    assert request is not None
    dialog = request.dialog
    dialog.setAttribute(Qt.WA_DeleteOnClose, False)
    state.bot.addWidget(dialog)
    entry = widget.vim_status.yank_history.snapshot()[0]
    original = state.editor.toPlainText()
    widget.cleanup()
    dialog.selected_entry = entry
    dialog.finished.emit(QDialog.Accepted)
    assert widget._yank_picker is None
    assert state.editor.toPlainText() == original
