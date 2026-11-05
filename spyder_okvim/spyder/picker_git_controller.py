"""Git action intent, repository preconditions and picker-independent execution."""

from __future__ import annotations

import logging
import os
import os.path as osp
import weakref
from dataclasses import dataclass, replace

from qtpy.QtWidgets import QInputDialog, QMessageBox

from spyder_okvim.spyder.picker_git_actions import (
    GitMutationService,
    action_args,
    status_action,
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

    @staticmethod
    def _operation(source, action, entry):
        if source == "git_status" and action == "stage_toggle":
            return status_action(entry.target)
        if source in ("git_log", "git_file_log"):
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
        if self.busy or picker.phase != "active" or (entry is None and not creating):
            self.sync()
            return
        operation = self._operation(picker.source, action, entry)
        if operation is None or not picker.git_root:
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
            entry=entry,
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
        buffers = self._buffers(request.root) if request.action in _DISK_ACTIONS else []
        dirty = [
            buffer.path
            for buffer in buffers
            if buffer.editor_ref().document().isModified()
        ]
        if dirty:
            self._finish_preflight(
                request,
                "save or close modified buffers first: "
                + ", ".join(osp.basename(path) for path in dirty),
            )
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
        # A confirmation runs a nested event loop; protect edits made while it
        # was open as well as those that predated the action.
        buffers = self._buffers(request.root) if request.action in _DISK_ACTIONS else []
        if any(buffer.editor_ref().document().isModified() for buffer in buffers):
            self._finish_preflight(request, "save or close modified buffers first")
            return
        target = (
            replace(
                request.entry.target,
                path=osp.relpath(request.entry.target.path, request.root),
            )
            if request.entry is not None
            else PickerTarget("")
        )
        try:
            args = action_args(request.action, target, branch_name=name)
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

        accepted = self.service.submit(
            request,
            request.root,
            args,
            finished,
            expected_head=head,
            expected_branch=branch,
            expected_ref=expected_ref,
        )
        if not accepted:
            self.running = None
            self._message("Git: another operation is already running")
        self.sync()

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
        if request.action.startswith("reset_"):
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

    def _buffers(self, root):
        # Retain every view: the first clone may close while Git is running.
        # Deduplicate documents only when a live view actually reloads them.
        buffers = []
        for stack in self._stacks():
            if stack is None or widget_is_deleted(stack):
                continue
            for finfo in stack.data:
                editor = finfo.editor
                if widget_is_deleted(editor):
                    continue
                document = editor.document()
                if not _in_repository(finfo.filename, root):
                    continue
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
