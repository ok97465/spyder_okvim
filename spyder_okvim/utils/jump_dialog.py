from __future__ import annotations

# Standard Libraries
import os.path as osp

# Third Party Libraries
from qtpy.QtCore import Qt

from .list_dialog import PopupListDialog


class JumpListDialog(PopupListDialog):
    """Dialog to display the jump list."""

    _MIN_WIDTH = 400
    _MAX_HEIGHT = 300

    def __init__(self, vim_status, parent=None) -> None:
        super().__init__(
            "Jumps", parent=parent, width=self._MIN_WIDTH, max_height=self._MAX_HEIGHT
        )

        self.vim_status = vim_status
        self.jump_list = vim_status.jump_list

        self._populate()
        self.update_current_row()

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
        items: list[str] = []
        for i, jump in enumerate(self.jump_list.jumps, start=1):
            line, col, text = self._get_line_info(jump.file, jump.pos)
            basename = osp.basename(jump.file)
            mark = ">" if i == self.jump_list.index else " "
            items.append(f"{mark}{i:>3} {line:>5} {col:>4} {basename} {text}")
        self.list_model.setStringList(items)

    def update_current_row(self) -> None:
        row = max(0, self.jump_list.index - 1)
        if self.list_model.rowCount() > 0:
            self.list_viewer.setCurrentIndex(self.list_model.index(row))

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
        super().keyPressEvent(event)
