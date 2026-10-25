"""Regression tests for Vim's named, numbered and special registers."""

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtWidgets import QApplication

# Project Libraries
from spyder_okvim.vim.state import VimState


@pytest.fixture
def register_bot(vim_bot):
    """Isolate the active editor, registers, command state and clipboard."""
    _, stack, _, vim, qtbot = vim_bot
    previous_index = stack.get_stack_index()
    commandline = vim.vim_cmd.commandline
    status = vim.vim_cmd.vim_status
    clipboard_text = QApplication.clipboard().text()
    commandline.setFocus()
    QCoreApplication.processEvents()
    commandline.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    status.reset_for_test()
    editor = stack.get_current_editor()
    commandline.clear()
    commandline.setFocus()
    try:
        yield editor, status, commandline, qtbot
    finally:
        commandline.setFocus()
        QCoreApplication.processEvents()
        commandline.esc_pressed()
        status.disconnect_from_editor()
        stack.set_stack_index(previous_index)
        QApplication.clipboard().setText(clipboard_text)


def prepare_editor(register_bot, text):
    """Set document text and seed the last yank independently of named writes."""
    editor, status, commandline, qtbot = register_bot
    editor.set_text(text)
    status.cursor.set_cursor_pos(0)
    status.set_register('"', "previous", VimState.NORMAL)
    status.set_register("0", "last yank", VimState.NORMAL)
    return editor, status, commandline, qtbot


def register_contents(status):
    """Take value snapshots so later register writes cannot mutate expectations."""
    return {
        name: (info.content, info.type) for name, info in status.register_dict.items()
    }


@pytest.mark.parametrize(
    "command, content, register_type, expected",
    [
        ('"ayyj"Ayy', "alpha\nbeta\n", VimState.VLINE, "alpha\nbeta\ntail"),
        ('"aylj"Ayl', "ab", VimState.NORMAL, "alpha\nbeta\ntail"),
        ('"aylj"Ayy', "a\nbeta\n", VimState.VLINE, "alpha\nbeta\ntail"),
        ('"ayyj"Ayl', "alpha\nb\n", VimState.VLINE, "alpha\nbeta\ntail"),
        ('v$"ayj"Ayy', "alpha\n\nbeta\n", VimState.VLINE, "alpha\nbeta\ntail"),
        ('"ayyjv$"Ay', "alpha\nbeta\n\n", VimState.VLINE, "alpha\nbeta\ntail"),
        ('"Ayy', "alpha\n", VimState.VLINE, "alpha\nbeta\ntail"),
    ],
)
def test_uppercase_yank_appends_to_lowercase_register(
    register_bot, command, content, register_type, expected
):
    """Uppercase writes append, including mixed character and linewise yanks."""
    editor, status, commandline, qtbot = prepare_editor(
        register_bot, "alpha\nbeta\ntail"
    )

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == expected
    assert status.register_dict["a"].content == content
    assert status.register_dict["a"].type == register_type
    assert status.register_dict['"'].content == content
    assert status.register_dict['"'].type == register_type
    assert status.register_dict["0"].content == "last yank"
    assert "A" not in status.register_dict
    assert commandline.text() == ""
    assert status.is_normal()


@pytest.mark.parametrize("paste", ["p", '"ap', '"Ap'])
def test_appended_register_is_available_to_default_and_named_paste(register_bot, paste):
    """Every spelling of the appended register pastes the complete line content."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "one\ntwo\ntail")

    qtbot.keyClicks(commandline, '"ayyj"Ayy' + paste)

    assert editor.toPlainText() == "one\ntwo\none\ntwo\ntail"
    assert status.register_dict["a"].content == "one\ntwo\n"
    assert status.register_dict['"'].content == "one\ntwo\n"


@pytest.mark.parametrize(
    "text, command, content, register_type, after_command, after_paste",
    [
        ("abcd", '"ayl', "a", VimState.NORMAL, "abcd", "aabcd"),
        ("abcd", 'vl"ay', "ab", VimState.NORMAL, "abcd", "aabbcd"),
        ("one\ntwo", 'V"ay', "one\n", VimState.VLINE, "one\ntwo", "one\none\ntwo"),
        ("abcd", '"ax', "a", VimState.NORMAL, "bcd", "bacd"),
        ("abcd", 'vl"ad', "ab", VimState.NORMAL, "cd", "cabd"),
        ("one\ntwo", '"add', "one\n", VimState.VLINE, "two", "two\none"),
        ("one\ntwo", 'V"ad', "one\n", VimState.VLINE, "two", "two\none"),
    ],
)
def test_named_yank_and_delete_update_default_paste(
    register_bot, text, command, content, register_type, after_command, after_paste
):
    """Named operators update the unnamed register in all three selection modes."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, text)

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == after_command
    assert status.register_dict["a"].content == content
    assert status.register_dict['"'].content == content
    assert status.register_dict['"'].type == register_type
    assert status.register_dict["0"].content == "last yank"

    qtbot.keyClicks(commandline, "p")

    assert editor.toPlainText() == after_paste
    assert commandline.text() == ""
    assert status.is_normal()


