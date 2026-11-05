"""Explicit Git mutations, isolated from replaceable picker read requests.

A submitted write owns its process until completion. Closing or replacing a
picker can release its callback, but never turns a search cancellation into an
interrupted Git write.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
import re

from qtpy.QtCore import QObject, QProcess, QProcessEnvironment, QTimer
from qtpy.QtWidgets import QApplication

from spyder_okvim.spyder.picker_git import GitResult, MAX_GIT_ERROR, MAX_GIT_OUTPUT
from spyder_okvim.utils.picker import PickerTarget


GIT_ACTION_TIMEOUT_MS = 120_000


def _sha(value: str) -> str:
    if not re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", value):
        raise ValueError("Select a fixed Git object ID")
    return value


def _branch_name(value: str) -> str:
    """Reject invalid names before they can be interpreted as Git options."""
    invalid = "~^:?*[\\"
    parts = value.split("/")
    if (
        not value
        or value.startswith("-")
        or value == "@"
        or value.endswith(".")
        or ".." in value
        or "@{" in value
        or any(
            ord(character) <= 32 or ord(character) == 127 or character in invalid
            for character in value
        )
        or any(
            not part or part.startswith(".") or part.endswith(".lock") for part in parts
        )
    ):
        raise ValueError("Enter a valid Git branch name")
    return value


def _branch_ref(target: PickerTarget) -> tuple[str, bool]:
    reference = target.ref
    if reference.startswith("refs/heads/"):
        return _branch_name(reference[len("refs/heads/") :]), False
    if reference.startswith("refs/remotes/"):
        return _branch_name(reference[len("refs/remotes/") :]), True
    raise ValueError("Select a local or remote-tracking branch")


def action_args(action: str, target: PickerTarget, branch_name: str = "") -> list[str]:
    """Build one argument vector; confirmation and live validation belong to UI."""
    if action in ("stage", "unstage"):
        paths = list(
            dict.fromkeys(path for path in (target.path, target.old_path) if path)
        )
        if not paths:
            raise ValueError("Select a file")
        # Path-limited reset also unstages additions before the first commit.
        return (
            ["add", "--all", "--", *paths]
            if action == "stage"
            else ["reset", "--", *paths]
        )
    if action == "checkout_commit":
        return ["switch", "--detach", _sha(target.commit)]
    if action in ("reset_mixed", "reset_soft", "reset_hard"):
        return ["reset", "--" + action.removeprefix("reset_"), _sha(target.commit)]
    if action == "stash_apply":
        return ["stash", "apply", "--index", _sha(target.commit)]
    if action == "create_branch":
        # Telescope creates from the current HEAD, then switches to the new ref.
        return ["switch", "--create", _branch_name(branch_name)]
    name, remote = _branch_ref(target)
    if action == "checkout_branch":
        return (
            ["switch", "--detach", _sha(target.commit)]
            if remote
            else ["switch", "--", name]
        )
    if action == "track_branch":
        if not remote:
            raise ValueError("Select a remote-tracking branch to track")
        return ["switch", "--track", target.ref]
    if action == "delete_branch":
        return ["branch", "--delete", *(["--remotes"] if remote else []), "--", name]
    if action == "rebase":
        return ["rebase", target.ref]
    if action == "merge":
        return ["merge", "--no-edit", target.ref]
    raise ValueError(f"Unknown Git action: {action}")


def status_action(target: PickerTarget) -> str:
    """An indexed change is unstaged first, including files with both changes."""
    if target.status in ("DD", "AU", "UD", "UA", "DU", "AA", "UU"):
        return "stage"
    return (
        "unstage"
        if target.status and target.status[0] not in (".", "?", "!")
        else "stage"
    )


@dataclass
class _Mutation:
    key: object
    cwd: str
    args: tuple[str, ...]
    callback: Callable[[GitResult], None] | None
    checks: list[tuple[str, str]] = field(default_factory=list)


class GitMutationService(QObject):
    """Run one write, with no replaceable queue and no popup cancellation API."""

    def __init__(
        self,
        *,
        timeout_ms: int = GIT_ACTION_TIMEOUT_MS,
        output_limit: int = MAX_GIT_OUTPUT,
        program: str = "git",
    ):
        application = QApplication.instance()
        if application is None:
            raise RuntimeError("GitMutationService requires a QApplication")
        super().__init__(application)
        self.timeout_ms = timeout_ms
        self.output_limit = max(1, output_limit)
        self.program = program
        self._active: _Mutation | None = None
        self._process: QProcess | None = None
        self._checking: tuple[str, str] | None = None
        self._closed = False
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._truncated = False
        self._error = ""
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._timed_out)
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._kill_active)
        application.aboutToQuit.connect(self._shutdown)

    @property
    def busy(self) -> bool:
        return self._active is not None

    def submit(
        self,
        key: object,
        cwd: str,
        args: Sequence[str],
        callback: Callable[[GitResult], None],
        *,
        expected_head: str | None = None,
        expected_ref: tuple[str, str] | None = None,
        expected_branch: str | None = None,
    ) -> bool:
        """Reserve the slot; optional captured refs are checked before writing.

        ``expected_head=''`` denotes an unborn HEAD. A mismatched precondition
        reports an error without starting the requested mutation.
        """
        if self._closed or self.busy:
            return False
        if not args or not all(isinstance(argument, str) for argument in args):
            raise ValueError("A Git action requires an argument vector")
        checks = []
        if expected_head is not None:
            checks.append(("HEAD", _sha(expected_head) if expected_head else ""))
        if expected_branch is not None:
            if expected_branch and not expected_branch.startswith("refs/heads/"):
                raise ValueError("Expected a full current branch ref")
            checks.append(("symbolic HEAD", expected_branch))
        if expected_ref is not None:
            reference, expected = expected_ref
            if not reference.startswith(("refs/heads/", "refs/remotes/")):
                raise ValueError("Expected a full local or remote-tracking ref")
            checks.append((reference, _sha(expected)))
        self._active = _Mutation(key, cwd, tuple(args), callback, checks)
        self._start_next()
        return True

    def _start_next(self):
        request = self._active
        if request is None:
            return
        self._checking = request.checks.pop(0) if request.checks else None
        if self._checking is None:
            args = list(request.args)
        elif self._checking[0] == "symbolic HEAD":
            args = ["symbolic-ref", "--quiet", "HEAD"]
        else:
            args = ["rev-parse", "--verify", self._checking[0]]
        self._stdout.clear()
        self._stderr.clear()
        self._truncated = False
        self._error = ""
        process = self._process = QProcess(self)
        process.setWorkingDirectory(request.cwd)
        environment = QProcessEnvironment.systemEnvironment()
        for key, value in (
            ("GIT_TERMINAL_PROMPT", "0"),
            ("GIT_EDITOR", "true"),
            ("GIT_SEQUENCE_EDITOR", "true"),
            ("LC_ALL", "C"),
        ):
            environment.insert(key, value)
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        self._timeout.start(self.timeout_ms)
        process.start(
            self.program,
            ["--no-pager", "--literal-pathspecs", "-c", "color.ui=false", *args],
        )

    def _read_stdout(self):
        if self._process is not None:
            data = bytes(self._process.readAllStandardOutput())
            limit = (
                max(self.output_limit, 8192) if self._checking else self.output_limit
            )
            remaining = max(0, limit - len(self._stdout))
            self._stdout.extend(data[:remaining])
            self._truncated |= len(data) > remaining

    def _read_stderr(self):
        if self._process is not None:
            data = bytes(self._process.readAllStandardError())
            remaining = max(0, MAX_GIT_ERROR - len(self._stderr))
            self._stderr.extend(data[:remaining])
            self._truncated |= len(data) > remaining

    def _timed_out(self):
        self._error = "Git action timed out; inspect repository state before retrying"
        if self._process is not None:
            self._process.terminate()
            self._kill_timer.start(100)

    def _kill_active(self):
        if self._process is not None:
            self._process.kill()

    def _process_error(self, error):
        if self._process is not None and error == QProcess.FailedToStart:
            self._error = self._process.errorString()
            self._finished(-1)

    def _finished(self, returncode, *_args):
        if self._active is None or self._process is None:
            return
        self._read_stdout()
        self._read_stderr()
        self._timeout.stop()
        self._kill_timer.stop()
        process, self._process = self._process, None
        process.deleteLater()
        if self._checking is not None and not self._error:
            reference, expected = self._checking
            actual = (
                self._stdout.decode("utf-8", errors="surrogateescape").strip()
                if returncode == 0
                else ""
            )
            if actual == expected and (
                returncode == 0
                or (reference == "HEAD" and not expected)
                or (reference == "symbolic HEAD" and not expected and returncode == 1)
            ):
                self._start_next()
                return
            self._error = f"Git {reference} changed; refresh before running this action"
        request, self._active = self._active, None
        stderr = self._stderr.decode("utf-8", errors="replace").strip()
        stdout = self._stdout.decode("utf-8", errors="replace").strip()
        details = "\n".join(part for part in (stderr, stdout) if part)
        error = self._error or (
            (details or f"Git action failed ({returncode})") if returncode else ""
        )
        result = GitResult(
            request.key, bytes(self._stdout), stderr, error, self._truncated, returncode
        )
        try:
            if not self._closed and request.callback is not None:
                request.callback(result)
        finally:
            if self._closed:
                self.deleteLater()

    def close(self):
        """Stop accepting writes; an already accepted operation still finishes."""
        if self._closed:
            return
        self._closed = True
        if self._active is not None:
            self._active.callback = None
        else:
            self.deleteLater()

    def _shutdown(self):
        self.close()
        self._kill_active()
