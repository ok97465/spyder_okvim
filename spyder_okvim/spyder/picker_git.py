"""Bounded read-only Git processes and NUL-safe value parsers.

Paths stay separate from patch text; quoted headers never become navigation
locations. All process operations run through Qt without GUI-thread waits.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import os
import re

from qtpy.QtCore import QObject, QProcess, QProcessEnvironment, QTimer
from qtpy.QtWidgets import QApplication

from spyder_okvim.utils.picker import (
    CandidateSnapshot,
    PickerEntry,
    PickerTarget,
)

MAX_GIT_OUTPUT = 2 * 1024 * 1024
MAX_GIT_ERROR = 64 * 1024
GIT_TIMEOUT_MS = 10_000
LOG_PAGE_SIZE = 200


@dataclass(frozen=True)
class GitStatus:
    path: str
    old_path: str = ""
    xy: str = "??"
    kind: str = "untracked"
    submodule: str = "N..."


@dataclass(frozen=True)
class GitCommit:
    sha: str
    author: str
    timestamp: int
    subject: str


@dataclass(frozen=True)
class GitFile:
    status: str
    path: str
    old_path: str = ""


@dataclass(frozen=True)
class GitBranch:
    ref: str
    name: str
    sha: str
    current: bool = False
    upstream: str = ""


@dataclass(frozen=True)
class GitResult:
    key: object
    stdout: bytes
    stderr: str
    error: str = ""
    truncated: bool = False
    returncode: int = 0


def _nul_records(data: bytes) -> list[bytes]:
    """Ignore a partial last record when the process hit its output limit."""
    return data.split(b"\0")[:-1]


def parse_status(data: bytes) -> tuple[GitStatus, ...]:
    """Parse porcelain v2 -z while preserving whitespace in file names."""
    records = iter(_nul_records(data))
    result = []
    for record in records:
        kind = record[:1]
        if kind in (b"?", b"!") and record[1:2] == b" ":
            result.append(
                GitStatus(
                    os.fsdecode(record[2:]),
                    kind=("untracked" if kind == b"?" else "ignored"),
                )
            )
            continue
        if kind not in (b"1", b"2", b"u"):
            continue
        count = {b"1": 8, b"2": 9, b"u": 10}[kind]
        fields = record.split(b" ", count)
        if len(fields) != count + 1:
            continue
        old_path = ""
        if kind == b"2":
            original = next(records, None)
            if original is None:
                break
            old_path = os.fsdecode(original)
        result.append(
            GitStatus(
                path=os.fsdecode(fields[-1]),
                old_path=old_path,
                xy=fields[1].decode("ascii", "replace"),
                kind={b"1": "tracked", b"2": "renamed", b"u": "conflict"}[kind],
                submodule=fields[2].decode("ascii", "replace"),
            )
        )
    return tuple(result)


def parse_log(data: bytes) -> tuple[GitCommit, ...]:
    """Read the four NUL-delimited fields produced by ``log_args``."""
    fields = _nul_records(data)
    result = []
    for offset in range(0, len(fields) - 3, 4):
        sha, author, timestamp, subject = fields[offset : offset + 4]
        if not re.fullmatch(rb"[a-fA-F0-9]{40,64}", sha):
            continue
        try:
            timestamp_value = int(timestamp)
        except ValueError:
            continue
        result.append(
            GitCommit(
                sha.decode("ascii"),
                author.decode("utf-8", "replace"),
                timestamp_value,
                subject.decode("utf-8", "replace"),
            )
        )
    return tuple(result)


def parse_changed_files(data: bytes) -> tuple[GitFile, ...]:
    """Read --name-status -z, including two paths for copies/renames."""
    records = iter(_nul_records(data))
    result = []
    for record in records:
        if not re.fullmatch(rb"[ACDMRTUXB][0-9]*", record):
            continue
        first_path = next(records, None)
        if first_path is None:
            break
        old_path = ""
        path = first_path
        if record[:1] in (b"R", b"C"):
            path = next(records, None)
            if path is None:
                break
            old_path = os.fsdecode(first_path)
        result.append(GitFile(record.decode("ascii"), os.fsdecode(path), old_path))
    return tuple(result)


def parse_branches(data: bytes) -> tuple[GitBranch, ...]:
    """Read complete NUL-delimited ref records, omitting symbolic aliases.

    Git ref names cannot contain line breaks, so for-each-ref's final newline
    separates records while NULs keep each optional field unambiguous.
    """
    branches = []
    for record in data.splitlines():
        fields = record.split(b"\0")
        if len(fields) != 7 or fields[-1] != b"":
            continue
        ref, name, sha, current, upstream, symbolic = fields[:-1]
        if symbolic or not ref.startswith((b"refs/heads/", b"refs/remotes/")):
            continue
        if not re.fullmatch(rb"[a-fA-F0-9]{40,64}", sha):
            continue
        branches.append(
            GitBranch(
                os.fsdecode(ref),
                os.fsdecode(name),
                sha.decode("ascii"),
                current == b"*",
                os.fsdecode(upstream),
            )
        )
    return tuple(branches)


def status_args() -> list[str]:
    return ["status", "--porcelain=v2", "-z", "--untracked-files=all"]


def branches_args() -> list[str]:
    """List local and remote refs, with HEAD/upstream captured as values."""
    return [
        "for-each-ref",
        "--sort=refname",
        "--sort=-HEAD",
        "--format=%(refname)%00%(refname:short)%00%(objectname)%00%(HEAD)%00%(upstream)%00%(symref)%00",
        "refs/heads/",
        "refs/remotes/",
    ]


def branch_preview_args(target: PickerTarget) -> list[str]:
    """Preview a bounded log for the selected snapshot's immutable object ID."""
    return [
        "log",
        "--max-count=100",
        "--graph",
        "--decorate=short",
        "--date=short",
        "--format=%h %ad %s",
        _commit_id(target.commit),
        "--",
    ]


