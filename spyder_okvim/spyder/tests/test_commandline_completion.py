"""Qt integration tests for Ex completion and command-line key handling."""

# Standard Libraries
import os
import threading
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QInputMethodEvent
from qtpy.QtWidgets import QApplication
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.executor.executor_colon import ExecutorColon
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.ex_parser import is_substitute
from tests.qt_support import reset_vim_state


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
    reset_vim_state(status)
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
        reset_vim_state(status)
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


@pytest.fixture
def path_scans(monkeypatch):
    """Count directory reads while preserving the real filesystem behavior."""
    scan = Mock(wraps=os.scandir)
    monkeypatch.setattr(os, "scandir", scan)
    return scan


def press_tab(commandline, qtbot, key=Qt.Key_Tab, modifiers=Qt.NoModifier):
    """Wait for an explicit filesystem completion before checking its result."""
    qtbot.keyPress(commandline, key, modifiers)
    controller = commandline.vim_widget.commandline_popup
    qtbot.waitUntil(lambda: not controller.path_tab_pending, timeout=3000)


@pytest.fixture
def blocked_path_lookup(completion_bot, monkeypatch):
    """Hold real worker I/O while the GUI keeps accepting prompt input."""
    # Project Libraries
    from spyder_okvim.spyder import commandline_path_lookup as lookup

    _, _, commandline, qtbot, _ = completion_bot
    controller = commandline.vim_widget.commandline_popup
    blocked = SimpleNamespace(
        started=threading.Event(), release=threading.Event(), calls=[]
    )
    scan = lookup.path_completion_items

    def blocked_scan(request, cancelled=None):
        blocked.calls.append((request, threading.get_ident()))
        blocked.started.set()
        if not blocked.release.wait(5):
            raise TimeoutError("Test did not release its filesystem worker")
        return scan(request, cancelled=cancelled)

    monkeypatch.setattr(lookup, "path_completion_items", blocked_scan)
    try:
        yield blocked
    finally:
        blocked.release.set()
        qtbot.waitUntil(lambda: not controller._path_lookup.busy, timeout=3000)


def wait_for_path_candidates(commandline, qtbot, expected):
    """Wait for the debounced path result instead of a fixed timer deadline."""
    controller = commandline.vim_widget.commandline_popup
    qtbot.waitUntil(
        lambda: [
            candidate.text
            for candidate in controller.candidates
            if candidate.apply_scope == "path"
        ]
        == expected,
        timeout=2000,
    )


def test_tab_cycles_commands_and_preserves_focus(completion_bot):
    """Tab repeatedly cycles the original prefix without executing a command."""
    editor, status, commandline, qtbot, _ = completion_bot
    original = editor.toPlainText()
    qtbot.keyClicks(commandline, ":w")

    for expected in (":w", ":wq", ":w", ":wq"):
        press_tab(commandline, qtbot)
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
        press_tab(commandline, qtbot, key=key, modifiers=Qt.ShiftModifier)
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
        "spyder_okvim.spyder.commandline_input.completion_items", unexpected_completion
    )
    qtbot.keyClicks(commandline, prefix + "w")
    original = commandline.text()
    original_cursor = commandline.cursorPosition()

    press_tab(commandline, qtbot)
    press_tab(commandline, qtbot, modifiers=Qt.ShiftModifier)
    press_tab(commandline, qtbot, key=Qt.Key_Backtab)

    assert commandline.text() == original
    assert commandline.cursorPosition() == original_cursor
    assert commandline.hasFocus()


@pytest.mark.parametrize("draft", [":unknown", ":w missing/path"])
def test_no_match_keeps_the_prompt_and_focus(completion_bot, draft):
    """No matching command or path leaves the original input available."""
    _, _, commandline, qtbot, _ = completion_bot
    qtbot.keyClicks(commandline, draft)
    position = commandline.cursorPosition()

    press_tab(commandline, qtbot)

    assert commandline.text() == draft
    assert commandline.cursorPosition() == position
    assert commandline.hasFocus()


