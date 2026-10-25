"""Regression tests for shifts and reindentation using document settings."""

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt


INDENT_SETTINGS = [
    pytest.param("  ", 4, id="two-spaces"),
    pytest.param("    ", 4, id="four-spaces"),
    pytest.param("\t", 4, id="tabs-width-four"),
    pytest.param("\t", 8, id="tabs-width-eight"),
]


@pytest.fixture
def indentation_bot(vim_bot):
    """Use a known editor and restore the active tab after each case."""
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
        yield stack, editor, status, commandline, qtbot
    finally:
        commandline.esc_pressed()
        status.disconnect_from_editor()
        stack.set_stack_index(previous_index)


def prepare_editor(indentation_bot, monkeypatch, text, indent, tab_width):
    """Set document options without leaking them to the session fixture."""
    _, editor, status, commandline, qtbot = indentation_bot
    monkeypatch.setattr(editor, "indent_chars", indent)
    monkeypatch.setattr(editor, "tab_stop_width_spaces", tab_width)
    editor.set_text(text)
    status.cursor.set_cursor_pos(0)
    return editor, status, commandline, qtbot


@pytest.mark.parametrize("indent, tab_width", INDENT_SETTINGS)
@pytest.mark.parametrize(
    "command, forward, line_count",
    [
        pytest.param(">>", True, 1, id="normal-right"),
        pytest.param("<<", False, 1, id="normal-left"),
        pytest.param(">j", True, 2, id="motion-right"),
        pytest.param("<j", False, 2, id="motion-left"),
        pytest.param("vj>", True, 2, id="visual-right"),
        pytest.param("vj<", False, 2, id="visual-left"),
        pytest.param("Vj>", True, 2, id="vline-right"),
        pytest.param("Vj<", False, 2, id="vline-left"),
    ],
)
def test_shift_uses_document_settings(
    indentation_bot, monkeypatch, indent, tab_width, command, forward, line_count
):
    """Each command shifts the intended lines and is undone in one step."""
    lines = ["first", "second", "third"]
    original = "\n".join(lines if forward else [indent + line for line in lines])
    expected_lines = [
        (
            (indent + line if forward else line)
            if index < line_count
            else (line if forward else indent + line)
        )
        for index, line in enumerate(lines)
    ]
    editor, status, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, indent, tab_width
    )

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == "\n".join(expected_lines)
    assert editor.textCursor().position() == (len(indent) if forward else 0)
    assert commandline.text() == ""
    assert status.is_normal()
    assert status.get_pos_start_in_selection() is None

    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == original


@pytest.mark.parametrize("indent, tab_width", INDENT_SETTINGS)
@pytest.mark.parametrize("forward", [True, False], ids=["right", "left"])
def test_counted_shift_preserves_empty_lines(
    indentation_bot, monkeypatch, indent, tab_width, forward
):
    """A line count includes empty lines without adding whitespace to them."""
    plain = "first\n\nthird\nfourth"
    indented = f"{indent}first\n\n{indent}third\nfourth"
    original, expected = (plain, indented) if forward else (indented, plain)
    editor, _, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, indent, tab_width
    )

    qtbot.keyClicks(commandline, "3>>" if forward else "3<<")

    assert editor.toPlainText() == expected


@pytest.mark.parametrize(
    "indent, tab_width, original, command, expected",
    [
        pytest.param(
            "  ",
            4,
            " \tfirst\n \tsecond",
            ">j",
            "      first\n      second",
            id="spaces-right-with-tabs",
        ),
        pytest.param(
            "  ",
            4,
            "  \tfirst\n\t second",
            "<j",
            "  first\n   second",
            id="spaces-left-with-tabs",
        ),
        pytest.param(
            "    ",
            8,
            "\t first",
            "<<",
            "     first",
            id="spaces-left-through-tab",
        ),
        pytest.param(
            "\t",
            4,
            "   \t first",
            ">>",
            "\t\t first",
            id="tabs-right-with-spaces",
        ),
        pytest.param(
            "\t",
            4,
            " \t  first",
            "<<",
            "  first",
            id="tabs-left-preserves-remainder",
        ),
        pytest.param(
            "\t",
            8,
            " \t \t  first",
            "<<",
            "\t  first",
            id="wide-tabs-left-with-spaces",
        ),
        pytest.param(
            "  ",
            4,
            " first",
            "<<",
            "first",
            id="left-less-than-one-level",
        ),
    ],
)
def test_shift_measures_mixed_indentation_in_columns(
    indentation_bot, monkeypatch, indent, tab_width, original, command, expected
):
    """Tabs retain their visual width even when the shift crosses a tab stop."""
    editor, _, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, indent, tab_width
    )

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == expected


