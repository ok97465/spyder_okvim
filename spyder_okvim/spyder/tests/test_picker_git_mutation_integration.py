"""Accepted Git actions change only temporary repositories and refresh the picker."""

from unittest.mock import Mock

import pytest
from qtpy.QtCore import Qt

from spyder_okvim.spyder.tests.test_picker_git_shortcuts import git_picker, _open
from spyder_okvim.spyder.tests.test_picker_git_integration import _git


def _settled(state):
    state.bot.waitUntil(lambda: not state.picker.actions.busy, timeout=10000)
    if state.picker.phase == "active":
        state.bot.waitUntil(
            lambda: state.picker.result_token == state.picker._search_token(),
            timeout=5000,
        )


def _choose(state, identifier):
    state.picker.dialog.select_id(identifier)
    entry = state.picker.dialog.selected_entry()
    assert entry is not None and entry.id == identifier
    return entry


def _confirm(state):
    confirmation = Mock(return_value=True)
    state.monkeypatch.setattr(state.picker.actions, "confirm", confirmation)
    return confirmation


def _remote(state, name="topic"):
    sha = _git(state.root, "rev-parse", "HEAD").decode().strip()
    _git(state.root, "config", "remote.origin.url", str(state.root / "local-remote"))
    _git(
        state.root,
        "config",
        "remote.origin.fetch",
        "+refs/heads/*:refs/remotes/origin/*",
    )
    _git(state.root, "update-ref", f"refs/remotes/origin/{name}", sha)


@pytest.mark.parametrize("unborn", [False, True])
def test_status_tab_stages_and_unstages_without_changing_disk(git_picker, unborn):
    state = git_picker
    if unborn:
        root = state.root / "unborn"
        root.mkdir()
        _git(root, "init", "-b", "main")
        path = root / "fresh.py"
        path.write_text("new = 1\n")
        state.monkeypatch.setattr(
            state.main.projects, "get_active_project_path", lambda: str(root)
        )
    else:
        root, path = state.root, state.file
        path.write_text("staged = 2\n")
    before = path.read_text()
    dialog = _open(state, "ts")
    state.bot.keyClick(dialog.prompt, Qt.Key_Tab)
    _settled(state)
    assert _git(root, "show", f":{path.name}").decode() == before
    assert state.picker.dialog.selected_entry().target.status == (
        "A." if unborn else "M."
    )
    state.bot.keyClick(dialog.prompt, Qt.Key_Tab)
    _settled(state)
    assert path.read_text() == before
    if unborn:
        assert _git(root, "ls-files") == b""
        assert state.picker.dialog.selected_entry().target.status == "??"
    else:
        assert _git(root, "show", f":{path.name}").decode() == "original = 1\n"
        assert state.picker.dialog.selected_entry().target.status == ".M"


def test_status_tab_unstages_both_xy_then_stages_latest_worktree(git_picker):
    state = git_picker
    state.file.write_text("staged = 2\n")
    _git(state.root, "add", "file.py")
    state.file.write_text("worktree = 3\n")
    dialog = _open(state, "ts")
    assert dialog.selected_entry().target.status == "MM"
    state.bot.keyClick(dialog.prompt, Qt.Key_Tab)
    _settled(state)
    assert _git(state.root, "show", ":file.py").decode() == "original = 1\n"
    assert dialog.selected_entry().target.status == ".M"
    state.bot.keyClick(dialog.prompt, Qt.Key_Tab)
    _settled(state)
    assert _git(state.root, "show", ":file.py").decode() == "worktree = 3\n"
    assert dialog.selected_entry().target.status == "M."


def test_commit_enter_detaches_and_reloads_clean_open_buffer(git_picker):
    state = git_picker
    old = _git(state.root, "rev-parse", "HEAD").decode().strip()
    state.file.write_text("second = 2\n")
    _git(state.root, "commit", "-am", "second version")
    state.stack.load(str(state.file), processevents=False)
    state.vim._use_stack(state.stack)
    editor = state.stack.get_current_editor()
    assert not editor.document().isModified()
    dialog = _open(state, "tc")
    _choose(state, old)
    state.bot.keyClick(dialog.prompt, Qt.Key_Return)
    _settled(state)
    assert _git(state.root, "rev-parse", "HEAD").decode().strip() == old
    assert _git(state.root, "rev-parse", "--abbrev-ref", "HEAD") == b"HEAD\n"
    assert state.file.read_text() == "original = 1\n"
    assert editor.toPlainText() == "original = 1\n"
    assert not editor.document().isModified()
    assert state.picker.phase == "active"


