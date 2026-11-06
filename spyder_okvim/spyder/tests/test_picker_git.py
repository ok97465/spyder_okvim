"""Git picker boundaries tested with real local repositories and Qt processes."""

# Standard Libraries
import os
from pathlib import Path
import subprocess
import sys

# Third Party Libraries
import pytest

# Project Libraries
from spyder_okvim.spyder.picker_git import (
    MAX_GIT_ERROR,
    GitService,
    GitResult,
    git_snapshot,
    commit_files_args,
    commit_preview_args,
    log_args,
    parse_changed_files,
    parse_log,
    parse_status,
    status_args,
    status_diff_args,
    stash_args,
    stash_preview_args,
)


def git(directory, *args, check=True):
    return subprocess.run(
        ["git", "--literal-pathspecs", "-C", str(directory), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    ).stdout


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "Picker Tester")
    git(tmp_path, "config", "user.email", "picker@example.invalid")
    (tmp_path / "ordinary.txt").write_text("one\ntwo\nthree\n")
    (tmp_path / "deleted.txt").write_text("delete me\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "root commit")
    return tmp_path


def _status_entries(repository):
    snapshot = git_snapshot(
        "git_status",
        str(repository),
        1,
        str(repository),
        "",
        GitResult("status", git(repository, *status_args()), ""),
    )
    return {entry.id: entry for entry in snapshot.entries}


def test_status_display_tracks_new_file_staging_with_literal_path(repository):
    name = "new [literal]*\t\n.txt"
    path = repository / name
    path.write_text("new file\n")
    entry = _status_entries(repository)[name]
    assert entry.label == f"-U {name}"
    assert entry.target.status == "??"
    assert entry.target.path == str(path)
    git(repository, "add", name)
    entry = _status_entries(repository)[name]
    assert entry.label == f"+U {name}"
    assert entry.target.status == "A."
    assert entry.target.path == str(path)
    path.write_text("new file with an unstaged edit\n")
    entry = _status_entries(repository)[name]
    assert entry.label == f"+U -M {name}"
    assert entry.target.status == "AM"


def test_status_display_distinguishes_staged_unstaged_and_both(repository):
    path = repository / "ordinary.txt"
    path.write_text("staged version\n")
    entry = _status_entries(repository)[path.name]
    assert entry.label == "-M ordinary.txt"
    assert entry.target.status == ".M"
    git(repository, "add", path.name)
    entry = _status_entries(repository)[path.name]
    assert entry.label == "+M ordinary.txt"
    assert entry.target.status == "M."
    path.write_text("later worktree version\n")
    entry = _status_entries(repository)[path.name]
    assert entry.label == "+M -M ordinary.txt"
    assert entry.target.status == "MM"
    assert "+M -M ordinary.txt" in entry.search_text


def test_status_display_keeps_rename_and_deletion_codes(repository):
    name = "renamed [x]*\t\n.txt"
    git(repository, "mv", "ordinary.txt", name)
    (repository / "deleted.txt").unlink()
    entries = _status_entries(repository)
    assert entries[name].label == f"+R {name}"
    assert entries[name].target.status == "R."
    assert entries[name].target.old_path == "ordinary.txt"
    assert entries["deleted.txt"].label == "-D deleted.txt"
    assert entries["deleted.txt"].target.status == ".D"
    git(repository, "add", "deleted.txt")
    entry = _status_entries(repository)["deleted.txt"]
    assert entry.label == "+D deleted.txt"
    assert entry.target.status == "D."


def test_status_ids_distinguish_staged_deletion_and_untracked_replacement(repository):
    path = repository / "ordinary.txt"
    git(repository, "rm", path.name)
    path.write_text("recreated untracked content\n")

    entries = _status_entries(repository)

    assert len(entries) == 2
    assert entries[path.name].target.status == "D."
    replacement = next(
        entry for entry in entries.values() if entry.target.status == "??"
    )
    assert replacement.id != path.name
    assert replacement.target.path == entries[path.name].target.path == str(path)
    assert _status_entries(repository).keys() == entries.keys()

    git(repository, "add", path.name)
    staged = _status_entries(repository)
    assert list(staged) == [path.name]
    assert staged[path.name].target.status == "M."


def test_status_and_separate_index_worktree_patches(repository):
    path = repository / "ordinary.txt"
    path.write_text("staged\ntwo\nthree\n")
    git(repository, "add", "ordinary.txt")
    path.write_text("staged\nworktree\nthree\n")
    entries = parse_status(git(repository, *status_args()))
    assert [(item.path, item.xy) for item in entries] == [("ordinary.txt", "MM")]
    index = git(repository, *status_diff_args("ordinary.txt", staged=True))
    worktree = git(repository, *status_diff_args("ordinary.txt"))
    assert b"+staged" in index and b"+worktree" not in index
    assert b"+worktree" in worktree and b"+staged" not in worktree


def test_status_staged_only_rename_delete_binary_and_untracked(repository):
    target = "renamed [x]*\t\n.txt"
    git(repository, "mv", "ordinary.txt", target)
    (repository / "deleted.txt").unlink()
    (repository / "binary.dat").write_bytes(b"\0before\0after")
    git(repository, "add", "binary.dat")
    untracked = "untracked \t\n.txt"
    (repository / untracked).write_text("untracked\n")
    entries = {
        item.path: item for item in parse_status(git(repository, *status_args()))
    }
    assert entries[target].old_path == "ordinary.txt"
    assert entries[target].xy == "R."
    assert entries["deleted.txt"].xy == ".D"
    assert entries["binary.dat"].xy == "A."
    assert entries[untracked].kind == "untracked"
    assert b"Binary files" in git(repository, *status_diff_args("binary.dat", True))
    # Literal pathspecs ensure metacharacters remain the selected actual path.
    assert b"rename from ordinary.txt" in git(
        repository, *status_diff_args(target, True, "ordinary.txt")
    )


def test_root_history_and_change_files_preserve_special_paths(repository):
    root = git(repository, "rev-parse", "HEAD").decode().strip()
    history = parse_log(git(repository, *log_args()))
    assert len(history) == 1
    assert history[0].sha == root
    assert history[0].author == "Picker Tester"
    assert history[0].subject == "root commit"
    assert history[0].timestamp > 0
    assert {
        entry.path
        for entry in parse_changed_files(git(repository, *commit_files_args(root)))
    } == {"ordinary.txt", "deleted.txt"}
    patch = git(repository, *commit_preview_args(root)).decode()
    assert "new file mode" in patch
    assert "+one" in patch
    target = "new name\twith\nnewline.txt"
    git(repository, "mv", "ordinary.txt", target)
    git(repository, "commit", "-m", "renamed")
    second = git(repository, "rev-parse", "HEAD").decode().strip()
    entries = parse_changed_files(git(repository, *commit_files_args(second)))
    assert len(entries) == 1
    assert entries[0].old_path == "ordinary.txt"
    assert entries[0].path == target
    assert entries[0].status == "R100"
    assert [item.subject for item in parse_log(git(repository, *log_args(1, 1)))] == [
        "root commit"
    ]


def test_conflict_status_and_first_parent_merge_patch(repository):
    git(repository, "checkout", "-b", "other")
    (repository / "ordinary.txt").write_text("other\n")
    git(repository, "commit", "-am", "other change")
    git(repository, "checkout", "main")
    (repository / "ordinary.txt").write_text("main\n")
    git(repository, "commit", "-am", "main change")
    git(repository, "merge", "other", check=False)
    (entry,) = parse_status(git(repository, *status_args()))
    assert entry.kind == "conflict"
    assert entry.xy == "UU"
    displayed = _status_entries(repository)["ordinary.txt"]
    assert displayed.label == "!UU ordinary.txt"
    assert displayed.target.status == "UU"
    assert "Unmerged conflict" in displayed.detail
    (repository / "ordinary.txt").write_text("resolved\n")
    git(repository, "add", "ordinary.txt")
    git(repository, "commit", "-m", "merge resolved")
    sha = git(repository, "rev-parse", "HEAD").decode().strip()
    patch = git(repository, *commit_preview_args(sha)).decode()
    assert "-main" in patch and "+resolved" in patch
    assert "diff --cc" not in patch and "@@@" not in patch
    files = parse_changed_files(git(repository, *commit_files_args(sha)))
    assert [entry.path for entry in files] == ["ordinary.txt"]


def test_no_head_status(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "new.txt").write_text("new\n")
    git(tmp_path, "add", "new.txt")
    (entry,) = parse_status(git(tmp_path, *status_args()))
    assert entry.xy == "A."
    assert b"+new" in git(tmp_path, *status_diff_args("new.txt", True))


def test_truncated_nul_records_never_invent_last_path():
    assert parse_status(b"? complete.txt\0? partial")[-1].path == "complete.txt"
    assert parse_changed_files(b"M\0complete\0R100\0old\0partial") == (
        parse_changed_files(b"M\0complete\0")[0],
    )
    assert not parse_log(b"a" * 40 + b"\0author\0invalid\0subject\0")


@pytest.mark.parametrize(
    "prefix,status,kind", [(b"?", "??", "untracked"), (b"!", "!!", "ignored")]
)
def test_untracked_and_ignored_statuses_remain_distinct(prefix, status, kind):
    (record,) = parse_status(prefix + b" literal [x]*\t\n.txt\0")

    assert record.xy == status
    assert record.kind == kind
    assert record.path == "literal [x]*\t\n.txt"


def test_object_ids_are_fixed_values():
    with pytest.raises(ValueError):
        commit_preview_args("--output=/tmp/x")
    with pytest.raises(ValueError):
        commit_files_args("HEAD")


def test_service_runs_status_asynchronously(qtbot, repository):
    results = []
    service = GitService()
    service.submit("status", str(repository), status_args(), results.append)
    assert service.active_count == 1
    qtbot.waitUntil(lambda: bool(results))
    assert not results[0].error
    assert not parse_status(results[0].stdout)
    assert not service.busy
    service.close()


def _fake_program(tmp_path, body):
    script = tmp_path / "fake-git"
    script.write_text(f"#!{sys.executable}\n" + body)
    script.chmod(0o755)
    return str(script)


def test_service_cancel_replace_and_release_lane(qtbot, tmp_path):
    program = _fake_program(tmp_path, "import time\ntime.sleep(0.3)\nprint('done')\n")
    service = GitService(program=program)
    results = []
    service.submit(1, str(tmp_path), [], results.append)
    service.submit(2, str(tmp_path), [], results.append)
    service.submit(3, str(tmp_path), [], results.append)
    assert service.active_count == 1
    assert service.pending_count == 1
    qtbot.waitUntil(lambda: bool(results), timeout=3000)
    assert [result.key for result in results] == [3]
    assert not service.busy
    service.submit(4, str(tmp_path), [], results.append)
    service.cancel()
    qtbot.waitUntil(lambda: not service.busy)
    assert [result.key for result in results] == [3]
    service.close()


def test_service_timeout_and_hard_kill(qtbot, tmp_path):
    program = _fake_program(
        tmp_path,
        "import signal,time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "time.sleep(20)\n",
    )
    service = GitService(program=program, timeout_ms=200)
    results = []
    service.submit("timeout", str(tmp_path), [], results.append)
    qtbot.waitUntil(lambda: bool(results), timeout=2000)
    assert "timed out" in results[0].error
    assert not service.busy
    service.close()


def test_service_output_limit_and_failed_start_release_slot(qtbot, tmp_path):
    program = _fake_program(tmp_path, "print('x' * 100000)\n")
    service = GitService(program=program, output_limit=64)
    results = []
    service.submit("large", str(tmp_path), [], results.append)
    qtbot.waitUntil(lambda: bool(results))
    assert results[0].truncated
    assert len(results[0].stdout) == 64
    assert not service.busy
    service.close()
    service = GitService(program=str(tmp_path / "missing-git"))
    service.submit("missing", str(tmp_path), [], results.append)
    qtbot.waitUntil(lambda: len(results) == 2)
    assert results[-1].error
    assert not service.busy
    service.close()


def test_query_stops_when_error_output_exceeds_its_budget(qtbot, tmp_path):
    program = _fake_program(
        tmp_path,
        "import sys,time\nprint('x' * 100000, file=sys.stderr)\ntime.sleep(20)\n",
    )
    service = GitService(program=program)
    results = []
    service.submit("errors", str(tmp_path), [], results.append)
    qtbot.waitUntil(lambda: bool(results), timeout=3000)
    assert results[0].error == "Git error output limit reached"
    assert len(results[0].stderr.encode()) <= MAX_GIT_ERROR
    assert not service.busy
    service.close()


def test_service_resolves_worktree_root_from_subdirectory(qtbot, repository, tmp_path):
    worktree = tmp_path / "worktree"
    git(repository, "worktree", "add", "--detach", str(worktree), "HEAD")
    nested = worktree / "sub"
    nested.mkdir()
    service = GitService()
    results = []
    service.submit(
        "root", str(nested), ["rev-parse", "--show-toplevel"], results.append
    )
    qtbot.waitUntil(lambda: bool(results))
    assert Path(os.fsdecode(results[0].stdout).strip()) == worktree
    service.close()


def test_mode_only_patch(repository):
    git(repository, "config", "core.filemode", "true")
    path = repository / "ordinary.txt"
    path.chmod(0o755)
    patch = git(repository, *status_diff_args("ordinary.txt")).decode()
    assert "old mode 100644" in patch
    assert "new mode 100755" in patch
    assert "@@" not in patch


def test_stash_history_preview_is_read_only_and_pins_sha(repository):
    tracked = repository / "ordinary.txt"
    tracked.write_text("saved tracked change\n")
    untracked = repository / "untracked [literal]*\n.txt"
    untracked.write_text("saved untracked change\n")
    git(repository, "stash", "push", "--include-untracked", "-m", "saved changes")
    first = parse_log(git(repository, *stash_args()))
    assert len(first) == 1
    assert "saved changes" in first[0].subject
    first_sha = first[0].sha
    tracked.write_text("second saved change\n")
    git(repository, "stash", "push", "-m", "newest changes")
    before = (
        git(repository, "rev-parse", "HEAD"),
        git(repository, *status_args()),
        git(repository, *stash_args()),
    )
    patch = git(repository, *stash_preview_args(first_sha))
    assert b"+saved tracked change" in patch
    assert b"+saved untracked change" in patch
    assert b"+second saved change" not in patch
    assert [item.sha for item in parse_log(git(repository, *stash_args(1, 1)))] == [
        first_sha
    ]
    snapshot = git_snapshot(
        "git_stash",
        str(repository),
        1,
        str(repository),
        "",
        GitResult("stashes", before[2], ""),
    )
    assert all(entry.preview_kind == "stash" for entry in snapshot.entries)
    assert snapshot.entries[-1].target.commit == first_sha
    assert snapshot.entries[-1].id == first_sha
    assert before == (
        git(repository, "rev-parse", "HEAD"),
        git(repository, *status_args()),
        git(repository, *stash_args()),
    )


def test_file_history_follows_literal_path_and_excludes_other_files(repository):
    git(repository, "mv", "ordinary.txt", "renamed [x]*\n.txt")
    git(repository, "commit", "-m", "rename tracked file")
    (repository / "deleted.txt").write_text("unrelated modification\n")
    git(repository, "commit", "-am", "unrelated change")
    path = "renamed [x]*\n.txt"
    (repository / path).write_text("current file modification\n")
    git(repository, "commit", "-am", "current file change")
    raw = git(repository, *log_args(path=path))
    records = parse_log(raw)
    assert [item.subject for item in records] == [
        "current file change",
        "rename tracked file",
        "root commit",
    ]
    assert [
        item.subject for item in parse_log(git(repository, *log_args(1, 1, path)))
    ] == ["rename tracked file"]
    snapshot = git_snapshot(
        "git_file_log",
        str(repository),
        2,
        str(repository),
        "",
        GitResult("file history", raw, ""),
    )
    assert len(snapshot.entries) == 3
    assert all(
        entry.source_id == "git_file_log" and entry.preview_kind == "commit"
        for entry in snapshot.entries
    )
    # SHA-based previews include the historical name, instead of reusing the
    # current name as a pathspec in commits before the rename.
    assert b"a/ordinary.txt" in git(repository, *commit_preview_args(records[-1].sha))


def test_empty_stash_history_and_no_history_for_untracked_file(repository):
    stash = git_snapshot(
        "git_stash",
        str(repository),
        1,
        str(repository),
        "",
        GitResult("empty", git(repository, *stash_args()), ""),
    )
    assert not stash.entries
    assert stash.completeness == "No stashes."
    assert not parse_log(git(repository, *log_args(path="not-tracked.py")))
    with pytest.raises(ValueError):
        stash_preview_args("stash@{0}")
