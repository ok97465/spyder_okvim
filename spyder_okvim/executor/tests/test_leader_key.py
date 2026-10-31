# -*- coding: utf-8 -*-
"""Tests for the executor_leader_key."""

# Standard Libraries
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt, QTimer
from spyder.api.plugins import Plugins

# Project Libraries
from spyder_okvim.executor.executor_leader import ExecutorLeaderKey
from spyder_okvim.spyder.editor import EditorCommands
from tests.qt_support import reset_vim_state


def test_leader_hint_candidates_match_dispatch(vim_bot):
    """Hints preserve command order, case and the executable Enter key."""
    _, _, _, vim, _ = vim_bot
    executor = ExecutorLeaderKey(vim.vim_cmd.vim_status)
    candidates = executor.get_hint_candidates()

    assert candidates == [
        ("i", "Auto import"),
        ("I", "Search imports"),
        ("b", "Toggle breakpoint"),
        ("d", "Debug cell"),
        ("D", "Debug selection or line"),
        ("\r", "Run cell and advance"),
        ("r", "Run selection or line"),
        ("f", "Format document or selection"),
        ("p", "Switch file"),
        ("s", "Switch symbol"),
        ("y", "Yank history"),
    ]
    assert [key for key, _ in candidates] == list(executor.dispatcher)
    assert executor.dispatcher["i"] == executor.auto_import
    assert executor.dispatcher["I"] == executor.search_imports
    assert executor.dispatcher["d"] == executor.debug_cell
    assert executor.dispatcher["D"] == executor.debug_selection
    assert executor.dispatcher["\r"] == executor.run_cell_and_advance


def test_leader_hint_candidates_are_read_only(vim_bot):
    """Inspecting or modifying returned hints cannot change input or dispatch."""
    _, _, _, vim, _ = vim_bot
    status = vim.vim_cmd.vim_status
    executor = ExecutorLeaderKey(status)
    dispatcher = executor.dispatcher.copy()
    input_cmd = status.input_cmd.cmd
    sub_mode = status.sub_mode
    candidates = executor.get_hint_candidates()
    candidates.clear()

    assert executor.get_hint_candidates()
    assert executor.dispatcher == dispatcher
    assert status.input_cmd.cmd == input_cmd
    assert status.sub_mode is sub_mode
    assert executor.prev_executor is None


def test_yank_history_leader_dispatch(vim_bot, monkeypatch):
    """The picker command shares the widget's managed popup entry point."""
    _, _, _, vim, qtbot = vim_bot
    widget = vim.vim_cmd
    show = Mock()
    monkeypatch.setattr(widget, "show_yank_history", show, raising=False)
    widget.commandline.esc_pressed()
    qtbot.keyClicks(widget.commandline, " y")
    show.assert_called_once_with()
    assert widget.commandline.text() == ""


@pytest.mark.parametrize("key", [" ", "\r", "\b", "b", "I"])
def test_easymotion_hint_uses_current_key(vim_bot, key):
    """EasyMotion replaces collisions in place and retains raw special keys."""
    _, _, _, vim, _ = vim_bot
    executor = ExecutorLeaderKey(vim.vim_cmd.vim_status)
    original_keys = list(executor.dispatcher)
    expected_keys = original_keys if key in original_keys else original_keys + [key]

    executor.set_easymotion_key(key)
    candidates = executor.get_hint_candidates()
    executor.set_easymotion_key(key)

    assert executor.get_hint_candidates() == candidates
    assert [candidate_key for candidate_key, _ in candidates] == expected_keys
    assert list(executor.dispatcher) == expected_keys
    assert dict(candidates)[key] == "EasyMotion"
    assert executor.dispatcher[key] == executor.execute_easymotion
    assert executor.hint_prefix == key


