"""Manage persistent and local bookmarks for OkVim."""

from __future__ import annotations

# Standard Libraries
import json
import os
import os.path as osp
from collections import defaultdict
from collections.abc import Callable


class BookmarkManager:
    """Handle loading, saving and retrieving bookmarks."""

    def __init__(
        self,
        bookmarks_file: str,
        open_file_func: Callable[[str], None],
        get_editorstack_func: Callable[[], object],
        get_editor_func: Callable[[], object],
        set_cursor_pos_func: Callable[[int], None],
    ) -> None:
        self.bookmarks_file = bookmarks_file
        self.open_file = open_file_func
        self.get_editorstack = get_editorstack_func
        self.get_editor = get_editor_func
        self.set_cursor_pos = set_cursor_pos_func

        self.bookmarks: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
        self.bookmarks_global: dict[str, dict[str, int]] = {}
        self._load_persistent_bookmarks()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _load_persistent_bookmarks(self) -> None:
        """Load persistent bookmarks from disk if present."""
        if osp.isfile(self.bookmarks_file):
            try:
                with open(self.bookmarks_file, "r", encoding="utf-8") as fh:
                    self.bookmarks_global = json.load(fh)
            except Exception:
                self.bookmarks_global = {}
        else:
            self.bookmarks_global = {}

    def _save_persistent_bookmarks(self) -> None:
        """Save persistent bookmarks to disk."""
        folder = osp.dirname(self.bookmarks_file)
        os.makedirs(folder, exist_ok=True)
        with open(self.bookmarks_file, "w", encoding="utf-8") as fh:
            json.dump(self.bookmarks_global, fh)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Remove all bookmarks from memory and disk."""
        self.bookmarks = defaultdict(dict)
        self.bookmarks_global = {}
        self._save_persistent_bookmarks()

    def set_bookmark(self, name: str) -> None:
        """Set bookmark at the current cursor position."""
        editor = self.get_editor()
        cursor = editor.textCursor()
        line = cursor.blockNumber()
        col = cursor.position() - cursor.block().position()
        path = self.get_editorstack().get_current_filename()
        info = {"file": path, "line": line, "col": col}
        if name.isupper():
            self.bookmarks_global[name] = info
            self._save_persistent_bookmarks()
        else:
            self.bookmarks[path][name] = info

    def get_bookmark(self, name: str):
        """Return bookmark information for *name* or None."""
        if name.isupper():
            return self.bookmarks_global.get(name)
        current = self.get_editorstack().get_current_filename()
        return self.bookmarks.get(current, {}).get(name)

    def jump_to_bookmark(self, name: str) -> None:
        """Move cursor to bookmark *name* if it exists."""
        if name.isupper():
            info = self.bookmarks_global.get(name)
            if not info:
                return
            file_path = info.get("file")
            line = info.get("line")
            col = info.get("col")
            editor_stack = self.get_editorstack()
            if editor_stack.is_file_opened(file_path) is None:
                self.open_file(file_path)
            editor_stack.set_current_filename(file_path)
            editor = self.get_editor()
            block = editor.document().findBlockByNumber(line)
            if not block.isValid():
                self.bookmarks_global.pop(name, None)
                self._save_persistent_bookmarks()
                return
            pos = block.position() + min(col, block.length() - 1)
            self.set_cursor_pos(pos)
        else:
            current = self.get_editorstack().get_current_filename()
            info = self.bookmarks.get(current, {}).get(name)
            if not info:
                return
            line = info.get("line")
            col = info.get("col")
            editor = self.get_editor()
            block = editor.document().findBlockByNumber(line)
            if not block.isValid():
                self.bookmarks[current].pop(name, None)
                return
            pos = block.position() + min(col, block.length() - 1)
            self.set_cursor_pos(pos)

    def list_bookmarks(self) -> list[tuple[str, dict]]:
        """Return a combined list of local and global bookmarks."""
        current = self.get_editorstack().get_current_filename()
        marks = []
        for name, info in sorted(self.bookmarks.get(current, {}).items()):
            marks.append((name, info))
        for name, info in sorted(self.bookmarks_global.items()):
            marks.append((name, info))
        return marks
