"""Commit composition writes only the reviewed index in temporary repositories."""

import subprocess
from unittest.mock import Mock

import pytest
from qtpy.QtCore import QTimer, Qt

from spyder_okvim.spyder.picker_commit_dialog import CommitMessageDialog
from spyder_okvim.spyder.tests.test_picker_git_integration import _git
from spyder_okvim.spyder.tests.test_picker_git_mutation_integration import _settled
from spyder_okvim.spyder.tests.test_picker_git_shortcuts import _open
from spyder_okvim.spyder.tests.test_picker_git_shortcuts import (
    git_picker as _git_picker,
)


git_picker = _git_picker


def _stage(state, text="staged = 2\n"):
    state.file.write_text(text)
    _git(state.root, "add", state.file.name)


def _composer(state, message):
    compose = Mock(return_value=message)
    state.monkeypatch.setattr(state.picker.actions, "compose_commit", compose)
    return compose


def _count(root):
    return int(_git(root, "rev-list", "--count", "HEAD"))


def test_commit_shortcut_commits_index_and_preserves_disk_and_unsaved_editor(
    git_picker,
):
    state = git_picker
    _stage(state)
    state.file.write_text("worktree = 3\n")
    untracked = state.root / "untracked.py"
    untracked.write_text("untracked = 4\n")
    state.stack.load(str(state.file), processevents=False)
    state.vim._use_stack(state.stack)
    editor = state.stack.get_current_editor()
    editor.insertPlainText("unsaved ")
    buffer_text = editor.toPlainText()
    cursor = editor.textCursor().position()
    count = _count(state.root)
    compose = _composer(state, "Commit staged version")
    dialog = _open(state, "ts")

    state.bot.keyClick(dialog.prompt, Qt.Key_Return, Qt.ControlModifier)
    _settled(state)

    compose.assert_called_once()
    assert _count(state.root) == count + 1
    assert _git(state.root, "show", "HEAD:file.py") == b"staged = 2\n"
    assert _git(state.root, "show", ":file.py") == b"staged = 2\n"
    assert _git(state.root, "diff", "--cached") == b""
    assert state.file.read_text() == "worktree = 3\n"
    assert untracked.read_text() == "untracked = 4\n"
    assert _git(state.root, "ls-tree", "--name-only", "HEAD") == b"file.py\n"
    assert editor.toPlainText() == buffer_text
    assert editor.textCursor().position() == cursor
    assert editor.document().isModified()
    assert state.picker.phase == "active"


def test_commit_message_preserves_multiline_unicode_quotes_and_leading_dash(git_picker):
    state = git_picker
    _stage(state)
    message = "- 한글 제목 \"double\" 'single'\n\n본문: $(touch should-not-exist) `quoted`\n둘째 줄"
    _composer(state, message)
    _open(state, "ts")

    state.picker.actions.request("commit", None)
    _settled(state)

    assert _git(state.root, "log", "-1", "--format=%B").decode().rstrip("\n") == message
    assert not (state.root / "should-not-exist").exists()
    assert state.picker.git_root not in state.picker.actions.commit_drafts


def test_no_staged_changes_skips_composer_and_preserves_repository(git_picker):
    state = git_picker
    state.file.write_text("unstaged = 2\n")
    head = _git(state.root, "rev-parse", "HEAD")
    tree = _git(state.root, "write-tree")
    compose = _composer(state, "Must not commit")
    _open(state, "ts")

    state.picker.actions.request("commit", None)
    _settled(state)

    compose.assert_not_called()
    assert _git(state.root, "rev-parse", "HEAD") == head
    assert _git(state.root, "write-tree") == tree
    assert state.file.read_text() == "unstaged = 2\n"


def test_commit_creates_initial_commit_on_unborn_branch(git_picker):
    state = git_picker
    _git(state.root, "update-ref", "-d", "refs/heads/main")
    _stage(state, "initial = 1\n")
    _composer(state, "Initial commit")
    _open(state, "ts")

    state.picker.actions.request("commit", None)
    _settled(state)

    assert _count(state.root) == 1
    assert len(_git(state.root, "rev-list", "--parents", "-1", "HEAD").split()) == 1
    assert _git(state.root, "symbolic-ref", "--short", "HEAD") == b"main\n"
    assert _git(state.root, "show", "HEAD:file.py") == b"initial = 1\n"
    assert _git(state.root, "status", "--porcelain") == b""


