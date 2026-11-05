"""Explicit Git mutations, isolated from replaceable picker read requests.

A submitted write owns its process until completion. Closing or replacing a
picker can release its callback, but never turns a search cancellation into an
interrupted Git write.
"""

from __future__ import annotations

# Standard Libraries
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

# Project Libraries
from spyder_okvim.spyder.picker_git import MAX_GIT_OUTPUT, GitResult, _GitProcess
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


class GitMutationService(_GitProcess):
    """Run one write, with no replaceable queue and no popup cancellation API."""

    _timeout_message = "Git action timed out; inspect repository state before retrying"

    def __init__(
        self,
        *,
        timeout_ms: int = GIT_ACTION_TIMEOUT_MS,
        output_limit: int = MAX_GIT_OUTPUT,
        program: str = "git",
    ):
        super().__init__(
            timeout_ms=timeout_ms, output_limit=output_limit, program=program
        )
        self._active: _Mutation | None = None
        self._checking: tuple[str, str] | None = None

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
        self._start_process(
            request.cwd,
            args,
            output_limit=max(self.output_limit, 8192) if self._checking else None,
            environment_overrides=(
                ("GIT_EDITOR", "true"),
                ("GIT_SEQUENCE_EDITOR", "true"),
            ),
        )

    def _output_limit_reached(self, stream):
        # An accepted write must finish, even when its output no longer fits.
        self._truncated = True

    def _finished(self, returncode, *_args):
        if self._active is None or self._process is None:
            return
        self._release_process()
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