@pytest.mark.parametrize("navigate_back_to_draft", [False, True])
def test_history_navigation_restarts_completion(completion_bot, navigate_back_to_draft):
    """Each history destination gets candidates for its own current spelling."""
    _, _, commandline, qtbot, _ = completion_bot
    commandline.histories["ex"].append("q")
    qtbot.keyClicks(commandline, ":w")
    press_tab(commandline, qtbot)
    press_tab(commandline, qtbot)
    assert commandline.text() == ":wq"
    qtbot.keyPress(commandline, Qt.Key_Up)
    assert commandline.text() == ":q"

    if navigate_back_to_draft:
        qtbot.keyPress(commandline, Qt.Key_Down)
        assert commandline.text() == ":wq"
        press_tab(commandline, qtbot)
        assert commandline.text() == ":wq"
    else:
        press_tab(commandline, qtbot)
        assert commandline.text() == ":q"
        press_tab(commandline, qtbot)
        assert commandline.text() == ":q!"


def test_editing_text_restarts_completion(completion_bot):
    """Editing the prefix discards an earlier Tab cycle."""
    _, _, commandline, qtbot, _ = completion_bot
    qtbot.keyClicks(commandline, ":w")
    press_tab(commandline, qtbot)
    assert commandline.text() == ":w"
    qtbot.keyPress(commandline, Qt.Key_Backspace)
    assert commandline.text() == ":"

    press_tab(commandline, qtbot)

    assert commandline.text() == ":e"


def test_moving_the_caret_restarts_completion(completion_bot):
    """Tab completes at the new caret instead of cycling the old prefix."""
    _, _, commandline, qtbot, _ = completion_bot
    qtbot.keyClicks(commandline, ":w")
    press_tab(commandline, qtbot)
    qtbot.keyPress(commandline, Qt.Key_Left)
    assert commandline.cursorPosition() == 1

    press_tab(commandline, qtbot)

    assert commandline.text() == ":e"
    assert commandline.cursorPosition() == len(":e")


def test_completing_command_in_middle_preserves_its_argument(completion_bot):
    """Replacing a command name does not erase the path after the caret."""
    _, _, commandline, qtbot, _ = completion_bot
    qtbot.keyClicks(commandline, ":w draft file.py")
    commandline.setCursorPosition(2)
    press_tab(commandline, qtbot)
    press_tab(commandline, qtbot)

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

    press_tab(commandline, qtbot)

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

    press_tab(commandline, qtbot)

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

    press_tab(commandline, qtbot)
    assert commandline.text() == ":w 한글 폴더" + os.sep
    press_tab(commandline, qtbot)
    expected = ":w 한글 폴더" + os.sep + "완료 파일.py"
    assert commandline.text() == expected
    assert commandline.cursorPosition() == utf16_position(expected)
    assert commandline.hasFocus()


def test_tab_filters_extensions_without_reading_file_contents(
    completion_bot, monkeypatch, tmp_path
):
    """Allowed extensions include binary contents but exclude extensionless files."""
    _, _, commandline, qtbot, _ = completion_bot
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "binary.py").write_bytes(b"\x00\x01\x02\x03")
    (tmp_path / "notes").write_text("Project notes\n", encoding="utf-8")
    (tmp_path / "source").mkdir()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":e ")

    for expected in (":e binary.py", ":e source" + os.sep, ":e binary.py"):
        press_tab(commandline, qtbot)
        assert commandline.text() == expected
        assert commandline.hasFocus()


@pytest.mark.parametrize("command", ["e", "w"])
def test_tab_commits_composition_before_completing_path(
    completion_bot, monkeypatch, tmp_path, command
):
    """The final composing syllable participates in the path prefix."""
    _, _, commandline, qtbot, _ = completion_bot
    (tmp_path / "한글 파일.py").touch()
    (tmp_path / "other.py").touch()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":" + command + " ")
    send_input_method(commandline, preedit="한")
    commits = []

    def commit():
        commits.append(True)
        send_input_method(commandline, commit="한")

    monkeypatch.setattr(QApplication.inputMethod(), "commit", commit)
    press_tab(commandline, qtbot)

    assert commits == [True]
    assert commandline.text() == ":" + command + " 한글 파일.py"
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
    # Project Libraries
    from spyder_okvim.utils import commandline as helpers

    scandir = helpers.os.scandir
    lookups = []

    def scan(directory):
        lookups.append(directory)
        return scandir(directory)

    monkeypatch.setattr(helpers.os, "scandir", scan)
    qtbot.keyClicks(commandline, ":w al")
    qtbot.wait(160)
    assert lookups == []

    for expected in (":w alpha.py", ":w alpine.py", ":w alpha.py"):
        press_tab(commandline, qtbot)
        assert commandline.text() == expected
    assert len(lookups) == 1


