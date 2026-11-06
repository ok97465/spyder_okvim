"""Git action intent, repository preconditions and picker-independent execution."""

from __future__ import annotations

# Standard Libraries
import logging
import os
import os.path as osp
import stat
import weakref
from dataclasses import dataclass, replace

# Third Party Libraries
from qtpy.QtWidgets import QDialog, QInputDialog, QMessageBox

# Project Libraries
from spyder_okvim.spyder.picker_commit_dialog import CommitMessageDialog
from spyder_okvim.spyder.picker_git import parse_status
from spyder_okvim.spyder.picker_git_actions import (
    GitMutationService,
    action_args,
    can_revert_status,
    read_merge_head,
    status_action,
    worktree_stamp as _worktree_stamp,
)
from spyder_okvim.utils.picker import PickerEntry, PickerTarget
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted

logger = logging.getLogger(__name__)
_DISK_ACTIONS = frozenset(
    (
        "checkout_commit",
        "checkout_branch",
        "track_branch",
        "create_branch",
        "reset_hard",
        "rebase",
        "merge",
        "stash_apply",
        "revert_file",
    )
)
_CONFIRM_ACTIONS = frozenset(
    (
        "reset_soft",
        "reset_mixed",
        "reset_hard",
        "delete_branch",
        "rebase",
        "merge",
    )
)


@dataclass(frozen=True)
class GitActionRequest:
    session: int
    source: str
    scope: str
    query_generation: int
    selection_generation: int
    root: str
    action: str
    entry: PickerEntry | None


@dataclass(frozen=True)
class _BufferSnapshot:
    stack_ref: weakref.ReferenceType
    editor_ref: weakref.ReferenceType
    path: str
    revision: int
    disk_stamp: tuple[int, int, int] | None


def _in_repository(path, root):
    if not path or not root:
        return False
    root = osp.normcase(osp.realpath(root))
    # Keep tracked symlink paths inside the scope, and recognize open files
    # reached through a directory alias such as macOS /var -> /private/var.
    for candidate in (osp.abspath(path), osp.realpath(path)):
        try:
            if osp.commonpath((osp.normcase(candidate), root)) == root:
                return True
        except ValueError:
            continue
    return False


def _disk_stamp(path):
    try:
        stat = os.stat(path)
        return stat.st_ino, stat.st_size, stat.st_mtime_ns
    except OSError:
        return None


