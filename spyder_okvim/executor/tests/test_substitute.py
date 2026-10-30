"""Substitute commands through the real Ex input and editor undo stack."""

from unittest.mock import Mock

import pytest
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QTextCursor
from spyder.config.manager import CONF

from spyder_okvim.spyder.config import CONF_SECTION


@pytest.fixture
def substitute_bot(vim_bot):
    """Keep the active document, search settings, and input state isolated."""
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
    original = editor.toPlainText()
    options = {
        name: CONF.get(CONF_SECTION, name) for name in ("ignorecase", "smartcase")
    }
    editor.set_text("foo foo\n  foo foo\nlast")
    status.cursor.set_cursor_pos(0)
    commandline.clear()
    commandline.setFocus()
    try:
        yield editor, status, commandline, qtbot
    finally:
        editor.setReadOnly(False)
        commandline.esc_pressed()
        status.disconnect_from_editor()
        status.reset_for_test()
        editor.set_text(original)
        for name, value in options.items():
            CONF.set(CONF_SECTION, name, value)
        stack.set_stack_index(previous_index)


def submit(bot, body):
    """Use setText for Unicode input, then the ordinary Return commit path."""
    _, _, commandline, qtbot = bot
    qtbot.keyClicks(commandline, ":")
    commandline.setText(":" + body)
    qtbot.keyPress(commandline, Qt.Key_Return)


@pytest.mark.parametrize(
    "command, expected",
    [
        ("s/foo/x/", "x foo\n  foo foo\nlast"),
        ("substitute/foo/x/g", "x x\n  foo foo\nlast"),
        ("%s/foo/longer/g", "longer longer\n  longer longer\nlast"),
        ("2s/foo/x/g", "foo foo\n  x x\nlast"),
        ("1,2s/foo/x/", "x foo\n  x foo\nlast"),
        (".,$s/foo//g", " \n   \nlast"),
        ("s#foo#old/path#g", "old/path old/path\n  foo foo\nlast"),
        ("s/foo/x", "x foo\n  foo foo\nlast"),
        ("s/foo/", " foo\n  foo foo\nlast"),
        ("s/foo/xg", "xg foo\n  foo foo\nlast"),
        ("s/foo", " foo\n  foo foo\nlast"),
        ("su/foo/x/g", "x x\n  foo foo\nlast"),
        ("substit/foo/x/g", "x x\n  foo foo\nlast"),
        ("0s/foo/x/", "x foo\n  foo foo\nlast"),
        ("s/foo/x/g 2", "x x\n  x x\nlast"),
        ("1,2s/foo/x/99", "foo foo\n  x foo\nlast"),
        (r"s/foo/\1/", " foo\n  foo foo\nlast"),
        (r"s/foo/\z/", "z foo\n  foo foo\nlast"),
    ],
)
def test_substitute_ranges_and_syntax(substitute_bot, command, expected):
    editor, status, commandline, _ = substitute_bot
    submit(substitute_bot, command)
    assert editor.toPlainText() == expected
    assert status.is_normal()
    assert status.sub_mode is None
    assert commandline.text() == ""


@pytest.mark.parametrize(
    "command",
    [
        "4s/foo/x/",
        "2,1s/foo/x/",
        "1,s/foo/x/",
        "s/[foo/x/",
        r"s/foo/\r/",
        r"s/foo/\n/",
        r"s/foo/\=/n",
        "s/foo/x/g extra",
        "s",
        "1w",
        "%q!",
        "to_normal",
        "__init__",
        "s/foo/a\u2028b/",
    ],
)
def test_invalid_command_is_atomic(substitute_bot, command):
    editor, status, _, _ = substitute_bot
    status.search.search("last", ignorecase=False, forward=False)
    snapshot = status.search.snapshot()
    original = editor.toPlainText()
    position = editor.textCursor().position()
    steps = editor.document().availableUndoSteps()
    submit(substitute_bot, command)
    assert editor.toPlainText() == original
    assert editor.textCursor().position() == position
    assert editor.document().availableUndoSteps() == steps
    assert status.search.snapshot() == snapshot
    assert status.msg_label.text()


@pytest.mark.parametrize(
    "flags, expected",
    [
        ("gi", "x x x"),
        ("gI", "x FOO Foo"),
        ("giI", "x FOO Foo"),
        ("gIi", "x x x"),
        ("ggii", "x FOO Foo"),
    ],
)
def test_case_flags_override_config(substitute_bot, flags, expected):
    editor, status, _, _ = substitute_bot
    editor.set_text("foo FOO Foo")
    CONF.set(CONF_SECTION, "ignorecase", True)
    CONF.set(CONF_SECTION, "smartcase", True)
    submit(substitute_bot, "s/foo/x/" + flags)
    assert editor.toPlainText() == expected
    assert status.search.ignorecase is True
    assert CONF.get(CONF_SECTION, "ignorecase") is True
    assert CONF.get(CONF_SECTION, "smartcase") is True