@pytest.mark.parametrize("backward", [False, True])
def test_tab_reuses_automatic_candidates_and_keeps_original_cycle(
    completion_bot, monkeypatch, tmp_path, path_scans, backward
):
    """Automatic display is passive; first Tab applies the requested endpoint."""
    _, _, commandline, qtbot, _ = completion_bot
    for filename in ("alpha.py", "alpine.py"):
        (tmp_path / filename).touch()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":e al")
    wait_for_path_candidates(commandline, qtbot, [":e alpha.py", ":e alpine.py"])
    controller = commandline.vim_widget.commandline_popup
    assert commandline.text() == ":e al"
    assert controller.selected_index is None
    assert path_scans.call_count == 1

    expected = (
        [":e alpine.py", ":e alpha.py", ":e alpine.py"]
        if backward
        else [":e alpha.py", ":e alpine.py", ":e alpha.py"]
    )
    modifier = Qt.ShiftModifier if backward else Qt.NoModifier
    for value in expected:
        press_tab(commandline, qtbot, modifiers=modifier)
        assert commandline.text() == value
        qtbot.wait(160)
        assert path_scans.call_count == 1
        assert controller.popup.isVisible()


def test_tab_reuses_a_completed_empty_automatic_result(
    completion_bot, monkeypatch, tmp_path, path_scans
):
    """An empty directory is a completed lookup, including for later Tab."""
    _, _, commandline, qtbot, _ = completion_bot
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":e missing")
    qtbot.waitUntil(lambda: path_scans.call_count == 1, timeout=2000)
    controller = commandline.vim_widget.commandline_popup

    for _ in range(3):
        controller.sync()
        press_tab(commandline, qtbot)
        qtbot.wait(160)
        assert commandline.text() == ":e missing"
        assert controller.candidates == []
        assert path_scans.call_count == 1


@pytest.mark.parametrize("completion_enabled", [False, True])
@pytest.mark.parametrize("command", ["e", "w"])
def test_tab_reuses_empty_explicit_path_results(
    completion_bot, monkeypatch, tmp_path, path_scans, command, completion_enabled
):
    """An empty explicit result remains reusable outside automatic display scope."""
    _, _, commandline, qtbot, _ = completion_bot
    monkeypatch.chdir(tmp_path)
    controller = commandline.vim_widget.commandline_popup
    previous = CONF.get(CONF_SECTION, "commandline_completion_enabled", True)
    CONF.set(CONF_SECTION, "commandline_completion_enabled", completion_enabled)
    controller.apply_settings()
    try:
        qtbot.keyClicks(commandline, ":" + command + " missing")
        for _ in range(3):
            press_tab(commandline, qtbot)
            qtbot.wait(160)
            assert commandline.text() == ":" + command + " missing"
            assert path_scans.call_count == 1
    finally:
        CONF.set(CONF_SECTION, "commandline_completion_enabled", previous)
        controller.apply_settings()


@pytest.mark.parametrize("has_match", [False, True])
def test_tab_takes_over_a_pending_automatic_lookup(
    completion_bot, monkeypatch, tmp_path, path_scans, has_match
):
    """Tab resolves a pending request once and cancels its delayed duplicate."""
    _, _, commandline, qtbot, _ = completion_bot
    if has_match:
        (tmp_path / "alpha.py").touch()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":e al")
    path_scans.assert_not_called()

    press_tab(commandline, qtbot)

    expected = ":e alpha.py" if has_match else ":e al"
    assert commandline.text() == expected
    assert path_scans.call_count == 1
    qtbot.wait(160)
    press_tab(commandline, qtbot)
    qtbot.wait(160)
    assert commandline.text() == expected
    assert path_scans.call_count == 1


