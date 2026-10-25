"""Regression tests for counted Insert sessions and their last-change replay."""

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtWidgets import QApplication


@pytest.fixture
def insert_bot(vim_bot):
    """Keep the shared editor's focus, command state and tab independent."""
    _, stack, _, vim, qtbot = vim_bot
    previous_index = stack.get_stack_index()
    commandline = vim.vim_cmd.commandline
    status = vim.vim_cmd.vim_status
    commandline.setFocus()
    QCoreApplication.processEvents()
    commandline.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    status.reset_for_test()
    editor = stack.get_current_editor()
    commandline.clear()
    commandline.setFocus()
    QCoreApplication.processEvents()
    try:
        yield editor, status, commandline, qtbot
    finally:
        commandline.setFocus()
        QCoreApplication.processEvents()
        commandline.esc_pressed()
        status.disconnect_from_editor()
        stack.set_stack_index(previous_index)


def prepare_editor(insert_bot, text, position=0):
    """Set the original text and start with an empty undo history."""
    editor, status, commandline, qtbot = insert_bot
    editor.set_text(text)
    editor.document().clearUndoRedoStacks()
    status.cursor.set_cursor_pos(position)
    return editor, status, commandline, qtbot


def type_text(editor, qtbot, text):
    """Send newlines through the editor's ordinary Return handling."""
    for index, part in enumerate(text.split("\n")):
        if index:
            qtbot.keyPress(editor, Qt.Key_Return)
        qtbot.keyClicks(editor, part)


def leave_insert(commandline):
    """Use the same focus transition as the editor's Escape shortcut."""
    commandline.setFocus()
    QCoreApplication.processEvents()


@pytest.mark.parametrize(
    "original, position, command, text, before_escape, expected, cursor_position",
    [
        ("", 0, "80i", "-", "-", "-" * 80, 79),
        ("xy", 1, "3i", "-", "x-y", "x---y", 3),
        ("xy", 0, "3a", "-", "x-y", "x---y", 3),
        ("xy", 0, "3A", "-", "xy-", "xy---", 4),
        ("root", 0, "3o", "abc", "root\nabc", "root\nabc\nabc\nabc", 15),
        ("root", 0, "3O", "abc", "abc\nroot", "abc\nabc\nabc\nroot", 10),
    ],
)
def test_insert_count_applies_when_leaving_insert(
    insert_bot,
    original,
    position,
    command,
    text,
    before_escape,
    expected,
    cursor_position,
):
    """Only the first copy appears while typing; Escape commits the count."""
    editor, status, commandline, qtbot = prepare_editor(insert_bot, original, position)

    qtbot.keyClicks(commandline, command)
    type_text(editor, qtbot, text)
    assert editor.toPlainText() == before_escape

    leave_insert(commandline)

    assert editor.toPlainText() == expected
    assert editor.textCursor().position() == cursor_position
    assert status.is_normal()
    assert commandline.text() == ""


@pytest.mark.parametrize("command", ["i", "a", "A", "o", "O"])
@pytest.mark.parametrize("repeat, total_copies", [(".", 6), ("4.", 7)])
def test_dot_replays_insert_count(insert_bot, command, repeat, total_copies):
    """Dot keeps the original count, while an explicit count replaces it."""
    editor, status, commandline, qtbot = prepare_editor(insert_bot, "x")
    qtbot.keyClicks(commandline, "3" + command)
    qtbot.keyClicks(editor, "-")
    leave_insert(commandline)

    qtbot.keyClicks(commandline, repeat)

    if command == "i":
        expected = "-" * total_copies + "x"
    elif command in "aA":
        expected = "x" + "-" * total_copies
    elif command == "o":
        expected = "x" + "\n-" * total_copies
    else:
        expected = "-\n" * total_copies + "x"
    assert editor.toPlainText() == expected
    assert status.is_normal()
    assert commandline.text() == ""


@pytest.mark.parametrize("command", ["i", "a", "A", "o", "O"])
def test_counted_dot_becomes_the_next_dot_count(insert_bot, command):
    """An explicit dot count is retained by the following uncounted dot."""
    editor, status, commandline, qtbot = prepare_editor(insert_bot, "x")
    qtbot.keyClicks(commandline, "3" + command)
    qtbot.keyClicks(editor, "-")
    leave_insert(commandline)

    qtbot.keyClicks(commandline, "4..")

    if command == "i":
        expected = "-" * 11 + "x"
    elif command in "aA":
        expected = "x" + "-" * 11
    elif command == "o":
        expected = "x" + "\n-" * 11
    else:
        expected = "-\n" * 11 + "x"
    assert editor.toPlainText() == expected
    assert status.is_normal()
    assert commandline.text() == ""


