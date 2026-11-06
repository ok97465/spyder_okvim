"""HEAD message edits preserve the committed tree and pending changes."""

from unittest.mock import Mock

import pytest
from qtpy.QtCore import QTimer, Qt

from spyder_okvim.spyder.picker_commit_dialog import CommitMessageDialog
from spyder_okvim.spyder.tests.test_picker_git_integration import _git
from spyder_okvim.spyder.tests.test_picker_git_mutation_integration import (
    _choose,
    _settled,
)
from spyder_okvim.spyder.tests.test_picker_git_shortcuts import _open
from spyder_okvim.spyder.tests.test_picker_git_shortcuts import (
    git_picker as _git_picker,
)


git_picker = _git_picker


def _head(root):
    return _git(root, "rev-parse", "HEAD").decode().strip()


def _repository_state(root):
    return (
        _head(root),
        _git(root, "symbolic-ref", "HEAD"),
        _git(root, "write-tree"),
        _git(root, "status", "--porcelain"),
    )


@pytest.mark.parametrize("keys", ["tc", "tC"])
def test_message_edit_shortcut_keeps_staged_worktree_and_unsaved_changes(
    git_picker, keys
):
    state = git_picker
    head = _head(state.root)
    metadata_args = ("show", "-s", "--format=%T%n%P%n%an%n%ae%n%aI", "HEAD")
    metadata = _git(state.root, *metadata_args)
    state.file.write_text("staged = 2\n")
    _git(state.root, "add", state.file.name)
    state.file.write_text("worktree = 3\n")
    untracked = state.root / "untracked.py"
    untracked.write_text("untracked = 4\n")
    index = _git(state.root, "write-tree")
    status = _git(state.root, "status", "--porcelain")
    state.stack.load(str(state.file), processevents=False)
    state.vim._use_stack(state.stack)
    editor = state.stack.get_current_editor()
    editor.insertPlainText("unsaved ")
    buffer = editor.toPlainText(), editor.textCursor().position()
    message = "- 한글 제목 'quotes'\n\n본문 $(touch should-not-exist) `quoted`"
    compose = Mock(return_value=message)
    state.monkeypatch.setattr(state.picker.actions, "compose_amend", compose)
    dialog = _open(state, keys)

    state.bot.keyClick(dialog.prompt, Qt.Key_E, Qt.ControlModifier)
    _settled(state)

    compose.assert_called_once()
    assert compose.call_args.args[2] == "root snapshot\n"
    assert _head(state.root) != head
    assert _git(state.root, "log", "-1", "--format=%B").decode().rstrip("\n") == message
    assert _git(state.root, *metadata_args) == metadata
    assert _git(state.root, "write-tree") == index
    assert _git(state.root, "status", "--porcelain") == status
    assert state.file.read_text() == "worktree = 3\n"
    assert untracked.read_text() == "untracked = 4\n"
    assert not (state.root / "should-not-exist").exists()
    assert (editor.toPlainText(), editor.textCursor().position()) == buffer
    assert editor.document().isModified()
    assert state.picker.phase == "active"
    assert any("한글 제목" in entry.label for entry in state.picker.snapshot.entries)
    assert (str(state.root), head) not in state.picker.actions.amend_drafts


def test_editing_older_commit_is_rejected_without_opening_composer(git_picker):
    state = git_picker
    old = _head(state.root)
    _git(state.root, "commit", "--allow-empty", "-m", "Latest commit")
    before = _repository_state(state.root)
    compose = Mock(return_value="Must not replace latest message")
    state.monkeypatch.setattr(state.picker.actions, "compose_amend", compose)
    _open(state, "tc")

    state.picker.actions.request("edit_commit_message", _choose(state, old))
    _settled(state)

    compose.assert_not_called()
    assert _repository_state(state.root) == before
    assert "latest commit (HEAD)" in state.widget.msg_label.text()


