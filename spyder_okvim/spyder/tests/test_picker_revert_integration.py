"""Reverting a row changes only its worktree file and preserves staging."""

import os
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMessageBox

from spyder_okvim.spyder.tests.test_picker_git_integration import _git
from spyder_okvim.spyder.tests.test_picker_git_mutation_integration import _settled
from spyder_okvim.spyder.tests.test_picker_git_shortcuts import _open
from spyder_okvim.spyder.tests.test_picker_git_shortcuts import (
    git_picker as _git_picker,
)


git_picker = _git_picker


def _index(state):
    return _git(state.root, "ls-files", "--stage")


def _confirm(state, accepted=True):
    confirm = Mock(return_value=accepted)
    state.monkeypatch.setattr(state.picker.actions, "confirm", confirm)
    return confirm


def _choose_path(state, path):
    entry = next(
        entry
        for entry in state.picker.snapshot.entries
        if Path(entry.target.path) == path
    )
    state.picker.dialog.select_id(entry.id)
    selected = state.picker.dialog.selected_entry()
    assert selected is not None and selected.id == entry.id
    return selected


def test_status_control_r_restores_only_unstaged_part_of_mixed_file(git_picker):
    state = git_picker
    state.file.write_text("staged = 2\n")
    _git(state.root, "add", state.file.name)
    state.file.write_text("unstaged = 3\n")
    head = _git(state.root, "rev-parse", "HEAD")
    index = _index(state)
    staged_patch = _git(state.root, "diff", "--cached", "--binary")
    confirm = _confirm(state)
    dialog = _open(state, "ts")
    assert _choose_path(state, state.file).target.status == "MM"

    state.bot.keyClick(dialog.prompt, Qt.Key_R, Qt.ControlModifier)
    _settled(state)

    confirm.assert_called_once()
    assert state.file.read_text() == "staged = 2\n"
    assert _index(state) == index
    assert _git(state.root, "diff", "--cached", "--binary") == staged_patch
    assert _git(state.root, "diff", "--", state.file.name) == b""
    assert _git(state.root, "rev-parse", "HEAD") == head
    assert _choose_path(state, state.file).target.status == "M."


def test_unstaged_revert_restores_disk_and_reloads_clean_open_editor(git_picker):
    state = git_picker
    state.file.write_text("unstaged = 2\n")
    state.stack.load(str(state.file), processevents=False)
    state.vim._use_stack(state.stack)
    editor = state.stack.get_current_editor()
    assert editor.toPlainText() == "unstaged = 2\n"
    assert not editor.document().isModified()
    index = _index(state)
    _confirm(state)
    _open(state, "ts")
    entry = _choose_path(state, state.file)

    state.picker.actions.request("revert", entry)
    _settled(state)

    assert state.file.read_text() == "original = 1\n"
    assert editor.toPlainText() == "original = 1\n"
    assert not editor.document().isModified()
    assert _index(state) == index
    assert _git(state.root, "status", "--porcelain") == b""


@pytest.mark.parametrize("change", ["modified", "added", "deleted"])
def test_staged_only_row_cannot_revert_or_open_confirmation(git_picker, change):
    state = git_picker
    path = state.file
    if change == "deleted":
        _git(state.root, "rm", path.name)
    else:
        if change == "added":
            path = state.root / "new staged.py"
        path.write_text("staged = 2\n")
        _git(state.root, "add", path.name)
    contents = path.read_bytes() if path.exists() else None
    head = _git(state.root, "rev-parse", "HEAD")
    index = _index(state)
    staged_patch = _git(state.root, "diff", "--cached", "--binary")
    confirm = _confirm(state)
    dialog = _open(state, "ts")
    entry = _choose_path(state, path)
    assert entry.target.status[1] == "."

    state.bot.keyClick(dialog.prompt, Qt.Key_R, Qt.ControlModifier)
    _settled(state)
    state.picker.actions.request("revert", entry)
    _settled(state)

    confirm.assert_not_called()
    assert (path.read_bytes() if path.exists() else None) == contents
    assert _index(state) == index
    assert _git(state.root, "diff", "--cached", "--binary") == staged_patch
    assert _git(state.root, "rev-parse", "HEAD") == head


