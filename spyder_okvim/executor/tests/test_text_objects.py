"""Regression tests for paragraph, WORD and backtick text objects."""

# Third Party Libraries
import pytest

# Project Libraries
from spyder_okvim.vim import VimState


@pytest.fixture
def text_object_bot(vim_bot):
    """Isolate commands from the active tab and previous Insert sessions."""
    _, stack, _, vim, qtbot = vim_bot
    previous_index = stack.get_stack_index()
    commandline = vim.vim_cmd.commandline
    status = vim.vim_cmd.vim_status
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
        commandline.esc_pressed()
        status.disconnect_from_editor()
        stack.set_stack_index(previous_index)


def prepare_text_object(text_object_bot, text, position=0):
    """Load text and place the cursor before executing a text object."""
    editor, status, commandline, qtbot = text_object_bot
    editor.set_text(text)
    status.cursor.set_cursor_pos(position)
    commandline.setFocus()
    return editor, status, commandline, qtbot


@pytest.mark.parametrize(
    "text, position, command, expected",
    [
        ("one.two   next", 1, "yaW", "one.two   "),
        ("one two.three", 5, "yaW", " two.three"),
        ("one\t\ttwo.three next", 4, "yaW", "\t\ttwo.three"),
        ("one.two next.third last", 0, "y2aW", "one.two next.third "),
        ("one two three four five", 0, "2y2aW", "one two three four "),
        ("one.two\n  next.third last", 0, "y2aW", "one.two\n  next.third"),
        ("one.two\n  next.third last", 0, "yaW", "one.two"),
        ("", 0, "yaW", ""),
    ],
)
def test_around_word_yank(text_object_bot, text, position, command, expected):
    """WORDs include punctuation and select surrounding whitespace like Vim."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, text, position
    )

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == text
    assert status.get_register().content == expected
    assert status.get_register().type == VimState.NORMAL
    assert commandline.text() == ""
    assert status.sub_mode is None


@pytest.mark.parametrize(
    "text, position, command, expected, removed",
    [
        ("one.two   next", 4, "caW", "next", "one.two   "),
        ("one two.three", 8, "caW", "one", " two.three"),
        ("one   two.three next", 4, "daW", "one next", "   two.three"),
        ("one.two next.third last", 0, "d2aW", "last", "one.two next.third "),
    ],
)
def test_around_word_edit(text_object_bot, text, position, command, expected, removed):
    """Changing and deleting a WORD use the same range as yanking it."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, text, position
    )

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == expected
    assert status.get_register().content == removed
    assert commandline.text() == ""
    assert status.sub_mode is None


@pytest.mark.parametrize(
    "text, position, command, selected",
    [
        ("one.two   next", 4, "vaW", "one.two   "),
        ("one two.three", 8, "vaW", " two.three"),
        ("one   two.three next", 4, "vaW", "   two.three"),
        ("one.two next.third last", 0, "v2aW", "one.two next.third "),
    ],
)
def test_around_word_visual(text_object_bot, text, position, command, selected):
    """Visual selection can be expanded to an entire WORD and whitespace."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, text, position
    )

    qtbot.keyClicks(commandline, command)

    selection = editor.get_extra_selections("vim_selection")[0]
    assert selection.cursor.selectedText() == selected
    assert status.vim_state == VimState.VISUAL
    assert commandline.text() == ""


@pytest.mark.parametrize(
    "text, position, command, expected, copied",
    [
        ("left `body` right", 7, "yi`", "left `body` right", "body"),
        ("left `body` right", 10, "yi`", "left `body` right", "body"),
        ("left `body` right", 0, "yi`", "left `body` right", "body"),
        ("left `body`   right", 7, "ya`", "left `body`   right", "`body`   "),
        ("left `body`", 7, "ya`", "left `body`", " `body`"),
        ("left `body` right", 7, "di`", "left `` right", "body"),
        ("left `body` right", 7, "ci`", "left `` right", "body"),
        ("left `body`   right", 7, "da`", "left right", "`body`   "),
        ("left `body`", 7, "da`", "left", " `body`"),
        ("left `` right", 5, "da`", "left right", "`` "),
    ],
)
def test_backtick_operator(text_object_bot, text, position, command, expected, copied):
    """Backticks support inner and surrounding objects for each operator."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, text, position
    )

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == expected
    assert status.get_register().content == copied
    assert status.get_register().type == VimState.NORMAL
    assert commandline.text() == ""
    assert status.sub_mode is None


