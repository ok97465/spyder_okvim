"""Build jump-list display snapshots and render them through navigation callbacks."""

from __future__ import annotations

# Standard Libraries
import os.path as osp
from collections.abc import Callable
from dataclasses import dataclass

# Third Party Libraries
from qtpy.QtCore import Qt
from qtpy.QtGui import QStandardItem

from .jump_list import JumpList
from .list_dialog import PopupTableDialog


@dataclass(frozen=True)
class JumpRow:
    """One display row with one-based sequence, line and column numbers."""

    number: int
    line_number: int
    column_number: int
    filename: str
    text: str


@dataclass(frozen=True)
class JumpSnapshot:
    """Prepared rows and the one-based history index; zero denotes an empty list."""

    rows: tuple[JumpRow, ...]
    current_index: int


def read_jump_location(file_path: str, position: int) -> tuple[int, int, str]:
    """Return one-based display coordinates and line text for a stored position.

    Preserve the existing metadata calculation, which interprets ``position``
    as a Python string index. Jump navigation still uses the original Qt offset;
    reconciling non-BMP display coordinates is a separate behavior change.
    Unreadable files retain the existing (1, 1, empty text) display fallback.
    """
    line = column = 0
    text = ""
    try:
        with open(file_path, "r", encoding="utf-8") as stream:
            data = stream.read()
        line = data.count("\n", 0, position)
        line_start = data.rfind("\n", 0, position) + 1
        line_end = data.find("\n", position)
        if line_end == -1:
            line_end = len(data)
        column = position - line_start
        text = data[line_start:line_end].strip()
    except Exception:
        pass
    return line + 1, column + 1, text


def build_jump_snapshot(
    jump_list: JumpList,
    *,
    read_location: Callable[[str, int], tuple[int, int, str]] = read_jump_location,
) -> JumpSnapshot:
    """Read metadata outside the dialog and freeze the current history order.

    ``read_location`` may return prepared or in-memory metadata. History remains
    owned by the caller; the snapshot contains no mutable list or editor object.
    """
    rows = []
    for number, jump in enumerate(jump_list.jumps, start=1):
        line, column, text = read_location(jump.file, jump.pos)
        rows.append(JumpRow(number, line, column, osp.basename(jump.file), text))
    return JumpSnapshot(tuple(rows), jump_list.index)


class JumpListDialog(PopupTableDialog):
    """Display a prepared snapshot and request host navigation via callbacks.

    ``on_back`` and ``on_forward`` perform navigation and return a fresh snapshot.
    ``on_finished`` restores the caller's focus without exposing its widget or
    Vim state to the dialog. All callbacks run synchronously on the GUI thread.
    """

    _MIN_WIDTH = 800
    _MAX_HEIGHT = 600

    def __init__(
        self,
        snapshot: JumpSnapshot,
        parent=None,
        *,
        on_back: Callable[[], JumpSnapshot] | None = None,
        on_forward: Callable[[], JumpSnapshot] | None = None,
        on_select: Callable[[int], None] | None = None,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            "Jumps",
            parent=parent,
            headers=["#", "Line", "Col", "File", "Text"],
            min_width=self._MIN_WIDTH,
            max_height=self._MAX_HEIGHT,
        )
        self._on_back = on_back
        self._on_forward = on_forward
        self._on_select = on_select
        self.selected_index = None
        self.set_navigation_help(
            "jump to selected location",
            "Ctrl+O / Ctrl+I: move through history immediately",
        )
        self.set_snapshot(snapshot)
        if on_finished is not None:
            self.finished.connect(lambda *_: on_finished())

    def set_snapshot(self, snapshot: JumpSnapshot) -> None:
        """Replace display metadata and highlight the current one-based index."""
        self.snapshot = snapshot
        self._populate()
        self.update_current_row()

    def _populate(self) -> None:
        self.list_model.setRowCount(0)
        for entry in self.snapshot.rows:
            mark = ">" if entry.number == self.snapshot.current_index else ""
            row = [
                QStandardItem(f"{mark}{entry.number}"),
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

    def update_current_row(self) -> None:
        """Select the row corresponding to the snapshot's history index."""
        row = max(0, self.snapshot.current_index - 1)
        if self.list_model.rowCount() > 0:
            self.list_viewer.setCurrentIndex(self.list_model.index(row, 0))
            self.list_viewer.selectRow(row)

    def keyPressEvent(self, event) -> None:
        """Keep immediate history movement separate from row selection."""
        modifiers = event.modifiers()
        key = event.key()
        if modifiers == Qt.ControlModifier and key == Qt.Key_O:
            event.accept()
            if self._on_back is not None:
                self.set_snapshot(self._on_back())
            return
        if modifiers == Qt.ControlModifier and key == Qt.Key_I:
            event.accept()
            if self._on_forward is not None:
                self.set_snapshot(self._on_forward())
            return
        super().keyPressEvent(event)

    @staticmethod
    def _handles_key(event):
        return PopupTableDialog._handles_key(event) or (
            event.modifiers() == Qt.ControlModifier
            and event.key() in (Qt.Key_O, Qt.Key_I)
        )

    def accept(self):
        """Apply the selected location once, independently of history shortcuts."""
        row = self.list_viewer.currentIndex().row()
        if 0 <= row < len(self.snapshot.rows):
            self.selected_index = self.snapshot.rows[row].number
            if self._on_select is not None:
                self._on_select(self.selected_index)
        super().accept()

    def reject(self):
        self.selected_index = None
        super().reject()
