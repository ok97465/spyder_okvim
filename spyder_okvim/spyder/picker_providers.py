"""Value snapshots and GUI navigation adapters for the shared picker."""

from __future__ import annotations

# Standard Libraries
import os
import os.path as osp
from dataclasses import replace
from uuid import uuid4

# Third Party Libraries
from qtpy.QtGui import QTextCursor

# Project Libraries
from spyder_okvim.spyder.picker_preview import MAX_READ_BYTES, from_text, locate
from spyder_okvim.utils.picker import (
    MAX_CANDIDATE_BYTES,
    MAX_CANDIDATES,
    CandidateSnapshot,
    PickerEntry,
    PickerTarget,
)

FILE_EXTENSIONS = frozenset((".py", ".txt", ".md"))
MAX_METADATA_CHARS = 1024
_DOCUMENT_ID_PROPERTY = "_spyder_okvim_picker_document_id"


def collect_files(root, version, cancel):
    """Preserve the existing extension/hidden/symlink policy off the GUI thread."""
    if not root or not osp.isdir(root):
        return CandidateSnapshot(
            "files",
            root or "",
            version,
            (),
            "No project is open." if not root else "Project folder is unavailable.",
        )
    entries = []
    size = 0
    directories = [root]
    message = "complete"
    while directories and not cancel():
        directory = directories.pop()
        try:
            with os.scandir(directory) as children:
                for child in children:
                    if cancel():
                        break
                    if child.name.startswith(".") or child.is_symlink():
                        continue
                    if child.is_dir(follow_symlinks=False):
                        directories.append(child.path)
                    elif (
                        child.is_file(follow_symlinks=False)
                        and osp.splitext(child.name)[1] in FILE_EXTENSIONS
                    ):
                        relative = osp.relpath(child.path, root)
                        size += len(relative.encode("utf-8", errors="replace"))
                        if len(entries) >= MAX_CANDIDATES or size > MAX_CANDIDATE_BYTES:
                            return CandidateSnapshot(
                                "files",
                                root,
                                version,
                                tuple(entries),
                                "Candidate collection limited",
                            )
                        target = PickerTarget(osp.abspath(child.path))
                        entries.append(
                            PickerEntry(
                                relative,
                                "files",
                                child.name,
                                detail=osp.dirname(relative),
                                search_text=relative,
                                ordinal=len(entries),
                                target=target,
                            )
                        )
        except OSError as error:
            message = f"Some folders could not be read: {error.strerror}"
    entries.sort(key=lambda entry: entry.id)
    return CandidateSnapshot(
        "files",
        root,
        version,
        tuple(replace(entry, ordinal=i) for i, entry in enumerate(entries)),
        message,
    )


def enrich_entries(entries, content):
    """Return changed rows and whether content or snippet limits were reached."""
    enriched = []
    limited = False
    for entry in entries:
        metadata = locate(content, entry.target)
        coordinates = (
            f"{metadata.line_number}:{metadata.column_number or '?'}"
            if metadata.line_number is not None
            else "position unavailable"
        )
        snippet = metadata.text[:MAX_METADATA_CHARS]
        truncated = len(metadata.text) > MAX_METADATA_CHARS
        if truncated:
            snippet += "…"
        detail = f"{entry.target.path}  {coordinates}  {snippet}"
        if entry.detail != detail or entry.search_text != f"{entry.label} {detail}":
            enriched.append(
                replace(entry, detail=detail, search_text=f"{entry.label} {detail}")
            )
        limited |= bool(metadata.message) or truncated
    return tuple(enriched), limited