@pytest.mark.parametrize("command", ["i", "a", "A", "o", "O"])
def test_counted_insert_is_one_undo_redo_change(insert_bot, command):
    """The first insertion and all count copies share one undo transaction."""
    original = "x"
    editor, status, commandline, qtbot = prepare_editor(insert_bot, original)
    qtbot.keyClicks(commandline, "3" + command)
    qtbot.keyClicks(editor, "ab")
    leave_insert(commandline)
    inserted = editor.toPlainText()
    assert inserted != original

    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == original
    qtbot.keyPress(commandline, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == inserted

    qtbot.keyClicks(commandline, "u.")
    assert editor.toPlainText() == inserted
    assert status.is_normal()


@pytest.mark.parametrize("command", ["i", "a", "A", "o", "O"])
def test_dot_insert_has_its_own_undo_step(insert_bot, command):
    """Undoing a repeated insertion leaves the preceding insertion intact."""
    editor, _, commandline, qtbot = prepare_editor(insert_bot, "x")
    qtbot.keyClicks(commandline, "3" + command)
    qtbot.keyClicks(editor, "ab")
    leave_insert(commandline)
    first_change = editor.toPlainText()

    qtbot.keyClicks(commandline, ".")
    second_change = editor.toPlainText()
    assert second_change != first_change
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == first_change
    qtbot.keyPress(commandline, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == second_change
    qtbot.keyClicks(commandline, "uu")
    assert editor.toPlainText() == "x"


@pytest.mark.parametrize("command", ["i", "a", "A", "o", "O"])
def test_backspace_repeats_only_final_inserted_text(insert_bot, command):
    """Correcting a typo does not duplicate or drop text in count copies."""
    editor, _, commandline, qtbot = prepare_editor(insert_bot, "x")
    qtbot.keyClicks(commandline, "4" + command)
    qtbot.keyClicks(editor, "ab")
    qtbot.keyPress(editor, Qt.Key_Backspace)
    qtbot.keyClicks(editor, "c")
    leave_insert(commandline)

    if command == "i":
        expected = "ac" * 4 + "x"
    elif command in "aA":
        expected = "x" + "ac" * 4
    elif command == "o":
        expected = "x" + "\nac" * 4
    else:
        expected = "ac\n" * 4 + "x"
    assert editor.toPlainText() == expected

    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == "x"
    qtbot.keyPress(commandline, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == expected

    qtbot.keyClicks(commandline, "0." if command == "i" else ".")
    assert editor.toPlainText().count("ac") == 8


@pytest.mark.parametrize("command", ["i", "a", "A"])
def test_empty_insert_and_repeated_escape_do_not_leak_count(insert_bot, command):
    """An empty cancelled insertion cannot multiply the following session."""
    editor, status, commandline, qtbot = prepare_editor(insert_bot, "x")
    qtbot.keyClicks(commandline, "80" + command)
    leave_insert(commandline)
    commandline.esc_pressed()
    commandline.esc_pressed()
    assert editor.toPlainText() == "x"

    qtbot.keyClicks(commandline, "i")
    qtbot.keyClicks(editor, "z")
    leave_insert(commandline)
    commandline.esc_pressed()
    assert editor.toPlainText() == "zx"
    assert status.is_normal()


@pytest.mark.parametrize(
    "command, expected",
    [("3o", "root\n\n\n"), ("3O", "\n\n\nroot")],
)
def test_counted_open_without_typing_creates_empty_lines(insert_bot, command, expected):
    """Opening lines still honors count when no text was typed."""
    editor, _, commandline, qtbot = prepare_editor(insert_bot, "root")
    qtbot.keyClicks(commandline, command)
    leave_insert(commandline)
    commandline.esc_pressed()
    assert editor.toPlainText() == expected

    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == "root"
    qtbot.keyPress(commandline, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == expected


@pytest.mark.parametrize(
    "command, expected",
    [
        ("2o", "root\none\ntwo\none\ntwo"),
        ("2O", "one\ntwo\none\ntwo\nroot"),
    ],
)
def test_counted_open_repeats_multiline_input(insert_bot, command, expected):
    """A count repeats the entire inserted block in document order."""
    editor, _, commandline, qtbot = prepare_editor(insert_bot, "root")
    qtbot.keyClicks(commandline, command)
    type_text(editor, qtbot, "one\ntwo")
    leave_insert(commandline)
    assert editor.toPlainText() == expected


def test_counted_open_preserves_autoindent(insert_bot, monkeypatch):
    """Count copies retain the indentation supplied by the editor's Return."""
    editor, _, commandline, qtbot = prepare_editor(insert_bot, "if ready:")
    monkeypatch.setattr(editor, "indent_chars", "  ")
    qtbot.keyClicks(commandline, "3o")
    qtbot.keyClicks(editor, "abc")
    leave_insert(commandline)
    assert editor.toPlainText() == "if ready:\n  abc\n  abc\n  abc"


@pytest.mark.parametrize("key", [Qt.Key_Right, Qt.Key_End, Qt.Key_Down])
def test_insert_navigation_does_not_repeat_original_text(insert_bot, key):
    """Moving through existing text never turns it into counted input."""
    editor, _, commandline, qtbot = prepare_editor(insert_bot, "abc\ndef")
    qtbot.keyClicks(commandline, "3i")
    qtbot.keyPress(editor, key)
    leave_insert(commandline)
    assert editor.toPlainText() == "abc\ndef"

    qtbot.keyClicks(commandline, ".")
    assert editor.toPlainText() == "abc\ndef"


def test_navigation_between_edits_cancels_insert_count(insert_bot):
    """Text typed after a movement is inserted once without copying the source."""
    editor, _, commandline, qtbot = prepare_editor(insert_bot, "abc")
    qtbot.keyClicks(commandline, "3i")
    qtbot.keyClicks(editor, "X")
    qtbot.keyPress(editor, Qt.Key_Right)
    qtbot.keyClicks(editor, "Y")
    leave_insert(commandline)
    assert editor.toPlainText() == "XaYbc"


def test_editor_cursor_move_does_not_repeat_original_text(insert_bot):
    """Cursor changes outside the key recorder also protect the source text."""
    editor, _, commandline, qtbot = prepare_editor(insert_bot, "abc")
    qtbot.keyClicks(commandline, "3i")
    cursor = editor.textCursor()
    cursor.setPosition(2)
    editor.setTextCursor(cursor)
    leave_insert(commandline)
    assert editor.toPlainText() == "abc"


@pytest.mark.parametrize("command", ["i", "a", "A"])
def test_erasing_all_inserted_text_does_not_repeat_or_leak_count(insert_bot, command):
    """Deleting the whole input leaves an empty insertion for count and dot."""
    editor, _, commandline, qtbot = prepare_editor(insert_bot, "x")
    qtbot.keyClicks(commandline, "3" + command)
    qtbot.keyClicks(editor, "ab")
    qtbot.keyPress(editor, Qt.Key_Backspace)
    qtbot.keyPress(editor, Qt.Key_Backspace)
    leave_insert(commandline)
    commandline.esc_pressed()
    assert editor.toPlainText() == "x"

    qtbot.keyClicks(commandline, ".")
    assert editor.toPlainText() == "x"


def test_switching_editor_cancels_pending_insert_count(insert_bot):
    """An unfinished count cannot write into the next active document."""
    editor, status, commandline, qtbot = prepare_editor(insert_bot, "abc")
    qtbot.keyClicks(commandline, "3i")
    qtbot.keyClicks(editor, "X")
    stack = status.get_editorstack()
    stack.set_stack_index(1)
    other_editor = stack.get_current_editor()
    original_other_text = other_editor.toPlainText()
    leave_insert(commandline)
    assert editor.toPlainText() == "Xabc"
    assert other_editor.toPlainText() == original_other_text
    assert status.insert_cmd is None

    # The original document's partial edit still has a closed undo block.
    editor.undo()
    assert editor.toPlainText() == "abc"


def test_counted_insert_updates_editor_before_escape(insert_bot):
    """Each key delivers document updates used by drawing and completion."""
    editor, _, commandline, qtbot = prepare_editor(insert_bot, "x")
    updates = []

    def record_update():
        updates.append(editor.toPlainText())

    editor.document().contentsChanged.connect(record_update)
    try:
        qtbot.keyClicks(commandline, "3i")
        qtbot.keyClicks(editor, "a")
        assert updates[-1] == "ax"
        qtbot.keyClicks(editor, "b")
        assert updates[-1] == "abx"
        leave_insert(commandline)
        assert updates[-1] == "abababx"
    finally:
        editor.document().contentsChanged.disconnect(record_update)


def test_counted_context_menu_paste_shares_one_undo_step(insert_bot):
    """Pasting without a key event also joins the count copies to its undo."""
    editor, _, commandline, qtbot = prepare_editor(insert_bot, "x")
    clipboard = QApplication.clipboard()
    previous_text = clipboard.text()
    try:
        clipboard.setText("ab")
        qtbot.keyClicks(commandline, "3i")
        editor.paste()
        leave_insert(commandline)
        assert editor.toPlainText() == "abababx"
        qtbot.keyClicks(commandline, "u")
        assert editor.toPlainText() == "x"
        qtbot.keyPress(commandline, Qt.Key_R, Qt.ControlModifier)
        assert editor.toPlainText() == "abababx"
    finally:
        clipboard.setText(previous_text)