def test_commit_is_repository_wide_when_query_has_no_selected_file(git_picker):
    state = git_picker
    _stage(state)
    compose = _composer(state, "Commit despite unmatched query")
    dialog = _open(state, "ts")
    dialog.prompt.setText("does-not-match-any-status-entry")
    state.bot.waitUntil(
        lambda: state.picker.result_token == state.picker._search_token()
    )
    assert dialog.selected_entry() is None

    state.picker.actions.request("commit", None)
    _settled(state)

    compose.assert_called_once()
    assert _git(state.root, "log", "-1", "--format=%s") == (
        b"Commit despite unmatched query\n"
    )
    assert dialog.query() == "does-not-match-any-status-entry"
    assert dialog.selected_entry() is None


def test_cancelled_composer_preserves_index_head_and_existing_draft(git_picker):
    state = git_picker
    _stage(state)
    head = _git(state.root, "rev-parse", "HEAD")
    tree = _git(state.root, "write-tree")
    _composer(state, None)
    _open(state, "ts")
    root = state.picker.git_root
    state.picker.actions.commit_drafts[root] = "Previous draft\n\nBody"

    state.picker.actions.request("commit", None)
    _settled(state)

    assert _git(state.root, "rev-parse", "HEAD") == head
    assert _git(state.root, "write-tree") == tree
    assert state.picker.actions.commit_drafts[root] == "Previous draft\n\nBody"
    assert state.picker.phase == "active"


@pytest.mark.parametrize("branch_name", ["main", "refs/heads/topic"])
def test_real_composer_reopens_cancelled_draft_and_clears_it_after_commit(
    git_picker, branch_name
):
    state = git_picker
    _git(state.root, "branch", "-m", branch_name)
    _stage(state)
    head = _git(state.root, "rev-parse", "HEAD")
    tree = _git(state.root, "write-tree")
    message = "취소한 초안\n\nReopen this multiline message with 'quotes'."
    original_exec = CommitMessageDialog.exec_

    def edit_and_cancel(dialog):
        assert dialog.branch_label.text() == f"Branch: {branch_name}"

        def cancel():
            dialog.message_edit.setPlainText(message)
            dialog.reject()

        QTimer.singleShot(0, cancel)
        return original_exec(dialog)

    state.monkeypatch.setattr(CommitMessageDialog, "exec_", edit_and_cancel)
    _open(state, "ts")
    state.picker.actions.request("commit", None)
    _settled(state)

    assert _git(state.root, "rev-parse", "HEAD") == head
    assert _git(state.root, "write-tree") == tree
    assert state.picker.actions.commit_drafts[state.picker.git_root] == message
    reopened_messages = []

    def reopen_and_commit(dialog):
        assert dialog.branch_label.text() == f"Branch: {branch_name}"
        reopened_messages.append(dialog.message())
        QTimer.singleShot(
            0,
            lambda: state.bot.keyClick(
                dialog.message_edit, Qt.Key_Return, Qt.ControlModifier
            ),
        )
        return original_exec(dialog)

    state.monkeypatch.setattr(CommitMessageDialog, "exec_", reopen_and_commit)
    state.picker.actions.request("commit", None)
    _settled(state)

    assert reopened_messages == [message]
    assert _git(state.root, "rev-parse", "HEAD") != head
    assert _git(state.root, "log", "-1", "--format=%B").decode().rstrip("\n") == message
    assert state.picker.git_root not in state.picker.actions.commit_drafts


def test_unresolved_index_skips_composer_and_preserves_conflict(git_picker):
    state = git_picker
    _git(state.root, "switch", "-c", "topic")
    state.file.write_text("topic = 2\n")
    _git(state.root, "commit", "-am", "Topic version")
    _git(state.root, "switch", "main")
    state.file.write_text("main = 3\n")
    _git(state.root, "commit", "-am", "Main version")
    with pytest.raises(subprocess.CalledProcessError):
        _git(state.root, "merge", "topic")
    head = _git(state.root, "rev-parse", "HEAD")
    unmerged = _git(state.root, "ls-files", "--unmerged")
    assert unmerged
    contents = state.file.read_text()
    compose = _composer(state, "Must not commit unresolved index")
    _open(state, "ts")

    state.picker.actions.request("commit", None)
    _settled(state)

    compose.assert_not_called()
    assert _git(state.root, "rev-parse", "HEAD") == head
    assert _git(state.root, "ls-files", "--unmerged") == unmerged
    assert state.file.read_text() == contents
    assert (state.root / ".git" / "MERGE_HEAD").exists()