class PickerHost:
    """Spyder-only operations shared by the small source adapters."""

    def __init__(self, widget):
        self.widget = widget
        self.status = widget.vim_status
        self.history = ()
        self.history_version = 0
        self._open_content = None

    def filename(self):
        return self.status.get_editorstack().get_current_filename() or ""

    def project_root(self):
        projects = getattr(self.widget.main, "projects", None)
        root = projects.get_active_project_path() if projects is not None else None
        return (
            osp.abspath(root) if isinstance(root, (str, os.PathLike)) and root else ""
        )

    def history_values(self):
        values = tuple((jump.file, jump.pos) for jump in self.status.jump_list.jumps)
        if values != self.history:
            self.history = values
            self.history_version += 1
        return self.history

    def open_editor(self, path):
        stack = self.status.get_editorstack()
        path = osp.normcase(osp.abspath(path))
        for finfo in getattr(stack, "data", ()):
            if osp.normcase(osp.abspath(finfo.filename)) == path:
                return finfo.editor
        return None

    def content_identity(self, path):
        editor = self.open_editor(path)
        if editor is None:
            return None
        return self._document_identity(editor.document())

    def _document_identity(self, document):
        # Store identity on the native QObject: PyQt can discard and recreate
        # its Python wrapper between calls, including when other files preview.
        token = document.property(_DOCUMENT_ID_PROPERTY)
        if token is None:
            token = uuid4().hex
            document.setProperty(_DOCUMENT_ID_PROPERTY, token)
        return ("buffer", token, document.revision())

    def open_content(self, path):
        """Capture only a bounded prefix of the matching open document on GUI."""
        editor = self.open_editor(path)
        if editor is None:
            return None
        document = editor.document()
        identity = self._document_identity(document)
        if self._open_content is not None and self._open_content.identity == identity:
            return self._open_content
        cursor = QTextCursor(document)
        last = max(0, document.characterCount() - 1)
        cursor.setPosition(min(last, MAX_READ_BYTES // 2), QTextCursor.KeepAnchor)
        text = cursor.selectedText().replace("\u2029", "\n")
        self._open_content = from_text(
            text, identity, complete=last <= MAX_READ_BYTES // 2
        )
        return self._open_content

    def activate_file(self, path):
        """Use the shared host's guarded Spyder navigation operation."""
        return self.status.host.activate_file(path)

    def open_file(self, target):
        origin = self.status.get_current_location()
        if not self.activate_file(target.path):
            return False
        if origin is not None:
            self.status.jump_list.push(*origin)
        self.status.cursor.set_cursor_pos(0)
        self.status.push_jump()
        return True


class FilesProvider:
    def __init__(self, host):
        self.host = host

    def scope(self):
        return self.host.project_root()

    def validate(self, entry, scope):
        return scope == self.scope() and osp.isfile(entry.target.path)

    def execute(self, entry):
        return self.host.open_file(entry.target)


class MarksProvider:
    def __init__(self, host):
        self.host = host

    def scope(self):
        return self.host.filename()

    def snapshot(self, version):
        scope = self.scope()
        entries = []
        for ordinal, (name, location) in enumerate(
            self.host.status.bookmark_manager.list_bookmarks()
        ):
            target = PickerTarget(
                location["file"],
                block_number=location["line"],
                column_utf16=location["col"],
                mark_name=name,
            )
            mark_scope = "global" if name.isupper() else scope
            detail = (
                f"{target.path}  {target.block_number + 1}:{target.column_utf16 + 1}"
            )
            entries.append(
                PickerEntry(
                    f"{mark_scope}:{name}",
                    "marks",
                    name,
                    detail=detail,
                    search_text=f"{name} {detail}",
                    ordinal=ordinal,
                    target=target,
                )
            )
        return CandidateSnapshot(
            "marks", scope, version, tuple(entries), "Preparing text metadata"
        )

    def validate(self, entry, scope):
        target = entry.target
        current = self.host.status.bookmark_manager.get_bookmark(target.mark_name)
        return scope == self.scope() and current == {
            "file": target.path,
            "line": target.block_number,
            "col": target.column_utf16,
        }

    def execute(self, entry):
        status = self.host.status
        target = entry.target
        origin = status.get_current_location()
        if not self.host.activate_file(target.path):
            return False
        status.bookmark_manager.jump_to_bookmark(target.mark_name)
        if (
            self.host.filename() != target.path
            or status.bookmark_manager.get_bookmark(target.mark_name) is None
        ):
            return False
        if origin is not None:
            status.jump_list.push(*origin)
        status.push_jump()
        return True


class JumpsProvider:
    def __init__(self, host):
        self.host = host

    def scope(self):
        return str(id(self.host.status.get_editorstack()))

    def snapshot(self, version):
        entries = []
        for ordinal, (path, offset) in enumerate(self.host.history_values()):
            target = PickerTarget(
                path,
                offset_utf16=offset,
                history_index=ordinal + 1,
                history_version=self.host.history_version,
            )
            detail = f"{path}  location loading…"
            entries.append(
                PickerEntry(
                    f"{target.history_version}:{ordinal}",
                    "jumps",
                    str(ordinal + 1),
                    detail=detail,
                    search_text=detail,
                    ordinal=ordinal,
                    target=target,
                )
            )
        return CandidateSnapshot(
            "jumps", self.scope(), version, tuple(entries), "Preparing text metadata"
        )

    def current_id(self):
        self.host.history_values()
        return f"{self.host.history_version}:{self.host.status.jump_list.index - 1}"

    def validate(self, entry, scope):
        self.host.history_values()
        target = entry.target
        return (
            scope == self.scope()
            and target.history_version == self.host.history_version
            and 1 <= target.history_index <= len(self.host.history)
        )

    def execute(self, entry):
        if not self.host.activate_file(entry.target.path):
            return False
        # Opening a file can process events; the selected history entry may
        # have changed before its stored position is applied.
        if not self.validate(entry, self.scope()):
            return False
        self.host.status.jump_to_index(entry.target.history_index)
        return self.host.filename() == entry.target.path


class GitStatusProvider:
    def __init__(self, host):
        self.host = host

    def validate(self, entry, scope):
        return entry.target.path.startswith(scope + osp.sep) and osp.isfile(
            entry.target.path
        )

    def execute(self, entry):
        return self.host.open_file(entry.target)