@pytest.mark.parametrize(
    "original, command, after_first, expected",
    [
        ("first\nsecond", ">>", "  first\nsecond", "  first\n\tsecond"),
        ("    first\n\t second", "<<", "  first\n\t second", "  first\n second"),
    ],
)
def test_dot_reads_changed_document_settings(
    indentation_bot, monkeypatch, original, command, after_first, expected
):
    """Repeating a shift uses settings changed since the original command."""
    editor, status, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "  ", 4
    )
    qtbot.keyClicks(commandline, command)
    assert editor.toPlainText() == after_first

    monkeypatch.setattr(editor, "indent_chars", "\t")
    monkeypatch.setattr(editor, "tab_stop_width_spaces", 8)
    qtbot.keyClicks(commandline, "j.")

    assert editor.toPlainText() == expected
    assert status.indent == "\t"
    assert commandline.text() == ""


def test_shift_follows_active_document(indentation_bot, monkeypatch):
    """Switching real editor tabs also switches the indentation settings."""
    stack, first, status, commandline, qtbot = indentation_bot
    first, _, _, _ = prepare_editor(indentation_bot, monkeypatch, "first", "  ", 4)
    stack.set_stack_index(1)
    second = stack.get_current_editor()
    previous_text = second.toPlainText()
    monkeypatch.setattr(second, "indent_chars", "\t")
    monkeypatch.setattr(second, "tab_stop_width_spaces", 8)
    second.set_text("second")
    try:
        stack.set_stack_index(0)
        status.cursor.set_cursor_pos(0)
        qtbot.keyClicks(commandline, ">>")
        assert first.toPlainText() == "  first"
        assert second.toPlainText() == "second"

        stack.set_stack_index(1)
        status.cursor.set_cursor_pos(0)
        qtbot.keyClicks(commandline, ">>")
        assert second.toPlainText() == "\tsecond"
        assert first.toPlainText() == "  first"

        stack.set_stack_index(0)
        qtbot.keyClicks(commandline, "<<")
        assert first.toPlainText() == "first"
        assert second.toPlainText() == "\tsecond"

        stack.set_stack_index(1)
        qtbot.keyClicks(commandline, "<<")
        assert second.toPlainText() == "second"
        assert first.toPlainText() == "first"
        assert commandline.text() == ""
    finally:
        second.set_text(previous_text)
        stack.set_stack_index(0)