def test_numbered_delete_history_rotates_and_discards_oldest(register_bot):
    """Each line deletion shifts history once and retains only nine entries."""
    editor, status, commandline, qtbot = prepare_editor(
        register_bot, "\n".join(f"line {index}" for index in range(11))
    )

    qtbot.keyClicks(commandline, "dd" * 10)

    assert editor.toPlainText() == "line 10"
    for number in range(1, 10):
        info = status.register_dict[str(number)]
        assert info.content == f"line {10 - number}\n"
        assert info.type == VimState.VLINE
    assert status.register_dict['"'].content == "line 9\n"
    assert status.register_dict["0"].content == "last yank"

    qtbot.keyClicks(commandline, '"9P')

    assert editor.toPlainText() == "line 1\nline 10"


def test_named_append_delete_history_stores_each_deletion(register_bot):
    """History keeps the newly deleted text while the named register accumulates."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "one\ntwo\nthree")

    qtbot.keyClicks(commandline, '"add"Add')

    assert editor.toPlainText() == "three"
    assert status.register_dict["a"].content == "one\ntwo\n"
    assert status.register_dict['"'].content == "one\ntwo\n"
    assert status.register_dict["1"].content == "two\n"
    assert status.register_dict["2"].content == "one\n"
    assert status.register_dict["0"].content == "last yank"


def test_explicit_numbered_delete_writes_before_history_rotation(register_bot):
    """A numbered destination participates in the same later history shift."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "one\ntwo")
    for number in range(1, 4):
        status.set_register(str(number), f"saved {number}\n", VimState.VLINE)

    qtbot.keyClicks(commandline, '"2dd')

    assert editor.toPlainText() == "two"
    assert status.register_dict["1"].content == "one\n"
    assert status.register_dict["2"].content == "saved 1\n"
    assert status.register_dict["3"].content == "one\n"
    assert status.register_dict["4"].content == "saved 3\n"
    assert status.register_dict['"'].content == "one\n"
    assert status.register_dict["0"].content == "last yank"


def test_multiline_character_delete_history_preserves_register_type(register_bot):
    """History retains characterwise ranges when later line deletions shift them."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "ab\ncd\nef\ngh")

    qtbot.keyClicks(commandline, "2Ddd")

    assert editor.toPlainText() == "ef\ngh"
    assert status.register_dict["1"].content == "\n"
    assert status.register_dict["1"].type == VimState.VLINE
    assert status.register_dict["2"].content == "ab\ncd"
    assert status.register_dict["2"].type == VimState.NORMAL


@pytest.mark.parametrize("command", ['"acc', 'V"ac'])
def test_linewise_change_updates_delete_history(register_bot, command):
    """Changes use the same numbered history as deletes and preserve the yank."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "one\ntwo")

    qtbot.keyClicks(commandline, command)
    qtbot.keyClicks(editor, "new")
    commandline.setFocus()
    QCoreApplication.processEvents()

    assert editor.toPlainText() == "new\ntwo"
    assert status.register_dict["a"].content == "one\n"
    assert status.register_dict['"'].content == "one\n"
    assert status.register_dict["1"].content == "one\n"
    assert status.register_dict["1"].type == VimState.VLINE
    assert status.register_dict["0"].content == "last yank"
    assert status.is_normal()


@pytest.mark.parametrize("command, named", [("x", False), ('"ax', True)])
def test_small_delete_keeps_numbered_history(register_bot, command, named):
    """Single-line deletes use the small-delete register only without a name."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "abcd")
    status.set_register("1", "older\n", VimState.VLINE)
    status.set_register("-", "small", VimState.NORMAL)

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == "bcd"
    assert status.register_dict['"'].content == "a"
    assert status.register_dict["1"].content == "older\n"
    assert status.register_dict["0"].content == "last yank"
    assert status.register_dict["-"].content == ("small" if named else "a")


@pytest.mark.parametrize("command", ["d%", "c%", '"ad%', '"ac%'])
def test_matching_bracket_delete_uses_numbered_history(register_bot, command):
    """Bracket motions preserve small deletions in the numbered ring as in Vim."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "(ab)tail")
    status.set_register("1", "older\n", VimState.VLINE)
    status.set_register("-", "small", VimState.NORMAL)

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == "tail"
    assert status.register_dict['"'].content == "(ab)"
    assert status.register_dict["1"].content == "(ab)"
    assert status.register_dict["1"].type == VimState.NORMAL
    assert status.register_dict["2"].content == "older\n"
    assert status.register_dict["2"].type == VimState.VLINE
    assert status.register_dict["-"].content == (
        "small" if command[0] == '"' else "(ab)"
    )


