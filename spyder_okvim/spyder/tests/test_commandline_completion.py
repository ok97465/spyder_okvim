"""Qt integration tests for Ex completion and command-line key handling."""

import os
from unittest.mock import Mock

import pytest
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QInputMethodEvent
from qtpy.QtWidgets import QApplication

from spyder_okvim.executor.executor_colon import ExecutorColon
from spyder_okvim.utils.ex_parser import is_substitute


@pytest.fixture
def completion_bot(vim_bot):
    """Give each test an empty prompt, history, and a focused active editor."""
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
    original_text = editor.toPlainText()
    editor.set_text("foo x foo")
    status.cursor.set_cursor_pos(0)
    for history in commandline.histories.values():
        history.clear()
    try:
        yield editor, status, commandline, qtbot, stack
    finally:
        commandline.setFocus()
        QCoreApplication.processEvents()
        commandline.esc_pressed()
        status.disconnect_from_editor()
        status.reset_for_test()
        editor.set_text(original_text)
        for history in commandline.histories.values():
            history.clear()
        stack.set_stack_index(previous_index)


def send_input_method(widget, preedit="", commit=""):
    """Deliver native-style composition and commits without ASCII key helpers."""
    event = QInputMethodEvent(preedit, [])
    event.setCommitString(commit)
    QCoreApplication.sendEvent(widget, event)


def utf16_position(text):
    """Return the cursor offset used by Qt for a Python string."""
    return len(text.encode("utf-16-le")) // 2


def test_tab_cycles_commands_and_preserves_focus(completion_bot):
    """Tab repeatedly cycles the original prefix without executing a command."""
    editor, status, commandline, qtbot, _ = completion_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, ":w")

    for expected in (":w", ":wq", ":w", ":wq"):
        qtbot.keyPress(commandline, Qt.Key_Tab)
        assert commandline.text() == expected
        assert commandline.hasFocus()
        assert status.sub_mode is not None
        assert commandline.histories["ex"] == []
        assert editor.toPlainText() == original


def test_yanky_command_completion_and_dispatch(completion_bot, vim_bot, monkeypatch):
    """Yanky Ex commands complete and use the same widget entry points."""
    _, _, commandline, qtbot, _ = completion_bot
    widget = vim_bot[3].vim_cmd
    show, clear = Mock(), Mock()
    monkeypatch.setattr(widget, "show_yank_history", show, raising=False)
    monkeypatch.setattr(widget, "clear_yank_history", clear, raising=False)
    qtbot.keyClicks(commandline, ":YankyRing")
    qtbot.keyClick(commandline, Qt.Key_Tab)
    assert commandline.text() == ":YankyRingHistory"
    show.assert_not_called()
    qtbot.keyClick(commandline, Qt.Key_Return)
    show.assert_called_once_with()
    qtbot.keyClicks(commandline, ":YankyClear")
    qtbot.keyClick(commandline, Qt.Key_Tab)
    assert commandline.text() == ":YankyClearHistory"
    qtbot.keyClick(commandline, Qt.Key_Return)
    clear.assert_called_once_with()
    assert commandline.text() == ""


@pytest.mark.parametrize("backtab", [False, True])
def test_shift_tab_cycles_commands_backwards(completion_bot, backtab):
    """Both shifted Tab and Qt's Backtab key move through names in reverse."""
    _, _, commandline, qtbot, _ = completion_bot
    qtbot.keyClicks(commandline, ":q")
    key = Qt.Key_Backtab if backtab else Qt.Key_Tab

    for expected in (":q!", ":q", ":q!"):
        qtbot.keyPress(commandline, key, Qt.ShiftModifier)
        assert commandline.text() == expected
        assert commandline.hasFocus()


@pytest.mark.parametrize("prefix", ["/", "?", "2/", "d/", "v/", "V/"])
def test_search_tab_does_not_complete_or_move_focus(
    completion_bot, monkeypatch, prefix
):
    """Search text stays literal and Tab never reaches the Ex completer."""
    _, _, commandline, qtbot, _ = completion_bot

    def unexpected_completion(*args, **kwargs):
        pytest.fail("Search input must not request Ex completion")

    monkeypatch.setattr(
        "spyder_okvim.spyder.vim_widgets.completion_candidates", unexpected_completion
    )
    qtbot.keyClicks(commandline, prefix + "w")
    original = commandline.text()
    original_cursor = commandline.cursorPosition()

    qtbot.keyPress(commandline, Qt.Key_Tab)
    qtbot.keyPress(commandline, Qt.Key_Tab, Qt.ShiftModifier)
    qtbot.keyPress(commandline, Qt.Key_Backtab)

    assert commandline.text() == original
    assert commandline.cursorPosition() == original_cursor
    assert commandline.hasFocus()


