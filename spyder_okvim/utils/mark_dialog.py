from __future__ import annotations

# Standard Libraries
import os.path as osp

# Third Party Libraries
from qtpy.QtCore import Qt
from qtpy.QtGui import QStandardItem

from .list_dialog import PopupTableDialog


class MarkListDialog(PopupTableDialog):
    """Dialog to display bookmarks and allow jumping to them."""

    _MIN_WIDTH = 800
    _MAX_HEIGHT = 600

    def __init__(self, marks: list[tuple[str, dict]], parent=None) -> None:
        super().__init__(
            "Marks",
            parent=parent,
            headers=["Mark", "Line", "Col", "File", "Text"],
            min_width=self._MIN_WIDTH,
            max_height=self._MAX_HEIGHT,
        )

        self.marks = marks
        self.selected_mark = ""

        self._populate()
        if self.list_model.rowCount() > 0:
            self.list_viewer.setCurrentIndex(self.list_model.index(0, 0))
            self.list_viewer.selectRow(0)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def accept(self) -> None:
        """Store selected mark and close the dialog."""
        row = self.list_viewer.currentIndex().row()
        if 0 <= row < len(self.marks):
            self.selected_mark = self.marks[row][0]
        else:
            self.selected_mark = ""
        super().accept()

    def reject(self) -> None:
        """Clear selected mark when dialog is cancelled."""
        self.selected_mark = ""
        super().reject()

    def _populate(self) -> None:
        self.list_model.setRowCount(0)
        for mark, info in self.marks:
            file_path = info.get("file", "")
            line = info.get("line", 0)
            col = info.get("col", 0)
            text = ""
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    rows = fh.readlines()
                    if 0 <= line < len(rows):
                        text = rows[line].strip()
            except Exception:
                pass
            basename = osp.basename(file_path)
            row = [
                QStandardItem(mark),
                QStandardItem(str(line + 1)),
                QStandardItem(str(col + 1)),
                QStandardItem(basename),
                QStandardItem(text),
            ]
            for i, item in enumerate(row):
                item.setEditable(False)
                if i in (1, 2):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.list_model.appendRow(row)

    def get_selected_mark(self) -> str:
        """Return the mark selected by the user."""
        return self.selected_mark
