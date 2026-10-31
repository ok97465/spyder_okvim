"""Regression tests for saving and discarding real Spyder editor buffers."""

# Standard Libraries
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMessageBox
from spyder.plugins.editor.widgets.editorstack import EditorStack

# Project Libraries
from tests.qt_support import reset_vim_state


@pytest.fixture
def file_bot(vim_bot, monkeypatch, tmp_path):
    """Add a disposable document without closing the session's shared files."""
    main, stack, _, vim, qtbot = vim_bot
    status = vim.vim_cmd.vim_status
    commandline = vim.vim_cmd.commandline
    original_files = tuple(stack.data)
    original_current = stack.get_current_finfo()
    commandline.esc_pressed()
    status.disconnect_from_editor()

    path = tmp_path / "document.txt"
    path.write_text("original\n", encoding="utf-8")
    finfo = stack.new(str(path), "utf-8", "edited\n", empty=True)
    stack.set_stack_index(stack.data.index(finfo))
    finfo.newly_created = False
    finfo.editor.document().setModified(True)
    reset_vim_state(status)
    status.cursor.set_cursor_pos(0)
    commandline.clear()
    commandline.setFocus()

    monkeypatch.setattr(stack, "get_main_widget", lambda: main.editor)
    monkeypatch.setattr(stack, "format_on_save", False)
    monkeypatch.setattr(stack, "save_dialog_on_tests", True)
    monkeypatch.setattr(
        main.editor, "can_close_file", Mock(return_value=True), raising=False
    )
    monkeypatch.setattr(main.editor, "save", Mock(side_effect=stack.save))
    monkeypatch.setattr(main.editor, "close_file", Mock(side_effect=stack.close_file))

    def execute(command):
        qtbot.keyClicks(commandline, command)
        if command.startswith(":"):
            qtbot.keyPress(commandline, Qt.Key_Return)
        assert commandline.text() == ""
        assert status.sub_mode is None
        assert commandline.hasFocus()

    bot = SimpleNamespace(
        plugin=main.editor,
        stack=stack,
        finfo=finfo,
        path=path,
        status=status,
        commandline=commandline,
        execute=execute,
        colon=vim.vim_cmd.executor_normal_cmd.executor_colon,
    )
    try:
        yield bot
    finally:
        commandline.esc_pressed()
        status.disconnect_from_editor()
        for extra in tuple(stack.data):
            if extra not in original_files:
                EditorStack.close_file(stack, index=stack.data.index(extra), force=True)
        assert tuple(stack.data) == original_files
        stack.set_stack_index(stack.data.index(original_current))
        commandline.clear()


@pytest.mark.parametrize("command", [":wq", "ZZ"])
@pytest.mark.parametrize("modified", [True, False], ids=["edited", "unchanged"])
def test_save_and_close_existing_file(file_bot, command, modified):
    """A completed save closes its buffer and preserves the contents on disk."""
    bot = file_bot
    bot.finfo.editor.document().setModified(modified)

    bot.execute(command)

    assert bot.finfo not in bot.stack.data
    assert bot.path.read_text(encoding="utf-8") == (
        "edited\n" if modified else "original\n"
    )
    bot.plugin.save.assert_called_once_with()
    bot.plugin.close_file.assert_called_once_with()


@pytest.mark.parametrize("command", [":wq", "ZZ"])
def test_save_as_success_closes_new_file(file_bot, monkeypatch, command, tmp_path):
    """The new filename is written before a previously unnamed buffer closes."""
    bot = file_bot
    target = tmp_path / "saved document.txt"
    bot.finfo.filename = str(tmp_path / "untitled.txt")
    bot.finfo.newly_created = True
    monkeypatch.setattr(bot.stack, "select_savename", lambda *args: str(target))

    bot.execute(command)

    assert target.read_text(encoding="utf-8") == "edited\n"
    assert bot.finfo not in bot.stack.data


@pytest.mark.parametrize("command", [":wq", "ZZ"])
def test_cancelled_save_as_keeps_buffer(file_bot, monkeypatch, command, tmp_path):
    """Cancelling the filename dialog must not initiate a close prompt."""
    bot = file_bot
    bot.finfo.filename = str(tmp_path / "untitled.txt")
    bot.finfo.newly_created = True
    monkeypatch.setattr(bot.stack, "select_savename", lambda *args: None)

    bot.execute(command)

    assert bot.stack.get_current_finfo() is bot.finfo
    assert bot.finfo.editor.toPlainText() == "edited\n"
    assert bot.finfo.editor.document().isModified()
    assert bot.finfo.newly_created
    bot.plugin.close_file.assert_not_called()


@pytest.mark.parametrize("command", [":wq", "ZZ"])
def test_failed_write_keeps_buffer(file_bot, monkeypatch, command):
    """A real Spyder save failure leaves both the buffer and old disk data."""
    bot = file_bot

    def fail_write(*args):
        raise OSError("write failed")

    monkeypatch.setattr(bot.stack, "_write_to_file", fail_write)
    dialog = Mock(return_value=QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "exec_", dialog)

    bot.execute(command)

    dialog.assert_called_once_with()
    assert bot.stack.get_current_finfo() is bot.finfo
    assert bot.finfo.editor.toPlainText() == "edited\n"
    assert bot.finfo.editor.document().isModified()
    assert bot.path.read_text(encoding="utf-8") == "original\n"
    bot.plugin.close_file.assert_not_called()