def test_easymotion_key_change_restores_commands(vim_bot, monkeypatch):
    """Changing leader restores each overridden handler and its description."""
    _, _, _, vim, _ = vim_bot
    breakpoint_command = Mock(return_value=None)
    easymotion_command = Mock(return_value=None)
    monkeypatch.setattr(ExecutorLeaderKey, "toggle_breakpoint", breakpoint_command)
    monkeypatch.setattr(ExecutorLeaderKey, "execute_easymotion", easymotion_command)
    executor = ExecutorLeaderKey(vim.vim_cmd.vim_status)
    default_candidates = executor.get_hint_candidates()
    default_dispatcher = executor.dispatcher.copy()

    executor.set_easymotion_key("b")
    assert executor("b") is True
    easymotion_command.assert_called_once_with(1, "")
    breakpoint_command.assert_not_called()

    executor.set_easymotion_key("I")
    assert executor("b") is True
    breakpoint_command.assert_called_once_with(1, "")
    assert dict(executor.get_hint_candidates())["b"] == "Toggle breakpoint"
    executor.set_easymotion_key("\b")
    assert executor.dispatcher["I"] == default_dispatcher["I"]
    assert dict(executor.get_hint_candidates())["I"] == "Search imports"

    executor.set_easymotion_key(" ")
    assert executor.get_hint_candidates() == default_candidates + [(" ", "EasyMotion")]
    assert "\b" not in executor.dispatcher
    assert {key: executor.dispatcher[key] for key in default_dispatcher} == (
        default_dispatcher
    )


def test_auto_import(vim_bot):
    """Test auto_import."""
    _, _, editor, vim, qtbot = vim_bot

    editor.auto_import = Mock()
    editor.auto_import.auto_import = Mock()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "i")

    assert cmd_line.text() == ""
    assert editor.auto_import.auto_import.called


@pytest.mark.parametrize("accept", [False, True], ids=["cancel", "import"])
def test_search_imports_opens_unfiltered_project_picker(
    vim_bot, monkeypatch, tmp_path, accept
):
    """Space+I opens the real picker, imports or cancels, then restores Vim."""
    autoimport = pytest.importorskip("spyder.plugins.editor.extensions.autoimport")
    selector = pytest.importorskip("spyder.plugins.editor.widgets.importselector")
    _, _, editor, vim, qtbot = vim_bot
    extension = autoimport.AutoImportExtension
    monkeypatch.setattr(extension, "IMPORT_LISTS", {})
    monkeypatch.setattr(extension, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(editor, "auto_import", extension(editor, editor), raising=False)
    monkeypatch.setattr(editor, "filename", str(tmp_path / "main.py"))
    (tmp_path / "helpers.py").write_text(
        "class Worker:\n    pass\ndef calculate():\n    pass\n", encoding="utf-8"
    )
    text = "unrelated_cursor_word()\n"
    editor.set_text(text)
    cmd_line = vim.vim_cmd.commandline
    cmd_line.to_normal()
    reset_vim_state(vim.vim_cmd.vim_status)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(3)
    cmd_line.setFocus()
    observed = []
    timer = QTimer(editor)
    timeout = QTimer(editor)
    timeout.setSingleShot(True)

    def interact():
        for dialog in editor.findChildren(selector.ImportSearchDialog):
            if not dialog.isVisible() or not dialog._scan_complete:
                continue
            observed.append(
                (
                    dialog.search.text(),
                    {
                        dialog.results.topLevelItem(i).text(0)
                        for i in range(dialog.results.topLevelItemCount())
                    },
                    dialog.search.hasFocus(),
                )
            )
            timer.stop()
            if accept:
                dialog.search.setText("Worker")
            qtbot.keyClick(dialog.search, Qt.Key_Return if accept else Qt.Key_Escape)

    def close_on_timeout():
        for dialog in editor.findChildren(selector.ImportSearchDialog):
            dialog.reject()

    timer.timeout.connect(interact)
    timeout.timeout.connect(close_on_timeout)
    timer.start(10)
    timeout.start(5000)
    try:
        qtbot.keyPress(cmd_line, Qt.Key_Space)
        qtbot.keyClicks(cmd_line, "I")
        assert observed == [("", {"Worker", "calculate"}, True)]
        assert cmd_line.text() == ""
        assert cmd_line.isVisible()
        assert cmd_line.window().focusWidget() is cmd_line
        # Offscreen Qt has no window manager to reactivate the parent dialog.
        cmd_line.window().activateWindow()
        qtbot.waitUntil(cmd_line.hasFocus)
        assert editor.textCursor().block().text() == text.rstrip()
        assert editor.textCursor().positionInBlock() == 3
        if accept:
            assert "from helpers import Worker" in editor.toPlainText()
            editor.undo()
        assert editor.toPlainText() == text
    finally:
        timer.stop()
        timeout.stop()
        timer.deleteLater()
        timeout.deleteLater()
        cmd_line.to_normal()


@pytest.mark.parametrize("extension", [None, SimpleNamespace()])
def test_search_imports_without_custom_spyder(vim_bot, monkeypatch, extension):
    """A standard Spyder or an older fork still consumes the leader command."""
    _, _, editor, vim, qtbot = vim_bot
    monkeypatch.setattr(editor, "auto_import", extension, raising=False)
    cmd_line = vim.vim_cmd.commandline
    cmd_line.to_normal()
    text = editor.toPlainText()
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "I")
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text