@pytest.mark.parametrize("draft", [":unknown", ":w missing/path"])
def test_no_match_keeps_the_prompt_and_focus(completion_bot, draft):
    """No matching command or path leaves the original input available."""
    _, _, commandline, qtbot, _ = completion_bot
    qtbot.keyClicks(commandline, draft)
    position = commandline.cursorPosition()

    qtbot.keyPress(commandline, Qt.Key_Tab)

    assert commandline.text() == draft
    assert commandline.cursorPosition() == position
    assert commandline.hasFocus()


@pytest.mark.parametrize("navigate_back_to_draft", [False, True])
def test_history_navigation_restarts_completion(completion_bot, navigate_back_to_draft):
    """Each history destination gets candidates for its own current spelling."""
    _, _, commandline, qtbot, _ = completion_bot
    commandline.histories["ex"].append("q")
    qtbot.keyClicks(commandline, ":w")
    qtbot.keyPress(commandline, Qt.Key_Tab)
    qtbot.keyPress(commandline, Qt.Key_Tab)
    assert commandline.text() == ":wq"
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == ":q"

    if navigate_back_to_draft:
        qtbot.keyPress(commandline, Qt.Key_Down)
        assert commandline.text() == ":wq"
        qtbot.keyPress(commandline, Qt.Key_Tab)
        assert commandline.text() == ":wq"
    else:
        qtbot.keyPress(commandline, Qt.Key_Tab)
        assert commandline.text() == ":q"
        qtbot.keyPress(commandline, Qt.Key_Tab)
        assert commandline.text() == ":q!"


def test_editing_text_restarts_completion(completion_bot):
    """Editing the prefix discards an earlier Tab cycle."""
    _, _, commandline, qtbot, _ = completion_bot
    qtbot.keyClicks(commandline, ":w")
    qtbot.keyPress(commandline, Qt.Key_Tab)
    assert commandline.text() == ":w"
    qtbot.keyPress(commandline, Qt.Key_Backspace)
    assert commandline.text() == ":"

    qtbot.keyPress(commandline, Qt.Key_Tab)

    assert commandline.text() == ":e"


def test_moving_the_caret_restarts_completion(completion_bot):
    """Tab completes at the new caret instead of cycling the old prefix."""
    _, _, commandline, qtbot, _ = completion_bot
    qtbot.keyClicks(commandline, ":w")
    qtbot.keyPress(commandline, Qt.Key_Tab)
    qtbot.keyPress(commandline, Qt.Key_Left)
    assert commandline.cursorPosition() == 1

    qtbot.keyPress(commandline, Qt.Key_Tab)

    assert commandline.text() == ":e"
    assert commandline.cursorPosition() == len(":e")


def test_completing_command_in_middle_preserves_its_argument(completion_bot):
    """Replacing a command name does not erase the path after the caret."""
    _, _, commandline, qtbot, _ = completion_bot
    qtbot.keyClicks(commandline, ":w draft file.py")
    commandline.setCursorPosition(2)
    qtbot.keyPress(commandline, Qt.Key_Tab)
    qtbot.keyPress(commandline, Qt.Key_Tab)

    assert commandline.text() == ":wq draft file.py"
    assert commandline.cursorPosition() == 3


@pytest.mark.parametrize(
    "filename, prefix", [("한글 보고서.py", "한"), ("😀 보고서.py", "😀")]
)
@pytest.mark.parametrize(
    "command",
    [name for name in ExecutorColon.SUPPORTED_COMMANDS if not is_substitute(name)],
)
def test_relative_unicode_path_completion_uses_working_directory(
    completion_bot, monkeypatch, tmp_path, filename, prefix, command
):
    """Path-enabled commands complete from cwd, independently of the active file."""
    _, _, commandline, qtbot, stack = completion_bot
    folder = tmp_path / "working directory"
    folder.mkdir()
    (folder / filename).touch()
    editor_folder = tmp_path / "editor folder"
    editor_folder.mkdir()
    (editor_folder / (prefix + " editor only.py")).touch()
    monkeypatch.chdir(folder)
    monkeypatch.setattr(
        stack, "get_current_filename", lambda: str(editor_folder / "active.py")
    )
    qtbot.keyClicks(commandline, ":" + command + " ")
    send_input_method(commandline, commit=prefix)

    qtbot.keyPress(commandline, Qt.Key_Tab)

    expected = ":" + command + " " + filename
    assert commandline.text() == expected
    assert commandline.cursorPosition() == utf16_position(expected)
    assert commandline.hasFocus()


