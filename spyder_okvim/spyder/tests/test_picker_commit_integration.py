"""Commit composition writes only the reviewed index in temporary repositories."""

from pathlib import Path
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


def _merge_head_change(root, change):
    """Prepare valid merge parents without changing HEAD or the index."""
    merge_head = Path(
        _git(root, "rev-parse", "--path-format=absolute", "--git-path", "MERGE_HEAD")
        .decode()
        .strip()
    )
    tree = _git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    parents = [
        _git(root, "commit-tree", tree, "-m", message)
        for message in ("First parent", "Second parent", "Replacement parent")
    ]
    before, after = {
        "started": (None, parents[0]),
        "removed": (parents[0], None),
        "parents_changed": (parents[0] + parents[1], parents[0] + parents[2]),
    }[change]
    if before is not None:
        merge_head.write_bytes(before)
    return merge_head, after


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


@pytest.mark.parametrize("linked_worktree", [False, True])
def test_resolved_merge_with_unchanged_tree_can_be_committed(
    git_picker, linked_worktree
):
    state = git_picker
    if linked_worktree:
        linked = state.root / "linked"
        _git(state.root, "worktree", "add", "-b", "linked-main", str(linked))
        state.root = linked
        state.file = linked / "file.py"
        state.monkeypatch.setattr(
            state.main.projects, "get_active_project_path", lambda: str(linked)
        )
        assert (state.root / ".git").is_file()
    branch = _git(state.root, "symbolic-ref", "--short", "HEAD").decode().strip()
    _git(state.root, "switch", "-c", "topic")
    state.file.write_text("topic = 2\n")
    _git(state.root, "commit", "-am", "Topic version")
    topic = _git(state.root, "rev-parse", "HEAD").strip()
    _git(state.root, "switch", branch)
    state.file.write_text("main = 3\n")
    _git(state.root, "commit", "-am", "Main version")
    head = _git(state.root, "rev-parse", "HEAD").strip()
    with pytest.raises(subprocess.CalledProcessError):
        _git(state.root, "merge", "topic")
    _git(state.root, "checkout", "--ours", state.file.name)
    _git(state.root, "add", state.file.name)
    tree = _git(state.root, "write-tree")
    assert tree == _git(state.root, "rev-parse", "HEAD^{tree}")
    assert _git(state.root, "diff", "--cached") == b""
    compose = _composer(state, "Complete resolved merge")
    state.widget.open_picker("git_status")
    state.bot.waitUntil(
        lambda: state.picker.result_token == state.picker._search_token()
        and state.picker.git_root == str(state.root)
    )

    state.picker.actions.request("commit", None)
    _settled(state)

    compose.assert_called_once()
    assert topic.decode() in compose.call_args.args[2]
    assert "No staged changes relative to HEAD." in compose.call_args.args[2]
    assert _git(state.root, "show", "-s", "--format=%P", "HEAD").split() == [
        head,
        topic,
    ]
    assert _git(state.root, "rev-parse", "HEAD^{tree}") == tree
    assert _git(state.root, "status", "--porcelain") == b""
    merge_head = Path(
        _git(
            state.root,
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "MERGE_HEAD",
        )
        .decode()
        .strip()
    )
    assert not merge_head.exists()
    assert state.picker.git_root not in state.picker.actions.commit_drafts


@pytest.mark.parametrize("change", ["started", "removed", "parents_changed"])
def test_merge_state_change_while_composing_aborts_and_keeps_draft(git_picker, change):
    state = git_picker
    _stage(state)
    merge_head, after = _merge_head_change(state.root, change)
    head = _git(state.root, "rev-parse", "HEAD")
    index = _git(state.root, "write-tree")
    status = _git(state.root, "status", "--porcelain")
    draft = "Keep this draft after merge state changes"

    def compose(request, branch, summary):
        if after is None:
            merge_head.unlink()
        else:
            merge_head.write_bytes(after)
        return draft

    state.monkeypatch.setattr(state.picker.actions, "compose_commit", compose)
    _open(state, "ts")

    state.picker.actions.request("commit", None)
    _settled(state)

    assert _git(state.root, "rev-parse", "HEAD") == head
    assert _git(state.root, "write-tree") == index
    assert _git(state.root, "status", "--porcelain") == status
    assert (merge_head.read_bytes() if merge_head.exists() else None) == after
    assert state.picker.actions.commit_drafts[state.picker.git_root] == draft
    assert "merge" in state.widget.msg_label.text().lower()
    assert "changed" in state.widget.msg_label.text().lower()


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