@pytest.mark.parametrize("kind", ["intent_to_add", "conflict"])
def test_intent_to_add_and_conflicted_rows_are_not_revertible(git_picker, kind):
    state = git_picker
    if kind == "conflict":
        path = state.file
        _git(state.root, "switch", "-c", "topic")
        path.write_text("topic = 2\n")
        _git(state.root, "commit", "-am", "Topic version")
        _git(state.root, "switch", "main")
        path.write_text("main = 3\n")
        _git(state.root, "commit", "-am", "Main version")
        with pytest.raises(subprocess.CalledProcessError):
            _git(state.root, "merge", "topic")
    else:
        path = state.root / "new file.py"
        path.write_text("new = 2\n")
        _git(state.root, "add", "--intent-to-add", path.name)
    contents = path.read_bytes()
    index = _index(state)
    head = _git(state.root, "rev-parse", "HEAD")
    confirm = _confirm(state)
    dialog = _open(state, "ts")
    entry = _choose_path(state, path)

    state.bot.keyClick(dialog.prompt, Qt.Key_R, Qt.ControlModifier)
    _settled(state)
    state.picker.actions.request("revert", entry)
    _settled(state)

    confirm.assert_not_called()
    assert path.read_bytes() == contents
    assert _index(state) == index
    assert _git(state.root, "rev-parse", "HEAD") == head
    if kind == "conflict":
        assert _git(state.root, "ls-files", "--unmerged")
        assert (state.root / ".git" / "MERGE_HEAD").exists()


def test_cancelled_revert_keeps_worktree_and_staged_content(git_picker):
    state = git_picker
    state.file.write_text("staged = 2\n")
    _git(state.root, "add", state.file.name)
    state.file.write_text("unstaged = 3\n")
    index = _index(state)
    head = _git(state.root, "rev-parse", "HEAD")
    confirm = _confirm(state, False)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, state.file))
    _settled(state)

    confirm.assert_called_once()
    assert state.file.read_text() == "unstaged = 3\n"
    assert _index(state) == index
    assert _git(state.root, "rev-parse", "HEAD") == head


def test_unrelated_dirty_editor_does_not_block_selected_file_revert(git_picker):
    state = git_picker
    other = state.root / "other.py"
    other.write_text("other = 1\n")
    _git(state.root, "add", other.name)
    _git(state.root, "commit", "-m", "Add unrelated file")
    state.file.write_text("unstaged = 2\n")
    state.stack.load(str(other), processevents=False)
    state.vim._use_stack(state.stack)
    editor = state.stack.get_current_editor()
    editor.insertPlainText("unsaved ")
    buffer_text = editor.toPlainText()
    assert editor.document().isModified()
    index = _index(state)
    confirm = _confirm(state)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, state.file))
    _settled(state)

    confirm.assert_called_once()
    assert state.file.read_text() == "original = 1\n"
    assert _index(state) == index
    assert other.read_text() == "other = 1\n"
    assert editor.toPlainText() == buffer_text
    assert editor.document().isModified()


def test_dirty_selected_editor_blocks_revert_before_confirmation(git_picker):
    state = git_picker
    state.file.write_text("unstaged = 2\n")
    state.stack.load(str(state.file), processevents=False)
    state.vim._use_stack(state.stack)
    editor = state.stack.get_current_editor()
    editor.insertPlainText("unsaved ")
    buffer_text = editor.toPlainText()
    index = _index(state)
    confirm = _confirm(state)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, state.file))
    _settled(state)

    confirm.assert_not_called()
    assert state.file.read_text() == "unstaged = 2\n"
    assert editor.toPlainText() == buffer_text
    assert editor.document().isModified()
    assert _index(state) == index


def test_staged_rename_reverts_destination_only_and_keeps_recreated_old_path(
    git_picker,
):
    state = git_picker
    destination = state.root / "renamed file.py"
    _git(state.root, "mv", state.file.name, destination.name)
    destination.write_text("unstaged destination = 2\n")
    state.file.write_text("recreated old path = 3\n")
    index = _index(state)
    staged_patch = _git(state.root, "diff", "--cached", "--binary")
    _confirm(state)
    _open(state, "ts")
    entry = _choose_path(state, destination)
    assert entry.target.status == "RM"
    assert entry.target.old_path == state.file.name

    state.picker.actions.request("revert", entry)
    _settled(state)

    assert destination.read_text() == "original = 1\n"
    assert state.file.read_text() == "recreated old path = 3\n"
    assert _index(state) == index
    assert _git(state.root, "diff", "--cached", "--binary") == staged_patch
    assert _choose_path(state, destination).target.status == "R."