def test_completion_inside_quoted_non_bmp_path_keeps_suffix(
    completion_bot, monkeypatch, tmp_path
):
    """UTF-16 input offsets and output offsets preserve a closing path quote."""
    _, _, commandline, qtbot, _ = completion_bot
    (tmp_path / "😀 자료.py").touch()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":w ")
    commandline.setText(':w "😀 자WRONG"')
    commandline.setCursorPosition(utf16_position(':w "😀 자'))

    qtbot.keyPress(commandline, Qt.Key_Tab)

    assert commandline.text() == ':w "😀 자료.py"'
    assert commandline.cursorPosition() == utf16_position(':w "😀 자료.py')


def test_next_tab_enters_a_uniquely_completed_directory(
    completion_bot, monkeypatch, tmp_path
):
    """A unique directory result becomes the base for the next explicit Tab."""
    _, _, commandline, qtbot, _ = completion_bot
    folder = tmp_path / "한글 폴더"
    folder.mkdir()
    (folder / "완료 파일.py").touch()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":w ")
    send_input_method(commandline, commit="한")

    qtbot.keyPress(commandline, Qt.Key_Tab)
    assert commandline.text() == ":w 한글 폴더" + os.sep
    qtbot.keyPress(commandline, Qt.Key_Tab)
    expected = ":w 한글 폴더" + os.sep + "완료 파일.py"
    assert commandline.text() == expected
    assert commandline.cursorPosition() == utf16_position(expected)
    assert commandline.hasFocus()


def test_tab_skips_cache_directories_and_binary_files(
    completion_bot, monkeypatch, tmp_path
):
    """Tab cycles through text paths and ordinary directories only."""
    _, _, commandline, qtbot, _ = completion_bot
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "binary.py").write_bytes(b"\x00\x01\x02\x03")
    (tmp_path / "notes").write_text("Project notes\n", encoding="utf-8")
    (tmp_path / "source").mkdir()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":e ")

    for expected in (":e notes", ":e source" + os.sep, ":e notes"):
        qtbot.keyPress(commandline, Qt.Key_Tab)
        assert commandline.text() == expected
        assert commandline.hasFocus()


def test_tab_commits_composition_before_completing_path(
    completion_bot, monkeypatch, tmp_path
):
    """The final composing syllable participates in the path prefix."""
    _, _, commandline, qtbot, _ = completion_bot
    (tmp_path / "한글 파일.py").touch()
    (tmp_path / "other.py").touch()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":w ")
    send_input_method(commandline, preedit="한")
    commits = []

    def commit():
        commits.append(True)
        send_input_method(commandline, commit="한")

    monkeypatch.setattr(QApplication.inputMethod(), "commit", commit)
    qtbot.keyPress(commandline, Qt.Key_Tab)

    assert commits == [True]
    assert commandline.text() == ":w 한글 파일.py"
    assert commandline.hasFocus()


def test_up_commits_composition_before_saving_the_draft(completion_bot, monkeypatch):
    """Returning from history restores the committed composing syllable too."""
    _, _, commandline, qtbot, _ = completion_bot
    commandline.histories["search"].append("foo")
    qtbot.keyClicks(commandline, "/draft")
    send_input_method(commandline, preedit="한")
    pending = ["한"]
    commits = []

    def commit():
        commits.append(True)
        if pending:
            send_input_method(commandline, commit=pending.pop())

    monkeypatch.setattr(QApplication.inputMethod(), "commit", commit)
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == "/foo"
    qtbot.keyPress(commandline, Qt.Key_Down)

    assert commits == [True, True]
    assert commandline.text() == "/draft한"
    assert commandline.cursorPosition() == len("/draft한")
    assert commandline.hasFocus()


