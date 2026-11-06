"""Git mutations operate on explicit targets and outlive popup read requests."""

import subprocess

import pytest

from spyder_okvim.spyder.picker_git_actions import (
    GitMutationService,
    action_args,
    can_revert_status,
    status_action,
    worktree_stamp,
)
from spyder_okvim.utils.picker import PickerTarget


def git(directory, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(directory), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def sha(directory, reference="HEAD"):
    return git(directory, "rev-parse", reference).stdout.decode().strip()


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "Git Action Tester")
    git(tmp_path, "config", "user.email", "picker@example.invalid")
    (tmp_path / "file.txt").write_text("root\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "root")
    return tmp_path


def _run(repository, action, target, **kwargs):
    return git(
        repository, "--literal-pathspecs", *action_args(action, target, **kwargs)
    )


@pytest.mark.parametrize(
    "status,action",
    [
        ("??", "stage"),
        (".M", "stage"),
        ("M.", "unstage"),
        ("MM", "unstage"),
        ("A.", "unstage"),
        ("R.", "unstage"),
        ("UU", "stage"),
        ("AA", "stage"),
    ],
)
def test_status_toggle_uses_index_state_and_resolves_conflicts(status, action):
    assert status_action(PickerTarget("file.txt", status=status)) == action


@pytest.mark.parametrize(
    "status,allowed",
    [
        (".M", True),
        ("MM", True),
        ("AM", True),
        ("RM", True),
        (".D", True),
        ("AD", True),
        (".T", True),
        ("M.", False),
        ("A.", False),
        ("D.", False),
        ("R.", False),
        ("??", True),
        (".A", False),
        ("UU", False),
        ("UD", False),
        ("DD", False),
    ],
)
def test_revert_eligibility_allows_unstaged_restore_or_untracked_delete(
    status, allowed
):
    assert can_revert_status(PickerTarget("file.txt", status=status)) is allowed


def test_untracked_revert_requires_guarded_deletion_service():
    with pytest.raises(ValueError, match="guarded mutation service"):
        action_args(
            "revert_file", PickerTarget("new.txt", status="??"), index_tree="1" * 40
        )


def test_stage_and_unstage_preserve_worktree_and_literal_paths(repository):
    name = "literal [x]*\t\n.txt"
    (repository / name).write_text("literal\n")
    (repository / "other.txt").write_text("unselected\n")
    target = PickerTarget(name, status="??")
    _run(repository, "stage", target)
    assert (
        git(repository, "diff", "--cached", "--name-only", "-z").stdout
        == name.encode() + b"\0"
    )
    _run(repository, "unstage", target)
    assert git(repository, "diff", "--cached", "--name-only", "-z").stdout == b""
    assert (repository / name).read_text() == "literal\n"


def test_unstage_before_first_commit(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "new.txt").write_text("new\n")
    git(tmp_path, "add", ".")
    _run(tmp_path, "unstage", PickerTarget("new.txt", status="A."))
    assert git(tmp_path, "status", "--porcelain=v1").stdout == b"?? new.txt\n"


def test_rename_unstage_restores_both_index_paths(repository):
    git(repository, "mv", "file.txt", "renamed.txt")
    target = PickerTarget("renamed.txt", old_path="file.txt", status="R.")
    _run(repository, "unstage", target)
    assert git(repository, "ls-files", "-z").stdout == b"file.txt\0"
    assert not (repository / "file.txt").exists()
    assert (repository / "renamed.txt").read_text() == "root\n"


@pytest.mark.parametrize("mode", ["soft", "mixed", "hard"])
def test_reset_modes_have_distinct_index_and_worktree_effects(repository, mode):
    root = sha(repository)
    file = repository / "file.txt"
    file.write_text("second\n")
    git(repository, "commit", "-am", "second")
    file.write_text("index\n")
    git(repository, "add", "file.txt")
    file.write_text("worktree\n")
    _run(repository, "reset_" + mode, PickerTarget(str(repository), commit=root))
    assert sha(repository) == root
    assert git(repository, "show", ":file.txt").stdout == (
        b"index\n" if mode == "soft" else b"root\n"
    )
    assert file.read_text() == ("root\n" if mode == "hard" else "worktree\n")


def test_commit_checkout_is_fixed_detached_snapshot(repository):
    root = sha(repository)
    (repository / "file.txt").write_text("second\n")
    git(repository, "commit", "-am", "second")
    _run(repository, "checkout_commit", PickerTarget(str(repository), commit=root))
    assert sha(repository) == root
    assert git(repository, "symbolic-ref", "-q", "HEAD", check=False).returncode == 1
    assert (repository / "file.txt").read_text() == "root\n"


def test_branch_create_checkout_and_safe_delete(repository):
    target = PickerTarget(
        str(repository), ref="refs/heads/main", commit=sha(repository)
    )
    _run(repository, "create_branch", target, branch_name="feature/unicode-한글")
    assert (
        git(repository, "symbolic-ref", "HEAD").stdout.strip()
        == "refs/heads/feature/unicode-한글".encode()
    )
    _run(repository, "checkout_branch", target)
    feature = PickerTarget(
        str(repository), ref="refs/heads/feature/unicode-한글", commit=target.commit
    )
    _run(repository, "delete_branch", feature)
    assert (
        git(repository, "show-ref", "--verify", feature.ref, check=False).returncode
        == 128
    )
    git(repository, "switch", "-c", "unmerged")
    (repository / "new.txt").write_text("unmerged\n")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "unmerged")
    unmerged = PickerTarget(
        str(repository), ref="refs/heads/unmerged", commit=sha(repository)
    )
    _run(repository, "checkout_branch", target)
    assert (
        git(repository, *action_args("delete_branch", unmerged), check=False).returncode
        != 0
    )
    assert sha(repository, unmerged.ref) == unmerged.commit