class PickerGitActions:
    """Keep accepted mutations alive when the popup or its query is replaced.

    Preflight and confirmation still belong to a particular current selection.
    After submit, only the process service owns execution; UI cancellation drops
    intent but never kills an accepted Git write.
    """

    def __init__(self, picker):
        self.picker = picker
        self.service = GitMutationService()
        self.pending = None
        self.running = None
        self.commit_drafts = {}
        self.amend_drafts = {}

    @property
    def busy(self):
        return self.service.busy or self.pending is not None or self.running is not None

    def sync(self):
        picker = self.picker
        if picker.phase == "active" and not widget_is_deleted(picker.dialog):
            picker.dialog.set_actions_busy(self.busy)

    def invalidate_pending(self):
        self.pending = None
        self.sync()

    def _valid(self, request):
        picker = self.picker
        if (
            self.pending is not request
            or picker.phase != "active"
            or picker.session != request.session
            or picker.source != request.source
            or picker.scope != request.scope
            or not picker._context_valid()
            or picker.query_generation != request.query_generation
            or picker.selection_generation != request.selection_generation
            or picker.result_token != picker._search_token()
        ):
            return False
        if request.action == "commit":
            return True
        entry = picker.dialog.selected_entry()
        if request.entry is None:
            return entry is None and request.action == "create_branch"
        return (
            entry is not None
            and entry.id == request.entry.id
            and entry.target == request.entry.target
        )

    def _message(self, text):
        if not self.picker.widget._closed and not widget_is_deleted(self.picker.widget):
            self.picker.host.status.set_message(text[:2000])

    def _read_context(self, request, args, callback):
        owner = weakref.ref(self)

        def completed(result):
            actions = owner()
            if actions is None:
                return
            if not actions._valid(request):
                if actions.pending is request:
                    actions.pending = None
                actions.sync()
                return
            callback(result)

        if not self.service.submit(request, request.root, args, completed):
            self.pending = None
            self.sync()

    def _read_index(self, request, callback):
        """Read a complete index identity before reviewing or restoring it."""

        def completed(result):
            if result.error or result.returncode or result.truncated:
                self._finish_preflight(
                    request, result.error or result.stderr or "Git index output limited"
                )
                return
            callback(result.stdout.decode("ascii", errors="replace").strip())

        self._read_context(request, ["write-tree"], completed)

    def _read_merge_state(self, request, callback):
        """Resolve MERGE_HEAD through Git so linked worktrees use their own state."""

        def completed(result):
            if result.error or result.returncode or result.truncated:
                self._finish_preflight(
                    request, result.error or result.stderr or "Git path output limited"
                )
                return
            path = osp.join(request.root, os.fsdecode(result.stdout.rstrip(b"\r\n")))
            try:
                contents = read_merge_head(path)
            except OSError as error:
                self._finish_preflight(request, str(error))
                return
            callback((path, contents))

        self._read_context(
            request, ["rev-parse", "--git-path", "MERGE_HEAD"], completed
        )

    @staticmethod
    def _operation(source, action, entry):
        if source == "git_status":
            if action == "commit":
                return "commit"
            if action == "stage_toggle":
                return status_action(entry.target)
            if action == "revert":
                return "revert_file"
        if source in ("git_log", "git_file_log"):
            if action == "edit_commit_message":
                return action
            if action == "checkout":
                return "checkout_commit"
            if action in ("reset_mixed", "reset_soft", "reset_hard"):
                return action
        if source == "git_stash" and action == "stash_apply":
            return action
        if source == "git_branches":
            return {
                "checkout": "checkout_branch",
                "branch_track": "track_branch",
                "branch_create": "create_branch",
                "branch_delete": "delete_branch",
                "branch_rebase": "rebase",
                "branch_merge": "merge",
            }.get(action)
        return None

    def request(self, action, entry):
        picker = self.picker
        creating = picker.source == "git_branches" and action == "branch_create"
        committing = picker.source == "git_status" and action == "commit"
        if (
            self.busy
            or picker.phase != "active"
            or (entry is None and not (creating or committing))
        ):
            self.sync()
            return
        operation = self._operation(picker.source, action, entry)
        if operation is None or not picker.git_root:
            return
        if operation == "revert_file" and not can_revert_status(entry.target):
            self._message("Git: select an unstaged change to revert")
            return
        if operation == "track_branch" and not entry.target.ref.startswith(
            "refs/remotes/"
        ):
            self._message("Git: select a remote-tracking branch to track")
            return
        if picker.result_token != picker._search_token() or not picker._context_valid():
            return
        request = GitActionRequest(
            session=picker.session,
            source=picker.source,
            scope=picker.scope,
            query_generation=picker.query_generation,
            selection_generation=picker.selection_generation,
            root=picker.git_root,
            action=operation,
            entry=None if committing else entry,
        )
        self.pending = request
        self.sync()

        # Both reads use the mutation lane. Preview/query cancellation cannot
        # strand preflight; stale intent is discarded before any write begins.
        def branch_read(result):
            if result.error and result.returncode not in (1,):
                self._finish_preflight(request, result.error)
                return
            branch = result.stdout.decode("utf-8", errors="surrogateescape").strip()
            self._read_context(
                request,
                ["rev-parse", "--verify", "HEAD"],
                lambda head: self._prepared(request, branch, head),
            )

        self._read_context(request, ["symbolic-ref", "--quiet", "HEAD"], branch_read)

    def _finish_preflight(self, request, error=""):
        if self.pending is request:
            self.pending = None
        if error:
            self._message(f"Git: {error}")
        self.sync()

    def _prepared(self, request, branch, result):
        if result.returncode and result.returncode not in (1, 128):
            self._finish_preflight(request, result.error or result.stderr)
            return
        if result.error and not result.returncode:
            self._finish_preflight(request, result.error)
            return
        head = (
            result.stdout.decode("ascii", errors="replace").strip()
            if not result.returncode
            else ""
        )
        if request.action in ("commit", "edit_commit_message"):
            prepare = (
                self._prepare_commit
                if request.action == "commit"
                else self._prepare_message_edit
            )
            self._read_merge_state(
                request, lambda state: prepare(request, branch, head, state)
            )
            return
        if request.action == "revert_file":
            self._prepare_revert(request, branch, head)
            return
        changes_disk = request.action in _DISK_ACTIONS
        buffers = self._clean_buffers(request) if changes_disk else []
        if buffers is None:
            return
        name = ""
        if request.action == "create_branch":
            name = self.name_branch()
            if name is None:
                self._finish_preflight(request)
                return
        if request.action in _CONFIRM_ACTIONS and not self.confirm(request, branch):
            self._finish_preflight(request)
            return
        if not self._valid(request):
            self._finish_preflight(request)
            return
        # Only prompts run a nested event loop. Recapture those buffers to
        # protect intervening edits; other actions can reuse their snapshot.
        if changes_disk and (
            request.action == "create_branch" or request.action in _CONFIRM_ACTIONS
        ):
            buffers = self._clean_buffers(request)
            if buffers is None:
                return
        self._submit_action(request, branch, head, buffers=buffers, name=name)

    def _prepare_commit(self, request, branch, head, merge_state):
        """Inspect the entire staged index, independent of the filtered row."""

        def tree_read(index):
            self._read_context(
                request,
                [
                    "diff",
                    "--cached",
                    "--stat",
                    "--exit-code",
                    "--no-ext-diff",
                    "--no-textconv",
                ],
                lambda summary: summary_read(index, summary),
            )

        def summary_read(index, result):
            # --exit-code reports staged differences with status 1.
            merging = merge_state[1] is not None
            if result.returncode == 0 and not result.error and not merging:
                self._finish_preflight(request, "No staged changes to commit")
                return
            if result.returncode not in (0, 1) or (
                result.returncode == 0 and result.error
            ):
                self._finish_preflight(request, result.error or result.stderr)
                return
            summary = result.stdout.decode("utf-8", errors="replace").strip()
            if result.truncated:
                summary += "\n[Staged summary truncated]"
            if merging:
                parents = merge_state[1].decode("ascii", errors="replace").strip()
                summary = f"Merge parents:\n{parents}\n\n" + (
                    summary or "No staged changes relative to HEAD."
                )
            message = self.compose_commit(request, branch, summary)
            if message is None:
                self._finish_preflight(request)
                return
            self.commit_drafts[request.root] = message
            self._submit_action(
                request,
                branch,
                head,
                message=message,
                index=index,
                merge_state=merge_state,
            )

        self._read_index(request, tree_read)

    def _prepare_message_edit(self, request, branch, head, merge_state):
        """Reword only the selected HEAD, never include the staged index."""
        if not head or request.entry.target.commit != head:
            self._finish_preflight(
                request, "Select the latest commit (HEAD) to edit its message"
            )
            return

        def tree_read(index):
            self._read_context(
                request,
                [
                    "show",
                    "--no-patch",
                    "--no-show-signature",
                    "--encoding=UTF-8",
                    "--format=format:%B",
                    head,
                    "--",
                ],
                lambda result: message_read(index, result),
            )

        def message_read(index, result):
            if result.error or result.returncode or result.truncated:
                self._finish_preflight(
                    request,
                    result.error or result.stderr or "Commit message output limited",
                )
                return
            original = result.stdout.decode("utf-8", errors="replace")
            message = self.compose_amend(request, branch, original)
            if message is None:
                self._finish_preflight(request)
                return
            self.amend_drafts[(request.root, head)] = message
            self._submit_action(
                request,
                branch,
                head,
                message=message,
                index=index,
                merge_state=merge_state,
            )

        self._read_index(request, tree_read)

    def _prepare_revert(self, request, branch, head):
        """Restore unstaged content or delete an untracked file, keeping the index."""
        target = request.entry.target
        path = osp.relpath(target.path, request.root).replace(os.sep, "/")
        deleting = target.status == "??"

        def status_read(result):
            if result.error or result.returncode or result.truncated:
                self._finish_preflight(
                    request,
                    result.error or result.stderr or "Git status output limited",
                )
                return
            records = parse_status(result.stdout)
            current = next(
                (
                    item
                    for item in records
                    if item.path == path
                    and item.xy == target.status
                    and item.old_path == target.old_path
                ),
                None,
            )
            if current is None or not can_revert_status(target):
                self._finish_preflight(
                    request, "Git status changed; refresh before reverting"
                )
                return
            if current.submodule.startswith("S"):
                self._finish_preflight(
                    request, "Revert submodule files in their own repository"
                )
                return
            self._read_index(request, tree_read)

        def tree_read(index):
            if deleting:
                self._confirm_revert(request, branch, head, index)
                return
            self._read_context(
                request,
                ["ls-tree", "-z", index, "--", path],
                lambda baseline: baseline_read(index, baseline),
            )

        def baseline_read(index, result):
            if result.error or result.returncode or result.truncated:
                self._finish_preflight(
                    request,
                    result.error or result.stderr or "Staged file output limited",
                )
                return
            if not result.stdout.endswith(b"\0") or not result.stdout.startswith(
                (b"100644 blob ", b"100755 blob ", b"120000 blob ")
            ):
                self._finish_preflight(
                    request, "Selected file has no staged version to restore"
                )
                return
            self._confirm_revert(request, branch, head, index)

        self._read_context(
            request,
            [
                "status",
                "--porcelain=v2",
                "-z",
                "--untracked-files=all",
                "--",
                path,
                *([target.old_path] if target.old_path else []),
            ],
            status_read,
        )

    def _confirm_revert(self, request, branch, head, index):
        """Recheck the selected file and its editors across the modal confirmation."""
        target = request.entry.target
        deleting = target.status == "??"
        try:
            before = _worktree_stamp(target.path)
            if deleting and (
                before is None
                or not (stat.S_ISREG(before[1]) or stat.S_ISLNK(before[1]))
            ):
                self._finish_preflight(
                    request, "Select an untracked file, not a directory, to delete"
                )
                return
            if not deleting and before is not None and stat.S_ISDIR(before[1]):
                self._finish_preflight(
                    request, "Select a file, not a directory, to revert"
                )
                return
            if self._clean_buffers(request, path=target.path) is None:
                return
            if not self.confirm(request, branch):
                self._finish_preflight(request)
                return
            if not self._valid(request):
                self._finish_preflight(request)
                return
            buffers = self._clean_buffers(request, path=target.path)
            if buffers is None:
                return
            if _worktree_stamp(target.path) != before:
                self._finish_preflight(
                    request, "File changed; refresh before reverting"
                )
                return
        except OSError as error:
            self._finish_preflight(request, str(error))
            return
        self._submit_action(
            request,
            branch,
            head,
            buffers=buffers,
            index=index,
            file_stamp=before,
        )

    def _submit_action(
        self,
        request,
        branch,
        head,
        *,
        buffers=(),
        name="",
        message="",
        index=None,
        file_stamp=None,
        merge_state=None,
    ):
        if not self._valid(request):
            self._finish_preflight(request)
            return
        target = (
            replace(
                request.entry.target,
                path=osp.relpath(request.entry.target.path, request.root),
            )
            if request.entry is not None
            else PickerTarget("")
        )
        deleting = request.action == "revert_file" and target.status == "??"
        if not deleting:
            try:
                args = action_args(
                    request.action,
                    target,
                    branch_name=name,
                    message=message,
                    index_tree=index or "",
                )
            except ValueError as error:
                self._finish_preflight(request, str(error))
                return
        expected_ref = None
        if target.ref and request.action != "create_branch":
            expected_ref = (target.ref, target.commit)
        self.running = request
        self.pending = None
        owner = weakref.ref(self)

        def finished(result):
            actions = owner()
            if actions is not None:
                actions._finished(request, buffers, result)

        if deleting:
            accepted = self.service.submit_delete_untracked(
                request,
                request.root,
                target.path,
                file_stamp,
                finished,
                expected_head=head,
                expected_branch=branch,
                expected_index=index,
            )
        else:
            accepted = self.service.submit(
                request,
                request.root,
                args,
                finished,
                expected_head=head,
                expected_branch=branch,
                expected_ref=expected_ref,
                expected_index=index,
                expected_merge_state=merge_state,
                expected_worktree=(
                    (target.path, file_stamp)
                    if request.action == "revert_file"
                    else None
                ),
            )
        if not accepted:
            self.running = None
            self._message("Git: another operation is already running")
        self.sync()

    def compose_commit(self, request, branch, summary):
        return self._compose_message(
            branch, summary, drafts=self.commit_drafts, key=request.root
        )

    def compose_amend(self, request, branch, original):
        commit = request.entry.target.commit
        return self._compose_message(
            branch,
            f"HEAD: {commit}\n\nStaged changes, working files and unsaved buffers are kept.",
            drafts=self.amend_drafts,
            key=(request.root, commit),
            message=original,
            amend=True,
        )

    def _compose_message(
        self, branch, summary, *, drafts, key, message="", amend=False
    ):
        dialog = CommitMessageDialog(
            self.picker.dialog,
            branch=branch,
            summary=summary,
            message=drafts.get(key, message),
            amend=amend,
        )

        # Keep edits even if the parent picker disappears in the modal loop.
        def save_draft():
            drafts[key] = dialog.message()

        dialog.message_edit.textChanged.connect(save_draft)
        try:
            accepted = dialog.exec_() == QDialog.Accepted
            if widget_is_deleted(dialog):
                return None
            return dialog.message() if accepted else None
        finally:
            if not widget_is_deleted(dialog):
                dialog.deleteLater()

    def name_branch(self):
        name, accepted = QInputDialog.getText(
            self.picker.dialog,
            "Create Git branch",
            "New branch name (from current HEAD):",
        )
        return name if accepted and name else None

    def confirm(self, request, branch):
        target = request.entry.target
        current = branch.removeprefix("refs/heads/") or "detached HEAD"
        if request.action == "revert_file":
            path = osp.relpath(target.path, request.root)
            if target.status == "??":
                text = (
                    f"Delete untracked file {path}?"
                    "\nThe selected file will be removed from disk."
                    "\nStaged changes and other files will be kept."
                )
            else:
                text = (
                    f"Revert unstaged changes in {path}?"
                    "\nThe working file will be restored to its staged version."
                    "\nStaged changes will be kept. Unstaged changes will be discarded."
                )
        elif request.action.startswith("reset_"):
            mode = request.action.removeprefix("reset_")
            text = f"Reset {current} to {target.commit[:12]} ({mode})?"
            if mode == "hard":
                text += (
                    "\nIndex and tracked working-tree changes will be discarded."
                    "\nUntracked files obstructing the target may also be removed."
                )
        elif request.action == "delete_branch":
            text = f"Delete {target.ref}?"
            if target.ref.startswith("refs/remotes/"):
                text += "\nOnly the local remote-tracking reference is deleted."
        elif request.action == "rebase":
            text = f"Rebase {current} onto {target.ref}?"
        else:
            text = f"Merge {target.ref} into {current}?"
        return (
            QMessageBox.question(
                self.picker.dialog,
                "Confirm Git action",
                text,
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            == QMessageBox.Yes
        )

    def _stacks(self):
        host = self.picker.host
        widget = host.widget.editor_widget.get_widget()
        stacks = getattr(widget, "editorstacks", ())
        if not isinstance(stacks, (list, tuple)):
            stacks = ()
        current = host.status.get_editorstack()
        return list(dict.fromkeys((*stacks, current)))

    def _buffers(self, root, *, path=None):
        # Retain every view: the first clone may close while Git is running.
        # Deduplicate documents only when a live view actually reloads them.
        selected_paths = (
            {osp.normcase(osp.abspath(path)), osp.normcase(osp.realpath(path))}
            if path is not None
            else None
        )
        buffers = []
        for stack in self._stacks():
            if stack is None or widget_is_deleted(stack):
                continue
            for finfo in stack.data:
                editor = finfo.editor
                if widget_is_deleted(editor):
                    continue
                if (
                    selected_paths is not None
                    and osp.normcase(osp.abspath(finfo.filename)) not in selected_paths
                    and osp.normcase(osp.realpath(finfo.filename)) not in selected_paths
                ):
                    continue
                if not _in_repository(finfo.filename, root):
                    continue
                document = editor.document()
                buffers.append(
                    _BufferSnapshot(
                        stack_ref=weakref.ref(stack),
                        editor_ref=weakref.ref(editor),
                        path=finfo.filename,
                        revision=document.revision(),
                        disk_stamp=_disk_stamp(finfo.filename),
                    )
                )
        return buffers

    def _clean_buffers(self, request, *, path=None):
        """Capture live views, or end preflight if any has unsaved changes."""
        buffers = self._buffers(request.root, path=path)
        dirty = dict.fromkeys(
            buffer.path
            for buffer in buffers
            if buffer.editor_ref().document().isModified()
        )
        if dirty:
            self._finish_preflight(
                request,
                "save or close modified buffers first: "
                + ", ".join(osp.basename(path) for path in dirty),
            )
            return None
        return buffers

    def _reload_changed_buffers(self, request, buffers):
        if request.action not in _DISK_ACTIONS:
            return ""
        kept = False
        refreshed = set()
        picker = self.picker
        picker.navigating = True
        try:
            for buffer in buffers:
                stack = live_widget(buffer.stack_ref)
                editor = live_widget(buffer.editor_ref)
                if stack is None or editor is None:
                    continue
                document = editor.document()
                if (
                    document in refreshed
                    or _disk_stamp(buffer.path) == buffer.disk_stamp
                ):
                    continue
                if (
                    document.isModified()
                    or document.revision() != buffer.revision
                    or not osp.isfile(buffer.path)
                ):
                    kept = True
                    continue
                index = stack.is_file_opened(buffer.path)
                if index is not None and stack.data[index].editor is editor:
                    stack.reload(index)
                    refreshed.add(document)
            if (
                picker.phase == "active"
                and live_widget(picker.stack_ref)
                is picker.host.status.get_editorstack()
            ):
                editor = picker.host.status.get_editor()
                if editor is not None:
                    picker.editor_ref = weakref.ref(editor)
                    picker.dialog.set_editor(editor)
        finally:
            picker.navigating = False
        return " · Changed/removed buffers kept for review" if kept else ""

    def _finished(self, request, buffers, result):
        self.running = None
        picker = self.picker
        if picker.widget._closed or widget_is_deleted(picker.widget):
            return
        if request.action == "commit" and not result.error and not result.returncode:
            self.commit_drafts.pop(request.root, None)
        if (
            request.action == "edit_commit_message"
            and not result.error
            and not result.returncode
        ):
            self.amend_drafts.pop((request.root, request.entry.target.commit), None)
        try:
            note = self._reload_changed_buffers(request, buffers)
        except (OSError, RuntimeError):
            logger.exception("Could not refresh open buffers after Git")
            note = " · Refresh open files to see disk changes"
        for state in picker.states.values():
            state.snapshot = None
        picker.content.clear()
        affected = (
            picker.git_root == request.root
            or _in_repository(picker.project, request.root)
            or _in_repository(picker.host.filename(), request.root)
        )
        if picker.phase == "active" and affected and picker._context_valid():
            picker.refresh()
        error = result.error or (result.stderr if result.returncode else "")
        message = (
            f"Git {request.action}: {error}"
            if error
            else f"Git {request.action}: completed"
        )
        self._message(message + note)
        self.sync()

    def cleanup(self):
        self.pending = None
        self.service.close()
