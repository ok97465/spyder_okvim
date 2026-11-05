"""Shared picker session, asynchronous publication and host focus ownership."""

from __future__ import annotations

import logging
import os.path as osp
import weakref
from collections import deque
from dataclasses import dataclass, replace
from functools import partial

from qtpy.QtCore import QObject, QTimer
from qtpy.QtWidgets import QApplication

from spyder_okvim.spyder.picker_dialog import PickerDialog
from spyder_okvim.spyder.picker_git import (
    GitService,
    commit_files_args,
    commit_preview_args,
    log_args,
    git_snapshot,
    status_args,
    status_diff_args,
    stash_args,
    stash_preview_args,
    branches_args,
    branch_preview_args,
)
from spyder_okvim.spyder.picker_preview import ContentPreview, ContentService, preview
from spyder_okvim.spyder.picker_git_controller import PickerGitActions
from spyder_okvim.spyder.picker_providers import (
    FilesProvider,
    GitStatusProvider,
    JumpsProvider,
    MarksProvider,
    PickerHost,
    collect_files,
    enrich_entries,
)
from spyder_okvim.spyder.picker_work import PickerWorkService
from spyder_okvim.utils.picker import (
    CandidateSnapshot,
    search,
)
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted


logger = logging.getLogger(__name__)
GIT_HISTORY_SOURCES = ("git_log", "git_file_log")
GIT_PAGED_SOURCES = (*GIT_HISTORY_SOURCES, "git_stash")


@dataclass
class SourceState:
    query: str = ""
    selected_id: str | None = None
    scroll: int | None = None
    snapshot: CandidateSnapshot | None = None


@dataclass(frozen=True)
class _ContentRequest:
    path: str
    selection_generation: int
    buffer_identity: tuple | None


def _read_content(service, path, prepared, entries, target, cancel):
    content = prepared if prepared is not None else service.read(path, cancel)
    enriched, limited = enrich_entries(entries, content)
    return enriched, limited, preview(content, target) if target is not None else None


