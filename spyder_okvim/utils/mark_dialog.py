from __future__ import annotations

# Standard Libraries
import os.path as osp

# Third Party Libraries
from qtpy.QtCore import Qt

from .list_dialog import PopupListDialog


class MarkListDialog(PopupListDialog):
    """Dialog to display bookmarks and allow jumping to them."""

    _MIN_WIDTH = 800
    _MAX_HEIGHT = 600

    def __init__(self, marks: list[tuple[str, dict]], parent=None) -> None:
        super().__init__(
            "Marks",
            parent=parent,
            min_width=self._MIN_WIDTH,
            max_height=self._MAX_HEIGHT,
        )

        self.marks = marks
        self.selected_mark = ""

        self._populate()
        if self.list_model.rowCount() > 0:
            self.list_viewer.setCurrentIndex(self.list_model.index(0))

    def _populate(self) -> None:
        items: list[str] = []
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
            items.append(
                f"{mark:>2} | {line + 1:>5} | {col + 1:>4} | {basename} | {text}"
                )
        self.list_model.setStringList(items)

    def get_selected_mark(self) -> str:
        row = self.list_viewer.currentIndex().row()
        if 0 <= row < len(self.marks):
            return self.marks[row][0]
        return ""