@pytest.mark.parametrize("mode", ["mixed", "soft", "hard"])
def test_commit_reset_modes_preserve_their_index_worktree_contract(git_picker, mode):
    state = git_picker
    old = _git(state.root, "rev-parse", "HEAD").decode().strip()
    state.file.write_text("committed = 2\n")
    _git(state.root, "commit", "-am", "second version")
    state.file.write_text("staged = 3\n")
    _git(state.root, "add", "file.py")
    state.file.write_text("worktree = 4\n")
    confirmation = _confirm(state)
    _open(state, "tc")
    entry = _choose(state, old)
    state.picker.actions.request(f"reset_{mode}", entry)
    _settled(state)
    confirmation.assert_called_once()
    assert confirmation.call_args.args[0].action == f"reset_{mode}"
    assert _git(state.root, "rev-parse", "HEAD").decode().strip() == old
    assert _git(state.root, "rev-parse", "--abbrev-ref", "HEAD") == b"main\n"
    assert _git(state.root, "show", ":file.py").decode() == (
        "staged = 3\n" if mode == "soft" else "original = 1\n"
    )
    assert state.file.read_text() == (
        "original = 1\n" if mode == "hard" else "worktree = 4\n"
    )
    assert len(state.picker.snapshot.entries) == 1


@pytest.mark.parametrize("action", ["checkout", "reset_hard"])
def test_disk_action_refuses_unsaved_editor_changes(git_picker, action):
    state = git_picker
    old = _git(state.root, "rev-parse", "HEAD").decode().strip()
    state.file.write_text("committed = 2\n")
    _git(state.root, "commit", "-am", "second version")
    head = _git(state.root, "rev-parse", "HEAD")
    state.stack.load(str(state.file), processevents=False)
    state.vim._use_stack(state.stack)
    editor = state.stack.get_current_editor()
    editor.insertPlainText("unsaved ")
    before = editor.toPlainText()
    confirmation = _confirm(state)
    _open(state, "tc")
    entry = _choose(state, old)
    state.picker.actions.request(action, entry)
    _settled(state)
    assert _git(state.root, "rev-parse", "HEAD") == head
    assert editor.toPlainText() == before
    assert state.file.read_text() == "committed = 2\n"
    assert "modified buffers" in state.widget.msg_label.text()
    confirmation.assert_not_called()


def test_reset_confirmation_cancellation_and_stale_query_do_not_write(git_picker):
    state = git_picker
    old = _git(state.root, "rev-parse", "HEAD").decode().strip()
    _git(state.root, "commit", "--allow-empty", "-m", "later commit")
    head = _git(state.root, "rev-parse", "HEAD")
    _open(state, "tc")
    entry = _choose(state, old)
    state.monkeypatch.setattr(
        state.picker.actions, "confirm", lambda request, branch: False
    )
    state.picker.actions.request("reset_hard", entry)
    _settled(state)
    assert _git(state.root, "rev-parse", "HEAD") == head

    def invalidate(request, branch):
        state.picker.dialog.prompt.setText("later")
        return True

    state.monkeypatch.setattr(state.picker.actions, "confirm", invalidate)
    state.picker.actions.request("reset_hard", entry)
    _settled(state)
    assert _git(state.root, "rev-parse", "HEAD") == head


@pytest.mark.parametrize(
    "operation", ["checkout", "track", "create", "delete", "delete_remote"]
)
def test_branch_actions_checkout_track_create_delete(git_picker, operation):
    state = git_picker
    _confirm(state)
    if operation in ("track", "delete_remote"):
        _remote(state)
        identifier = "refs/remotes/origin/topic"
    else:
        _git(state.root, "branch", "topic")
        identifier = "refs/heads/topic"
    dialog = _open(state, "tb")
    entry = _choose(state, identifier)
    if operation == "checkout":
        state.bot.keyClick(dialog.prompt, Qt.Key_Return)
    elif operation == "track":
        state.bot.keyClick(dialog.prompt, Qt.Key_T, Qt.ControlModifier)
    elif operation == "create":
        state.monkeypatch.setattr(
            state.picker.actions, "name_branch", lambda: "created/topic"
        )
        state.picker.actions.request("branch_create", entry)
    else:
        state.picker.actions.request("branch_delete", entry)
    _settled(state)
    if operation in ("checkout", "track"):
        assert _git(state.root, "rev-parse", "--abbrev-ref", "HEAD") == b"topic\n"
        assert any(item.label == "* topic" for item in state.picker.snapshot.entries)
        if operation == "track":
            assert _git(state.root, "config", "branch.topic.remote") == b"origin\n"
            assert (
                _git(state.root, "config", "branch.topic.merge")
                == b"refs/heads/topic\n"
            )
    elif operation == "create":
        assert (
            _git(state.root, "rev-parse", "--abbrev-ref", "HEAD") == b"created/topic\n"
        )
        assert any(
            item.target.ref == "refs/heads/created/topic"
            for item in state.picker.snapshot.entries
        )
    else:
        assert _git(state.root, "for-each-ref", identifier) == b""
        assert all(
            item.target.ref != identifier for item in state.picker.snapshot.entries
        )
        assert _git(state.root, "rev-parse", "--abbrev-ref", "HEAD") == b"main\n"


