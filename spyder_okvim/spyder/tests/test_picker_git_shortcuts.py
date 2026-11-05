"""Leader Git pickers share the same scoped session and preview pipeline."""

from types import SimpleNamespace

import pytest
from qtpy.QtCore import QCoreApplication, Qt

from spyder_okvim.spyder.tests.test_picker_git_integration import (
    _git,
    _ready,
    _repository,
)
from tests.qt_support import reset_vim_state


@pytest.fixture
def git_picker(vim_bot, monkeypatch, tmp_path):
    main, stack, _, vim, bot = vim_bot
    widget = vim.vim_cmd
    original = stack.get_current_filename()
    filenames = set(stack.get_filenames())
    reset_vim_state(widget.vim_status)
    file = _repository(tmp_path)
    monkeypatch.setattr(main.projects, "get_active_project_path", lambda: str(tmp_path))
    main.activateWindow()
    widget.commandline.setFocus()
    yield SimpleNamespace(
        main=main,
        stack=stack,
        vim=vim,
        widget=widget,
        picker=widget.picker,
        bot=bot,
        root=tmp_path,
        file=file,
        monkeypatch=monkeypatch,
    )
    widget.picker.cancel()
    bot.waitUntil(lambda: not widget.picker.git.busy)
    bot.waitUntil(lambda: not widget.picker.actions.busy)
    bot.waitUntil(lambda: not any(widget.picker.work.active.values()))
    widget.vim_status.disconnect_from_editor()
    stack.set_current_filename(original)
    for filename in set(stack.get_filenames()) - filenames:
        index = stack.is_file_opened(filename)
        with monkeypatch.context() as cleanup:
            cleanup.setattr(
                stack,
                "get_main_widget",
                lambda: SimpleNamespace(can_close_file=lambda filename: True),
            )
            stack.close_file(index, force=True)
    vim._use_stack(stack)
    QCoreApplication.processEvents()
    main.activateWindow()
    widget.commandline.setFocus()
    QCoreApplication.processEvents()


def _open(state, keys):
    state.widget.commandline.esc_pressed()
    state.bot.keyClick(state.widget.commandline, Qt.Key_Space)
    state.bot.keyClicks(state.widget.commandline, keys)
    state.bot.waitUntil(lambda: _ready(state.picker))
    return state.picker.dialog


def test_status_shortcut_opens_worktree_patch(git_picker):
    state = git_picker
    state.file.write_text("worktree = 3\n")
    dialog = _open(state, "ts")
    assert state.picker.source == "git_status"
    state.bot.waitUntil(lambda: "+worktree = 3" in dialog.preview.toPlainText())
    assert "Unstaged:" in dialog.preview.toPlainText()


def test_stash_shortcut_inspects_saved_tracked_and_untracked_without_applying(
    git_picker,
):
    state = git_picker
    state.file.write_text("saved = 2\n")
    (state.root / "untracked.py").write_text("saved_untracked = 3\n")
    _git(state.root, "stash", "push", "--include-untracked", "-m", "picker stash")
    before = (
        _git(state.root, "rev-parse", "HEAD"),
        _git(state.root, "stash", "list", "--format=%H"),
        state.file.read_text(),
        state.widget.vim_status.get_current_location(),
    )
    dialog = _open(state, "tS")
    assert state.picker.source == "git_stash"
    state.bot.waitUntil(lambda: "+saved_untracked = 3" in dialog.preview.toPlainText())
    assert "+saved = 2" in dialog.preview.toPlainText()
    state.bot.waitUntil(lambda: not state.picker.git.busy)
    assert before == (
        _git(state.root, "rev-parse", "HEAD"),
        _git(state.root, "stash", "list", "--format=%H"),
        state.file.read_text(),
        state.widget.vim_status.get_current_location(),
    )
    assert not (state.root / "untracked.py").exists()
    assert dialog.load_more_button.isVisible()


def test_current_file_shortcut_follows_rename_and_back_restores_file_history(
    git_picker,
):
    state = git_picker
    (state.root / "other.py").write_text("unrelated = 0\n")
    _git(state.root, "add", ".")
    _git(state.root, "commit", "-m", "unrelated change")
    renamed = state.root / "renamed file.py"
    _git(state.root, "mv", "file.py", renamed.name)
    _git(state.root, "commit", "-m", "rename current file")
    state.stack.load(str(renamed), processevents=False)
    state.vim._use_stack(state.stack)
    before = state.widget.vim_status.get_current_location()
    dialog = _open(state, "tC")
    assert state.picker.source == "git_file_log"
    labels = " ".join(entry.label for entry in state.picker.snapshot.entries)
    assert "root snapshot" in labels and "rename current file" in labels
    assert "unrelated change" not in labels
    assert str(renamed) in state.picker.scope
    dialog.prompt.setText("root snapshot")
    state.bot.waitUntil(lambda: _ready(state.picker) and dialog.model.rowCount() == 1)
    selected = dialog.selection_id()
    state.bot.waitUntil(lambda: "+original = 1" in dialog.preview.toPlainText())
    state.bot.keyClick(dialog.prompt, Qt.Key_L, Qt.ControlModifier)
    state.bot.waitUntil(
        lambda: state.picker.source == "git_files" and _ready(state.picker)
    )
    assert state.picker.snapshot.entries[0].target.path == str(state.file)
    state.bot.mouseClick(dialog.back_button, Qt.LeftButton)
    state.bot.waitUntil(
        lambda: state.picker.source == "git_file_log" and _ready(state.picker)
    )
    assert dialog.query() == "root snapshot"
    assert dialog.selection_id() == selected
    assert state.widget.vim_status.get_current_location() == before


def test_current_file_uses_its_repository_and_repository_history_uses_project(
    git_picker,
):
    state = git_picker
    other = state.root / "other-repo"
    other.mkdir()
    _repository(other)
    _git(other, "commit", "--allow-empty", "-m", "other project only")
    state.monkeypatch.setattr(
        state.main.projects, "get_active_project_path", lambda: str(other)
    )
    state.stack.load(str(state.file), processevents=False)
    state.vim._use_stack(state.stack)
    dialog = _open(state, "tc")
    assert state.picker.git_root == str(other)
    assert any(
        "other project only" in entry.label for entry in state.picker.snapshot.entries
    )
    # The same popup must resolve this file's repo instead of reusing the project's.
    state.widget.open_picker("git_file_log")
    state.bot.waitUntil(lambda: _ready(state.picker))
    assert state.picker.dialog is dialog
    assert state.picker.git_root == str(state.root)
    assert all(
        "other project only" not in entry.label
        for entry in state.picker.snapshot.entries
    )


def test_empty_stash_and_uncommitted_file_have_distinct_empty_states(git_picker):
    state = git_picker
    state.widget.open_picker("git_stash")
    state.bot.waitUntil(lambda: state.picker.result_token is not None)
    assert not state.picker.snapshot.entries
    assert "No stashes" in state.picker.dialog.status_label.text()
    fresh = state.root / "never committed.py"
    fresh.write_text("fresh = 1\n")
    state.picker.cancel()
    state.stack.load(str(fresh), processevents=False)
    state.vim._use_stack(state.stack)
    state.widget.open_picker("git_file_log")
    state.bot.waitUntil(lambda: state.picker.result_token is not None)
    assert not state.picker.snapshot.entries
    assert "No commits for this file" in state.picker.dialog.status_label.text()
    state.bot.keyClick(state.picker.dialog.prompt, Qt.Key_Return)
    assert state.picker.phase == "active"