@pytest.mark.parametrize(
    "text, position, command, selected",
    [
        ("left `body` right", 7, "vi`", "body"),
        ("left `body` right", 10, "vi`", "body"),
        ("left `body`   right", 7, "va`", "`body`   "),
        ("left `body`", 7, "va`", " `body`"),
        ("`first` `second`", 10, "vi`", "second"),
    ],
)
def test_backtick_visual(text_object_bot, text, position, command, selected):
    """Visual backtick objects select the intended pair and surrounding spaces."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, text, position
    )

    qtbot.keyClicks(commandline, command)

    selection = editor.get_extra_selections("vim_selection")[0]
    assert selection.cursor.selectedText() == selected
    assert status.vim_state == VimState.VISUAL
    assert commandline.text() == ""


@pytest.mark.parametrize("text", ["", "plain text", "left `body", "`left\nright`"])
@pytest.mark.parametrize("command", ["di`", "da`"])
def test_missing_backtick_pair_is_noop(text_object_bot, text, command):
    """An absent or unmatched pair cannot delete text or replace a register."""
    editor, status, commandline, qtbot = prepare_text_object(text_object_bot, text)
    status.set_register('"', "saved", VimState.NORMAL)

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == text
    assert status.get_register().content == "saved"
    assert commandline.text() == ""
    assert status.sub_mode is None


@pytest.mark.parametrize("quote", ["'", '"'])
@pytest.mark.parametrize("object_command", ["di", "da"])
def test_unclosed_quote_is_noop(text_object_bot, quote, object_command):
    """Existing quote objects also reject a missing closing delimiter safely."""
    text = "left " + quote + "body"
    editor, status, commandline, qtbot = prepare_text_object(text_object_bot, text)
    status.set_register('"', "saved", VimState.NORMAL)

    qtbot.keyClicks(commandline, object_command + quote)

    assert editor.toPlainText() == text
    assert status.get_register().content == "saved"
    assert commandline.text() == ""
    assert status.sub_mode is None


def test_empty_backtick_change_enters_insert(text_object_bot):
    """An empty quoted string is a valid insertion target."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, "left `` right", 5
    )

    qtbot.keyClicks(commandline, "ci`")
    qtbot.keyClicks(editor, "value")
    commandline.esc_pressed()

    assert editor.toPlainText() == "left `value` right"
    assert status.sub_mode is None
    assert commandline.text() == ""