def test_remote_checkout_track_and_tracking_ref_delete(repository, tmp_path):
    remote = tmp_path / "remote.git"
    # The separate remote stays local to this test; no network operations.
    git(repository, "clone", "--bare", str(repository), str(remote))
    git(repository, "remote", "add", "origin", str(remote))
    git(repository, "fetch", "origin")
    git(repository, "update-ref", "refs/remotes/origin/topic", sha(repository))
    target = PickerTarget(
        str(repository), ref="refs/remotes/origin/topic", commit=sha(repository)
    )
    _run(repository, "checkout_branch", target)
    assert git(repository, "symbolic-ref", "-q", "HEAD", check=False).returncode == 1
    _run(repository, "track_branch", target)
    assert git(repository, "symbolic-ref", "HEAD").stdout.strip() == b"refs/heads/topic"
    assert git(repository, "config", "branch.topic.remote").stdout.strip() == b"origin"
    assert (
        git(repository, "config", "branch.topic.merge").stdout.strip()
        == b"refs/heads/topic"
    )
    git(repository, "switch", "main")
    _run(repository, "delete_branch", target)
    assert (
        git(repository, "show-ref", "--verify", target.ref, check=False).returncode
        == 128
    )
    assert sha(repository, "refs/heads/topic") == target.commit


def test_merge_and_rebase_apply_selected_branch_to_current(repository):
    git(repository, "switch", "-c", "topic")
    (repository / "topic.txt").write_text("topic\n")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "topic")
    topic = PickerTarget(
        str(repository), ref="refs/heads/topic", commit=sha(repository)
    )
    git(repository, "switch", "main")
    _run(repository, "merge", topic)
    assert (repository / "topic.txt").read_text() == "topic\n"
    assert git(repository, "symbolic-ref", "HEAD").stdout.strip() == b"refs/heads/main"
    git(repository, "switch", "topic")
    (repository / "next.txt").write_text("upstream\n")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "next")
    git(repository, "switch", "main")
    (repository / "local.txt").write_text("local\n")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "local")
    _run(repository, "rebase", topic)
    assert (repository / "next.txt").read_text() == "upstream\n"
    assert (repository / "local.txt").read_text() == "local\n"
    assert git(repository, "symbolic-ref", "HEAD").stdout.strip() == b"refs/heads/main"


def test_stash_apply_fixed_sha_restores_saved_index_and_untracked(repository):
    (repository / "file.txt").write_text("staged\n")
    git(repository, "add", "file.txt")
    (repository / "untracked.txt").write_text("saved untracked\n")
    git(repository, "stash", "push", "--include-untracked", "-m", "first")
    saved = sha(repository, "refs/stash")
    (repository / "file.txt").write_text("later stash\n")
    git(repository, "stash", "push", "-m", "second")
    before = git(repository, "stash", "list", "--format=%H").stdout
    _run(repository, "stash_apply", PickerTarget(str(repository), commit=saved))
    assert (repository / "file.txt").read_text() == "staged\n"
    assert git(repository, "show", ":file.txt").stdout == b"staged\n"
    assert (repository / "untracked.txt").read_text() == "saved untracked\n"
    assert git(repository, "stash", "list", "--format=%H").stdout == before