@pytest.mark.parametrize("pattern, expected", [("foo", "x x x"), ("Foo", "foo FOO x")])
def test_substitute_uses_search_smartcase(substitute_bot, pattern, expected):
    editor, _, _, _ = substitute_bot
    editor.set_text("foo FOO Foo")
    CONF.set(CONF_SECTION, "ignorecase", True)
    CONF.set(CONF_SECTION, "smartcase", True)
    submit(substitute_bot, f"s/{pattern}/x/g")
    assert editor.toPlainText() == expected


def test_substitute_is_one_undo_and_redo(substitute_bot):
    editor, status, commandline, qtbot = substitute_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, "x")
    before = editor.toPlainText()
    submit(substitute_bot, "%s/foo/longer/g")
    replaced = editor.toPlainText()
    assert replaced == "oo longer\n  longer longer\nlast"
    assert editor.textCursor().blockNumber() == 1
    assert editor.textCursor().positionInBlock() == 2
    qtbot.keyClicks(commandline, "x")
    assert editor.toPlainText() != replaced
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == replaced
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == before
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == original
    qtbot.keyPress(commandline, Qt.Key_R, modifier=Qt.ControlModifier)
    assert editor.toPlainText() == before
    qtbot.keyPress(commandline, Qt.Key_R, modifier=Qt.ControlModifier)
    assert editor.toPlainText() == replaced
    assert status.is_normal()


@pytest.mark.parametrize(
    "command, count, position",
    [("%s/foo/x/n", 2, 0), ("%s/foo/x/gn", 4, 0), ("%s/foo/foo/g", 4, 10)],
)
def test_count_and_noop_cursor_without_undo(substitute_bot, command, count, position):
    editor, status, _, _ = substitute_bot
    status.cursor.set_cursor_pos(3)
    original = editor.toPlainText()
    steps = editor.document().availableUndoSteps()
    submit(substitute_bot, command)
    assert editor.toPlainText() == original
    assert editor.textCursor().position() == position
    assert editor.document().availableUndoSteps() == steps
    assert status.msg_label.text().startswith(f"{count} ")
    assert "2 lines" in status.msg_label.text()
    assert status.search.txt_searched == "foo"


@pytest.mark.parametrize(
    "flags, expected_message",
    [("", "Pattern not found: missing"), ("e", ""), ("ne", "")],
)
def test_no_match_updates_search_without_editing(
    substitute_bot, flags, expected_message
):
    editor, status, _, _ = substitute_bot
    status.search.search("last", forward=False)
    steps = editor.document().availableUndoSteps()
    submit(substitute_bot, "s/missing/x/" + flags)
    assert status.msg_label.text() == expected_message
    assert status.search.txt_searched == "missing"
    assert status.search.forward is False
    assert editor.textCursor().position() == 0
    assert editor.document().availableUndoSteps() == steps
    assert status.jump_list.jumps == []


@pytest.mark.parametrize(
    "command, responses",
    [
        ("%s/foo/longer/g", ""),
        ("%s/foo/foo/g", ""),
        ("%s/foo/x/gn", ""),
        ("%s/foo/longer/gc", "a"),
    ],
)
def test_substitution_jump_tracks_origin_after_length_changes(
    substitute_bot, command, responses
):
    editor, status, commandline, qtbot = substitute_bot
    status.cursor.set_cursor_pos(editor.document().lastBlock().position() + 2)
    submit(substitute_bot, command)
    if responses:
        qtbot.keyClicks(commandline, responses)
    destination = editor.textCursor().position()
    origin = editor.document().lastBlock().position() + 2
    qtbot.keyPress(commandline, Qt.Key_O, modifier=Qt.ControlModifier)
    assert editor.textCursor().position() == origin
    qtbot.keyPress(commandline, Qt.Key_I, modifier=Qt.ControlModifier)
    assert editor.textCursor().position() == destination


@pytest.mark.parametrize(
    "replacement, origin", [("😀", 0), ("😀😀", 2), ("a\u0301", 0), ("😀a\u0301", 2)]
)
def test_substitution_jump_stays_on_a_unicode_character(
    substitute_bot, replacement, origin
):
    editor, status, commandline, qtbot = substitute_bot
    editor.set_text("foofoo\nlast")
    status.cursor.set_cursor_pos(4)
    submit(substitute_bot, f"s/foofoo/{replacement}/")
    qtbot.keyPress(commandline, Qt.Key_O, modifier=Qt.ControlModifier)
    assert editor.textCursor().position() == origin


