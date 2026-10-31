"""Regression tests for document searches and refreshed search results."""

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt
from qtpy.QtGui import QTextCursor

# Project Libraries
from tests.qt_support import reset_vim_state


def _highlight_ranges(editor):
    """Read the actual highlight group without triggering a search refresh."""
    return [
        (selection.cursor.selectionStart(), selection.cursor.selectionEnd())
        for selection in editor.get_extra_selections("vim_search")
    ]


def _record_highlight_updates(editor, monkeypatch):
    """Observe search paints through the editor's public selection API."""
    updates = []
    set_extra_selections = editor.set_extra_selections

    def record(key, selections):
        if key == "vim_search":
            updates.append(
                [
                    (selection.cursor.selectionStart(), selection.cursor.selectionEnd())
                    for selection in selections
                ]
            )
        return set_extra_selections(key, selections)

    monkeypatch.setattr(editor, "set_extra_selections", record)
    return updates


@pytest.fixture
def search_editor(vim_bot):
    """Use a known editor and restore the shared session after each test."""
    _, stack, editor, vim, qtbot = vim_bot
    status = vim.vim_cmd.vim_status
    helper = vim.vim_cmd.executor_normal_cmd.helper_motion
    original_filename = stack.get_current_filename()
    original_text = editor.toPlainText()
    filename = next(info.filename for info in stack.data if info.editor is editor)
    stack.set_current_filename(filename)
    reset_vim_state(status)
    try:
        yield stack, editor, status, helper, qtbot
    finally:
        reset_vim_state(status)
        editor.set_text(original_text)
        stack.set_current_filename(original_filename)


@pytest.mark.parametrize(
    "text, pattern, expected",
    [
        ("a\n\nb\n", "^", [(0, 0), (2, 2), (3, 3), (5, 5)]),
        ("a\n\nb\n", "$", [(1, 1), (2, 2), (4, 4), (5, 5)]),
        ("a\n\nb\n", r"\b", [(0, 0), (1, 1), (3, 3), (4, 4)]),
        ("foo food foo", r"\bfoo\b", [(0, 3), (9, 12)]),
        ("foo bar bar", r"(?<=foo )bar", [(4, 7)]),
        ("foo bar foobar", r"foo(?= bar)", [(0, 3)]),
        ("a\n\nb\n", "a*", [(0, 1), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]),
        ("😀a\n한글", "^", [(0, 0), (4, 4)]),
        ("😀a\n한글", "$", [(3, 3), (6, 6)]),
        ("😀a", r"(?=.)", [(0, 0), (2, 2)]),
        ("😀a", "a*", [(0, 0), (2, 3), (3, 3)]),
        ("a\u0301b", r"\b", [(0, 0), (1, 1), (2, 2), (3, 3)]),
        ("a\u0301b", r"(?=.)", [(0, 0), (1, 1), (2, 2)]),
        ("aaa", r"a\K", [(1, 1), (2, 2), (3, 3)]),
        ("aa", r"(?=a)|a", [(0, 0), (0, 1), (1, 1), (1, 2)]),
        ("", "^", [(0, 0)]),
        ("", "$", [(0, 0)]),
        ("", r"\b", []),
        ("foo", "[", []),
    ],
)
def test_search_patterns_terminate_and_keep_document_positions(
    search_editor, text, pattern, expected
):
    """Zero-width and contextual matches retain Qt's UTF-16 positions."""
    _, editor, status, _, _ = search_editor
    editor.set_text(text)
    status.cursor.set_cursor_pos(0)

    status.search.search(pattern, ignorecase=False)

    assert status.search.get_sel_start_list() == sorted(
        {start for start, _ in expected}
    )
    assert _highlight_ranges(editor) == expected
    assert editor.textCursor().position() == 0
    assert all(
        selection.cursor.document() is editor.document()
        for selection in status.search.selection_list
    )


def test_repeat_count_uses_distinct_match_positions(search_editor):
    """Empty and nonempty matches at one position count as one motion stop."""
    _, editor, status, helper, _ = search_editor
    editor.set_text("aaa")
    status.search.search(r"(?=a)|a", ignorecase=False)
    status.cursor.set_cursor_pos(0)

    assert status.search.get_sel_start_list() == [0, 1, 2]
    assert helper.n(2).cursor_pos == 2
    assert helper.N(2).cursor_pos == 1