@pytest.mark.parametrize(
    "name",
    [
        "-option",
        "bad..name",
        "bad name",
        "bad@{name",
        ".hidden",
        "bad.lock",
        "trailing/",
        "",
    ],
)
def test_branch_name_validation_rejects_options_and_invalid_refs(name):
    with pytest.raises(ValueError):
        action_args("create_branch", PickerTarget("/repo"), branch_name=name)


def _submit(qtbot, service, directory, args, **kwargs):
    results = []
    assert service.submit("action", str(directory), args, results.append, **kwargs)
    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    assert not service.busy
    return results[0]


def test_service_checks_head_branch_and_selected_ref_before_write(qtbot, repository):
    service = GitMutationService()
    root = sha(repository)
    target = PickerTarget(str(repository), commit=root)
    git(repository, "branch", "same-object")
    result = _submit(
        qtbot,
        service,
        repository,
        action_args("reset_hard", target),
        expected_head=root,
        expected_branch="refs/heads/other",
    )
    assert "changed" in result.error
    assert git(repository, "symbolic-ref", "HEAD").stdout.strip() == b"refs/heads/main"
    result = _submit(
        qtbot, service, repository, ["branch", "never"], expected_head="0" * 40
    )
    assert "changed" in result.error
    assert git(repository, "show-ref", "refs/heads/never", check=False).returncode != 0
    result = _submit(
        qtbot,
        service,
        repository,
        ["branch", "never"],
        expected_head=root,
        expected_branch="refs/heads/main",
        expected_ref=("refs/heads/same-object", "0" * 40),
    )
    assert "changed" in result.error
    result = _submit(
        qtbot,
        service,
        repository,
        ["branch", "accepted"],
        expected_head=root,
        expected_branch="refs/heads/main",
        expected_ref=("refs/heads/same-object", root),
    )
    assert not result.error
    assert sha(repository, "refs/heads/accepted") == root
    service.close()


def test_service_unborn_head_and_detached_branch_checks(qtbot, tmp_path):
    git(tmp_path, "init", "-b", "main")
    service = GitMutationService()
    result = _submit(
        qtbot,
        service,
        tmp_path,
        ["switch", "--create", "feature"],
        expected_head="",
        expected_branch="refs/heads/main",
    )
    assert not result.error
    service.close()


def test_service_rechecks_staged_tree_before_commit(qtbot, repository):
    path = repository / "file.txt"
    path.write_text("reviewed index\n")
    git(repository, "add", "file.txt")
    reviewed = git(repository, "write-tree").stdout.decode().strip()
    before = sha(repository)
    path.write_text("externally restaged\n")
    git(repository, "add", "file.txt")
    service = GitMutationService()
    args = action_args("commit", PickerTarget(""), message="Reviewed commit")
    result = _submit(qtbot, service, repository, args, expected_index=reviewed)
    assert "index changed" in result.error
    assert sha(repository) == before
    assert git(repository, "show", ":file.txt").stdout == b"externally restaged\n"
    latest = git(repository, "write-tree").stdout.decode().strip()
    result = _submit(qtbot, service, repository, args, expected_index=latest)
    assert not result.error
    assert sha(repository) != before
    assert git(repository, "show", "HEAD:file.txt").stdout == b"externally restaged\n"
    service.close()


@pytest.mark.parametrize("message", ["", " \t\n", "subject\0invalid"])
def test_invalid_commit_message_cannot_reach_git(message):
    with pytest.raises(ValueError, match="commit message"):
        action_args("commit", PickerTarget(""), message=message)


