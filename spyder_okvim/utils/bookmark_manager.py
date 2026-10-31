"""Store local/global Vim marks and navigate through supplied editor actions.

JSON I/O remains a small pair of functions in this feature module. The manager
accepts replacements so mark rules can be exercised with an in-memory store
without creating another repository or navigation layer.
"""

from __future__ import annotations

# Standard Libraries
import json
import os
import os.path as osp
from collections import defaultdict
from collections.abc import Callable
from typing import TypedDict


class BookmarkLocation(TypedDict):
    """Persisted mark coordinates: a path, zero-based block and UTF-16 column."""

    file: str
    line: int
    col: int


def load_bookmarks(path: str) -> dict[str, BookmarkLocation]:
    """Read existing global marks, returning an empty store on load failure.

    Keep the existing JSON format and permissive failure behavior. Schema
    validation and recovery policy are separate from this structural change.
    """
    if not osp.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as stream:
            return json.load(stream)
    except Exception:
        return {}


def save_bookmarks(path: str, bookmarks: dict[str, BookmarkLocation]) -> None:
    """Write global marks using the existing format; propagate write failures."""
    os.makedirs(osp.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(bookmarks, stream)


class BookmarkManager:
    """Own mark rules while delegating persistence and host navigation.

    Lowercase marks belong to a file and stay in memory; uppercase marks are
    global and persisted. Host callbacks resolve the active editor on demand.
    ``load``/``persist`` receive the configured path, so tests can substitute an
    in-memory store without changing mark lookup or cross-file jump behavior.
    """

    def __init__(
        self,
        bookmarks_file: str,
        open_file_func: Callable[[str], None],
        get_editorstack_func: Callable[[], object],
        get_editor_func: Callable[[], object],
        set_cursor_pos_func: Callable[[int], None],
        *,
        load: Callable[[str], dict[str, BookmarkLocation]] = load_bookmarks,
        persist: Callable[[str, dict[str, BookmarkLocation]], None] = save_bookmarks,
    ) -> None:
        self.bookmarks_file = bookmarks_file
        self.open_file = open_file_func
        self.get_editorstack = get_editorstack_func
        self.get_editor = get_editor_func
        self.set_cursor_pos = set_cursor_pos_func
        self._persist = persist

        self.bookmarks: dict[str, dict[str, BookmarkLocation]] = defaultdict(dict)
        self.bookmarks_global = load(bookmarks_file)

    def save(self) -> None:
        """Save persistent bookmarks to disk."""
        self._persist(self.bookmarks_file, self.bookmarks_global)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Remove all bookmarks from memory and disk."""
        self.bookmarks = defaultdict(dict)
        self.bookmarks_global = {}
        self.save()

    def set_bookmark(self, name: str) -> None:
        """Capture the current block/UTF-16 column; persist uppercase marks."""
        editor = self.get_editor()
        cursor = editor.textCursor()
        line = cursor.blockNumber()
        col = cursor.position() - cursor.block().position()
        path = self.get_editorstack().get_current_filename()
        info: BookmarkLocation = {"file": path, "line": line, "col": col}
        if name.isupper():
            self.bookmarks_global[name] = info
            self.save()
        else:
            self.bookmarks[path][name] = info

    def get_bookmark(self, name: str) -> BookmarkLocation | None:
        """Return bookmark information for *name* or None."""
        if name.isupper():
            return self.bookmarks_global.get(name)
        current = self.get_editorstack().get_current_filename()
        return self.bookmarks.get(current, {}).get(name)

    def jump_to_bookmark(self, name: str) -> None:
        """Open global targets and move to a live mark, dropping missing blocks.

        Stored columns are Qt UTF-16 offsets within a zero-based block. Clamp
        the destination to the current block's end after edits.
        """
        info = self.get_bookmark(name)
        if not info:
            return
        if name.isupper():
            file_path = info["file"]
            editor_stack = self.get_editorstack()
            if editor_stack.is_file_opened(file_path) is None:
                self.open_file(file_path)
            editor_stack.set_current_filename(file_path)
        editor = self.get_editor()
        block = editor.document().findBlockByNumber(info["line"])
        if not block.isValid():
            if name.isupper():
                self.bookmarks_global.pop(name, None)
                self.save()
            else:
                current = self.get_editorstack().get_current_filename()
                self.bookmarks[current].pop(name, None)
            return
        pos = block.position() + min(info["col"], block.length() - 1)
        self.set_cursor_pos(pos)

    def list_bookmarks(self) -> list[tuple[str, BookmarkLocation]]:
        """Return a combined list of local and global bookmarks."""
        current = self.get_editorstack().get_current_filename()
        marks = []
        for name, info in sorted(self.bookmarks.get(current, {}).items()):
            marks.append((name, info))
        for name, info in sorted(self.bookmarks_global.items()):
            marks.append((name, info))
        return marks