def test_case_insensitive_regex_survives_result_refresh(search_editor):
    """Case-insensitive regex results must not be filtered as literal text."""
    _, editor, status, _, qtbot = search_editor
    editor.set_text("FOO Bar baz")
    status.search.search(r"\b(foo|bar)\b", ignorecase=True)
    assert status.search.get_sel_start_list() == [0, 4]

    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.End)
    cursor.insertText(" BAR")

    qtbot.waitUntil(
        lambda: _highlight_ranges(editor) == [(0, 3), (4, 7), (12, 15)],
        timeout=2000,
    )
    assert status.search.get_sel_start_list() == [0, 4, 12]


def test_repeat_search_refreshes_before_delayed_highlights(search_editor):
    """n/N immediately include new matches and exclude deleted matches."""
    _, editor, status, helper, _ = search_editor
    editor.set_text("foo xx")
    status.search.search("foo", ignorecase=False)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.End)
    cursor.insertText(" foo")
    status.cursor.set_cursor_pos(0)

    assert helper.n().cursor_pos == 7
    assert helper.N().cursor_pos == 7

    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(3, QTextCursor.KeepAnchor)
    cursor.removeSelectedText()
    status.cursor.set_cursor_pos(0)

    assert helper.n().cursor_pos == 4
    assert helper.N().cursor_pos == 4

    cursor = editor.textCursor()
    cursor.setPosition(4)
    cursor.setPosition(7, QTextCursor.KeepAnchor)
    cursor.removeSelectedText()

    assert helper.n().cursor_pos is None
    assert helper.N().cursor_pos is None
    assert _highlight_ranges(editor) == []


def test_edit_updates_highlights_without_repeat_search(search_editor):
    """Typing refreshes the displayed highlights even without n/N."""
    _, editor, status, _, qtbot = search_editor
    editor.set_text("foo bar")
    status.search.search("foo", ignorecase=False)
    assert _highlight_ranges(editor) == [(0, 3)]

    cursor = editor.textCursor()
    cursor.select(QTextCursor.Document)
    cursor.insertText("bar bar foo")
    qtbot.waitUntil(lambda: _highlight_ranges(editor) == [(8, 11)], timeout=2000)

    cursor.select(QTextCursor.Document)
    cursor.insertText("bar bar")
    qtbot.waitUntil(lambda: _highlight_ranges(editor) == [], timeout=2000)


def test_contextual_match_is_rechecked_after_edit(search_editor):
    """Changing adjacent text can invalidate an otherwise unchanged match."""
    _, editor, status, helper, qtbot = search_editor
    editor.set_text("foo bar")
    status.search.search(r"foo(?= bar)", ignorecase=False)
    assert status.search.get_sel_start_list() == [0]

    cursor = editor.textCursor()
    cursor.setPosition(4)
    cursor.setPosition(7, QTextCursor.KeepAnchor)
    cursor.insertText("baz")
    assert helper.n().cursor_pos is None
    assert _highlight_ranges(editor) == []

    editor.undo()
    qtbot.waitUntil(lambda: _highlight_ranges(editor) == [(0, 3)], timeout=2000)
    assert helper.N().cursor_pos == 0


def test_search_results_follow_undo_and_redo(search_editor):
    """Undo and redo invalidate matches just like ordinary document edits."""
    _, editor, status, helper, qtbot = search_editor
    editor.set_text("foo")
    status.search.search("foo", ignorecase=False)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.End)
    cursor.insertText(" foo")
    status.cursor.set_cursor_pos(0)
    assert helper.n().cursor_pos == 4

    editor.undo()
    status.cursor.set_cursor_pos(0)
    assert helper.n().cursor_pos == 0
    assert status.search.get_sel_start_list() == [0]

    editor.redo()
    qtbot.waitUntil(lambda: _highlight_ranges(editor) == [(0, 3), (4, 7)], timeout=2000)
    status.cursor.set_cursor_pos(0)
    assert helper.N().cursor_pos == 4


def test_switching_documents_uses_only_current_document_matches(search_editor):
    """Switching tabs refreshes highlights and never reuses foreign cursors."""
    stack, editor, status, helper, qtbot = search_editor
    other_info = next(info for info in stack.data if info.editor is not editor)
    other = other_info.editor
    original_other_text = other.toPlainText()
    filename = stack.get_current_filename()
    try:
        editor.set_text("foo gap foo")
        other.set_text("xx foo")
        status.search.search("foo", ignorecase=False)
        assert status.search.get_sel_start_list() == [0, 8]

        stack.set_current_filename(other_info.filename)
        qtbot.waitUntil(lambda: _highlight_ranges(other) == [(3, 6)], timeout=2000)
        status.cursor.set_cursor_pos(0)
        assert helper.n().cursor_pos == 3
        assert status.search.get_sel_start_list() == [3]
        assert all(
            selection.cursor.document() is other.document()
            for selection in status.search.selection_list
        )

        # An inactive editor may change while another tab owns the search state.
        editor.set_text("gap foo")
        assert status.search.get_sel_start_list() == [3]
        assert _highlight_ranges(other) == [(3, 6)]

        stack.set_current_filename(filename)
        qtbot.waitUntil(lambda: _highlight_ranges(editor) == [(4, 7)], timeout=2000)
        status.search.search("gap", ignorecase=False)
        stack.set_current_filename(other_info.filename)
        qtbot.waitUntil(lambda: _highlight_ranges(other) == [], timeout=2000)
        assert helper.n().cursor_pos is None
        assert helper.N().cursor_pos is None
    finally:
        stack.set_current_filename(filename)
        other.set_text(original_other_text)