@pytest.mark.parametrize("operation", ["merge", "rebase"])
def test_branch_merge_and_rebase_use_selected_branch(git_picker, operation):
    state = git_picker
    _git(state.root, "checkout", "-b", "topic")
    (state.root / "topic.py").write_text("topic = 1\n")
    _git(state.root, "add", ".")
    _git(state.root, "commit", "-m", "topic commit")
    topic = _git(state.root, "rev-parse", "HEAD").decode().strip()
    _git(state.root, "checkout", "main")
    (state.root / "main.py").write_text("main = 1\n")
    _git(state.root, "add", ".")
    _git(state.root, "commit", "-m", "main commit")
    before = _git(state.root, "rev-parse", "HEAD").decode().strip()
    _confirm(state)
    _open(state, "tb")
    entry = _choose(state, "refs/heads/topic")
    state.picker.actions.request(f"branch_{operation}", entry)
    _settled(state)
    parents = (
        _git(state.root, "rev-list", "--parents", "-n", "1", "HEAD").decode().split()
    )
    assert parents[0] != before
    if operation == "merge":
        assert parents[1:] == [before, topic]
    else:
        assert parents[1:] == [topic]
        assert _git(state.root, "log", "-1", "--format=%s") == b"main commit\n"
    assert (state.root / "main.py").exists() and (state.root / "topic.py").exists()
    assert _git(state.root, "rev-parse", "--abbrev-ref", "HEAD") == b"main\n"


def test_stash_enter_applies_index_worktree_and_untracked_without_dropping(git_picker):
    state = git_picker
    state.file.write_text("staged = 2\n")
    _git(state.root, "add", "file.py")
    state.file.write_text("worktree = 3\n")
    untracked = state.root / "untracked.py"
    untracked.write_text("untracked = 1\n")
    _git(state.root, "stash", "push", "--include-untracked", "-m", "saved state")
    before = _git(state.root, "stash", "list", "--format=%H")
    dialog = _open(state, "tS")
    state.bot.keyClick(dialog.prompt, Qt.Key_Return)
    _settled(state)
    assert _git(state.root, "stash", "list", "--format=%H") == before
    assert _git(state.root, "show", ":file.py").decode() == "staged = 2\n"
    assert state.file.read_text() == "worktree = 3\n"
    assert untracked.read_text() == "untracked = 1\n"
    assert state.picker.phase == "active"


def test_accepted_checkout_finishes_when_picker_is_closed(git_picker):
    state = git_picker
    old = _git(state.root, "rev-parse", "HEAD").decode().strip()
    _git(state.root, "commit", "--allow-empty", "-m", "later commit")
    hook = state.root / ".git" / "hooks" / "post-checkout"
    hook.write_text("#!/bin/sh\nsleep 0.2\nexit 0\n")
    hook.chmod(0o755)
    _open(state, "tc")
    entry = _choose(state, old)
    state.picker.actions.request("checkout", entry)
    state.bot.waitUntil(lambda: state.picker.actions.running is not None)
    state.picker.cancel()
    _settled(state)
    assert state.picker.phase == "closed"
    assert _git(state.root, "rev-parse", "HEAD").decode().strip() == old


@pytest.mark.parametrize("unborn", [False, True])
def test_create_branch_without_selected_result_uses_current_head(git_picker, unborn):
    state = git_picker
    if unborn:
        _git(state.root, "update-ref", "-d", "refs/heads/main")
    index = _git(state.root, "ls-files", "--stage")
    state.widget.open_picker("git_branches")
    state.bot.waitUntil(lambda: state.picker.result_token is not None)
    dialog = state.picker.dialog
    if not unborn:
        dialog.prompt.setText("does-not-match-any-branch")
        state.bot.waitUntil(lambda: state.picker.result_token is not None)
    assert dialog.selected_entry() is None
    state.monkeypatch.setattr(
        state.picker.actions, "name_branch", lambda: "created/empty"
    )
    state.picker.actions.request("branch_create", None)
    _settled(state)
    assert _git(state.root, "symbolic-ref", "--short", "HEAD") == b"created/empty\n"
    assert _git(state.root, "ls-files", "--stage") == index
    assert state.file.read_text() == "original = 1\n"


@pytest.mark.parametrize("operation", ["merge", "rebase"])
def test_conflicting_branch_action_keeps_resolution_state_and_reports_error(
    git_picker, operation
):
    state = git_picker
    _git(state.root, "checkout", "-b", "topic")
    state.file.write_text("topic change\n")
    _git(state.root, "commit", "-am", "topic change")
    topic = _git(state.root, "rev-parse", "HEAD")
    _git(state.root, "checkout", "main")
    state.file.write_text("main change\n")
    _git(state.root, "commit", "-am", "main change")
    before = _git(state.root, "rev-parse", "HEAD")
    _confirm(state)
    _open(state, "tb")
    entry = _choose(state, "refs/heads/topic")
    state.picker.actions.request(f"branch_{operation}", entry)
    _settled(state)
    assert _git(state.root, "ls-files", "--unmerged")
    assert "<<<<<<<" in state.file.read_text()
    assert "conflict" in state.widget.msg_label.text().lower()
    assert state.picker.phase == "active"
    if operation == "merge":
        assert (state.root / ".git" / "MERGE_HEAD").exists()
        assert _git(state.root, "rev-parse", "HEAD") == before
    else:
        assert any(
            (state.root / ".git" / name).exists()
            for name in ("rebase-merge", "rebase-apply")
        )
        assert _git(state.root, "rev-parse", "HEAD") == topic
        assert _git(state.root, "rev-parse", "refs/heads/main") == before
