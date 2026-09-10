# -*- coding: utf-8 -*-
"""Tests for the executor_leader_key."""

# Standard Libraries
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt, QTimer
from spyder.api.plugins import Plugins


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
    vim.vim_cmd.vim_status.reset_for_test()
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
            observed.append((
                dialog.search.text(),
                {dialog.results.topLevelItem(i).text(0)
                 for i in range(dialog.results.topLevelItemCount())},
                dialog.search.hasFocus(),
            ))
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
    vim.vim_cmd.vim_status.reset_for_test()
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
    vim.vim_cmd.vim_status.reset_for_test()
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
