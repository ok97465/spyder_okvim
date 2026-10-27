"""History puts preserve register state, the surrounding text, and Qt undo."""

from unittest.mock import Mock

import pytest
from qtpy.QtCore import QCoreApplication
from qtpy.QtGui import QTextCursor

from spyder_okvim.vim.state import VimState
from spyder_okvim.vim.yank_history import YankEntry
from spyder_okvim.utils import put as put_module


def prepare(vim_bot, text="abcd"):
    _, _, editor, vim, qtbot = vim_bot
    line = vim.vim_cmd.commandline
    line.esc_pressed()
    status = vim.vim_cmd.vim_status
    status.disconnect_from_editor()
    status.reset_for_test()
    editor.set_text(text)
    status.cursor.set_cursor_pos(0)
    line.clear()
    line.setFocus()
    controller = status.put_controller
    controller.bind_editor(editor)
    status.yank_history.clear()
    return editor, status, line, qtbot, controller


def record(status, text, kind="charwise"):
    return status.yank_history.record(text, kind)


@pytest.mark.parametrize("command", ["p", "P"])
def test_cycle_undo_redo_and_registers(vim_bot, command):
    editor, status, line, bot, controller = prepare(vim_bot)
    record(status, "old")
    record(status, "NEW")
    status.set_register('"', "NEW", VimState.NORMAL)
    before_registers = {
        name: (r.content, r.type) for name, r in status.register_dict.items()
    }
    before_history = status.yank_history.snapshot()
    bot.keyClicks(line, command)
    assert controller.can_cycle()
    controller.cycle(1)
    expected = "aoldbcd" if command == "p" else "oldabcd"
    assert editor.toPlainText() == expected
    controller.cycle(-1)
    controller.cycle(1)
    assert status.yank_history.snapshot() == before_history
    assert {
        name: (r.content, r.type) for name, r in status.register_dict.items()
    } == before_registers
    editor.undo()
    assert editor.toPlainText() == "abcd"
    assert not controller.can_cycle()
    editor.redo()
    assert editor.toPlainText() == expected
    assert not controller.can_cycle()


def test_previous_edit_is_not_joined(vim_bot):
    editor, status, line, bot, controller = prepare(vim_bot)
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    cursor.insertText("before")
    cursor.endEditBlock()
    status.cursor.set_cursor_pos(0)
    record(status, "X")
    status.set_register('"', "Y", VimState.NORMAL)
    bot.keyClicks(line, "p")
    controller.cycle(1)
    editor.undo()
    assert editor.toPlainText() == "beforeabcd"
    editor.undo()
    assert editor.toPlainText() == "abcd"


@pytest.mark.parametrize(
    "text,selection,first,kind,older,older_kind,expected",
    [
        ("ab", "", "X", "charwise", "L\n", "linewise", "ab\nL"),
        ("ab\ncd", "", "X", "charwise", "L\n", "linewise", "ab\nL\ncd"),
        ("ab", "", "L\n", "linewise", "X", "charwise", "aXb"),
        ("abcd\nef", "vl", "X", "charwise", "L\n", "linewise", "\nL\ncd\nef"),
        ("ab\ncd\nef", "Vj", "X", "charwise", "L\n", "linewise", "L\nef"),
    ],
)
def test_cycle_type_changes_and_selection_undo(
    vim_bot, text, selection, first, kind, older, older_kind, expected
):
    editor, status, line, bot, controller = prepare(vim_bot, text)
    record(status, older, older_kind)
    status.set_register(
        '"', first, VimState.VLINE if kind == "linewise" else VimState.NORMAL
    )
    bot.keyClicks(line, selection + "p")
    assert controller.can_cycle()
    controller.cycle(1)
    assert editor.toPlainText() == expected
    editor.undo()
    assert editor.toPlainText() == text
    editor.redo()
    assert editor.toPlainText() == expected


def test_named_original_and_count_clamping(vim_bot):
    editor, status, line, bot, controller = prepare(vim_bot, "x")
    record(status, "A")
    record(status, "B")
    status.set_register("a", "named", VimState.NORMAL)
    bot.keyClicks(line, '"a2p')
    controller.cycle(1, 999)
    assert editor.toPlainText() == "xAA"
    controller.cycle(-1, 999)
    assert editor.toPlainText() == "xnamednamed"
    assert status.register_dict["a"].content == "named"


