from __future__ import annotations

# Standard Libraries
import os.path as osp

# Third Party Libraries
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QStandardItem

from .list_dialog import PopupTableDialog


class JumpListDialog(PopupTableDialog):
    """Dialog to display the jump list."""

    _MIN_WIDTH = 800
    _MAX_HEIGHT = 600

    def __init__(self, vim_status, parent=None) -> None:
        super().__init__(
            "Jumps",
            parent=parent,
            headers=["#", "Line", "Col", "File", "Text"],
            min_width=self._MIN_WIDTH,
            max_height=self._MAX_HEIGHT,
        )

        self.vim_status = vim_status
        self.jump_list = vim_status.jump_list

        self._populate()
        self.update_current_row()

        # Forward key events from the list viewer to this dialog
        self.list_viewer.installEventFilter(self)

        # When closed return focus to command line
        self.finished.connect(lambda *_: self.vim_status.set_focus_to_vim())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_line_info(self, file_path: str, pos: int) -> tuple[int, int, str]:
        """Return line, column and text for *pos* in *file_path*."""
        line = col = 0
        text = ""
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                data = fh.read()
            line = data.count("\n", 0, pos)
            line_start = data.rfind("\n", 0, pos) + 1
            line_end = data.find("\n", pos)
            if line_end == -1:
                line_end = len(data)
            col = pos - line_start
            text = data[line_start:line_end].strip()
        except Exception:
            pass
        return line + 1, col + 1, text

    def _populate(self) -> None:
        self.list_model.setRowCount(0)
        for i, jump in enumerate(self.jump_list.jumps, start=1):
            line, col, text = self._get_line_info(jump.file, jump.pos)
            basename = osp.basename(jump.file)
            mark = ">" if i == self.jump_list.index else ""
            row = [
                QStandardItem(f"{mark}{i}"),
                QStandardItem(str(line)),
                QStandardItem(str(col)),
                QStandardItem(basename),
                QStandardItem(text),
            ]
            for idx, item in enumerate(row):
                item.setEditable(False)
                if idx in (1, 2):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.list_model.appendRow(row)

    def update_current_row(self) -> None:
        row = max(0, self.jump_list.index - 1)
        if self.list_model.rowCount() > 0:
            self.list_viewer.setCurrentIndex(self.list_model.index(row, 0))
            self.list_viewer.selectRow(row)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:
        mod = event.modifiers()
        key = event.key()
        if mod == Qt.ControlModifier and key == Qt.Key_O:
            self.vim_status.jump_backward()
            self._populate()
            self.update_current_row()
            return
        if mod == Qt.ControlModifier and key == Qt.Key_I:
            self.vim_status.jump_forward()
            self._populate()
            self.update_current_row()
            return
        if mod == Qt.ControlModifier and key in (Qt.Key_N, Qt.Key_P):
            # Prevent `Ctrl+n`/`Ctrl+p` from navigating the list
            # (these shortcuts are used in other dialogs)
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        """Handle shortcut events forwarded from the list viewer."""
        if obj is self.list_viewer and event.type() in (
            QEvent.ShortcutOverride,
            QEvent.KeyPress,
        ):
            self.keyPressEvent(event)
            return True
        return super().eventFilter(obj, event)