def test_unique_directory_waits_for_next_explicit_tab_before_descending(
    completion_bot, monkeypatch, tmp_path, path_scans
):
    """Applying a unique directory keeps its list until another Tab enters it."""
    _, _, commandline, qtbot, _ = completion_bot
    folder = tmp_path / "source"
    folder.mkdir()
    (folder / "child.py").touch()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":e s")
    directory_input = ":e source" + os.sep
    wait_for_path_candidates(commandline, qtbot, [directory_input])

    press_tab(commandline, qtbot)
    assert commandline.text() == directory_input
    qtbot.wait(160)
    assert path_scans.call_count == 1

    press_tab(commandline, qtbot)
    assert commandline.text() == directory_input + "child.py"
    qtbot.wait(160)
    assert path_scans.call_count == 2


def test_tab_discards_automatic_result_after_working_directory_changes(
    completion_bot, monkeypatch, tmp_path, path_scans
):
    """The same draft in a different cwd must query that new directory."""
    _, _, commandline, qtbot, _ = completion_bot
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "alpha.py").touch()
    (second / "albatross.py").touch()
    monkeypatch.chdir(first)
    qtbot.keyClicks(commandline, ":e al")
    wait_for_path_candidates(commandline, qtbot, [":e alpha.py"])

    monkeypatch.chdir(second)
    press_tab(commandline, qtbot)

    assert commandline.text() == ":e albatross.py"
    qtbot.wait(160)
    assert path_scans.call_count == 2


def test_tab_applies_cached_unicode_path_with_middle_cursor_and_quote(
    completion_bot, monkeypatch, tmp_path, path_scans
):
    """Cached Python cursor offsets convert back to Qt while preserving suffix."""
    _, _, commandline, qtbot, _ = completion_bot
    (tmp_path / "😀 자료.py").touch()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":e ")
    commandline.setText(':e "😀 자WRONG"')
    commandline.setCursorPosition(utf16_position(':e "😀 자'))
    wait_for_path_candidates(commandline, qtbot, [':e "😀 자료.py"'])
    assert path_scans.call_count == 1

    press_tab(commandline, qtbot)

    assert commandline.text() == ':e "😀 자료.py"'
    assert commandline.cursorPosition() == utf16_position(':e "😀 자료.py')
    qtbot.wait(160)
    assert path_scans.call_count == 1


@pytest.mark.parametrize(
    "directions, expected",
    [
        ([1, 1], "alpine.py"),
        ([1, -1], "alps.py"),
        ([-1, 1], "alpha.py"),
        ([-1, -1], "alpine.py"),
        ([1, 1, 1, 1], "alpha.py"),
        ([-1, -1, -1, -1], "alps.py"),
    ],
)
def test_pending_tabs_preserve_direction_and_cycle_count(
    completion_bot, monkeypatch, tmp_path, blocked_path_lookup, directions, expected
):
    """Rapid explicit Tabs retain their count while a single worker is busy."""
    _, _, commandline, qtbot, _ = completion_bot
    for filename in ("alpha.py", "alpine.py", "alps.py"):
        (tmp_path / filename).touch()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":e al")
    blocked = blocked_path_lookup
    controller = commandline.vim_widget.commandline_popup
    first, *remaining = directions
    modifier = Qt.NoModifier if first == 1 else Qt.ShiftModifier
    qtbot.keyPress(commandline, Qt.Key_Tab, modifier)
    qtbot.waitUntil(blocked.started.is_set, timeout=2000)
    assert controller.path_tab_pending
    assert commandline.text() == ":e al"
    assert blocked.calls[0][1] != threading.get_ident()

    for direction in remaining:
        modifier = Qt.NoModifier if direction == 1 else Qt.ShiftModifier
        qtbot.keyPress(commandline, Qt.Key_Tab, modifier)
        assert commandline.text() == ":e al"

    blocked.release.set()
    qtbot.waitUntil(lambda: not controller.path_tab_pending, timeout=2000)
    assert commandline.text() == ":e " + expected
    assert len(blocked.calls) == 1
    qtbot.wait(160)
    assert len(blocked.calls) == 1