def test_composer_prefills_full_message_and_keeps_cancelled_amend_draft(git_picker):
    state = git_picker
    original = "기존 제목\n\nOriginal multiline body\nSecond line"
    _git(state.root, "commit", "--amend", "-m", original)
    head = _head(state.root)
    before = _repository_state(state.root)
    draft = "수정한 제목\n\nEdited body"
    original_exec = CommitMessageDialog.exec_

    def edit_and_cancel(dialog):
        assert dialog.message() == original + "\n"
        assert dialog.windowTitle() == "Edit HEAD commit message"
        assert head in dialog.summary_view.toPlainText()

        def cancel():
            dialog.message_edit.setPlainText(draft)
            dialog.reject()

        QTimer.singleShot(0, cancel)
        return original_exec(dialog)

    state.monkeypatch.setattr(CommitMessageDialog, "exec_", edit_and_cancel)
    dialog = _open(state, "tc")
    state.picker.actions.commit_drafts[str(state.root)] = (
        "Unrelated staged commit draft"
    )
    state.bot.keyClick(dialog.prompt, Qt.Key_E, Qt.ControlModifier)
    _settled(state)

    assert _repository_state(state.root) == before
    assert state.picker.actions.amend_drafts[(str(state.root), head)] == draft

    def reopen_and_save(dialog):
        assert dialog.message() == draft
        QTimer.singleShot(
            0,
            lambda: state.bot.keyClick(
                dialog.message_edit, Qt.Key_Return, Qt.ControlModifier
            ),
        )
        return original_exec(dialog)

    state.monkeypatch.setattr(CommitMessageDialog, "exec_", reopen_and_save)
    state.bot.keyClick(dialog.prompt, Qt.Key_E, Qt.ControlModifier)
    _settled(state)

    assert _head(state.root) != head
    assert _git(state.root, "log", "-1", "--format=%B").decode().rstrip("\n") == draft
    assert (str(state.root), head) not in state.picker.actions.amend_drafts
    assert state.picker.actions.commit_drafts[str(state.root)] == (
        "Unrelated staged commit draft"
    )


@pytest.mark.parametrize("change", ["index", "head", "branch"])
def test_repository_change_while_editing_aborts_and_keeps_draft(git_picker, change):
    state = git_picker
    head = _head(state.root)
    after_external_change = []

    def compose(request, branch, original):
        if change == "index":
            state.file.write_text("external staged = 2\n")
            _git(state.root, "add", state.file.name)
        elif change == "head":
            _git(state.root, "commit", "--allow-empty", "-m", "External commit")
        else:
            _git(state.root, "switch", "-c", "external-branch")
        after_external_change.append(_repository_state(state.root))
        return "Keep this amendment draft"

    state.monkeypatch.setattr(state.picker.actions, "compose_amend", compose)
    dialog = _open(state, "tc")
    state.bot.keyClick(dialog.prompt, Qt.Key_E, Qt.ControlModifier)
    _settled(state)

    assert _repository_state(state.root) == after_external_change[0]
    assert state.picker.actions.amend_drafts[(str(state.root), head)] == (
        "Keep this amendment draft"
    )


def test_failed_message_edit_keeps_draft_and_can_retry(git_picker):
    state = git_picker
    head = _head(state.root)
    hook = state.root / ".git" / "hooks" / "commit-msg"
    hook.write_text("#!/bin/sh\nprintf 'message rejected\\n' >&2\nexit 1\n")
    hook.chmod(0o755)
    before = _repository_state(state.root)
    compose = Mock(return_value="Retry amended message")
    state.monkeypatch.setattr(state.picker.actions, "compose_amend", compose)
    dialog = _open(state, "tc")

    state.bot.keyClick(dialog.prompt, Qt.Key_E, Qt.ControlModifier)
    _settled(state)

    assert _repository_state(state.root) == before
    assert state.picker.actions.amend_drafts[(str(state.root), head)] == (
        "Retry amended message"
    )
    assert "message rejected" in state.widget.msg_label.text()
    hook.unlink()
    state.bot.keyClick(dialog.prompt, Qt.Key_E, Qt.ControlModifier)
    _settled(state)

    assert _git(state.root, "log", "-1", "--format=%s") == b"Retry amended message\n"
    assert (str(state.root), head) not in state.picker.actions.amend_drafts