def test_index_change_during_confirmation_aborts_without_losing_new_staging(git_picker):
    state = git_picker
    state.file.write_text("staged = 2\n")
    _git(state.root, "add", state.file.name)
    state.file.write_text("unstaged = 3\n")
    extra = state.root / "new staged.py"
    extra.write_text("newly staged = 4\n")
    head = _git(state.root, "rev-parse", "HEAD")
    after_confirmation = []

    def stage_another_file(request, branch):
        _git(state.root, "add", extra.name)
        after_confirmation.append(_index(state))
        return True

    state.monkeypatch.setattr(state.picker.actions, "confirm", stage_another_file)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, state.file))
    _settled(state)

    assert after_confirmation == [_index(state)]
    assert state.file.read_text() == "unstaged = 3\n"
    assert _git(state.root, "show", ":file.py") == b"staged = 2\n"
    assert _git(state.root, "show", f":{extra.name}") == b"newly staged = 4\n"
    assert _git(state.root, "rev-parse", "HEAD") == head


def test_worktree_edit_during_confirmation_aborts_without_losing_new_content(
    git_picker,
):
    state = git_picker
    state.file.write_text("unstaged = 2\n")
    index = _index(state)
    head = _git(state.root, "rev-parse", "HEAD")
    new_contents = "new disk edit made while confirmation was open = 3\n"

    def edit_during_confirmation(request, branch):
        state.file.write_text(new_contents)
        return True

    confirm = Mock(side_effect=edit_during_confirmation)
    state.monkeypatch.setattr(state.picker.actions, "confirm", confirm)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, state.file))
    _settled(state)

    confirm.assert_called_once()
    assert state.file.read_text() == new_contents
    assert _index(state) == index
    assert _git(state.root, "rev-parse", "HEAD") == head


@pytest.mark.parametrize("initial_change", ["modified", "deleted"])
def test_worktree_edit_during_async_checks_is_kept_and_revert_can_retry(
    git_picker, initial_change
):
    state = git_picker
    if initial_change == "deleted":
        state.file.unlink()
    else:
        state.file.write_text("unstaged = 2\n")
    index = _index(state)
    head = _git(state.root, "rev-parse", "HEAD")
    confirm = _confirm(state)
    _open(state, "ts")
    service = state.picker.actions.service
    start_next = service._start_next
    edits = []
    new_contents = "external edit after confirmation = 3\n"

    def edit_after_preconditions():
        request = service._active
        if request and request.args[0] == "restore" and not request.checks:
            state.file.write_text(new_contents)
            edits.append(True)
        start_next()

    state.monkeypatch.setattr(service, "_start_next", edit_after_preconditions)
    state.picker.actions.request("revert", _choose_path(state, state.file))
    _settled(state)

    assert edits == [True]
    confirm.assert_called_once()
    assert state.file.read_text() == new_contents
    assert _index(state) == index
    assert _git(state.root, "rev-parse", "HEAD") == head
    assert "File changed" in state.widget.msg_label.text()

    state.monkeypatch.setattr(service, "_start_next", start_next)
    state.picker.actions.request("revert", _choose_path(state, state.file))
    _settled(state)

    assert confirm.call_count == 2
    assert state.file.read_text() == "original = 1\n"
    assert _index(state) == index
    assert _git(state.root, "rev-parse", "HEAD") == head


def test_selected_editor_edit_during_confirmation_aborts_revert(git_picker):
    state = git_picker
    state.file.write_text("unstaged = 2\n")
    state.stack.load(str(state.file), processevents=False)
    state.vim._use_stack(state.stack)
    editor = state.stack.get_current_editor()
    assert not editor.document().isModified()
    index = _index(state)
    after_confirmation = []

    def edit_during_confirmation(request, branch):
        editor.insertPlainText("new unsaved edit ")
        after_confirmation.append(editor.toPlainText())
        return True

    confirm = Mock(side_effect=edit_during_confirmation)
    state.monkeypatch.setattr(state.picker.actions, "confirm", confirm)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, state.file))
    _settled(state)

    confirm.assert_called_once()
    assert after_confirmation == [editor.toPlainText()]
    assert editor.document().isModified()
    assert state.file.read_text() == "unstaged = 2\n"
    assert _index(state) == index


def test_unborn_staged_addition_restores_worktree_to_staged_content(git_picker):
    state = git_picker
    _git(state.root, "update-ref", "-d", "refs/heads/main")
    state.file.write_text("staged initial = 2\n")
    _git(state.root, "add", state.file.name)
    state.file.write_text("unstaged initial = 3\n")
    index = _index(state)
    _confirm(state)
    _open(state, "ts")
    entry = _choose_path(state, state.file)
    assert entry.target.status == "AM"

    state.picker.actions.request("revert", entry)
    _settled(state)

    assert state.file.read_text() == "staged initial = 2\n"
    assert _index(state) == index
    assert _git(state.root, "show", ":file.py") == b"staged initial = 2\n"
    assert _git(state.root, "symbolic-ref", "--short", "HEAD") == b"main\n"
    with pytest.raises(subprocess.CalledProcessError):
        _git(state.root, "rev-parse", "--verify", "HEAD")
    assert _choose_path(state, state.file).target.status == "A."