@pytest.mark.parametrize("cancel_action", ["edit", "enter", "escape"])
def test_pending_tab_is_cancelled_by_input_execution_or_escape(
    completion_bot, monkeypatch, tmp_path, blocked_path_lookup, cancel_action
):
    """A late result never applies the Tab once its original draft is left."""
    _, status, commandline, qtbot, _ = completion_bot
    (tmp_path / "alpha.py").touch()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":e al")
    blocked = blocked_path_lookup
    controller = commandline.vim_widget.commandline_popup
    qtbot.keyPress(commandline, Qt.Key_Tab)
    qtbot.waitUntil(blocked.started.is_set, timeout=2000)
    assert controller.path_tab_pending

    if cancel_action == "edit":
        qtbot.keyClicks(commandline, "z")
        expected = ":e alz"
    else:
        key = Qt.Key_Return if cancel_action == "enter" else Qt.Key_Escape
        qtbot.keyPress(commandline, key)
        expected = ""
        assert status.sub_mode is None
    assert commandline.text() == expected
    assert not controller.path_tab_pending
    assert not blocked.release.is_set()

    blocked.release.set()
    qtbot.waitUntil(lambda: not controller._path_lookup.busy, timeout=2000)
    qtbot.wait(160)
    assert commandline.text() == expected
    assert commandline.completion_result is None
    assert controller.candidates == []


@pytest.mark.parametrize("transition", ["rewrite", "cursor", "cwd", "escape"])
def test_deferred_tab_rechecks_context_after_input_started_observers(
    completion_bot, monkeypatch, tmp_path, blocked_path_lookup, transition
):
    """A worker's delayed Tab cannot overwrite changes at its input boundary."""
    _, status, commandline, qtbot, _ = completion_bot
    (tmp_path / "alpha.py").touch()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(tmp_path)
    qtbot.keyClicks(commandline, ":e al")
    qtbot.keyPress(commandline, Qt.Key_Tab)
    blocked = blocked_path_lookup
    qtbot.waitUntil(blocked.started.is_set, timeout=2000)
    controller = commandline.vim_widget.commandline_popup
    signal = commandline.vim_widget.sig_input_started
    observed = []

    def change_context():
        signal.disconnect(change_context)
        observed.append(True)
        if transition == "rewrite":
            commandline.setText(":w")
        elif transition == "cursor":
            commandline.setCursorPosition(3)
        elif transition == "cwd":
            monkeypatch.chdir(other)
        else:
            commandline.esc_pressed()

    signal.connect(change_context)
    try:
        blocked.release.set()
        qtbot.waitUntil(lambda: not controller._path_lookup.busy, timeout=2000)
    finally:
        if not observed:
            signal.disconnect(change_context)
    assert observed == [True]
    expected = {"rewrite": ":w", "cursor": ":e al", "cwd": ":e al", "escape": ""}
    assert commandline.text() == expected[transition]
    assert commandline.completion_result is None
    assert not controller.path_tab_pending
    if transition == "cursor":
        assert commandline.cursorPosition() == 3
    elif transition == "escape":
        assert status.sub_mode is None
    qtbot.wait(160)
    assert commandline.text() == expected[transition]
    assert commandline.completion_result is None


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
    press_tab(commandline, qtbot)
    assert commandline.text() == ":e alpha.py"

    monkeypatch.chdir(second)
    press_tab(commandline, qtbot)

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
            press_tab(commandline, qtbot)
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

    press_tab(commandline, qtbot)
    assert commandline.text() == ":e " + quote + completed + quote
    assert commandline.cursorPosition() == utf16_position(":e " + quote + completed)
    opener.assert_not_called()
    qtbot.keyPress(commandline, Qt.Key_Return)

    opener.assert_called_once_with(str(target))
    assert commandline.text() == ""
    assert commandline.hasFocus()
    assert status.sub_mode is None
    assert status.is_normal()