def test_clear_highlights_stays_hidden_until_repeat_search(
    search_editor, vim_bot, monkeypatch
):
    """Ctrl+C remains effective through delayed refreshes after editing."""
    _, editor, status, helper, qtbot = search_editor
    _, _, _, vim, _ = vim_bot
    editor.set_text("foo")
    status.search.search("foo", ignorecase=False)
    qtbot.keyPress(vim.vim_cmd.commandline, Qt.Key_C, Qt.ControlModifier)
    assert _highlight_ranges(editor) == []
    updates = _record_highlight_updates(editor, monkeypatch)

    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.End)
    cursor.insertText(" foo")
    qtbot.waitUntil(lambda: bool(updates), timeout=2000)
    assert all(update == [] for update in updates)
    assert _highlight_ranges(editor) == []

    status.cursor.set_cursor_pos(0)
    assert helper.n().cursor_pos == 4
    assert _highlight_ranges(editor) == [(0, 3), (4, 7)]


def test_consecutive_edits_coalesce_highlight_updates(search_editor, monkeypatch):
    """A burst of edits paints the completed result once."""
    _, editor, status, _, qtbot = search_editor
    editor.set_text("foo")
    status.search.search("foo", ignorecase=False)
    updates = _record_highlight_updates(editor, monkeypatch)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.End)

    for _ in range(3):
        cursor.insertText(" foo")

    assert updates == []
    expected = [(0, 3), (4, 7), (8, 11), (12, 15)]
    qtbot.waitUntil(lambda: _highlight_ranges(editor) == expected, timeout=2000)
    assert updates == [expected]


def test_reset_cancels_pending_search_updates(search_editor, monkeypatch):
    """A pending callback cannot repaint the old search after status reset."""
    _, editor, status, _, qtbot = search_editor
    editor.set_text("foo")
    status.search.search("foo", ignorecase=False)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.End)
    cursor.insertText(" foo")
    reset_vim_state(status)
    updates = _record_highlight_updates(editor, monkeypatch)

    cursor.insertText(" foo")
    qtbot.wait(300)

    assert _highlight_ranges(editor) == []
    assert updates == []
    assert status.search.get_sel_start_list() == []


def test_close_cancels_pending_search_and_disconnects_editor_changes(
    search_editor, monkeypatch
):
    """Closing search state prevents edits or tab switches from reviving it."""
    stack, editor, status, _, qtbot = search_editor
    other_info = next(info for info in stack.data if info.editor is not editor)
    filename = stack.get_current_filename()
    editor.set_text("foo")
    status.search.search("foo", ignorecase=False)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.End)
    cursor.insertText(" foo")
    status.search.close()
    updates = _record_highlight_updates(editor, monkeypatch)

    try:
        cursor.insertText(" foo")
        stack.set_current_filename(other_info.filename)
        stack.set_current_filename(filename)
        qtbot.wait(300)
        assert _highlight_ranges(editor) == []
        assert updates == []
    finally:
        stack.set_current_filename(filename)


def test_current_match_follows_cursor_and_respects_clear_highlights(search_editor):
    _, editor, status, _, _ = search_editor
    editor.set_text("foo gap foo")
    status.search.search("foo")

    def current_ranges():
        return [
            (selection.cursor.selectionStart(), selection.cursor.selectionEnd())
            for selection in editor.get_extra_selections("vim_search_current")
        ]

    status.cursor.set_cursor_pos(0)
    assert current_ranges() == [(0, 3)]
    current = editor.get_extra_selections("vim_search_current")[0]
    regular = editor.get_extra_selections("vim_search")[0]
    assert current.format.fontUnderline()
    assert current.format != regular.format
    status.cursor.set_cursor_pos(8)
    assert current_ranges() == [(8, 11)]
    status.search.clear_highlights()
    status.cursor.set_cursor_pos(0)
    assert current_ranges() == []
    status.search.get_sel_start_list()
    assert current_ranges() == [(0, 3)]
    status.search.close()
    assert current_ranges() == []
