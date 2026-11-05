"""Branch snapshots retain exact refs and immutable preview objects."""

import subprocess

import pytest

from spyder_okvim.spyder.picker_git import (
    GitResult,
    branch_preview_args,
    branches_args,
    git_snapshot,
    parse_branches,
)


def git(path, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(path), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    ).stdout


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "Branch Picker")
    git(tmp_path, "config", "user.email", "branches@example.invalid")
    (tmp_path / "source.py").write_text("value = 1\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "branch root")
    return tmp_path


def test_local_remote_and_symbolic_refs_keep_exact_identity(repository):
    git(repository, "branch", "topic/한글")
    sha = git(repository, "rev-parse", "HEAD").decode().strip()
    git(repository, "config", "remote.origin.url", "https://example.invalid/repo")
    git(
        repository,
        "config",
        "remote.origin.fetch",
        "+refs/heads/*:refs/remotes/origin/*",
    )
    git(repository, "update-ref", "refs/remotes/origin/main", sha)
    git(repository, "update-ref", "refs/remotes/origin/topic/한글", sha)
    git(
        repository,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/main",
    )
    git(repository, "branch", "--set-upstream-to=origin/main", "main")
    before = git(repository, "show-ref")
    rows = parse_branches(git(repository, *branches_args()))
    values = {row.ref: row for row in rows}
    assert set(values) == {
        "refs/heads/main",
        "refs/heads/topic/한글",
        "refs/remotes/origin/main",
        "refs/remotes/origin/topic/한글",
    }
    assert values["refs/heads/main"].current
    assert values["refs/heads/main"].upstream == "refs/remotes/origin/main"
    assert values["refs/heads/topic/한글"].name == "topic/한글"
    assert sum(row.current for row in rows) == 1
    assert all(row.sha == sha for row in rows)
    assert git(repository, "show-ref") == before


def test_snapshot_and_preview_use_selected_object_even_if_branch_moves(repository):
    raw = git(repository, *branches_args())
    snapshot = git_snapshot(
        "git_branches", str(repository), 4, str(repository), "", GitResult(1, raw, "")
    )
    assert len(snapshot.entries) == 1
    entry = snapshot.entries[0]
    assert entry.id == "refs/heads/main"
    assert entry.label == "* main"
    assert entry.preview_kind == "branch"
    assert entry.target.ref == "refs/heads/main"
    assert entry.target.path == str(repository)
    original = entry.target.commit
    git(repository, "commit", "--allow-empty", "-m", "after snapshot")
    assert git(repository, "rev-parse", "HEAD").decode().strip() != original
    preview = git(repository, *branch_preview_args(entry.target)).decode()
    assert "branch root" in preview
    assert "after snapshot" not in preview
    assert original in branch_preview_args(entry.target)


def test_detached_head_does_not_mark_a_local_branch_as_current(repository):
    git(repository, "checkout", "--detach", "HEAD")
    branches = parse_branches(git(repository, *branches_args()))
    assert len(branches) == 1
    assert branches[0].ref == "refs/heads/main"
    assert not branches[0].current


def test_unborn_repository_produces_explicit_empty_branch_snapshot(tmp_path):
    git(tmp_path, "init", "-b", "main")
    data = git(tmp_path, *branches_args())
    assert not parse_branches(data)
    snapshot = git_snapshot(
        "git_branches", str(tmp_path), 1, str(tmp_path), "", GitResult(0, data, "")
    )
    assert snapshot.entries == ()
    assert snapshot.completeness == "No branches in this repository."


def test_parser_discards_incomplete_or_malformed_branch_records(repository):
    valid = git(repository, *branches_args())
    assert len(parse_branches(valid + b"refs/heads/incomplete\0")) == 1
    assert parse_branches(b"refs/heads/bad\0bad\0not-a-sha\0*\0\0\0\n") == ()
    assert parse_branches(b"refs/tags/tag\0tag\0" + b"a" * 40 + b"\0 \0\0\0\n") == ()