def test_path_lookup_runs_on_tab_and_reuses_cycle_candidates(
    completion_bot, monkeypatch, tmp_path
):
    """Typing performs no directory I/O and repeated Tab reuses one listing."""
    _, _, commandline, qtbot, _ = completion_bot
    (tmp_path / "alpha.py").touch()
    (tmp_path / "alpine.py").touch()
    monkeypatch.chdir(tmp_path)
    from spyder_okvim.utils import commandline as helpers

    scandir = helpers.os.scandir
    lookups = []

    def scan(directory):
        lookups.append(directory)
        return scandir(directory)

    monkeypatch.setattr(helpers.os, "scandir", scan)
    qtbot.keyClicks(commandline, ":w al")
    assert lookups == []

    for expected in (":w alpha.py", ":w alpine.py", ":w alpha.py"):
        qtbot.keyPress(commandline, Qt.Key_Tab)
        assert commandline.text() == expected
    assert len(lookups) == 1


def test_changing_working_directory_discards_old_path_candidates(
    completion_bot, monkeypatch, tmp_path
):
    """Changing cwd during completion cannot cycle into the old directory."""
    _, _, commandline, qtbot, _ = completion_bot
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "alpha.py").touch()
    (first / "alpine.py").touch()
    (second / "alpha.py").touch()
    monkeypatch.chdir(first)
    qtbot.keyClicks(commandline, ":e al")
    qtbot.keyPress(commandline, Qt.Key_Tab)
    assert commandline.text() == ":e alpha.py"

    monkeypatch.chdir(second)
    qtbot.keyPress(commandline, Qt.Key_Tab)

    assert commandline.text() == ":e alpha.py"


def test_edit_path_tab_cycle_opens_the_chosen_file(
    completion_bot, vim_bot, monkeypatch, tmp_path
):
    """The requested :e a<Tab> workflow opens a file and targets its editor."""
    editor, status, commandline, qtbot, stack = completion_bot
    main = vim_bot[0]
    editor_folder = tmp_path / "editor folder"
    editor_folder.mkdir()
    source = editor_folder / "active.py"
    (editor_folder / "a_editor_only.py").touch()
    first = tmp_path / "a_first.py"
    second = tmp_path / "a_second.py"
    first.write_text("abcd", encoding="utf-8")
    second.touch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(stack, "get_main_widget", lambda: main.editor)
    monkeypatch.setattr(
        main.editor, "can_close_file", Mock(return_value=True), raising=False
    )
    source_finfo = stack.get_current_finfo()
    monkeypatch.setattr(source_finfo, "filename", str(source))
    opened = []

    def open_file(path):
        finfo = stack.load(path, processevents=False)
        opened.append(finfo)
        status.cursor.set_cursor_pos(0)

    opener = Mock(side_effect=open_file)
    monkeypatch.setattr(main.editor, "load", opener, raising=False)
    status.cursor.set_cursor_pos(2)
    qtbot.keyClicks(commandline, ":e a")
    try:
        for expected in (":e a_first.py", ":e a_second.py", ":e a_first.py"):
            qtbot.keyPress(commandline, Qt.Key_Tab)
            assert commandline.text() == expected
            opener.assert_not_called()
            assert commandline.hasFocus()

        qtbot.keyPress(commandline, Qt.Key_Return)

        opener.assert_called_once_with(str(first))
        assert commandline.text() == ""
        assert commandline.hasFocus()
        assert status.sub_mode is None
        assert status.is_normal()
        assert [(jump.file, jump.pos) for jump in status.jump_list.jumps] == [
            (str(source), 2),
            (str(first), 0),
        ]
        assert commandline.histories["ex"] == ["e a_first.py"]
        assert len(opened) == 1
        target_editor = opened[0].editor
        assert status.get_editor() is target_editor
        assert target_editor.toPlainText().startswith("abcd")
        assert target_editor.get_extra_selections("vim_cursor")
        qtbot.keyClicks(commandline, "l")
        assert target_editor.textCursor().position() == 1
        assert editor.textCursor().position() == 2
    finally:
        commandline.esc_pressed()
        for finfo in opened:
            finfo.editor.document().setModified(False)
            index = stack.is_file_opened(finfo.filename)
            if index is not None:
                stack.close_file(index, force=True)
        stack.set_current_filename(str(source))