@pytest.mark.parametrize("filename", ["README", "notes.txt"])
def test_edit_can_open_files_outside_completion_extensions(
    completion_bot, vim_bot, monkeypatch, tmp_path, filename
):
    """Completion's extension allowlist never limits an explicitly entered :e."""
    _, status, commandline, qtbot, _ = completion_bot
    target = tmp_path / filename
    target.write_text("ordinary text", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    opener = Mock()
    monkeypatch.setattr(vim_bot[0].editor, "load", opener, raising=False)
    qtbot.keyClicks(commandline, ":e " + filename)

    qtbot.keyPress(commandline, Qt.Key_Return)

    opener.assert_called_once_with(str(target))
    assert commandline.text() == ""
    assert status.sub_mode is None


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

    press_tab(commandline, qtbot)

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

    press_tab(commandline, qtbot)
    press_tab(commandline, qtbot, key=Qt.Key_Backtab)

    assert commandline.text() == ":%" + body
    scandir.assert_not_called()


def test_accepting_field_history_preserves_range_flags_and_other_fields(completion_bot):
    """A selected middle-field suggestion changes input before it can execute."""
    editor, status, line, qtbot, _ = completion_bot
    history = ["s/old/bar/g", "s/old/barn/i"]
    line.histories["ex"][:] = history
    original = editor.toPlainText()
    revision = editor.document().revision()
    previous = status.last_substitute
    qtbot.keyClicks(line, ":")
    line.setText(":%s/foo/baWRONG/g 3")
    line.setCursorPosition(len(":%s/foo/ba"))
    controller = line.vim_widget.commandline_popup

    assert [candidate.text for candidate in controller.candidates] == [
        ":%s/foo/barn/g 3",
        ":%s/foo/bar/g 3",
    ]
    assert controller.selected_index is None
    qtbot.keyPress(line, Qt.Key_N, Qt.ControlModifier)
    assert line.text() == ":%s/foo/baWRONG/g 3"
    qtbot.keyPress(line, Qt.Key_Return)

    assert line.text() == ":%s/foo/barn/g 3"
    assert line.cursorPosition() == len(":%s/foo/barn")
    assert status.sub_mode is not None
    assert controller.selected_index is None
    assert editor.toPlainText() == original
    assert editor.document().revision() == revision
    assert status.last_substitute is previous
    assert line.histories["ex"] == history


def test_tab_cycles_field_history_using_original_prefix(completion_bot, monkeypatch):
    """Tab reuses the field list and leaves the command's other text intact."""
    _, _, line, qtbot, _ = completion_bot
    line.histories["ex"][:] = ["s/old/barn/g", "s/old/bar/g"]
    scandir = Mock(side_effect=AssertionError("field completion requested paths"))
    monkeypatch.setattr(os, "scandir", scandir)
    qtbot.keyClicks(line, ":")
    line.setText(":3,8s/foo/baWRONG/gi 2")
    line.setCursorPosition(len(":3,8s/foo/ba"))
    controller = line.vim_widget.commandline_popup

    for key, value in [
        (Qt.Key_Tab, "bar"),
        (Qt.Key_Tab, "barn"),
        (Qt.Key_Backtab, "bar"),
    ]:
        press_tab(line, qtbot, key=key)
        assert line.text() == ":3,8s/foo/" + value + "/gi 2"
        assert line.cursorPosition() == len(":3,8s/foo/" + value)
        assert line.hasFocus()
        assert controller.popup.isVisible()
        assert controller.selected_index is not None
        assert (
            controller.candidates[controller.selected_index].apply_scope
            == "replacement"
        )
    scandir.assert_not_called()


@pytest.mark.parametrize(
    "history, text, prefix, expected, scope",
    [
        (
            [r"s/a\/b/c\/d/g", "s#other#wrong#g"],
            r":%s/a\/OLD/keep/g",
            r":%s/a\/",
            r":%s/a\/b/keep/g",
            "pattern",
        ),
        (
            ["s#old#wrong#g", "s/foo//g"],
            ":%s/foo/WRONG/g",
            ":%s/foo/",
            ":%s/foo//g",
            "replacement",
        ),
        (
            ["s/foo/😀bar/g"],
            ":%s/foo/😀bOLD/g",
            ":%s/foo/😀b",
            ":%s/foo/😀bar/g",
            "replacement",
        ),
    ],
)
def test_field_completion_preserves_raw_escapes_empty_values_and_utf16_cursor(
    completion_bot, history, text, prefix, expected, scope
):
    _, _, line, qtbot, _ = completion_bot
    line.histories["ex"][:] = history
    qtbot.keyClicks(line, ":")
    line.setText(text)
    line.setCursorPosition(utf16_position(prefix))
    controller = line.vim_widget.commandline_popup
    assert len(controller.candidates) == 1
    assert controller.candidates[0].apply_scope == scope
    applied_cursor = controller.candidates[0].cursor_position
    if expected == ":%s/foo//g":
        assert controller.candidates[0].label == "(빈 문자열: 삭제)"

    press_tab(line, qtbot)

    assert line.text() == expected
    assert line.cursorPosition() == utf16_position(expected[:applied_cursor])
    assert line.hasFocus()