def test_service_cannot_be_replaced_and_close_does_not_interrupt_write(
    qtbot, repository
):
    service = GitMutationService()
    results = []
    script = "!python -c \"import time,subprocess; time.sleep(.15); subprocess.check_call(['git','branch','completed'])\""
    assert service.submit(
        "one", str(repository), ["-c", "alias.slow=" + script, "slow"], results.append
    )
    process = service._process
    assert not service.submit(
        "two", str(repository), ["branch", "never"], results.append
    )
    assert service._process is process
    service.close()
    service.close()
    qtbot.waitUntil(lambda: not service.busy, timeout=5000)
    assert results == []
    assert sha(repository, "refs/heads/completed") == sha(repository)
    assert git(repository, "show-ref", "refs/heads/never", check=False).returncode != 0


def test_service_output_limit_does_not_interrupt_write(qtbot, repository):
    service = GitMutationService(output_limit=30)
    result = _submit(
        qtbot,
        service,
        repository,
        ["-c", "alias.verbose=!python -c 'print(\"x\"*10000)'", "verbose"],
    )
    assert result.returncode == 0 and not result.error
    assert result.truncated
    assert len(result.stdout) == 30
    service.close()


def test_service_failure_releases_slot_and_callback_can_submit_next(qtbot, repository):
    service = GitMutationService()
    results = []

    def first(result):
        results.append(result)
        assert not service.busy
        service.submit("next", str(repository), ["branch", "next"], results.append)

    assert service.submit("bad", str(repository), ["not-a-git-command"], first)
    qtbot.waitUntil(lambda: len(results) == 2)
    assert results[0].error
    assert not results[1].error
    assert sha(repository, "refs/heads/next") == sha(repository)
    service.close()


def test_service_timeout_and_failed_start_release_slot(qtbot, repository):
    service = GitMutationService(timeout_ms=20)
    result = _submit(
        qtbot,
        service,
        repository,
        ["-c", "alias.slow=!python -c 'import time; time.sleep(2)'", "slow"],
    )
    assert "timed out" in result.error
    service.close()
    missing = GitMutationService(program="/missing/git")
    result = _submit(qtbot, missing, repository, ["status"])
    assert result.error and result.returncode == -1
    missing.close()


def test_service_detects_checkout_to_same_object_branch(qtbot, repository):
    service = GitMutationService()
    root = sha(repository)
    git(repository, "branch", "other")
    git(repository, "switch", "other")
    result = _submit(
        qtbot,
        service,
        repository,
        ["branch", "never"],
        expected_head=root,
        expected_branch="refs/heads/main",
    )
    assert "symbolic HEAD changed" in result.error
    assert git(repository, "show-ref", "refs/heads/never", check=False).returncode != 0
    service.close()


def test_preflight_identity_is_not_truncated_by_action_output_budget(qtbot, repository):
    service = GitMutationService(output_limit=10)
    result = _submit(
        qtbot,
        service,
        repository,
        ["branch", "created"],
        expected_head=sha(repository),
        expected_branch="refs/heads/main",
    )
    assert not result.error
    assert sha(repository, "refs/heads/created") == sha(repository)
    service.close()


def _delete_untracked(qtbot, service, directory, path, stamp=None, **checks):
    results = []
    if stamp is None:
        stamp = worktree_stamp(path)
    assert service.submit_delete_untracked(
        "delete", str(directory), str(path), stamp, results.append, **checks
    )
    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    assert not service.busy
    return results[0]


def test_delete_untracked_is_literal_and_preserves_neighbors_and_index(
    qtbot, repository
):
    selected = repository / "new [x]*\t\n한글.txt"
    selected.write_text("selected\n")
    adjacent = repository / "new x.txt"
    adjacent.write_text("keep neighboring untracked file\n")
    before = git(repository, "ls-files", "--stage", "-z").stdout
    service = GitMutationService()
    results = []
    assert service.submit_delete_untracked(
        "delete",
        str(repository),
        selected.name,
        worktree_stamp(selected),
        results.append,
        expected_head=sha(repository),
        expected_branch="refs/heads/main",
        expected_index=git(repository, "write-tree").stdout.decode().strip(),
    )
    assert service.busy
    assert not service.submit("other", str(repository), ["status"], results.append)
    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    assert not results[0].error
    assert not selected.exists()
    assert adjacent.read_text() == "keep neighboring untracked file\n"
    assert (repository / "file.txt").read_text() == "root\n"
    assert git(repository, "ls-files", "--stage", "-z").stdout == before
    service.close()