class PickerController(QObject):
    """One popup per VimWidget; worker lanes survive every popup close/reopen."""

    def __init__(self, widget):
        super().__init__(widget)
        self.widget = widget
        self._closed = False
        self.host = PickerHost(widget)
        self.providers = {
            "files": FilesProvider(self.host),
            "marks": MarksProvider(self.host),
            "jumps": JumpsProvider(self.host),
            "git_status": GitStatusProvider(self.host),
        }
        self.work = PickerWorkService()
        self.work.completed.connect(self._completed)
        self.git = GitService()
        self.content = ContentService()
        self.dialog = None
        self.phase = "closed"
        self.actions = PickerGitActions(self)
        self.navigating = False
        self.session = 0
        self.dataset = 0
        self.query_generation = 0
        self.selection_generation = 0
        self.collect_generation = 0
        self.git_generation = 0
        self.source = "files"
        self.scope = ""
        self.states = {}
        self.snapshot = None
        self.result_token = None
        self.stack_ref = self.window_ref = self.editor_ref = None
        self.project = ""
        self.git_root = ""
        self.commit = ""
        self.git_limits = {}
        self.git_roots = {}
        self.commit_source = "git_log"
        self.metadata = deque()
        self.metadata_limited = False
        self.metadata_done = set()
        self._content_active = None
        self._accepted = None
        self._buffer_identity = None
        self._query_timer = QTimer(self)
        self._query_timer.setSingleShot(True)
        self._query_timer.setInterval(40)
        self._query_timer.timeout.connect(self._search)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(50)
        self._preview_timer.timeout.connect(self._preview)
        self._context_timer = QTimer(self)
        self._context_timer.setInterval(150)
        self._context_timer.timeout.connect(self._check_context)

    @property
    def owns_focus(self):
        return self.phase != "closed"

    def allows_navigation(self, stack):
        return (
            self.navigating
            and stack is live_widget(self.stack_ref)
            and stack.window() is live_widget(self.window_ref)
        )

    def _context_valid(self):
        stack = live_widget(self.stack_ref)
        window = live_widget(self.window_ref)
        editor = live_widget(self.editor_ref)
        return (
            not self.widget._closed
            and stack is not None
            and window is not None
            and editor is not None
            and self.host.status.get_editorstack() is stack
            and stack.window() is window
            and self.host.status.get_editor() is editor
            and self.host.project_root() == self.project
        )

    def open(self, source):
        if self.widget._closed or self._closed:
            return
        if self.phase == "active" and self._context_valid():
            if source != self.source:
                self._switch_source(source)
            self.dialog.focus_query()
            return
        self.cancel()
        editor = self.host.status.get_editor()
        stack = self.host.status.get_editorstack()
        if editor is None or widget_is_deleted(editor) or stack is None:
            return
        self.session += 1
        self.stack_ref = weakref.ref(stack)
        self.window_ref = weakref.ref(stack.window())
        self.editor_ref = weakref.ref(editor)
        self.project = self.host.project_root()
        self.states = {}
        self.git_root = self.commit = ""
        self.git_limits = {}
        self.git_roots = {}
        self.commit_source = "git_log"
        self.phase = "active"
        self.dialog = PickerDialog(parent=editor, editor=editor)
        dialog = self.dialog
        dialog.query_changed.connect(self._query_changed)
        dialog.source_changed.connect(self._switch_source)
        dialog.selection_changed.connect(self._selection_changed)
        dialog.accepted_entry.connect(self._accept)
        dialog.action_requested.connect(self._git_action)
        dialog.navigate_history.connect(self._navigate_history)
        dialog.refresh_requested.connect(self.refresh)
        dialog.back_requested.connect(self._back)
        dialog.load_more_requested.connect(self._load_more)
        dialog.finished.connect(self._finished)
        dialog.show()
        self._switch_source(source, save=False)
        dialog.focus_query()
        self._context_timer.start()

    def _save_state(self):
        state = self.states.setdefault((self.source, self.scope), SourceState())
        state.query = self.dialog.query()
        state.selected_id = self.dialog.selection_id() or state.selected_id
        state.scroll = self.dialog.scroll_position()
        state.snapshot = self.snapshot

    def _git_directory(self, source):
        if source == "git_file_log":
            return osp.dirname(self.host.filename()) or self.project
        return self.project or osp.dirname(self.host.filename())

    def _scope_for(self, source):
        if source.startswith("git_"):
            root = self.git_root or self._git_directory(source)
            if source == "git_files":
                return f"{root}:{self.commit}"
            if source == "git_file_log":
                return f"{root}:{self.host.filename()}"
            return root
        return self.providers[source].scope()

    def _switch_source(self, source, save=True):
        if self.phase != "active" or not self._context_valid():
            return
        if save:
            self._save_state()
        self._invalidate_results()
        self.work.cancel()
        self.git.cancel()
        self._content_active = None
        self.metadata.clear()
        self.metadata_done.clear()
        if source.startswith("git_") and source != "git_files":
            self.git_root = self.git_roots.get(self._git_directory(source), "")
        self.source, self.scope = source, self._scope_for(source)
        self.dialog.set_source(source)
        self.dialog.set_scope(self.scope)
        self.dialog.set_back_enabled(source == "git_files")
        self.dialog.set_load_more_enabled(source in GIT_PAGED_SOURCES)
        self.actions.sync()
        state = self.states.setdefault((source, self.scope), SourceState())
        self.dialog.set_query(state.query)
        self.snapshot = state.snapshot
        self.metadata_limited = False
        if self.snapshot is not None and source in ("marks", "jumps"):
            # Targets may have changed while another source was visible.
            fresh = self.providers[source].snapshot(self.dataset + 1)
            if tuple(entry.target for entry in fresh.entries) != tuple(
                entry.target for entry in self.snapshot.entries
            ):
                self.snapshot = None
        if self.snapshot is None:
            self._collect()
        else:
            self._search()
            self._prepare_metadata()

    def _invalidate_results(self):
        self.actions.invalidate_pending()
        self.result_token = None
        self.query_generation += 1
        self.selection_generation += 1
        self._query_timer.stop()
        self._preview_timer.stop()
        if self.dialog is not None and not widget_is_deleted(self.dialog):
            self.dialog.set_busy("Searching…")
            self.dialog.set_preview(ContentPreview("", message="Select a result"))

    def _collect(self):
        self.dataset += 1
        self.collect_generation += 1
        self.snapshot = None
        self.dialog.set_busy("Collecting…")
        if self.source == "files":
            self.work.submit(
                "collect",
                (self.session, self.source, self.scope, self.collect_generation),
                partial(collect_files, self.scope, self.dataset),
            )
        elif self.source in ("marks", "jumps"):
            self._publish_snapshot(self.providers[self.source].snapshot(self.dataset))
            self._prepare_metadata()
        else:
            self._collect_git()

    def _publish_snapshot(self, snapshot):
        self.snapshot = snapshot
        self.scope = snapshot.scope_id
        self.dialog.set_scope(self.scope)
        self.states.setdefault((self.source, self.scope), SourceState()).snapshot = (
            snapshot
        )
        self.result_token = None
        self._search()

    def _query_changed(self, text):
        if self.phase != "active":
            return
        state = self.states.setdefault((self.source, self.scope), SourceState())
        state.selected_id = self.dialog.selection_id() or state.selected_id
        state.scroll = None
        self._invalidate_results()
        self.work.cancel("search")
        self._query_timer.start()

    def _search_token(self):
        return (
            self.session,
            self.source,
            self.scope,
            self.snapshot.dataset_version if self.snapshot else None,
            self.query_generation,
        )

    def _search(self):
        if self.phase != "active" or self.snapshot is None:
            return
        self._query_timer.stop()
        self.work.submit(
            "search",
            self._search_token(),
            partial(search, self.snapshot, self.dialog.query()),
        )

    def _completed(self, lane, token, result):
        if self.phase != "active" or not self._context_valid():
            return
        if lane == "collect":
            self._collected(token, result)
        elif lane == "search":
            self._searched(token, result)
        elif lane == "content":
            self._content_ready(token, result)

    def _collected(self, token, result):
        if token != (
            self.session,
            self.source,
            self.scope,
            self.collect_generation,
        ):
            return
        if isinstance(result, Exception):
            self.dialog.set_status(f"Collection failed: {result}")
            return
        self._publish_snapshot(result)

    def _searched(self, token, result):
        if token != self._search_token():
            return
        if isinstance(result, Exception):
            self.dialog.set_status(f"Search failed: {result}")
            return
        if result.cancelled:
            return
        self.result_token = token
        state = self.states.setdefault((self.source, self.scope), SourceState())
        selected = state.selected_id
        if self.source == "jumps" and not self.dialog.query() and selected is None:
            selected = self.providers["jumps"].current_id()
        self.dialog.set_results(result, selected_id=selected, scroll=state.scroll)
        state.scroll = None
        self._set_status(result)
        if self.source == "jumps":
            self.dialog.set_current_id(self.providers["jumps"].current_id())

    def _content_ready(self, request, result):
        # The request object owns publication; replacing or clearing it rejects
        # late work without duplicating session/source/generation counters.
        if request is not self._content_active:
            return
        self._content_active = None
        path = request.path
        selected = request.selection_generation == self.selection_generation
        if isinstance(result, Exception):
            first_failure = path not in self.metadata_done
            self.metadata_done.add(path)
            if self.source in ("marks", "jumps"):
                self.metadata_limited = True
            entry = self.dialog.selected_entry()
            if selected and entry is not None and entry.target.path == path:
                self.dialog.set_preview(
                    ContentPreview("", message=f"Read failed: {result}")
                )
            # Failed metadata must advance the queue rather than retry forever.
            if first_failure and self.source in ("marks", "jumps"):
                self._search()
            self._schedule_metadata()
            return
        if self.host.content_identity(path) != request.buffer_identity:
            self._preview_timer.start()
            self._schedule_metadata()
            return
        enriched, limited, display = result
        self.metadata_done.add(path)
        self.metadata_limited |= limited
        if enriched and self.snapshot is not None:
            updates = {entry.id: entry for entry in enriched}
            self.dataset += 1
            entries = tuple(
                updates.get(entry.id, entry) for entry in self.snapshot.entries
            )
            self.snapshot = replace(
                self.snapshot, dataset_version=self.dataset, entries=entries
            )
            state = self.states.setdefault((self.source, self.scope), SourceState())
            state.selected_id = self.dialog.selection_id() or state.selected_id
            state.snapshot = self.snapshot
            self._search()
        if display is not None and selected:
            self.dialog.set_preview(display)
        self._schedule_metadata()

    def _set_status(self, result):
        total = len(self.snapshot.entries)
        message = f"{result.total_matches} / {total} results"
        if not total:
            message = {
                "files": "No files in this project.",
                "marks": "No marks.",
                "jumps": "No jumps.",
                "git_status": "Working tree clean.",
                "git_log": "No commits.",
                "git_file_log": "No commits for this file.",
                "git_stash": "No stashes.",
                "git_branches": "No branches.",
                "git_files": "No changed files.",
            }.get(self.source, "No results.")
        if result.truncated:
            message += f" · Showing best {len(result.matches)}"
        completeness = self.snapshot.completeness
        if completeness not in ("complete", "Preparing text metadata"):
            message += f" · {completeness}"
        if self.metadata:
            message += " · Preparing text metadata"
        elif self.metadata_limited:
            message += " · Text search partially limited"
        if self.source in GIT_PAGED_SOURCES:
            noun = "stashes" if self.source == "git_stash" else "commits"
            message += f" · {total} {noun} loaded"
        self.dialog.set_status(message)

    def _prepare_metadata(self):
        if self.source not in ("marks", "jumps") or self.snapshot is None:
            return
        self.metadata = deque(
            dict.fromkeys(entry.target.path for entry in self.snapshot.entries)
        )
        self._schedule_metadata()

    def _schedule_metadata(self):
        if self.phase != "active" or self._content_active is not None:
            return
        while self.metadata and self.metadata[0] in self.metadata_done:
            self.metadata.popleft()
        if self.metadata:
            self._submit_content(self.metadata[0], None)

    def _selection_changed(self, entry):
        if self.phase != "active":
            return
        self.actions.invalidate_pending()
        self.selection_generation += 1
        if self.snapshot is not None:
            self.git.cancel()
            self.git_generation += 1
        if entry is not None:
            self.states.setdefault(
                (self.source, self.scope), SourceState()
            ).selected_id = entry.id
        self.dialog.set_preview(
            ContentPreview("", message="Loading preview…" if entry else "No selection")
        )
        self._preview_timer.start()

    def _preview(self):
        if self.phase != "active" or self.result_token != self._search_token():
            return
        entry = self.dialog.selected_entry()
        if entry is None:
            return
        if self.source.startswith("git_") and entry.preview_kind != "code":
            self._git_preview(entry)
        else:
            self._submit_content(entry.target.path, entry.target)

    def _submit_content(self, path, target):
        prepared = self.host.open_content(path)
        if target is not None:
            self._buffer_identity = prepared.identity if prepared else None
        entries = (
            tuple(entry for entry in self.snapshot.entries if entry.target.path == path)
            if self.source in ("marks", "jumps")
            else ()
        )
        request = _ContentRequest(
            path,
            self.selection_generation,
            prepared.identity if prepared else None,
        )
        self._content_active = request
        self.work.submit(
            "content",
            request,
            partial(_read_content, self.content, path, prepared, entries, target),
        )

    def refresh(self):
        if self.phase != "active":
            return
        self._save_state()
        self._invalidate_results()
        self.work.cancel()
        self.git.cancel()
        self.content.clear()
        self.metadata.clear()
        self.metadata_done.clear()
        self._content_active = None
        self.metadata_limited = False
        self._collect()

    def _check_context(self):
        if self.phase != "active":
            return
        if not self._context_valid():
            self.cancel()
            return
        entry = self.dialog.selected_entry()
        if entry is not None and self.result_token is not None:
            identity = self.host.content_identity(entry.target.path)
            if identity != self._buffer_identity:
                self._buffer_identity = identity
                self.metadata_done.discard(entry.target.path)
                self._preview_timer.start()

    def _navigate_history(self, direction):
        if (
            self.phase != "active"
            or self.source != "jumps"
            or self.snapshot is None
            or not self._context_valid()
        ):
            return
        previous_version = self.host.history_version
        values = self.host.history_values()
        if previous_version != self.host.history_version:
            self.refresh()
            return
        index = self.host.status.jump_list.index + (-1 if direction < 0 else 1)
        if not 1 <= index <= len(values):
            return
        entry = next(
            (
                entry
                for entry in self.snapshot.entries
                if entry.target.history_index == index
            ),
            None,
        )
        provider = self.providers["jumps"]
        if entry is None or not provider.validate(entry, self.scope):
            self.refresh()
            return
        self.navigating = True
        try:
            status = self.host.status
            if not provider.execute(entry):
                status.set_message("Picker: target could not be opened")
                return
            self.editor_ref = weakref.ref(status.get_editor())
            self.dialog.set_editor(status.get_editor())
        finally:
            self.navigating = False
        if not self._context_valid():
            self.cancel()
            return
        if values != self.host.history_values():
            self.refresh()
            return
        current = self.providers["jumps"].current_id()
        self.states[(self.source, self.scope)].selected_id = current
        self.dialog.set_current_id(current)
        # A view-only marker update does not recreate candidates or read files.
        self.dialog.select_id(current)
        self.dialog.focus_query()

    def _accept(self, entry):
        if (
            self.phase != "active"
            or not self._context_valid()
            or self.result_token != self._search_token()
            or entry is None
        ):
            return
        if self.source in GIT_HISTORY_SOURCES or self.source == "git_branches":
            self.actions.request("checkout", entry)
            return
        if self.source == "git_stash":
            self.actions.request("stash_apply", entry)
            return
        if self.source == "git_files" or (
            self.source == "git_status" and not osp.isfile(entry.target.path)
        ):
            self._git_preview(entry)
            return
        provider = self.providers[self.source]
        if not provider.validate(entry, self.scope):
            self.refresh()
            self.host.status.set_message(
                "Picker: target changed or is unavailable; refreshed"
            )
            return
        self._accepted = (provider, entry, self.scope)
        self.dialog.accept()

    def _git_action(self, action, entry):
        if action == "commit_files":
            if (
                self.source in GIT_HISTORY_SOURCES
                and self.phase == "active"
                and self.result_token == self._search_token()
                and entry is not None
            ):
                self.commit_source = self.source
                self.commit = entry.target.commit
                self._switch_source("git_files")
            return
        self.actions.request(action, entry)

    def _finished(self, result):
        if self.phase != "active":
            return
        self.phase = "finishing"
        self._stop_work()
        session = self.session
        QTimer.singleShot(0, partial(self._complete, session))

    def _complete(self, session):
        if self.phase != "finishing" or session != self.session:
            return
        if not self._context_valid():
            self.cancel()
            return
        action = self._accepted
        self._accepted = None
        self.navigating = True
        try:
            if action is not None:
                provider, entry, scope = action
                if not provider.validate(entry, scope) or not provider.execute(entry):
                    self.host.status.set_message("Picker: target could not be opened")
            editor = self.host.status.get_editor()
            if editor is not None:
                self.editor_ref = weakref.ref(editor)
        except Exception:
            logger.exception("Picker navigation failed")
            self.host.status.set_message("Picker: target could not be opened")
        finally:
            self.navigating = False
        # Popup destruction posts focus events. Ownership stays through one
        # additional event-loop turn and is invalidated by any replacement.
        QTimer.singleShot(0, partial(self._restore_focus, session))

    def _restore_focus(self, session, attempt=0):
        if self.phase != "finishing" or session != self.session:
            return
        if self._context_valid():
            window = live_widget(self.window_ref)
            active = QApplication.activeWindow()
            if active is None or active is window:
                if active is None:
                    window.activateWindow()
                self.widget.commandline.setFocus()
                if attempt < 3 and (
                    attempt == 0 or not self.widget.commandline.hasFocus()
                ):
                    QTimer.singleShot(
                        0, partial(self._restore_focus, session, attempt + 1)
                    )
                    return
        self.phase = "closed"
        self.dialog = None
        self.states.clear()
        self.snapshot = None

    def _stop_work(self):
        self.result_token = None
        self._query_timer.stop()
        self._preview_timer.stop()
        self._context_timer.stop()
        self.work.cancel()
        self.git.cancel()
        self._content_active = None
        self.metadata.clear()

    def cancel(self):
        dialog = self.dialog
        self.phase = "closed"
        self.actions.invalidate_pending()
        self.session += 1
        self._accepted = None
        self._stop_work()
        self.dialog = None
        self.states.clear()
        self.snapshot = None
        if dialog is not None and not widget_is_deleted(dialog):
            dialog.reject()

    def cleanup(self):
        if self._closed:
            return
        self._closed = True
        self.cancel()
        self.work.completed.disconnect(self._completed)
        self.work.close()
        self.git.close()
        self.actions.cleanup()

    def _git_request(self, args, callback):
        self.git_generation += 1
        token = (self.session, self.source, self.scope, self.git_generation)

        def completed(result):
            if (
                self.phase != "active"
                or token != (self.session, self.source, self.scope, self.git_generation)
                or not self._context_valid()
            ):
                return
            callback(result)

        self.git.submit(
            token,
            self.git_root or self._git_directory(self.source),
            args,
            completed,
        )

    def _collect_git(self):
        if self.source == "git_file_log" and not self.host.filename():
            self._publish_snapshot(
                CandidateSnapshot(
                    self.source, self.scope, self.dataset, (), "No current file."
                )
            )
            return
        if not self.git_root:

            def located(result):
                if result.error or result.returncode:
                    self.dialog.set_status(
                        result.error or result.stderr or "Not a Git repository"
                    )
                    return
                self.git_root = result.stdout.decode(errors="surrogateescape").rstrip(
                    "\n"
                )
                self.git_roots[self._git_directory(self.source)] = self.git_root
                self.scope = self._scope_for(self.source)
                self._collect_git()

            self._git_request(["rev-parse", "--show-toplevel"], located)
            return
        limit = self.git_limits.get((self.source, self.scope), 200)
        if self.source == "git_status":
            args = status_args()
        elif self.source == "git_branches":
            args = branches_args()
        elif self.source == "git_stash":
            args = stash_args(limit=limit)
        elif self.source == "git_files":
            args = commit_files_args(self.commit)
        else:
            path = (
                osp.relpath(self.host.filename(), self.git_root)
                if self.source == "git_file_log"
                else None
            )
            args = log_args(limit=limit, path=path)
        source, version = self.source, self.dataset

        def collected(result):
            if result.error or (result.returncode and not result.truncated):
                message = result.error or result.stderr or "Git query failed"
                if (
                    source in GIT_HISTORY_SOURCES
                    and "does not have any commits" in message
                ):
                    self._publish_snapshot(
                        CandidateSnapshot(
                            source,
                            self.scope,
                            version,
                            (),
                            "No commits in this repository.",
                        )
                    )
                else:
                    self.dialog.set_status(message)
                return
            self._publish_snapshot(
                git_snapshot(
                    source, self.scope, version, self.git_root, self.commit, result
                )
            )

        self._git_request(args, collected)

    def _git_preview(self, entry):
        from spyder_okvim.spyder.picker_preview import (
            MAX_PREVIEW_CHARS,
            MAX_PREVIEW_LINES,
        )

        target = entry.target
        selection = self.selection_generation
        editor = self.host.open_editor(target.path)
        self._buffer_identity = self.host.content_identity(target.path)
        note = (
            "Saved disk/index diff; open buffer may contain unsaved changes.\n\n"
            if editor is not None and editor.document().isModified()
            else ""
        )
        if target.status in ("DD", "AU", "UD", "UA", "DU", "AA", "UU"):
            note += "Unmerged conflict: combined patch has no two-way line mapping.\n\n"

        def display(result, prefix=""):
            if selection != self.selection_generation:
                return
            text = prefix + result.stdout.decode("utf-8", errors="replace")
            message = result.error or result.stderr
            lines = text[:MAX_PREVIEW_CHARS].split("\n", MAX_PREVIEW_LINES)
            limited = len(text) > MAX_PREVIEW_CHARS or len(lines) > MAX_PREVIEW_LINES
            text = "\n".join(lines[:MAX_PREVIEW_LINES])
            if result.truncated or limited:
                message = (message + " · " if message else "") + "Patch preview limited"
            self.dialog.set_preview(
                ContentPreview(text, message=message, language="diff")
            )

        if entry.preview_kind == "branch":
            self._git_request(branch_preview_args(target), display)
        elif entry.preview_kind == "stash":
            self._git_request(stash_preview_args(target.commit), display)
        elif entry.preview_kind in ("commit", "commit_file"):
            path = (
                osp.relpath(target.path, self.git_root)
                if entry.preview_kind == "commit_file"
                else None
            )
            self._git_request(
                commit_preview_args(target.commit, path=path, old_path=target.old_path),
                display,
            )
        else:
            path = osp.relpath(target.path, self.git_root)

            def unstaged(result):
                first = (
                    note
                    + "Unstaged: index ↔ disk worktree\n"
                    + (
                        result.stdout.decode("utf-8", errors="replace")
                        or "No unstaged patch.\n"
                    )
                )
                if result.error:
                    first += result.error + "\n"
                if result.truncated:
                    first += "\n[Unstaged patch output limited]\n"
                self._git_request(
                    status_diff_args(path, staged=True, old_path=target.old_path),
                    lambda staged: display(staged, first + "\nStaged: HEAD ↔ index\n"),
                )

            self._git_request(
                status_diff_args(path, old_path=target.old_path), unstaged
            )

    def _back(self):
        if self.source == "git_files":
            self._switch_source(self.commit_source)

    def _load_more(self):
        if self.phase == "active" and self.source in GIT_PAGED_SOURCES:
            key = (self.source, self.scope)
            self.git_limits[key] = min(100_000, self.git_limits.get(key, 200) + 200)
            self.refresh()