@pytest.mark.parametrize("indent, tab_width", INDENT_SETTINGS)
@pytest.mark.parametrize(
    "command, line_count",
    [
        pytest.param("==", 1, id="current-line"),
        pytest.param("=j", 2, id="motion"),
        pytest.param("3==", 3, id="line-count"),
        pytest.param("=2j", 3, id="motion-count"),
        pytest.param("2=2j", 5, id="multiplied-count"),
        pytest.param("=G", 6, id="to-end"),
    ],
)
def test_reindent_uses_document_settings_and_range(
    indentation_bot, monkeypatch, indent, tab_width, command, line_count
):
    """Reindent only the requested lines and keep expression formatting intact."""
    # Only the first body line needs more indentation. The remaining lines
    # need less; a zero-indented later line can also be an intentional dedent.
    lines = ["first=1"] + [" \t" * 8 + f"value{index}={index}" for index in range(2, 7)]
    original = "if True:\n" + "\n".join(lines)
    expected = "if True:\n" + "\n".join(
        indent + line.lstrip(" \t") if index < line_count else line
        for index, line in enumerate(lines)
    )
    editor, status, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, indent, tab_width
    )
    status.cursor.set_cursor_pos(len("if True:\n"))

    def unexpected_format(*args, **kwargs):
        pytest.fail("Reindent must not invoke the document formatter")

    monkeypatch.setattr(editor, "format_document_or_range", unexpected_format)

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == expected
    assert editor.textCursor().position() == len("if True:\n") + len(indent)
    assert commandline.text() == ""
    assert status.is_normal()
    assert status.sub_mode is None
    assert status.get_pos_start_in_selection() is None

    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == original
    qtbot.keyClick(commandline, Qt.Key_R, Qt.ControlModifier)
    assert editor.toPlainText() == expected


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("gg=G", id="whole-document"),
        pytest.param("3j=gg", id="backward-motion"),
        pytest.param("=ip", id="paragraph-object"),
    ],
)
def test_reindent_document_backward_motion_and_text_object(
    indentation_bot, monkeypatch, command
):
    """All range entry points correct both excessive and missing indentation."""
    original = "  if True:\nfirst=1\n      second=2\npass"
    expected = "if True:\n  first=1\n  second=2\npass"
    editor, _, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "  ", 4
    )

    qtbot.keyClicks(commandline, command)

    assert editor.toPlainText() == expected
    assert editor.textCursor().position() == 0
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == original


def test_reindent_leaves_empty_lines_empty(indentation_bot, monkeypatch):
    """Reindenting across empty lines does not insert trailing whitespace."""
    original = "if True:\nfirst=1\n\n        second=2\n"
    editor, _, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "    ", 4
    )

    qtbot.keyClicks(commandline, "gg=G")

    assert editor.toPlainText() == "if True:\n    first=1\n\n    second=2\n"


def test_reindent_excludes_line_at_exclusive_motion_end(indentation_bot, monkeypatch):
    """A word motion ending at the next line's start does not reindent it."""
    original = "if True:\nfirst\nsecond"
    editor, status, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "  ", 4
    )
    status.cursor.set_cursor_pos(len("if True:\n"))

    qtbot.keyClicks(commandline, "=w")

    assert editor.toPlainText() == "if True:\n  first\nsecond"


@pytest.mark.parametrize("cancel", [True, False], ids=["escape", "failed-motion"])
def test_reindent_cancel_and_failed_motion_do_not_edit(
    indentation_bot, monkeypatch, cancel
):
    """Incomplete and unmatched motions leave the document and repeat intact."""
    original = "if True:\nfirst=1"
    editor, status, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "  ", 4
    )
    status.cursor.set_cursor_pos(len("if True:\n"))
    previous_repeat = (status.dot_cmd.num_str, status.dot_cmd.cmd)

    qtbot.keyClicks(commandline, "=")
    if cancel:
        qtbot.keyClick(commandline, Qt.Key_Escape)
    else:
        qtbot.keyClicks(commandline, "fz")

    assert editor.toPlainText() == original
    assert (status.dot_cmd.num_str, status.dot_cmd.cmd) == previous_repeat
    assert commandline.text() == ""
    assert status.sub_mode is None


def test_reindent_dot_uses_current_document_settings(indentation_bot, monkeypatch):
    """Dot reindents the new location using the current indentation width."""
    original = "if True:\nfirst=1\nif False:\nsecond=2"
    editor, status, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "  ", 4
    )
    status.cursor.set_cursor_pos(len("if True:\n"))
    qtbot.keyClicks(commandline, "==")
    assert editor.toPlainText() == "if True:\n  first=1\nif False:\nsecond=2"

    monkeypatch.setattr(editor, "indent_chars", "\t")
    monkeypatch.setattr(editor, "tab_stop_width_spaces", 8)
    qtbot.keyClicks(commandline, "2j.")

    assert editor.toPlainText() == "if True:\n  first=1\nif False:\n\tsecond=2"
    assert commandline.text() == ""