def test_cycle_and_picker_dot_use_snapshot(vim_bot):
    editor, status, line, bot, controller = prepare(vim_bot, "xy")
    record(status, "old")
    status.set_register('"', "new", VimState.NORMAL)
    bot.keyClicks(line, "p")
    controller.cycle(1)
    status.set_register('"', "different", VimState.NORMAL)
    bot.keyClicks(line, "l2.")
    assert editor.toPlainText() == "xoldyoldold"
    assert status.dot_cmd.put_payload.entry.text == "old"


@pytest.mark.parametrize("selection,expected", [("vl", "XYcd\nXYgh"), ("V", "XY\nXY")])
def test_snapshot_dot_rebuilds_selection(vim_bot, selection, expected):
    editor, status, line, bot, controller = prepare(vim_bot, "abcd\nefgh")
    bot.keyClicks(line, selection)
    controller.put(entry=YankEntry.from_register("XY", VimState.NORMAL))
    bot.keyClicks(line, "j0.")
    assert editor.toPlainText() == expected


@pytest.mark.parametrize(
    "text,command,repeat,expected",
    [
        ("ab\ncd\nef\ngh\nij", 'vj"ap', "j0.", "Zd\nZh\nij"),
        ("a\nb\nc\nd\ne", 'Vj"ap', "j.", "Z\nZ\ne"),
        ("abcd\nefgh", '2lvh"ap', "j0.", "aZd\nZgh"),
    ],
)
def test_cycled_named_put_dot_rebuilds_visual_shape(
    vim_bot, text, command, repeat, expected
):
    editor, status, line, bot, controller = prepare(vim_bot, text)
    record(status, "Z")
    status.set_register("a", "original", VimState.NORMAL)
    bot.keyClicks(line, command)
    controller.cycle(1)
    status.set_register("a", "changed", VimState.NORMAL)
    bot.keyClicks(line, repeat)
    assert editor.toPlainText() == expected
    assert status.dot_cmd.put_payload.entry.text == "Z"
    assert line.text() == ""
    assert status.is_normal()


@pytest.mark.parametrize(
    "action", ["cursor", "same_length", "undo", "clear_undo", "readonly"]
)
def test_external_changes_expire_session(vim_bot, action):
    editor, status, line, bot, controller = prepare(vim_bot)
    status.set_register('"', "X", VimState.NORMAL)
    bot.keyClicks(line, "p")
    assert controller.can_cycle()
    if action == "cursor":
        status.cursor.set_cursor_pos(0)
    elif action == "same_length":
        cursor = editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(1, QTextCursor.KeepAnchor)
        cursor.insertText("z")
    elif action == "undo":
        editor.undo()
    elif action == "clear_undo":
        editor.document().clearUndoRedoStacks()
    else:
        editor.setReadOnly(True)
    try:
        assert not controller.can_cycle()
    finally:
        editor.setReadOnly(False)


def test_rehighlight_does_not_expire_session(vim_bot):
    editor, status, line, bot, controller = prepare(vim_bot, "word")
    status.set_register('"', "X", VimState.NORMAL)
    bot.keyClicks(line, "p")
    editor.highlighter.rehighlight()
    QCoreApplication.processEvents()
    assert controller.can_cycle()


def test_pending_external_edit_cannot_cycle_before_qt_notification(vim_bot):
    editor, status, line, bot, controller = prepare(vim_bot)
    status.set_register('"', "X", VimState.NORMAL)
    bot.keyClicks(line, "p")
    generation = controller.text_generation
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    try:
        cursor.setPosition(1)
        cursor.setPosition(2, QTextCursor.KeepAnchor)
        cursor.insertText("Y")
        assert controller.text_generation == generation
        assert not controller.can_cycle()
    finally:
        cursor.endEditBlock()


@pytest.mark.parametrize("reason", ["disabled", "empty", "oversize"])
def test_non_cycling_put_skips_reversible_text_copies(vim_bot, monkeypatch, reason):
    editor, status, line, bot, controller = prepare(vim_bot)
    status.set_register('"', "" if reason == "empty" else "X", VimState.NORMAL)
    if reason == "disabled":
        monkeypatch.setattr(status, "yanky_enabled", False)
    elif reason == "oversize":
        monkeypatch.setattr(put_module, "SESSION_BYTE_LIMIT", 1)
    copy_text = Mock(side_effect=AssertionError("unneeded reversible text copy"))
    monkeypatch.setattr(put_module, "_text", copy_text)
    bot.keyClicks(line, "vlp")
    assert editor.toPlainText() == ("cd" if reason == "empty" else "Xcd")
    assert not controller.can_cycle()
    assert copy_text.call_count == 0