def test_unstaged_deletion_is_restored_without_changing_index(git_picker):
    state = git_picker
    state.file.unlink()
    index = _index(state)
    head = _git(state.root, "rev-parse", "HEAD")
    _confirm(state)
    dialog = _open(state, "ts")
    assert _choose_path(state, state.file).target.status == ".D"

    state.bot.keyClick(dialog.prompt, Qt.Key_R, Qt.ControlModifier)
    _settled(state)

    assert state.file.read_text() == "original = 1\n"
    assert _index(state) == index
    assert _git(state.root, "rev-parse", "HEAD") == head
    assert _git(state.root, "status", "--porcelain") == b""


@pytest.mark.parametrize(
    "relative_path",
    [
        "new.py",
        "-new.py",
        "한글 새 파일.py",
        pytest.param(
            "nested/[draft]*?.py",
            marks=pytest.mark.skipif(
                os.name == "nt", reason="Windows filenames cannot contain * or ?"
            ),
        ),
    ],
)
def test_untracked_revert_deletes_only_selected_literal_file(git_picker, relative_path):
    state = git_picker
    path = state.root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("selected untracked = 1\n")
    adjacent = path.parent / "d123x.py"
    adjacent.write_text("adjacent untracked = 2\n")
    state.file.write_text("staged tracked = 3\n")
    _git(state.root, "add", state.file.name)
    state.file.write_text("unstaged tracked = 4\n")
    index = _index(state)
    staged_patch = _git(state.root, "diff", "--cached", "--binary")
    head = _git(state.root, "rev-parse", "HEAD")
    confirm = _confirm(state)
    dialog = _open(state, "ts")
    assert _choose_path(state, path).target.status == "??"

    state.bot.keyClick(dialog.prompt, Qt.Key_R, Qt.ControlModifier)
    _settled(state)

    confirm.assert_called_once()
    assert not path.exists()
    assert adjacent.read_text() == "adjacent untracked = 2\n"
    assert state.file.read_text() == "unstaged tracked = 4\n"
    assert _index(state) == index
    assert _git(state.root, "diff", "--cached", "--binary") == staged_patch
    assert _git(state.root, "rev-parse", "HEAD") == head


def test_cancelled_untracked_revert_keeps_selected_file(git_picker):
    state = git_picker
    path = state.root / "keep untracked.py"
    path.write_text("keep = 1\n")
    index = _index(state)
    confirm = _confirm(state, False)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, path))
    _settled(state)

    confirm.assert_called_once()
    assert path.read_text() == "keep = 1\n"
    assert _index(state) == index


def test_recreated_file_can_be_deleted_without_undoing_staged_deletion(git_picker):
    state = git_picker
    _git(state.root, "rm", state.file.name)
    state.file.write_text("recreated untracked file = 2\n")
    index = _index(state)
    head = _git(state.root, "rev-parse", "HEAD")
    confirm = _confirm(state)
    dialog = _open(state, "ts")
    entries = [
        entry
        for entry in state.picker.snapshot.entries
        if Path(entry.target.path) == state.file
    ]
    assert {entry.target.status for entry in entries} == {"D.", "??"}
    assert len({entry.id for entry in entries}) == 2
    untracked = next(entry for entry in entries if entry.target.status == "??")
    dialog.select_id(untracked.id)
    assert dialog.selected_entry() == untracked

    state.bot.keyClick(dialog.prompt, Qt.Key_R, Qt.ControlModifier)
    _settled(state)

    confirm.assert_called_once()
    assert not state.file.exists()
    assert _index(state) == index
    assert _git(state.root, "rev-parse", "HEAD") == head
    assert _git(state.root, "status", "--porcelain") == b"D  file.py\n"


def test_untracked_confirmation_names_deletion_and_defaults_to_cancel(git_picker):
    state = git_picker
    path = state.root / "review before deleting.py"
    path.write_text("keep on cancel = 1\n")
    index = _index(state)
    question = Mock(return_value=QMessageBox.Cancel)
    state.monkeypatch.setattr(QMessageBox, "question", question)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, path))
    _settled(state)

    question.assert_called_once()
    arguments = question.call_args.args
    assert "delete untracked file" in arguments[2].lower()
    assert path.name in arguments[2]
    assert "removed from disk" in arguments[2].lower()
    assert arguments[3] == QMessageBox.Yes | QMessageBox.Cancel
    assert arguments[4] == QMessageBox.Cancel
    assert path.read_text() == "keep on cancel = 1\n"
    assert _index(state) == index