def test_reindent_follows_active_document(indentation_bot, monkeypatch):
    """Reindent uses the active editor's document and indentation settings."""
    stack, first, status, commandline, qtbot = indentation_bot
    first, _, _, _ = prepare_editor(
        indentation_bot, monkeypatch, "if True:\nfirst=1", "  ", 4
    )
    stack.set_stack_index(1)
    second = stack.get_current_editor()
    previous_text = second.toPlainText()
    monkeypatch.setattr(second, "indent_chars", "\t")
    monkeypatch.setattr(second, "tab_stop_width_spaces", 8)
    second.set_text("if True:\nsecond=2")
    try:
        stack.set_stack_index(0)
        status.cursor.set_cursor_pos(len("if True:\n"))
        qtbot.keyClicks(commandline, "==")
        assert first.toPlainText() == "if True:\n  first=1"

        stack.set_stack_index(1)
        status.cursor.set_cursor_pos(len("if True:\n"))
        qtbot.keyClicks(commandline, "==")
        assert second.toPlainText() == "if True:\n\tsecond=2"
        assert first.toPlainText() == "if True:\n  first=1"
    finally:
        second.set_text(previous_text)
        stack.set_stack_index(0)


def test_reindent_non_python_replaces_prefix(indentation_bot, monkeypatch):
    """The generic indentation path replaces whitespace without duplication."""
    original = "  first\n      second\nthird"
    editor, status, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "  ", 4
    )
    monkeypatch.setattr(editor, "is_python_like", lambda: False)
    status.cursor.set_cursor_pos(len("  first\n"))

    qtbot.keyClicks(commandline, "=j")

    assert editor.toPlainText() == "  first\n  second\n  third"
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == original


def test_reindent_preserves_trailing_whitespace(indentation_bot, monkeypatch):
    """Moving between target lines must not trigger Spyder's trailing strip."""
    original = "if True:\nfirst=1  \n        second=2 \n"
    editor, _, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "  ", 4
    )

    qtbot.keyClicks(commandline, "gg=G")

    assert editor.toPlainText() == "if True:\n  first=1  \n  second=2 \n"


def test_reindent_preserves_valid_python_dedents(indentation_bot, monkeypatch):
    """Top-level code and nested block exits keep their existing scope."""
    original = (
        "if True:\n"
        "    if False:\n"
        "        nested=1\n"
        "    outer=2\n"
        "top_level=3"
    )
    editor, _, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "    ", 4
    )

    qtbot.keyClicks(commandline, "gg=G")

    assert editor.toPlainText() == original


@pytest.mark.parametrize("tab_width", [4, 8])
def test_reindent_rounds_partial_tab_indentation(
    indentation_bot, monkeypatch, tab_width
):
    """A partial tab level aligns to the scope without removing code text."""
    original = "if True:\n\tfirst=1\n second=2"
    editor, status, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "\t", tab_width
    )
    status.cursor.set_cursor_pos(len("if True:\n\tfirst=1\n"))

    qtbot.keyClicks(commandline, "==")

    assert editor.toPlainText() == "if True:\n\tfirst=1\n\tsecond=2"


def test_reindent_preserves_multiline_string_contents(indentation_bot, monkeypatch):
    """Indent the assignment while preserving whitespace inside its string."""
    string = '"""first\n  literal line \n\tanother line\n"""'
    original = "if True:\ntext = " + string
    editor, _, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "  ", 4
    )

    qtbot.keyClicks(commandline, "gg=G")

    assert editor.toPlainText() == "if True:\n  text = " + string
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == original


@pytest.mark.parametrize(
    "header, string",
    [
        pytest.param("if True:", '"hello"', id="string-expression"),
        pytest.param("def f():", '"""doc"""', id="single-line-docstring"),
        pytest.param(
            "def f():", '"""first\n  literal line \n"""', id="multiline-docstring"
        ),
    ],
)
def test_reindent_indents_string_openers(indentation_bot, monkeypatch, header, string):
    """Indent a string's opening statement while preserving its literal text."""
    original = header + "\n" + string
    editor, _, commandline, qtbot = prepare_editor(
        indentation_bot, monkeypatch, original, "  ", 4
    )

    qtbot.keyClicks(commandline, "gg=G")

    assert editor.toPlainText() == header + "\n  " + string
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == original
