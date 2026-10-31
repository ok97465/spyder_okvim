"""Prepare immutable mark rows and display them without reading files in Qt code."""

from __future__ import annotations

# Standard Libraries
import os.path as osp
from collections.abc import Callable, Iterable
from dataclasses import dataclass

# Third Party Libraries
from qtpy.QtCore import Qt
from qtpy.QtGui import QStandardItem

from .bookmark_manager import BookmarkLocation
from .list_dialog import PopupTableDialog


@dataclass(frozen=True)
class MarkRow:
    """Display metadata with one-based line/column numbers and no editor reference."""

    name: str
    line_number: int
    column_number: int
    filename: str
    text: str


def read_mark_line(file_path: str, block_number: int) -> str:
    """Read a zero-based block for display, returning empty text on failure."""
    try:
        with open(file_path, "r", encoding="utf-8") as stream:
            lines = stream.readlines()
        return lines[block_number].strip() if 0 <= block_number < len(lines) else ""
    except Exception:
        return ""


def build_mark_rows(
    marks: Iterable[tuple[str, BookmarkLocation]],
    *,
    read_line: Callable[[str, int], str] = read_mark_line,
) -> tuple[MarkRow, ...]:
    """Prepare display rows before opening a dialog, preserving the given order.

    Stored blocks and UTF-16 columns are zero-based; display coordinates are
    one-based. ``read_line`` can supply metadata from a prepared snapshot or a
    temporary store, so rendering requires neither files nor host navigation.
    """
    rows = []
    for name, location in marks:
        file_path = location.get("file", "")
        block_number = location.get("line", 0)
        column = location.get("col", 0)
        rows.append(
            MarkRow(
                name,
                block_number + 1,
                column + 1,
                osp.basename(file_path),
                read_line(file_path, block_number),
            )
        )
    return tuple(rows)


class MarkListDialog(PopupTableDialog):
    """Display prepared marks and return a selected name for the caller to apply."""

    _MIN_WIDTH = 800
    _MAX_HEIGHT = 600

    def __init__(self, rows: Iterable[MarkRow], parent=None) -> None:
        super().__init__(
            "Marks",
            parent=parent,
            headers=["Mark", "Line", "Col", "File", "Text"],
            min_width=self._MIN_WIDTH,
            max_height=self._MAX_HEIGHT,
        )
        self.rows = tuple(rows)
        self.selected_mark = ""
        self.set_navigation_help("jump to mark")
        self._populate()
        if self.list_model.rowCount() > 0:
            self.list_viewer.setCurrentIndex(self.list_model.index(0, 0))
            self.list_viewer.selectRow(0)

    def accept(self) -> None:
        """Store the selected mark name without performing navigation."""
        row = self.list_viewer.currentIndex().row()
        self.selected_mark = self.rows[row].name if 0 <= row < len(self.rows) else ""
        super().accept()

    def reject(self) -> None:
        """Clear the selected mark when the dialog is cancelled."""
        self.selected_mark = ""
        super().reject()

    def _populate(self) -> None:
        self.list_model.setRowCount(0)
        for entry in self.rows:
            row = [
                QStandardItem(entry.name),
                QStandardItem(str(entry.line_number)),
                QStandardItem(str(entry.column_number)),
                QStandardItem(entry.filename),
                QStandardItem(entry.text),
            ]
            for column, item in enumerate(row):
                item.setEditable(False)
                item.setToolTip(item.text())
                if column in (1, 2):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.list_model.appendRow(row)

    def get_selected_mark(self) -> str:
        """Return the selected mark name, or an empty string after cancellation."""
        return self.selected_mark