@pytest.mark.parametrize(
    "path_kind", ["relative", "dot", "parent", "nested", "absolute", "home"]
)
@pytest.mark.parametrize("quote", ["", "'", '"'])
def test_edit_completed_unicode_path_opens_matching_file(
    completion_bot, vim_bot, monkeypatch, tmp_path, path_kind, quote
):
    """Completed relative paths open from cwd, preserving Unicode and quotes."""
    _, status, commandline, qtbot, stack = completion_bot
    main = vim_bot[0]
    base = tmp_path / "working directory"
    base.mkdir()
    editor_folder = tmp_path / "editor folder"
    editor_folder.mkdir()
    (editor_folder / "한글 초안.py").touch()
    monkeypatch.chdir(base)
    target_folder = base
    path_prefix = ""
    if path_kind == "dot":
        path_prefix = "." + os.sep
    elif path_kind == "parent":
        target_folder = tmp_path
        path_prefix = ".." + os.sep
    elif path_kind == "nested":
        target_folder = base / "자료 폴더"
        target_folder.mkdir()
        path_prefix = target_folder.name + os.sep
    elif path_kind == "absolute":
        path_prefix = str(base) + os.sep
    elif path_kind == "home":
        expanduser = os.path.expanduser

        def expand(path):
            if path.startswith("~" + os.sep):
                return str(base / path[2:])
            return expanduser(path)

        monkeypatch.setattr(os.path, "expanduser", expand)
        path_prefix = "~" + os.sep
    target = target_folder / "한글 초안.py"
    target.touch()
    monkeypatch.setattr(
        stack, "get_current_filename", lambda: str(editor_folder / "active.py")
    )
    opener = Mock()
    monkeypatch.setattr(main.editor, "load", opener, raising=False)
    prefix = path_prefix + "한"
    completed = path_prefix + target.name
    qtbot.keyClicks(commandline, ":e ")
    commandline.setText(":e " + quote + prefix + quote)
    commandline.setCursorPosition(utf16_position(":e " + quote + prefix))

    qtbot.keyPress(commandline, Qt.Key_Tab)
    assert commandline.text() == ":e " + quote + completed + quote
    assert commandline.cursorPosition() == utf16_position(":e " + quote + completed)
    opener.assert_not_called()
    qtbot.keyPress(commandline, Qt.Key_Return)

    opener.assert_called_once_with(str(target))
    assert commandline.text() == ""
    assert commandline.hasFocus()
    assert status.sub_mode is None
    assert status.is_normal()


@pytest.mark.parametrize("argument", ["", '""', "''", "missing.py", "folder"])
def test_edit_invalid_path_reports_problem_without_opening(
    completion_bot, vim_bot, monkeypatch, tmp_path, argument
):
    """Empty, nonexistent, and directory arguments leave the current file open."""
    editor, status, commandline, qtbot, _ = completion_bot
    main = vim_bot[0]
    (tmp_path / "folder").mkdir()
    monkeypatch.chdir(tmp_path)
    opener = Mock()
    monkeypatch.setattr(main.editor, "load", opener, raising=False)
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, ":e" + (" " + argument if argument else ""))

    qtbot.keyPress(commandline, Qt.Key_Return)

    opener.assert_not_called()
    assert editor.toPlainText() == original
    assert status.msg_label.text()
    assert status.jump_list.jumps == []
    assert status.sub_mode is None
    assert status.is_normal()
    assert commandline.text() == ""
    assert commandline.hasFocus()


@pytest.mark.parametrize("prefix", [":", ":%", ":3,8", ":.,$"])
def test_substitute_header_completion_preserves_range_and_body(completion_bot, prefix):
    """Only the command span changes, including in an incomplete ranged header."""
    _, _, commandline, qtbot, _ = completion_bot
    qtbot.keyClicks(commandline, ":")
    commandline.setText(prefix + "su/foo/bar/g")
    commandline.setCursorPosition(len(prefix + "su"))

    qtbot.keyPress(commandline, Qt.Key_Tab)

    assert commandline.text() == prefix + "substitute/foo/bar/g"
    assert commandline.cursorPosition() == len(prefix + "substitute")


@pytest.mark.parametrize(
    "body", ["s/foo/bar/g", "s/foo bar/new path/g", "substitute#foo#bar#", "s foo"]
)
def test_substitute_body_never_queries_paths(completion_bot, monkeypatch, body):
    """Tab inside a substitute body leaves raw regex and replacement text alone."""
    _, _, commandline, qtbot, _ = completion_bot
    scandir = Mock(side_effect=AssertionError("substitute requested file completion"))
    monkeypatch.setattr(os, "scandir", scandir)
    qtbot.keyClicks(commandline, ":%" + body)

    qtbot.keyPress(commandline, Qt.Key_Tab)
    qtbot.keyPress(commandline, Qt.Key_Backtab)

    assert commandline.text() == ":%" + body
    scandir.assert_not_called()