@pytest.mark.parametrize("change", ["index", "head", "branch"])
def test_repository_change_while_composing_aborts_without_overwriting(
    change, git_picker
):
    state = git_picker
    _stage(state)
    extra = state.root / "external.py"
    after_external_change = {}

    def compose(request, branch, summary):
        if change == "index":
            extra.write_text("external = 1\n")
            _git(state.root, "add", extra.name)
        elif change == "head":
            _git(state.root, "commit", "-m", "External commit")
        else:
            _git(state.root, "switch", "-c", "external-branch")
        after_external_change.update(
            head=_git(state.root, "rev-parse", "HEAD"),
            branch=_git(state.root, "symbolic-ref", "HEAD"),
            index=_git(state.root, "write-tree"),
            status=_git(state.root, "status", "--porcelain"),
        )
        return "Draft must survive changed repository"

    state.monkeypatch.setattr(state.picker.actions, "compose_commit", compose)
    _open(state, "ts")

    state.picker.actions.request("commit", None)
    _settled(state)

    assert after_external_change == {
        "head": _git(state.root, "rev-parse", "HEAD"),
        "branch": _git(state.root, "symbolic-ref", "HEAD"),
        "index": _git(state.root, "write-tree"),
        "status": _git(state.root, "status", "--porcelain"),
    }
    assert state.picker.actions.commit_drafts[state.picker.git_root] == (
        "Draft must survive changed repository"
    )
    assert state.file.read_text() == "staged = 2\n"
    if change == "index":
        assert extra.read_text() == "external = 1\n"


def test_hook_failure_keeps_draft_and_staged_changes_for_retry(git_picker):
    state = git_picker
    _stage(state)
    head = _git(state.root, "rev-parse", "HEAD")
    tree = _git(state.root, "write-tree")
    hook = state.root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'commit hook rejected\\n' >&2\nexit 1\n")
    hook.chmod(0o755)
    message = "Retry this message\n\nKeep the body too"
    compose = _composer(state, message)
    _open(state, "ts")

    state.picker.actions.request("commit", None)
    _settled(state)

    assert _git(state.root, "rev-parse", "HEAD") == head
    assert _git(state.root, "write-tree") == tree
    assert state.picker.actions.commit_drafts[state.picker.git_root] == message
    assert "commit hook rejected" in state.widget.msg_label.text()
    hook.unlink()
    state.picker.actions.request("commit", None)
    _settled(state)

    assert compose.call_count == 2
    assert _git(state.root, "rev-parse", "HEAD") != head
    assert _git(state.root, "log", "-1", "--format=%B").decode().rstrip("\n") == message
    assert state.picker.git_root not in state.picker.actions.commit_drafts
    assert _git(state.root, "diff", "--cached") == b""


def test_repeated_commit_shortcut_while_busy_creates_one_commit(git_picker):
    state = git_picker
    _stage(state)
    count = _count(state.root)
    hook = state.root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nsleep 0.2\nexit 0\n")
    hook.chmod(0o755)
    compose = _composer(state, "One requested commit")
    dialog = _open(state, "ts")

    state.bot.keyClick(dialog.prompt, Qt.Key_Return, Qt.ControlModifier)
    state.bot.keyClick(dialog.prompt, Qt.Key_Enter, Qt.ControlModifier)
    _settled(state)

    compose.assert_called_once()
    assert _count(state.root) == count + 1


def test_accepted_commit_finishes_after_picker_is_closed(git_picker):
    state = git_picker
    _stage(state)
    count = _count(state.root)
    hook = state.root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nsleep 0.2\nexit 0\n")
    hook.chmod(0o755)
    _composer(state, "Commit after closing picker")
    _open(state, "ts")
    state.picker.actions.request("commit", None)
    state.bot.waitUntil(lambda: state.picker.actions.running is not None)

    state.picker.cancel()
    _settled(state)

    assert state.picker.phase == "closed"
    assert _count(state.root) == count + 1
    assert _git(state.root, "show", "HEAD:file.py") == b"staged = 2\n"