def log_args(
    limit: int = LOG_PAGE_SIZE, skip: int = 0, path: str | None = None
) -> list[str]:
    """List repository history, or follow one literal path through renames."""
    args = [
        "log",
        f"--max-count={max(1, min(limit, 100000))}",
        f"--skip={max(0, skip)}",
        "--format=%H%x00%an%x00%at%x00%s",
        "-z",
    ]
    if path is not None:
        args.extend(["--follow", "--", path])
    return args


def stash_args(limit: int = LOG_PAGE_SIZE, skip: int = 0) -> list[str]:
    """List stash reflog entries as fixed object IDs, never mutable ordinals."""
    return ["stash", "list", *log_args(limit, skip)[1:]]


def stash_preview_args(sha: str) -> list[str]:
    """Inspect tracked and saved untracked changes without applying a stash."""
    return [
        "stash",
        "show",
        "--patch",
        "--include-untracked",
        "--no-ext-diff",
        "--no-textconv",
        "--color=never",
        _commit_id(sha),
        "--",
    ]


def _commit_id(value: str) -> str:
    if not re.fullmatch(r"[a-fA-F0-9]{4,64}", value):
        raise ValueError("Expected a fixed Git object ID")
    return value


def commit_files_args(sha: str) -> list[str]:
    return [
        "diff-tree",
        "--root",
        "--no-commit-id",
        "--name-status",
        "-r",
        "-z",
        "--find-renames",
        "--diff-merges=first-parent",
        _commit_id(sha),
        "--",
    ]