@pytest.mark.parametrize("command", ['"_yy', '"_dd', '"_x', 'v"_y', 'v"_d', 'V"_d'])
def test_black_hole_operations_leave_every_register_unchanged(register_bot, command):
    """Black-hole yanks and deletes discard text without touching any history."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "one\ntwo")
    for name in "a123456789-":
        status.set_register(name, f"saved {name}", VimState.NORMAL)
    QApplication.clipboard().setText("clipboard")
    before = register_contents(status)

    qtbot.keyClicks(commandline, command)

    assert register_contents(status) == before
    assert QApplication.clipboard().text() == "clipboard"
    assert commandline.text() == ""
    assert status.is_normal()


def test_black_hole_paste_is_empty(register_bot):
    """Reading the black-hole register cannot recover previously discarded text."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "abcd")

    qtbot.keyClicks(commandline, '"_x"_p')

    assert editor.toPlainText() == "bcd"
    assert status.register_dict['"'].content == "previous"


@pytest.mark.parametrize(
    "command, expected, content",
    [('"+yy', "one\ntwo", "one\n"), ('"+dd', "two", "one\n")],
)
def test_clipboard_operators_update_unnamed_register(
    register_bot, command, expected, content
):
    """Clipboard writes also provide the most recent text for default paste."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "one\ntwo")

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == expected
    assert QApplication.clipboard().text() == content
    assert status.register_dict['"'].content == content
    assert status.register_dict['"'].type == VimState.VLINE
    assert status.register_dict["0"].content == "last yank"


def test_unnamed_yank_still_updates_zero_and_delete_preserves_it(register_bot):
    """The yank register remains available after later named and unnamed deletes."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "one\ntwo\nthree")

    qtbot.keyClicks(commandline, 'yydd"add"0P')

    assert editor.toPlainText() == "one\nthree"
    assert status.register_dict["0"].content == "one\n"
    assert status.register_dict["0"].type == VimState.VLINE
    assert status.register_dict["1"].content == "two\n"
    assert status.register_dict["2"].content == "one\n"


def test_dot_repeats_uppercase_append_delete(register_bot):
    """Dot must preserve the uppercase write intent when appending again."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "abcd")
    status.set_register("a", "seed", VimState.NORMAL)

    qtbot.keyClicks(commandline, '"Ax.')

    assert editor.toPlainText() == "cd"
    assert status.register_dict["a"].content == "seedab"
    assert status.register_dict['"'].content == "seedab"
    assert commandline.text() == ""
    assert status.is_normal()


def test_dot_repeats_black_hole_delete(register_bot):
    """Repeated black-hole deletion must continue to leave all registers alone."""
    editor, status, commandline, qtbot = prepare_editor(register_bot, "one\ntwo\nthree")
    before = register_contents(status)

    qtbot.keyClicks(commandline, '"_dd.')

    assert editor.toPlainText() == "three"
    assert register_contents(status) == before
    assert commandline.text() == ""
    assert status.is_normal()


@pytest.mark.parametrize("register_prefix", ["", '"a'])
@pytest.mark.parametrize(
    "setup, command, deleted, expected",
    [
        (("/target", Qt.Key_Return, "0"), "dn", "abc ", "target def target tail"),
        (("/target", Qt.Key_Return, "w"), "dN", "target ", "abc def target tail"),
        ((), "d/target", "abc ", "target def target tail"),
        (("3lma0",), "d`a", "abc ", "target def target tail"),
    ],
)
def test_search_and_mark_deletes_use_numbered_history(
    register_bot, register_prefix, setup, command, deleted, expected
):
    """Single-line search and mark operators also rotate the delete history."""
    editor, status, commandline, qtbot = prepare_editor(
        register_bot, "abc target def target tail"
    )
    status.set_register("1", "older\n", VimState.VLINE)
    status.set_register("-", "small", VimState.NORMAL)

    for key in setup:
        if isinstance(key, str):
            qtbot.keyClicks(commandline, key)
        else:
            qtbot.keyClick(commandline, key)
    qtbot.keyClicks(commandline, register_prefix + command)
    if command.startswith("d/"):
        qtbot.keyClick(commandline, Qt.Key_Return)

    assert editor.toPlainText() == expected
    assert status.register_dict['"'].content == deleted
    assert status.register_dict["1"].content == deleted
    assert status.register_dict["1"].type == VimState.NORMAL
    assert status.register_dict["2"].content == "older\n"
    assert status.register_dict["2"].type == VimState.VLINE
    assert status.register_dict["-"].content == (
        "small" if register_prefix else deleted
    )
    assert status.register_dict["0"].content == "last yank"
    if register_prefix:
        assert status.register_dict["a"].content == deleted
    assert commandline.text() == ""
    assert status.is_normal()