def test_toggle_breakpoint(vim_bot):
    """Test toggle breakpoint command."""
    _, editor_stack, editor, vim, qtbot = vim_bot

    editor.breakpoints_manager = Mock()
    editor.breakpoints_manager.toogle_breakpoint = Mock()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "b")

    assert cmd_line.text() == ""
    assert editor.breakpoints_manager.toogle_breakpoint.called


def test_run_cell_and_advance(vim_bot):
    """Test run_cell_and_advance."""
    _, editor_stack, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.to_normal()

    cmd_line = vim.vim_cmd.commandline
    signal = editor_stack.sig_trigger_action
    expected_args = ("run cell and advance", Plugins.Run)
    with qtbot.waitSignal(signal, timeout=1000) as blocker:
        qtbot.keyPress(cmd_line, Qt.Key_Space)
        qtbot.keyPress(cmd_line, Qt.Key_Enter)

    assert cmd_line.text() == ""
    assert blocker.signal_triggered
    assert tuple(blocker.args) == expected_args


def test_debug_cell(vim_bot):
    """Lowercase leader d dispatches Spyder's current-cell debugger action."""
    _, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    cmd_line.to_normal()
    text = "# %% First\nalpha = 1\n# %% Second\nbeta = 2\n"
    editor.set_text(text)
    reset_vim_state(vim.vim_cmd.vim_status)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(text.index("beta"))
    cmd_line.setFocus()
    original_cursor = editor.textCursor()

    try:
        signal = editor_stack.sig_trigger_action
        with qtbot.waitSignal(signal, timeout=1000) as blocker:
            qtbot.keyPress(cmd_line, Qt.Key_Space)
            qtbot.keyClicks(cmd_line, "d")

        assert cmd_line.text() == ""
        assert tuple(blocker.args) == ("run cell in debugger", Plugins.Run)
        assert editor.textCursor().position() == original_cursor.position()
        assert editor.textCursor().anchor() == original_cursor.anchor()
        assert editor.toPlainText() == text
    finally:
        cmd_line.to_normal()