def commit_preview_args(
    sha: str, path: str | None = None, old_path: str = ""
) -> list[str]:
    """Root commits compare to empty; merges compare to their first parent."""
    args = [
        "show",
        "--format=commit %H%nParents (first-parent comparison; root uses empty tree): %P%nAuthor: %an <%ae>%nDate: %aI%n%n%B",
        "--root",
        "--diff-merges=first-parent",
        "--no-ext-diff",
        "--no-textconv",
        "--color=never",
        "--find-renames",
        _commit_id(sha),
        "--",
    ]
    if path is not None:
        args.append(path)
        if old_path and old_path != path:
            args.append(old_path)
    return args


def status_diff_args(path: str, staged: bool = False, old_path: str = "") -> list[str]:
    args = ["diff", "--no-ext-diff", "--no-textconv", "--color=never", "--find-renames"]
    if staged:
        args.append("--cached")
    return [*args, "--", path, *([old_path] if old_path and old_path != path else [])]


def git_snapshot(source, scope, version, root, commit, result):
    """Adapt bounded Git values to the same candidate contract as other sources."""
    entries = []
    if source == "git_branches":
        records = parse_branches(result.stdout)
    elif source == "git_status":
        records = parse_status(result.stdout)
    elif source == "git_files":
        records = parse_changed_files(result.stdout)
    else:
        records = parse_log(result.stdout)
    for ordinal, record in enumerate(records):
        if source == "git_branches":
            target = PickerTarget(
                root, commit=record.sha, ref=record.ref, upstream=record.upstream
            )
            label = f"{'* ' if record.current else ''}{record.name}"
            detail = record.sha[:10]
            if record.upstream:
                upstream = record.upstream.removeprefix("refs/remotes/").removeprefix(
                    "refs/heads/"
                )
                detail += f" · upstream {upstream}"
            identifier, kind = record.ref, "branch"
        elif source in ("git_log", "git_file_log", "git_stash"):
            target = PickerTarget(root, commit=record.sha)
            label = f"{record.sha[:10]} {record.subject}"
            detail = f"{record.author} · {record.timestamp}"
            identifier = record.sha
            kind = "stash" if source == "git_stash" else "commit"
        else:
            target = PickerTarget(
                os.path.join(root, record.path),
                commit=commit if source == "git_files" else "",
                old_path=record.old_path,
                status=record.xy if source == "git_status" else record.status,
            )
            label = f"{target.status} {record.path}"
            detail = f"from {record.old_path}" if record.old_path else root
            identifier, kind = record.path, (
                "status" if source == "git_status" else "commit_file"
            )
            if source == "git_status":
                if record.kind == "untracked":
                    kind = "code"
                    detail += " · Untracked: file content preview"
                elif record.kind == "conflict":
                    detail += " · Unmerged conflict: combined patch"
                if record.submodule.startswith("S"):
                    detail += f" · Submodule {record.submodule}"
        entries.append(
            PickerEntry(
                id=identifier,
                source_id=source,
                label=label,
                detail=detail,
                search_text=f"{label} {detail}",
                ordinal=ordinal,
                target=target,
                preview_kind=kind,
            )
        )
    completeness = "Git output limited" if result.truncated else "complete"
    if source == "git_status" and not entries and not result.truncated:
        completeness = "Working tree is clean."
    elif source == "git_branches" and not entries and not result.truncated:
        completeness = "No branches in this repository."
    elif source in ("git_log", "git_file_log", "git_stash") and not result.truncated:
        noun = "stashes" if source == "git_stash" else "commits"
        completeness = (
            f"Loaded {len(entries)} newest {noun}; search covers this range."
            if entries
            else f"No {noun}."
        )
    return CandidateSnapshot(source, scope, version, tuple(entries), completeness)


@dataclass
class _Request:
    key: object
    cwd: str
    args: tuple[str, ...]
    callback: Callable[[GitResult], None] | None