@pytest.mark.parametrize("command", ["V3p", "V3P"])
def test_counted_empty_register_put_in_vline(vim_bot, command):
    editor, status, line, bot, controller = prepare(vim_bot, "ab\ncd")
    status.set_register('"', "", VimState.NORMAL)
    bot.keyClicks(line, command)
    assert editor.toPlainText() == "\ncd"
    assert not controller.can_cycle()
    editor.undo()
    assert editor.toPlainText() == "ab\ncd"


def test_non_bmp_cursor_and_patch_use_qt_positions(vim_bot):
    editor, status, line, bot, controller = prepare(vim_bot, "ab")
    record(status, "한🙂")
    status.set_register('"', "😀", VimState.NORMAL)
    bot.keyClicks(line, "p")
    assert editor.toPlainText() == "a😀b"
    assert editor.textCursor().position() == 1
    controller.cycle(1)
    assert editor.toPlainText() == "a한🙂b"
    assert editor.textCursor().position() == 2
    editor.undo()
    assert editor.toPlainText() == "ab"


def test_cycle_boundary_and_duplicate_result_do_not_edit(vim_bot):
    editor, status, line, bot, controller = prepare(vim_bot)
    record(status, "A")
    record(status, "B")
    record(status, "A")
    status.set_register('"', "A", VimState.NORMAL)
    bot.keyClicks(line, "p")
    notify = Mock()
    editor.document().undoCommandAdded.connect(notify)
    try:
        controller.cycle(-1)
        assert notify.call_count == 0
        # Jump past B directly to the other A without editing.
        controller.cycle(1, 2)
        assert notify.call_count == 0
        assert status.dot_cmd.put_payload.entry.text == "A"
    finally:
        editor.document().undoCommandAdded.disconnect(notify)


def test_session_and_accumulated_cycle_budgets(vim_bot, monkeypatch):
    editor, status, line, bot, controller = prepare(vim_bot)
    status.set_register('"', "large", VimState.NORMAL)
    monkeypatch.setattr(put_module, "SESSION_BYTE_LIMIT", 2)
    bot.keyClicks(line, "p")
    assert editor.toPlainText() == "alargebcd"
    assert not controller.can_cycle()
    monkeypatch.setattr(put_module, "SESSION_BYTE_LIMIT", 100)
    record(status, "B")
    bot.keyClicks(line, "p")
    monkeypatch.setattr(put_module, "CYCLE_BYTE_LIMIT", 1)
    previous = editor.toPlainText()
    assert controller.cycle(1)
    assert editor.toPlainText() == previous
    assert not controller.can_cycle()


def test_identical_text_with_different_type_updates_snapshot_without_edit(vim_bot):
    editor, status, line, bot, controller = prepare(vim_bot, "x")
    record(status, "A\n", "linewise")
    status.set_register('"', "\nA", VimState.NORMAL)
    bot.keyClicks(line, "p")
    old_revision = editor.document().revision()
    controller.cycle(1)
    assert editor.toPlainText() == "x\nA"
    assert editor.document().revision() == old_revision
    assert status.dot_cmd.put_payload.entry.kind == "linewise"
    # Repeating in the middle of a line must retain linewise meaning.
    status.cursor.set_cursor_pos(0)
    bot.keyClicks(line, ".")
    assert editor.toPlainText() == "x\nA\nA"


def test_same_range_uses_one_replacement_and_one_notification(vim_bot, monkeypatch):
    editor, status, line, bot, controller = prepare(vim_bot, "abcdef")
    record(status, "short")
    record(status, "long replacement")
    status.set_register('"', "initial", VimState.NORMAL)
    bot.keyClicks(line, "v3lp")
    original = controller._apply
    calls = Mock(wraps=original)
    monkeypatch.setattr(controller, "_apply", calls)
    notify = Mock()
    monkeypatch.setattr(editor, "document_did_change", notify)
    controller.cycle(1, 2)
    assert editor.toPlainText() == "shortef"
    assert calls.call_count == 1
    assert notify.call_count == 1
    assert controller.can_cycle()
    controller.cycle(-1, 2)
    assert editor.toPlainText() == "initialef"
    assert controller.can_cycle()