def test_empty_pattern_uses_confirmed_search_after_cancel(substitute_bot):
    editor, status, commandline, qtbot = substitute_bot
    status.search.search("foo", ignorecase=False, forward=False)
    qtbot.keyClicks(commandline, "/last")
    qtbot.keyPress(commandline, Qt.Key_Escape)
    submit(substitute_bot, "s//x/g")
    assert editor.toPlainText() == "x x\n  foo foo\nlast"
    assert status.search.txt_searched == "foo"
    assert status.search.forward is False


def test_empty_pattern_requires_previous_search(substitute_bot):
    editor, status, _, _ = substitute_bot
    submit(substitute_bot, "s//x/")
    assert editor.toPlainText() == "foo foo\n  foo foo\nlast"
    assert "No previous" in status.msg_label.text()
    assert not editor.document().isUndoAvailable()


def test_unicode_captures_nbsp_and_cursor(substitute_bot):
    editor, _, _, _ = substitute_bot
    editor.set_text("😀 가\u00a0나 가 나\n\t😀 가\u00a0나  ")
    submit(substitute_bot, r"%s/(가 나)/[\1&]/g")
    document = editor.document()
    assert document.firstBlock().text() == "😀 [가\u00a0나가\u00a0나] [가 나가 나]"
    assert document.lastBlock().text() == "\t😀 [가\u00a0나가\u00a0나]  "
    assert editor.textCursor().blockNumber() == 1
    assert editor.textCursor().positionInBlock() == 1


@pytest.mark.parametrize(
    "text, command, expected",
    [
        ("", "%s/^/x/", "x"),
        ("foo\n", "%s/^/x/", "xfoo\nx"),
        ("foo", "%s/foo/x/", "x"),
        ("foo\n", "$s/^/x/", "foo\nx"),
    ],
)
def test_empty_document_and_final_block(substitute_bot, text, command, expected):
    editor, _, _, _ = substitute_bot
    editor.set_text(text)
    submit(substitute_bot, command)
    assert editor.toPlainText() == expected


@pytest.mark.parametrize("command", ["%s/foo/x/g", "%s/foo/foo/g", "%s/absent/x/e"])
def test_readonly_rejects_substitution_without_search_update(substitute_bot, command):
    editor, status, _, _ = substitute_bot
    original = editor.toPlainText()
    editor.setReadOnly(True)
    submit(substitute_bot, command)
    assert editor.toPlainText() == original
    assert not editor.document().isUndoAvailable()
    assert status.search.txt_searched == ""
    assert "read-only" in status.msg_label.text()
    submit(substitute_bot, "%s/foo/x/gn")
    assert status.msg_label.text().startswith("4 matches")


def test_skip_rstrip_and_change_notification(substitute_bot, monkeypatch):
    editor, _, _, _ = substitute_bot
    editor.skip_rstrip = False
    changed = Mock(wraps=editor.document_did_change)
    monkeypatch.setattr(editor, "document_did_change", changed)
    submit(substitute_bot, "%s/foo/x/g")
    assert editor.skip_rstrip is False
    changed.assert_called_once_with()


def test_substitute_preserves_dot_repeat(substitute_bot):
    editor, _, commandline, qtbot = substitute_bot
    editor.set_text("abc foo\nabc foo")
    qtbot.keyClicks(commandline, "x")
    submit(substitute_bot, "%s/foo/bar/g")
    qtbot.keyClicks(commandline, ".")
    assert editor.toPlainText() == "bc bar\nbc bar"


def test_search_refresh_occurs_after_edits_once(substitute_bot, monkeypatch):
    editor, status, _, _ = substitute_bot
    refresh = Mock(wraps=status.search.refresh)
    monkeypatch.setattr(status.search, "refresh", refresh)
    submit(substitute_bot, "%s/foo/x/g")
    refresh.assert_called_once_with()
    assert status.search.get_sel_start_list() == []
    assert editor.toPlainText().startswith("x x")


@pytest.mark.parametrize(
    "ignorecase, flag, expected", [(False, "i", 8), (True, "I", 4)]
)
def test_case_flags_do_not_change_later_search(
    substitute_bot, ignorecase, flag, expected
):
    editor, status, commandline, qtbot = substitute_bot
    editor.set_text("foo FOO foo")
    CONF.set(CONF_SECTION, "ignorecase", ignorecase)
    CONF.set(CONF_SECTION, "smartcase", False)
    status.search.search("last", forward=False)
    submit(substitute_bot, "%s/foo/x/gn" + flag)
    qtbot.keyClicks(commandline, "N")
    assert editor.textCursor().position() == expected
    qtbot.keyClicks(commandline, "n")
    assert editor.textCursor().position() == 0
    assert status.search.forward is False


@pytest.mark.parametrize("replacement", [r"\r", r"\n", r"\U", r"\9", "bad\u2028text"])
def test_count_ignores_unused_replacement(substitute_bot, replacement):
    editor, status, _, _ = substitute_bot
    original = editor.toPlainText()
    submit(substitute_bot, f"%s/foo/{replacement}/gnc")
    assert editor.toPlainText() == original
    assert not editor.document().isUndoAvailable()
    assert status.msg_label.text().startswith("4 matches")


