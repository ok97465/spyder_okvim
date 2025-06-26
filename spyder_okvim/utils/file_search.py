# -*- coding: utf-8 -*-
"""Dialog for locating files inside a project tree."""
from __future__ import annotations

# Standard Libraries
import os.path as osp
import re
import sys

# Third Party Libraries
from qtpy.QtCore import QDir, QDirIterator, Qt, Signal
from qtpy.QtGui import QKeyEvent, QStandardItem
from qtpy.QtWidgets import QApplication, QDialog, QLineEdit, QWidget
from spyder.config.gui import get_font

from .list_dialog import PopupTableDialog


def fuzzyfinder(query: str, collection: list[str]) -> list[str]:
    """Fuzzy search.

    Ref: https://github.com/amjith/fuzzyfinder

    Args:
        query: A partial string typically entered by a user.
        collection: Collection of strings filtered by ``query``.

    Returns:
        list: Suggestions narrowed down from ``collection`` using ``query``.

    """
    suggestions = []
    pat = ".*?".join(map(re.escape, query))
    # lookahead regex to manage overlapping matches
    pat = "(?=({0}))".format(pat)
    regex = re.compile(pat, re.IGNORECASE)

    for txt in collection:
        r = list(regex.finditer(txt))
        if r:
            best = min(r, key=lambda x: len(x.group(1)))  # find shortest match
            suggestions.append((len(best.group(1)), txt))

    return [z[-1] for z in sorted(suggestions)]


class FileSearchLineEdit(QLineEdit):
    """Line editor used by :class:`FileSearchDialog`."""

    sig_up_key_pressed = Signal()
    sig_pg_up_key_pressed = Signal()
    sig_pg_half_up_key_pressed = Signal()
    sig_down_key_pressed = Signal()
    sig_pg_down_key_pressed = Signal()
    sig_pg_half_down_key_pressed = Signal()
    sig_enter_key_pressed = Signal()
    sig_esc_key_pressed = Signal()

    def __init__(self, parent: QDialog | None, textChanged) -> None:
        """Initialize the line edit.

        Args:
            parent: Owning dialog.
            textChanged: Slot to invoke when text changes.
        """
        super().__init__(parent, textChanged=textChanged)
        self.dispatcher_nomodifier = {
            Qt.Key_Up: self.sig_up_key_pressed.emit,
            Qt.Key_Down: self.sig_down_key_pressed.emit,
            Qt.Key_Enter: self.sig_enter_key_pressed.emit,
            Qt.Key_Return: self.sig_enter_key_pressed.emit,
            Qt.Key_Escape: self.sig_esc_key_pressed.emit,
            Qt.Key_PageUp: self.sig_pg_up_key_pressed.emit,
            Qt.Key_PageDown: self.sig_pg_down_key_pressed.emit,
        }

        self.dispatcher_ctrl = {
            Qt.Key_P: self.sig_up_key_pressed.emit,
            Qt.Key_B: self.sig_pg_up_key_pressed.emit,
            Qt.Key_U: self.sig_pg_half_up_key_pressed.emit,
            Qt.Key_N: self.sig_down_key_pressed.emit,
            Qt.Key_F: self.sig_pg_down_key_pressed.emit,
            Qt.Key_D: self.sig_pg_half_down_key_pressed.emit,
        }

    def keyPressEvent(self, e: QKeyEvent) -> None:
        """Override Qt method."""
        key = e.key()
        modifier = e.modifiers()
        pressed_ctrl = modifier == Qt.ControlModifier
        pressed_nomodifier = modifier == Qt.NoModifier

        if pressed_nomodifier and key in self.dispatcher_nomodifier.keys():
            self.dispatcher_nomodifier[key]()
            return

        if pressed_ctrl and key in self.dispatcher_ctrl.keys():
            self.dispatcher_ctrl[key]()
            return

        super().keyPressEvent(e)


class FileSearchDialog(PopupTableDialog):
    """Dialog used to select a file path from a project."""

    _MIN_WIDTH = 800
    _MAX_HEIGHT = 600

    def __init__(self, folder: str | None, parent: QWidget | None = None) -> None:
        """Create the dialog and populate file information.

        Args:
            folder: Root directory to search.
            parent: Parent widget for the dialog.
        """
        super().__init__(
            "Path Finder",
            parent=parent,
            headers=["File", "Folder"],
            min_width=self._MIN_WIDTH,
            max_height=self._MAX_HEIGHT,
        )
        font = get_font(font_size_delta=2)

        self.folder = folder
        self.path_selected = ""
        self.path_list = []
        self.results_old = {}
        self.list_viewer.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.list_viewer.setFocusPolicy(Qt.NoFocus)

        # Set edit
        self.edit = FileSearchLineEdit(self, textChanged=self.update_list)
        self.edit.setFont(font)
        self.edit.sig_esc_key_pressed.connect(self.close)
        self.edit.sig_enter_key_pressed.connect(self.enter)

        self.edit.sig_up_key_pressed.connect(lambda: self.prev_row(1))
        self.edit.sig_pg_up_key_pressed.connect(self.pg_up)
        self.edit.sig_pg_half_up_key_pressed.connect(self.pg_half_up)

        self.edit.sig_down_key_pressed.connect(lambda: self.next_row(1))
        self.edit.sig_pg_down_key_pressed.connect(self.pg_down)
        self.edit.sig_pg_half_down_key_pressed.connect(self.pg_half_down)

        self.layout_.insertWidget(0, self.edit)

        self.collect_paths()
        self.update_list()

        self.edit.setFocus()

    def get_selected_path(self) -> str:
        """Return the file path chosen by the user."""
        return self.path_selected

    def collect_paths(self) -> None:
        """Populate the list of discoverable file paths."""
        if self.folder is None or not osp.isdir(self.folder):
            self.edit.setPlaceholderText("The project is not valid.")
        else:
            dir_ = QDir(self.folder)
            it = QDirIterator(
                self.folder,
                ["*.py", "*.txt", "*.md"],
                QDir.Files | QDir.NoDotAndDotDot | QDir.NoSymLinks,
                QDirIterator.Subdirectories,
            )
            while it.hasNext():
                self.path_list.append(dir_.relativeFilePath(it.next()))

        self.results_old[""] = self.path_list

    def update_list(self) -> None:
        """Update listview."""
        query = self.edit.text()
        query = query.replace(" ", "")
        paths = self.results_old.get(query, None)

        if paths is None:
            collections = self.results_old.get(query[:-1], self.path_list)
            paths = fuzzyfinder(query, collections)

        if paths:
            self.list_model.setRowCount(0)
            for path in paths:
                basename = osp.basename(path)
                dirname = osp.dirname(path)
                item = QStandardItem(basename)
                item.setData(path, Qt.UserRole)
                row = [item, QStandardItem(dirname)]
                for it in row:
                    it.setEditable(False)
                self.list_model.appendRow(row)
            self.list_viewer.setCurrentIndex(self.list_model.index(0, 0))
            self.list_viewer.selectRow(0)

    def enter(self) -> None:
        """Select next row in list viewer."""
        idx = self.list_viewer.currentIndex()
        item = self.list_model.item(idx.row(), 0)
        rel_path = item.data(Qt.UserRole) if item else None
        if rel_path and isinstance(self.folder, str):
            path = osp.join(self.folder, rel_path)
            self.path_selected = path
        self.close()