@pytest.mark.parametrize(
    "key, action",
    [
        ("r", "run selection and advance"),
        ("D", "run selection in debugger"),
    ],
)
@pytest.mark.parametrize(
    "start, selection_keys, expected_selection",
    [
        pytest.param(12, "", "", id="current-line"),
        pytest.param(0, "v2l", "alp", id="characterwise-at-zero"),
        pytest.param(10, "v2l", "bet", id="characterwise-after-zero"),
        pytest.param(0, "Vj", "alpha = 1\nbeta = 2", id="linewise-at-zero"),
        pytest.param(10, "Vj", "beta = 2\ngamma = 3", id="linewise-after-zero"),
    ],
)
def test_run_or_debug_selection(
    vim_bot, key, action, start, selection_keys, expected_selection
):
    """Expose Vim selections to Spyder while dispatching r and uppercase D."""
    _, editor_stack, editor, vim, qtbot = vim_bot
    cmd_line = vim.vim_cmd.commandline
    cmd_line.to_normal()
    text = "alpha = 1\nbeta = 2\ngamma = 3\n"
    editor.set_text(text)
    reset_vim_state(vim.vim_cmd.vim_status)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(start)
    cmd_line.setFocus()
    if selection_keys:
        qtbot.keyClicks(cmd_line, selection_keys)
    original_cursor = editor.textCursor()
    assert not original_cursor.hasSelection()

    delivered = []

    def capture_action(action_id, plugin):
        # Spyder consumes the native selection synchronously during emission.
        delivered.append(
            (action_id, plugin, editor.textCursor(), editor_stack.get_selection()[0])
        )

    signal = editor_stack.sig_trigger_action
    signal.connect(capture_action)
    try:
        qtbot.keyPress(cmd_line, Qt.Key_Space)
        qtbot.keyClicks(cmd_line, key)

        assert cmd_line.text() == ""
        assert len(delivered) == 1
        action_id, plugin, delivered_cursor, executable_text = delivered[0]
        assert (action_id, plugin) == (action, Plugins.Run)
        assert executable_text == (expected_selection or "beta = 2")
        assert (
            delivered_cursor.selectedText().replace("\u2029", "\n")
            == expected_selection
        )
        if expected_selection:
            assert delivered_cursor.selectionStart() == start
            assert delivered_cursor.selectionEnd() == start + len(expected_selection)
        else:
            assert not delivered_cursor.hasSelection()
            assert delivered_cursor.position() == start
            assert delivered_cursor.block().text() == "beta = 2"

        restored_cursor = editor.textCursor()
        assert restored_cursor.position() == original_cursor.position()
        assert restored_cursor.anchor() == original_cursor.anchor()
        assert editor.toPlainText() == text
    finally:
        signal.disconnect(capture_action)
        cmd_line.to_normal()


@pytest.mark.parametrize("method_name", ["run_selection", "debug_selection"])
def test_selection_and_focus_restored_when_run_action_fails(vim_bot, method_name):
    """Spyder action failures cannot leave the temporary native selection set."""
    _, _, _, vim, _ = vim_bot
    executor = ExecutorLeaderKey(vim.vim_cmd.vim_status)
    original_cursor = object()
    editor = Mock()
    emit = Mock(side_effect=RuntimeError("action failed"))
    cursor = SimpleNamespace(
        get_editor=Mock(return_value=editor),
        get_editorstack=Mock(
            return_value=SimpleNamespace(sig_trigger_action=SimpleNamespace(emit=emit))
        ),
        set_selection_to_editor_using_vim_selection=Mock(return_value=original_cursor),
    )
    focus_input = Mock()
    executor.vim_status = SimpleNamespace(
        host=EditorCommands(Mock(), cursor, Mock(), focus_input)
    )

    with pytest.raises(RuntimeError, match="action failed"):
        getattr(executor, method_name)()

    editor.setTextCursor.assert_called_once_with(original_cursor)
    focus_input.assert_called_once_with()


def test_formatting(vim_bot):
    """Test formatting."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text("a\nb\nc\n")
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    vim.vim_cmd.vim_status.to_normal()

    editor.format_document_or_range = Mock()

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "f")

    assert cmd_line.text() == ""
    assert editor.format_document_or_range.called

    editor.format_document_or_range = Mock()
    qtbot.keyClicks(cmd_line, "ggVj")

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "f")

    assert cmd_line.text() == ""
    assert editor.format_document_or_range.called


def test_open_switcher_plugin(vim_bot):
    """Test open switcher when provided by plugin."""
    main, _, _, vim, qtbot = vim_bot

    if hasattr(main, "open_switcher"):
        delattr(main, "open_switcher")

    plugin = Mock()
    main.get_plugin = Mock(return_value=plugin)

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "p")

    assert cmd_line.text() == ""
    assert plugin.open_switcher.called


def test_open_symbol_swithcer_plugin(vim_bot):
    """Test open symbol switcher when provided by plugin."""
    main, _, _, vim, qtbot = vim_bot

    if hasattr(main, "open_switcher"):
        delattr(main, "open_switcher")

    plugin = Mock()
    main.get_plugin = Mock(return_value=plugin)

    cmd_line = vim.vim_cmd.commandline
    qtbot.keyPress(cmd_line, Qt.Key_Space)
    qtbot.keyClicks(cmd_line, "s")

    assert cmd_line.text() == ""
    assert plugin.open_switcher.called