class GitService(QObject):
    """Keep one running process and one replaceable request across sessions.

    Cancel drops client callbacks immediately. A process must finish and release
    its slot before another starts, including after termination or a timeout.
    """

    def __init__(
        self,
        *,
        timeout_ms: int = GIT_TIMEOUT_MS,
        output_limit: int = MAX_GIT_OUTPUT,
        program: str = "git",
    ):
        application = QApplication.instance()
        if application is None:
            raise RuntimeError("GitService requires a QApplication")
        super().__init__(application)
        self.timeout_ms = timeout_ms
        self.output_limit = output_limit
        self.program = program
        self._active: _Request | None = None
        self._pending: _Request | None = None
        self._process: QProcess | None = None
        self._closed = False
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._error = ""
        self._truncated = False
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._timed_out)
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._kill_active)
        application.aboutToQuit.connect(self._shutdown)

    @property
    def busy(self) -> bool:
        return self._active is not None or self._pending is not None

    @property
    def active_count(self) -> int:
        return int(self._active is not None)

    @property
    def pending_count(self) -> int:
        return int(self._pending is not None)

    def submit(
        self,
        key: object,
        cwd: str,
        args: Sequence[str],
        callback: Callable[[GitResult], None],
    ) -> None:
        if self._closed:
            return
        self._pending = _Request(key, cwd, tuple(args), callback)
        if self._active is not None:
            self._active.callback = None
            self._stop_active()
        else:
            self._start_pending()

    def _start_pending(self) -> None:
        if self._closed or self._active is not None or self._pending is None:
            return
        self._active, self._pending = self._pending, None
        self._stdout.clear()
        self._stderr.clear()
        self._error = ""
        self._truncated = False
        process = self._process = QProcess(self)
        process.setWorkingDirectory(self._active.cwd)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("GIT_TERMINAL_PROMPT", "0")
        environment.insert("LC_ALL", "C")
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        self._timeout.start(self.timeout_ms)
        process.start(
            self.program,
            [
                "--no-pager",
                "--no-optional-locks",
                "--literal-pathspecs",
                "-c",
                "color.ui=false",
                *self._active.args,
            ],
        )

    def _read_stdout(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput())
        remaining = max(0, self.output_limit - len(self._stdout))
        self._stdout.extend(data[:remaining])
        if len(data) > remaining:
            self._truncated = True
            self._stop_active()

    def _read_stderr(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardError())
        remaining = max(0, MAX_GIT_ERROR - len(self._stderr))
        self._stderr.extend(data[:remaining])
        if len(data) > remaining:
            self._error = "Git error output limit reached"
            self._stop_active()

    def _timed_out(self) -> None:
        self._error = "Git query timed out"
        self._stop_active()

    def _stop_active(self) -> None:
        if self._process is not None:
            self._process.terminate()
            if not self._kill_timer.isActive():
                self._kill_timer.start(100)

    def _kill_active(self) -> None:
        if self._process is not None:
            self._process.kill()

    def _process_error(self, error) -> None:
        if self._process is None:
            return
        if error == QProcess.FailedToStart:
            self._error = self._process.errorString()
            self._finished(-1)

    def _finished(self, returncode: int, *_args) -> None:
        if self._active is None:
            return
        self._read_stdout()
        self._read_stderr()
        self._timeout.stop()
        self._kill_timer.stop()
        request, self._active = self._active, None
        process, self._process = self._process, None
        process.deleteLater()
        stderr = self._stderr.decode("utf-8", "replace").strip()
        error = self._error
        if returncode and not error and not self._truncated:
            error = stderr or f"Git query failed ({returncode})"
        result = GitResult(
            request.key, bytes(self._stdout), stderr, error, self._truncated, returncode
        )
        try:
            if not self._closed and request.callback is not None:
                request.callback(result)
        finally:
            if self._closed:
                self.deleteLater()
            else:
                self._start_pending()

    def cancel(self) -> None:
        self._pending = None
        if self._active is not None:
            self._active.callback = None
            self._stop_active()

    def _shutdown(self) -> None:
        # The event loop is leaving; the escalation timer may never fire.
        self.close()
        self._kill_active()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.cancel()
        if self._active is None:
            self.deleteLater()