@pytest.mark.parametrize(
    "prefix, column", [("\t  ", 3), ("\u00a0", 0), ("\t \u2003", 2)]
)
def test_substitute_cursor_skips_only_spaces_and_tabs(substitute_bot, prefix, column):
    editor, _, _, _ = substitute_bot
    editor.set_text("foo\n" + prefix + "foo")
    submit(substitute_bot, "%s/foo/foo/g")
    assert editor.textCursor().blockNumber() == 1
    assert editor.textCursor().positionInBlock() == column


@pytest.mark.parametrize(
    "flags, message", [("e", ""), ("ee", "Pattern not found: absent")]
)
def test_error_flag_toggles_on_each_occurrence(substitute_bot, flags, message):
    _, status, _, _ = substitute_bot
    submit(substitute_bot, "s/absent/x/" + flags)
    assert status.msg_label.text() == message


@pytest.mark.parametrize("body", [r"%s/\C/x/g", r"%s/(\C)\C/\1/g"])
def test_surrogate_error_does_not_apply_earlier_edits(substitute_bot, body):
    editor, status, _, _ = substitute_bot
    editor.set_text("a\n😀")
    original = editor.toPlainText()
    submit(substitute_bot, body)
    assert editor.toPlainText() == original
    assert not editor.document().isUndoAvailable()
    assert status.search.txt_searched == ""
    assert "surrogate" in status.msg_label.text()


def test_insert_edits_remain_separate_undo_steps(substitute_bot):
    editor, _, commandline, qtbot = substitute_bot
    editor.set_text("foo")
    qtbot.keyClicks(commandline, "i")
    qtbot.keyClicks(editor, "before ")
    qtbot.keyPress(editor, Qt.Key_Escape)
    submit(substitute_bot, "s/foo/bar/")
    qtbot.keyClicks(commandline, "A")
    qtbot.keyClicks(editor, " after")
    qtbot.keyPress(editor, Qt.Key_Escape)
    assert editor.toPlainText() == "before bar after"
    for expected in ("before bar", "before foo", "foo"):
        qtbot.keyClicks(commandline, "u")
        assert editor.toPlainText() == expected


def test_crlf_and_cursors_outside_edits_are_preserved(substitute_bot):
    editor, status, _, _ = substitute_bot
    editor.set_text("foo\r\n\tkeep  \r\nfoo\r\n")
    cursor = QTextCursor(editor.document().findBlockByNumber(1))
    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, 2)
    status.cursor.set_cursor_pos(cursor.position())
    status.bookmark_manager.set_bookmark("a")
    bookmark = status.bookmark_manager.get_bookmark("a").copy()
    status.cursor.set_cursor_pos(0)
    old_eol = editor.get_line_separator()
    submit(substitute_bot, "%s/foo/longer/g")
    assert editor.get_line_separator() == old_eol == "\r\n"
    assert editor.document().findBlockByNumber(1).text() == "\tkeep  "
    assert cursor.blockNumber() == 1
    assert cursor.positionInBlock() == 2
    assert status.bookmark_manager.get_bookmark("a") == bookmark
    status.bookmark_manager.jump_to_bookmark("a")
    assert editor.textCursor().position() == cursor.position()
    assert status.is_normal()


def test_cancelled_substitution_is_not_history(substitute_bot):
    editor, status, commandline, qtbot = substitute_bot
    previous = list(commandline.histories["ex"])
    qtbot.keyClicks(commandline, ":%s/foo/x/g")
    qtbot.keyPress(commandline, Qt.Key_Escape)
    assert commandline.histories["ex"] == previous
    assert editor.toPlainText() == "foo foo\n  foo foo\nlast"
    assert status.search.txt_searched == ""


def test_empty_matches_advance_before_next_match_and_undo_once(substitute_bot):
    editor, _, commandline, qtbot = substitute_bot
    editor.set_text("😀aa")
    submit(substitute_bot, "s/(?=a)|a/x/g")
    assert editor.toPlainText() == "😀xaxa"
    qtbot.keyClicks(commandline, "u")
    assert editor.toPlainText() == "😀aa"


def test_identical_replacements_do_not_create_undo(substitute_bot):
    editor, status, _, _ = substitute_bot
    editor.set_text("aa")
    status.cursor.set_cursor_pos(1)
    submit(substitute_bot, r"s/a*/&/g")
    assert editor.toPlainText() == "aa"
    assert editor.textCursor().position() == 0
    assert not editor.document().isUndoAvailable()
    assert "1 substitutions" in status.msg_label.text()
    assert "no changes" in status.msg_label.text()
