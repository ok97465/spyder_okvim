"""Read-only Git navigation through the same live picker/controller shell."""

import subprocess

from qtpy.QtCore import QCoreApplication, Qt


def _git(directory, *args):
    return subprocess.run(
        ["git", "-C", str(directory), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def _repository(path):
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.name", "Picker Integration")
    _git(path, "config", "user.email", "picker@example.invalid")
    file = path / "file.py"
    file.write_text("original = 1\n")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "root snapshot")
    return file


def _ready(controller):
    return (
        controller.phase == "active"
        and controller.snapshot is not None
        and controller.result_token == controller._search_token()
        and controller.dialog.selected_entry() is not None
    )


def test_staged_only_status_preview_preserves_editor(vim_bot, monkeypatch, tmp_path):
    main, stack, _, vim, qtbot = vim_bot
    file = _repository(tmp_path)
    file.write_text("staged = 2\n")
    _git(tmp_path, "add", "file.py")
    monkeypatch.setattr(main.projects, "get_active_project_path", lambda: str(tmp_path))
    widget = vim.vim_cmd
    controller = widget.picker
    editor = stack.get_current_editor()
    before = (
        editor.toPlainText(),
        editor.textCursor().position(),
        tuple(widget.vim_status.jump_list.jumps),
        _git(tmp_path, "rev-parse", "HEAD"),
    )
    widget.open_picker("git_status")
    try:
        qtbot.waitUntil(lambda: _ready(controller), timeout=5000)
        dialog = controller.dialog
        qtbot.waitUntil(
            lambda: "+staged = 2" in dialog.preview.toPlainText(), timeout=5000
        )
        text = dialog.preview.toPlainText()
        assert "Unstaged: index" in text and "No unstaged patch." in text
        assert "Staged: HEAD" in text
        assert controller.snapshot.entries[0].target.status == "M."
        assert before == (
            editor.toPlainText(),
            editor.textCursor().position(),
            tuple(widget.vim_status.jump_list.jumps),
            _git(tmp_path, "rev-parse", "HEAD"),
        )
        qtbot.keyClick(dialog.prompt, Qt.Key_Escape)
        qtbot.waitUntil(lambda: controller.phase == "closed")
    finally:
        controller.cancel()
        qtbot.waitUntil(lambda: not controller.git.busy)
        QCoreApplication.processEvents()
        main.activateWindow()
        vim.vim_cmd.commandline.setFocus()
        QCoreApplication.processEvents()


def test_commit_drilldown_back_restores_query_without_checkout(
    vim_bot, monkeypatch, tmp_path
):
    main, stack, _, vim, qtbot = vim_bot
    file = _repository(tmp_path)
    file.write_text("second = 2\n")
    _git(tmp_path, "commit", "-am", "second snapshot")
    head = _git(tmp_path, "rev-parse", "HEAD")
    monkeypatch.setattr(main.projects, "get_active_project_path", lambda: str(tmp_path))
    controller = vim.vim_cmd.picker
    vim.vim_cmd.open_picker("git_log")
    try:
        qtbot.waitUntil(lambda: _ready(controller), timeout=5000)
        dialog = controller.dialog
        dialog.prompt.setText("root")
        qtbot.waitUntil(
            lambda: _ready(controller) and len(controller.dialog.model.matches) == 1
        )
        selected = dialog.selection_id()
        qtbot.keyClick(dialog.prompt, Qt.Key_L, Qt.ControlModifier)
        qtbot.waitUntil(lambda: controller.source == "git_files" and _ready(controller))
        assert dialog.back_button.isVisible()
        qtbot.waitUntil(
            lambda: "+original = 1" in dialog.preview.toPlainText(), timeout=5000
        )
        assert "root uses empty tree" in dialog.preview.toPlainText()
        assert _git(tmp_path, "rev-parse", "HEAD") == head
        qtbot.mouseClick(dialog.back_button, Qt.LeftButton)
        qtbot.waitUntil(lambda: controller.source == "git_log" and _ready(controller))
        assert dialog.query() == "root"
        assert dialog.selection_id() == selected
        assert _git(tmp_path, "rev-parse", "HEAD") == head
    finally:
        controller.cancel()
        qtbot.waitUntil(lambda: not controller.git.busy)
        QCoreApplication.processEvents()
        main.activateWindow()
        vim.vim_cmd.commandline.setFocus()
        QCoreApplication.processEvents()