def test_type_restore_can_cycle_back(vim_bot):
    editor, status, line, bot, controller = prepare(vim_bot, "abcd\nefgh")
    record(status, "line\n", "linewise")
    status.set_register('"', "char", VimState.NORMAL)
    bot.keyClicks(line, "p")
    controller.cycle(1)
    assert editor.toPlainText() == "abcd\nline\nefgh"
    assert controller.can_cycle()
    controller.cycle(-1)
    assert editor.toPlainText() == "achar bcd\nefgh".replace(" ", "")
    assert controller.can_cycle()


def test_payload_dot_stays_in_macro_recording(vim_bot):
    editor, status, line, bot, controller = prepare(vim_bot, "x")
    controller.put(entry=YankEntry.from_register("A", VimState.NORMAL))
    bot.keyClicks(line, "qa.q")
    assert [key.text for key in status.manager_macro.registers["a"]] == ["."]
    assert editor.toPlainText() == "xAA"
    bot.keyClicks(line, "@a")
    bot.waitUntil(lambda: not line.vim_widget.is_playing_macro, timeout=5000)
    assert editor.toPlainText() == "xAAA"


def test_reentrant_edit_outside_patch_expires_session(vim_bot):
    editor, status, line, bot, controller = prepare(vim_bot, "abcd")
    record(status, "B")
    status.set_register('"', "A", VimState.NORMAL)
    bot.keyClicks(line, "p")
    fired = []

    def edit_elsewhere(*args):
        if not fired:
            fired.append(True)
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText("external")

    editor.document().contentsChange.connect(edit_elsewhere)
    try:
        controller.cycle(1)
        assert editor.toPlainText().endswith("external")
        assert not controller.can_cycle()
    finally:
        editor.document().contentsChange.disconnect(edit_elsewhere)


def test_old_highlight_timer_cannot_clear_new_put(vim_bot, monkeypatch):
    editor, status, line, bot, controller = prepare(vim_bot)
    cursor = status.cursor
    monkeypatch.setattr(cursor, "hl_put", True)
    monkeypatch.setattr(cursor, "hl_yank_dur", 1000)
    status.set_register('"', "one", VimState.NORMAL)
    bot.keyClicks(line, "p")
    old_timer = cursor._highlight_timers["hl_put"][0]
    bot.keyClicks(line, "p")
    current = editor.get_extra_selections("hl_put")[0].cursor
    assert current.selectedText() == "one"
    old_timer.timeout.emit()
    assert editor.get_extra_selections("hl_put")
    cursor.clear_highlights()
    assert not editor.get_extra_selections("hl_put")
    assert not cursor._highlight_timers


def test_large_count_candidate_is_checked_before_expansion(vim_bot, monkeypatch):
    editor, status, line, bot, controller = prepare(vim_bot)
    record(status, "b" * 200)
    status.set_register('"', "a", VimState.NORMAL)
    monkeypatch.setattr(put_module, "SESSION_BYTE_LIMIT", 100)
    bot.keyClicks(line, "10p")
    assert controller.can_cycle()
    planner = Mock(side_effect=AssertionError("oversize candidate was expanded"))
    monkeypatch.setattr(put_module, "plan_put", planner)
    previous = editor.toPlainText()
    assert controller.cycle(1)
    assert editor.toPlainText() == previous
    assert not controller.can_cycle()
    assert planner.call_count == 0


@pytest.mark.parametrize("kind,text", [("charwise", "older"), ("linewise", "older\n")])
def test_failed_cycle_recovers_previous_patch_and_repeat(
    vim_bot, monkeypatch, kind, text
):
    editor, status, line, bot, controller = prepare(vim_bot)
    record(status, text, kind)
    status.set_register('"', "NEW", VimState.NORMAL)
    bot.keyClicks(line, "p")
    previous = editor.toPlainText()
    previous_cursor = editor.textCursor().position()
    previous_payload = status.dot_cmd.put_payload
    with monkeypatch.context() as patch:
        patch.setattr(controller, "_finish", Mock(side_effect=RuntimeError("finish")))
        controller.cycle(1)
    assert editor.toPlainText() == previous
    assert editor.textCursor().position() == previous_cursor
    assert status.dot_cmd.put_payload is previous_payload
    assert controller.can_cycle()
    assert controller.session.index == 0
    editor.undo()
    assert editor.toPlainText() == "abcd"
    editor.redo()
    assert editor.toPlainText() == previous