def test_delete_untracked_refuses_indexed_file(qtbot, repository):
    selected = repository / "file.txt"
    before = git(repository, "ls-files", "--stage", "-z").stdout
    service = GitMutationService()
    result = _delete_untracked(qtbot, service, repository, selected)
    assert "now indexed" in result.error
    assert selected.read_text() == "root\n"
    assert git(repository, "ls-files", "--stage", "-z").stdout == before
    service.close()


def test_delete_untracked_refuses_changed_index(qtbot, repository):
    selected = repository / "new.txt"
    selected.write_text("keep selected\n")
    index = git(repository, "write-tree").stdout.decode().strip()
    (repository / "file.txt").write_text("new staging\n")
    git(repository, "add", "file.txt")
    service = GitMutationService()
    result = _delete_untracked(
        qtbot, service, repository, selected, expected_index=index
    )
    assert "index changed" in result.error
    assert selected.read_text() == "keep selected\n"
    assert git(repository, "show", ":file.txt").stdout == b"new staging\n"
    service.close()


def test_delete_untracked_rechecks_after_async_preconditions(
    qtbot, repository, monkeypatch
):
    selected = repository / "new.txt"
    selected.write_text("original untracked file\n")
    stamp = worktree_stamp(selected)
    service = GitMutationService()
    start_next = service._start_next
    swapped = []

    def replace_after_preconditions():
        if service._active is not None and not service._active.checks and not swapped:
            selected.unlink()
            selected.mkdir()
            (selected / "nested.txt").write_text("never recurse\n")
            swapped.append(True)
        start_next()

    monkeypatch.setattr(service, "_start_next", replace_after_preconditions)
    result = _delete_untracked(
        qtbot,
        service,
        repository,
        selected,
        stamp,
        expected_head=sha(repository),
        expected_index=git(repository, "write-tree").stdout.decode().strip(),
    )
    assert swapped == [True]
    assert "changed" in result.error
    assert (selected / "nested.txt").read_text() == "never recurse\n"
    service.close()


def test_delete_untracked_unlink_refuses_directory_replaced_after_final_stat(
    qtbot, repository, monkeypatch
):
    from spyder_okvim.spyder import picker_git_actions

    selected = repository / "new.txt"
    selected.write_text("original untracked file\n")
    stamp = worktree_stamp(selected)

    def replace_after_stat(path):
        observed = worktree_stamp(path)
        selected.unlink()
        selected.mkdir()
        (selected / "nested.txt").write_text("never recurse\n")
        return observed

    monkeypatch.setattr(picker_git_actions, "worktree_stamp", replace_after_stat)
    service = GitMutationService()
    result = _delete_untracked(qtbot, service, repository, selected, stamp)
    assert result.error
    assert (selected / "nested.txt").read_text() == "never recurse\n"
    service.close()


def test_accepted_untracked_delete_survives_service_close(qtbot, repository):
    selected = repository / "new.txt"
    selected.write_text("delete after close\n")
    service = GitMutationService()
    results = []
    assert service.submit_delete_untracked(
        "delete",
        str(repository),
        selected.name,
        worktree_stamp(selected),
        results.append,
        expected_head=sha(repository),
        expected_index=git(repository, "write-tree").stdout.decode().strip(),
    )
    service.close()
    qtbot.waitUntil(lambda: not service.busy, timeout=5000)
    assert not selected.exists()
    assert results == []


def test_delete_untracked_symlink_preserves_its_target(qtbot, repository):
    target = repository / "keep target.txt"
    target.write_text("keep symlink target\n")
    selected = repository / "remove link"
    try:
        selected.symlink_to(target)
    except OSError as error:
        pytest.skip(f"Symlink creation unavailable: {error}")
    service = GitMutationService()
    result = _delete_untracked(qtbot, service, repository, selected)
    assert not result.error
    assert not selected.is_symlink()
    assert target.read_text() == "keep symlink target\n"
    service.close()


def test_delete_untracked_refuses_parent_symlink_outside_repository(
    qtbot, repository, tmp_path_factory
):
    outside = tmp_path_factory.mktemp("outside-untracked")
    selected = repository / "outside-link"
    try:
        selected.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Symlink creation unavailable: {error}")
    outside_file = outside / "keep.txt"
    outside_file.write_text("outside repository\n")
    service = GitMutationService()
    result = _delete_untracked(qtbot, service, repository, selected / "keep.txt")
    assert "inside the repository" in result.error
    assert outside_file.read_text() == "outside repository\n"
    service.close()