@pytest.mark.parametrize("command", [":wq", "ZZ"])
@pytest.mark.parametrize("result", [False, None])
def test_incomplete_save_result_keeps_buffer(file_bot, monkeypatch, command, result):
    """Both failure and API paths without a result prevent closing."""
    bot = file_bot
    monkeypatch.setattr(bot.plugin, "save", Mock(return_value=result))

    bot.execute(command)

    assert bot.stack.get_current_finfo() is bot.finfo
    bot.plugin.close_file.assert_not_called()


@pytest.mark.parametrize("command", [":wq", "ZZ"])
@pytest.mark.parametrize("new_file", [False, True], ids=["modified", "new-file"])
def test_reported_success_without_completed_save_keeps_buffer(
    file_bot, monkeypatch, command, new_file
):
    """Formatting timeout can return True while a document remains unsaved."""
    bot = file_bot
    bot.finfo.newly_created = new_file
    bot.finfo.editor.document().setModified(not new_file)
    monkeypatch.setattr(bot.plugin, "save", Mock(return_value=True))

    bot.execute(command)

    assert bot.stack.get_current_finfo() is bot.finfo
    bot.plugin.close_file.assert_not_called()


@pytest.mark.parametrize("command", [":wq", "ZZ"])
def test_save_does_not_close_another_active_buffer(file_bot, monkeypatch, command):
    """A tab switch during a nested save dialog must not close the new tab."""
    bot = file_bot
    other = next(finfo for finfo in bot.stack.data if finfo is not bot.finfo)

    def save_and_switch():
        bot.finfo.editor.document().setModified(False)
        bot.stack.set_stack_index(bot.stack.data.index(other))
        return True

    monkeypatch.setattr(bot.plugin, "save", Mock(side_effect=save_and_switch))

    bot.execute(command)

    assert bot.stack.get_current_finfo() is other
    assert bot.finfo in bot.stack.data
    bot.plugin.close_file.assert_not_called()


def test_quit_can_cancel_without_discard(file_bot, monkeypatch):
    """Ordinary :q retains Spyder's save/discard/cancel prompt."""
    bot = file_bot
    dialog = Mock(return_value=QMessageBox.Cancel)
    monkeypatch.setattr(QMessageBox, "exec_", dialog)

    bot.execute(":q")

    dialog.assert_called_once_with()
    assert bot.stack.get_current_finfo() is bot.finfo
    assert bot.finfo.editor.document().isModified()
    assert bot.path.read_text(encoding="utf-8") == "original\n"


@pytest.mark.parametrize("command", [":q!", "ZQ"])
def test_force_quit_discards_buffer_and_autosave(
    file_bot, monkeypatch, command, tmp_path
):
    """Discard closes without prompting, saving, or retaining recovery data."""
    bot = file_bot
    autosave = tmp_path / "recovery.txt"
    autosave.write_text("edited\n", encoding="utf-8")
    bot.stack.autosave.name_mapping[str(bot.path)] = str(autosave)
    bot.stack.autosave.file_hashes[str(autosave)] = hash("edited\n")
    dialog = Mock(side_effect=AssertionError("discard must not prompt"))
    monkeypatch.setattr(QMessageBox, "exec_", dialog)

    bot.execute(command)

    assert bot.finfo not in bot.stack.data
    assert bot.path.read_text(encoding="utf-8") == "original\n"
    assert not autosave.exists()
    assert str(bot.path) not in bot.stack.autosave.name_mapping
    assert str(autosave) not in bot.stack.autosave.file_hashes
    bot.plugin.save.assert_not_called()
    bot.plugin.close_file.assert_not_called()


@pytest.mark.parametrize("command", [":q!", "ZQ"])
def test_force_quit_respects_debugger_refusal(file_bot, monkeypatch, command):
    """Discard must preserve Spyder's restriction on closing a debugging file."""
    bot = file_bot
    monkeypatch.setattr(bot.plugin, "can_close_file", Mock(return_value=False))
    remove_recovery = Mock()
    monkeypatch.setattr(bot.stack.autosave, "remove_autosave_file", remove_recovery)

    bot.execute(command)

    assert bot.stack.get_current_finfo() is bot.finfo
    assert bot.finfo.editor.document().isModified()
    remove_recovery.assert_not_called()


def test_force_quit_without_active_file(file_bot, monkeypatch):
    """An empty stack must not access its nonexistent document or recovery data."""
    bot = file_bot
    monkeypatch.setattr(bot.stack, "get_current_finfo", lambda: None)
    close = Mock()
    monkeypatch.setattr(bot.stack, "close_file", close)

    bot.colon.close_current_file(force=True)

    close.assert_not_called()
    bot.plugin.can_close_file.assert_not_called()


@pytest.mark.parametrize("command", [":q!", "ZQ"])
def test_discard_cleanup_does_not_close_another_buffer(file_bot, monkeypatch, command):
    """A recovery cleanup dialog may switch tabs without transferring the close."""
    bot = file_bot
    other = next(finfo for finfo in bot.stack.data if finfo is not bot.finfo)

    def cleanup_and_switch(filename):
        bot.stack.set_stack_index(bot.stack.data.index(other))

    monkeypatch.setattr(bot.stack.autosave, "remove_autosave_file", cleanup_and_switch)

    bot.execute(command)

    assert bot.stack.get_current_finfo() is other
    assert bot.finfo in bot.stack.data