def test_untracked_file_edited_during_confirmation_is_not_deleted(git_picker):
    state = git_picker
    path = state.root / "edited untracked.py"
    path.write_text("before = 1\n")
    index = _index(state)

    def edit_during_confirmation(request, branch):
        path.write_text("new content written while confirming = 2\n")
        return True

    confirm = Mock(side_effect=edit_during_confirmation)
    state.monkeypatch.setattr(state.picker.actions, "confirm", confirm)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, path))
    _settled(state)

    confirm.assert_called_once()
    assert path.read_text() == "new content written while confirming = 2\n"
    assert _index(state) == index


def test_untracked_file_staged_during_confirmation_is_not_deleted(git_picker):
    state = git_picker
    path = state.root / "newly staged.py"
    path.write_text("newly staged = 1\n")
    head = _git(state.root, "rev-parse", "HEAD")
    after_confirmation = []

    def stage_during_confirmation(request, branch):
        _git(state.root, "add", path.name)
        after_confirmation.append(_index(state))
        return True

    confirm = Mock(side_effect=stage_during_confirmation)
    state.monkeypatch.setattr(state.picker.actions, "confirm", confirm)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, path))
    _settled(state)

    confirm.assert_called_once()
    assert path.read_text() == "newly staged = 1\n"
    assert after_confirmation == [_index(state)]
    assert _git(state.root, "show", f":{path.name}") == b"newly staged = 1\n"
    assert _git(state.root, "rev-parse", "HEAD") == head


def test_dirty_untracked_editor_blocks_delete_before_confirmation(git_picker):
    state = git_picker
    path = state.root / "unsaved untracked.py"
    path.write_text("saved = 1\n")
    state.stack.load(str(path), processevents=False)
    state.vim._use_stack(state.stack)
    editor = state.stack.get_current_editor()
    editor.insertPlainText("unsaved ")
    buffer_text = editor.toPlainText()
    index = _index(state)
    confirm = _confirm(state)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, path))
    _settled(state)

    confirm.assert_not_called()
    assert path.read_text() == "saved = 1\n"
    assert editor.toPlainText() == buffer_text
    assert editor.document().isModified()
    assert _index(state) == index


def test_untracked_file_replaced_by_directory_is_not_removed(git_picker):
    state = git_picker
    path = state.root / "now a directory"
    path.write_text("formerly a file\n")
    index = _index(state)
    confirm = _confirm(state)
    _open(state, "ts")
    entry = _choose_path(state, path)
    path.unlink()
    path.mkdir()
    child = path / "keep child.py"
    child.write_text("keep child = 1\n")

    state.picker.actions.request("revert", entry)
    _settled(state)

    confirm.assert_not_called()
    assert child.read_text() == "keep child = 1\n"
    assert _index(state) == index


def test_untracked_nested_repository_is_not_deleted(git_picker):
    state = git_picker
    nested = state.root / "nested repo"
    nested.mkdir()
    _git(nested, "init", "-b", "main")
    child = nested / "keep.py"
    child.write_text("keep nested = 1\n")
    index = _index(state)
    confirm = _confirm(state)
    dialog = _open(state, "ts")
    entry = _choose_path(state, nested)
    assert entry.target.status == "??"

    state.bot.keyClick(dialog.prompt, Qt.Key_R, Qt.ControlModifier)
    _settled(state)
    state.picker.actions.request("revert", entry)
    _settled(state)

    confirm.assert_not_called()
    assert child.read_text() == "keep nested = 1\n"
    assert (nested / ".git").is_dir()
    assert _index(state) == index


def test_untracked_symlink_revert_removes_link_and_keeps_external_target(git_picker):
    state = git_picker
    target = state.root.parent / f"{state.root.name}-external-target.py"
    target.write_text("external target = 1\n")
    link = state.root / "untracked link.py"
    try:
        link.symlink_to(target)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
    index = _index(state)
    confirm = _confirm(state)
    _open(state, "ts")

    state.picker.actions.request("revert", _choose_path(state, link))
    _settled(state)

    confirm.assert_called_once()
    assert not link.exists() and not link.is_symlink()
    assert target.read_text() == "external target = 1\n"
    assert _index(state) == index