@pytest.mark.parametrize(
    "text, position, command, copied",
    [
        ("alpha\nbeta\n\nomega", 7, "yip", "alpha\nbeta\n"),
        ("alpha\nbeta\n\nomega", 7, "yap", "alpha\nbeta\n\n"),
        ("alpha\n\nomega", 9, "yap", "\nomega\n"),
        ("alpha\n\n\nomega\n\nlast", 7, "yip", "\n\n"),
        ("alpha\n\n\nomega\n\nlast", 7, "yap", "\n\nomega\n"),
        ("alpha\n\n\nomega\n\nlast", 0, "y2ip", "alpha\n\n\n"),
        ("alpha\n\n\nomega\n\nlast", 0, "y3ip", "alpha\n\n\nomega\n"),
        ("alpha\n\n\nomega\n\nlast", 0, "y2ap", "alpha\n\n\nomega\n\n"),
        ("alpha\n\n\nomega\n\nlast", 7, "y2ap", "\n\nomega\n\nlast\n"),
        ("alpha\n\nomega\n\nlast", 0, "2y2ip", "alpha\n\nomega\n\n"),
        ("alpha\n \t\nomega", 0, "yip", "alpha\n"),
        ("alpha\n \t\nomega", 6, "yip", " \t\n"),
        ("single paragraph", 4, "yip", "single paragraph\n"),
        ("single paragraph", 4, "yap", "single paragraph\n"),
        ("", 0, "yip", "\n"),
    ],
)
def test_paragraph_yank(text_object_bot, text, position, command, copied):
    """Paragraph objects and their counts produce linewise registers."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, text, position
    )

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == text
    assert status.get_register().content == copied
    assert status.get_register().type == VimState.VLINE
    assert commandline.text() == ""
    assert status.sub_mode is None


@pytest.mark.parametrize(
    "text, position, command, expected, removed",
    [
        ("alpha\nbeta\n\nomega", 7, "cip", "\n\nomega", "alpha\nbeta\n"),
        ("alpha\nbeta\n\nomega", 7, "dap", "omega", "alpha\nbeta\n\n"),
        ("alpha\n\nomega", 9, "dap", "alpha", "\nomega\n"),
        ("alpha\n\n\nomega", 7, "dip", "alpha\nomega", "\n\n"),
        ("alpha\n\n\nomega", 7, "dap", "alpha", "\n\nomega\n"),
        ("alpha\n\nomega\n\nlast", 0, "2dip", "omega\n\nlast", "alpha\n\n"),
        ("alpha\n\nomega\n\nlast", 0, "d2ip", "omega\n\nlast", "alpha\n\n"),
        ("alpha\n\nomega\n\nlast", 0, "d2ap", "last", "alpha\n\nomega\n\n"),
        ("single paragraph", 4, "dip", "", "single paragraph\n"),
    ],
)
def test_paragraph_edit(text_object_bot, text, position, command, expected, removed):
    """Delete/change respect full lines, surrounding blanks and one-step undo."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, text, position
    )

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == expected
    assert status.get_register().content == removed
    assert status.get_register().type == VimState.VLINE
    assert commandline.text() == ""
    assert status.sub_mode is None

    commandline.esc_pressed()
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == text


@pytest.mark.parametrize("command", ["cip", "vipc", "Vipc"])
def test_paragraph_change_inserts_replacement(text_object_bot, command):
    """Replacing a paragraph keeps its separator in Normal and Visual modes."""
    text = "alpha\nbeta\n\nomega"
    editor, status, commandline, qtbot = prepare_text_object(text_object_bot, text, 7)

    qtbot.keyClicks(commandline, command)
    qtbot.keyClicks(editor, "replacement")
    commandline.esc_pressed()

    assert editor.toPlainText() == "replacement\n\nomega"
    assert status.is_normal()


@pytest.mark.parametrize(
    "text, position, command",
    [
        ("single paragraph", 0, "d2ip"),
        ("single paragraph", 0, "d2ap"),
        ("alpha\n\n", 7, "dap"),
        ("", 0, "dap"),
        ("\n\n", 0, "dap"),
        (" \t", 0, "dap"),
    ],
)
def test_invalid_paragraph_range_is_noop(text_object_bot, text, position, command):
    """Unfulfilled counts and trailing blank paragraphs leave text/registers alone."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, text, position
    )
    status.set_register('"', "saved", VimState.NORMAL)

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == text
    assert status.get_register().content == "saved"
    assert commandline.text() == ""
    assert status.sub_mode is None


@pytest.mark.parametrize(
    "command, selected, copied, remaining",
    [
        ("vip", "alpha\nbeta", "alpha\nbeta\n", "\nomega"),
        ("vap", "alpha\nbeta\n", "alpha\nbeta\n\n", "omega"),
        ("Vip", "alpha\nbeta", "alpha\nbeta\n", "\nomega"),
        ("Vap", "alpha\nbeta\n", "alpha\nbeta\n\n", "omega"),
    ],
)
@pytest.mark.parametrize("operator", ["y", "d"])
def test_visual_paragraph_is_linewise(
    text_object_bot, command, selected, copied, remaining, operator
):
    """Visual paragraphs switch to line selection before yanking or deleting."""
    text = "alpha\nbeta\n\nomega"
    editor, status, commandline, qtbot = prepare_text_object(text_object_bot, text, 7)

    qtbot.keyClicks(commandline, command)

    selection = editor.get_extra_selections("vim_selection")[0]
    assert selection.cursor.selectedText().replace("\u2029", "\n") == selected
    assert status.vim_state == VimState.VLINE

    qtbot.keyClicks(commandline, operator)

    assert editor.toPlainText() == (text if operator == "y" else remaining)
    assert status.get_register().content == copied
    assert status.get_register().type == VimState.VLINE
    assert status.is_normal()


@pytest.mark.parametrize("command", ["yi`", "vi`"])
def test_backtick_escapes_and_unicode_positions(text_object_bot, command):
    """Escaped backticks and UTF-16 cursor offsets preserve the entire string."""
    text = "\U0001f600 `a\\`b` next"
    editor, status, commandline, qtbot = prepare_text_object(text_object_bot, text, 5)

    qtbot.keyClicks(commandline, command)

    if command.startswith("y"):
        assert status.get_register().content == "a\\`b"
    else:
        selection = editor.get_extra_selections("vim_selection")[0]
        assert selection.cursor.selectedText() == "a\\`b"


@pytest.mark.parametrize(
    "text, position, command, expected",
    [
        ("one.two\n\nnext last", 0, "y2aW", "one.two\n\nnext"),
        ("one.two\n\nnext last", 0, "y3aW", "one.two\n\nnext last"),
        ("one.two\n\n\nnext last", 0, "y2aW", "one.two\n\n"),
        ("one.two\n\n\nnext last", 0, "y3aW", "one.two\n\n\nnext "),
        ("\nnext last", 0, "yaW", "\nnext"),
        ("\n\nnext last", 0, "yaW", "\n"),
        ("\n\nnext last", 1, "yaW", "\nnext"),
        ("one   \n\n  next last", 3, "yaW", "   \n"),
        ("one   \n\n  next last", 3, "y2aW", "   \n\n  next"),
        ("one   \n\n  next last", 3, "y3aW", "   \n\n  next last"),
        ("\n\n", 1, "yaW", "\n"),
    ],
)
def test_around_word_blank_line_boundaries(
    text_object_bot, text, position, command, expected
):
    """Empty lines stop whitespace objects without losing WORD counts."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, text, position
    )

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == text
    assert status.get_register().content == expected
    assert status.get_register().type == VimState.NORMAL
    assert commandline.text() == ""
    assert status.sub_mode is None


@pytest.mark.parametrize("operator", ["y", "v"])
@pytest.mark.parametrize(
    "text, position, object_command, expected",
    [
        ("`first`  `second`", 7, "i`", "  "),
        ("`first`  `second`", 8, "a`", "`  `"),
        ("`first`  `second`", 6, "i`", "first"),
        ("`first`  `second`", 9, "i`", "second"),
        ("`first` gap `second`", 9, "i`", " gap "),
        ("\U0001f600 `foo`", 4, "a`", " `foo`"),
    ],
)
def test_backtick_pair_and_gap_boundaries(
    text_object_bot, operator, text, position, object_command, expected
):
    """Between strings, choose the adjacent delimiters like other quote objects."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, text, position
    )

    qtbot.keyClicks(commandline, operator + object_command)

    if operator == "y":
        assert status.get_register().content == expected
    else:
        selection = editor.get_extra_selections("vim_selection")[0]
        assert selection.cursor.selectedText() == expected


@pytest.mark.parametrize("command, selected", [("Vi`", "body"), ("VaW", "`body` ")])
def test_vline_to_character_text_object(text_object_bot, command, selected):
    """Character objects entered from Visual Line restore character selection."""
    editor, status, commandline, qtbot = prepare_text_object(
        text_object_bot, "left `body` right", 7
    )

    qtbot.keyClicks(commandline, command)

    selection = editor.get_extra_selections("vim_selection")[0]
    assert selection.cursor.selectedText() == selected
    assert status.vim_state == VimState.VISUAL
