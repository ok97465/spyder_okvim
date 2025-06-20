# -*- coding: utf-8 -*-
"""Filesystem helper used by EasyMotion and search features."""
from __future__ import annotations

# Standard library imports
import os.path as osp
import re
import sys

# Third party imports
from qtpy.QtCore import QDir, QDirIterator, QStringListModel, Qt, Signal
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import (
    QApplication,
    QDialog,
    QLineEdit,
    QListView,
    QVBoxLayout,
    QWidget,
)
from spyder.config.gui import get_font


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


class PathFinderEdit(QLineEdit):
    """Line editor for input of path finder."""

    sig_up_key_pressed = Signal()
    sig_pg_up_key_pressed = Signal()
    sig_pg_half_up_key_pressed = Signal()
    sig_down_key_pressed = Signal()
    sig_pg_down_key_pressed = Signal()
    sig_pg_half_down_key_pressed = Signal()
    sig_enter_key_pressed = Signal()
    sig_esc_key_pressed = Signal()

    def __init__(self, parent: QDialog | None, textChanged) -> None:
        """Init."""
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


class PathFinder(QDialog):
    """Search path of files in the folder."""

    _MIN_WIDTH = 800
    _MAX_HEIGHT = 600

    def __init__(self, folder: str | None, parent: QWidget | None = None) -> None:
        """Init."""
        super().__init__(parent)
        font = get_font()

        self.folder = folder
        self.path_selected = ""
        self.path_list = []
        self.results_old = {}
        self.setWindowTitle("Path Finder")
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowOpacity(0.95)
        self.setFixedHeight(self._MAX_HEIGHT)
        self.setFont(font)

        # Set List widget
        self.list_viewer = QListView(self)
        self.list_viewer.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.list_viewer.setFocusPolicy(Qt.NoFocus)
        self.list_viewer.setFixedWidth(self._MIN_WIDTH)
        self.list_viewer.setUniformItemSizes(True)
        self.list_model = QStringListModel()
        self.list_viewer.setModel(self.list_model)
        self.list_viewer.setFont(font)

        # Set edit
        self.edit = PathFinderEdit(self, textChanged=self.update_list)
        self.edit.setFont(font)
        self.edit.sig_esc_key_pressed.connect(self.close)
        self.edit.sig_enter_key_pressed.connect(self.enter)

        self.edit.sig_up_key_pressed.connect(lambda: self.prev_row(1))
        self.edit.sig_pg_up_key_pressed.connect(self.pg_up)
        self.edit.sig_pg_half_up_key_pressed.connect(self.pg_half_up)

        self.edit.sig_down_key_pressed.connect(lambda: self.next_row(1))
        self.edit.sig_pg_down_key_pressed.connect(self.pg_down)
        self.edit.sig_pg_half_down_key_pressed.connect(self.pg_half_down)

        layout = QVBoxLayout()
        layout.addWidget(self.edit)
        layout.addWidget(self.list_viewer)

        self.setLayout(layout)

        self.get_path_list()
        self.update_list()

        self.edit.setFocus()

    def get_path_selected(self) -> str:
        """Get path selected."""
        return self.path_selected

    def get_number_of_visible_lines(self) -> int:
        """Get the number of visible lines in list."""
        num_lines = 0
        lv = self.list_viewer
        height = lv.visualRect(lv.model().index(0, 0)).height()
        if height > 0:
            num_lines = lv.viewport().height() // height
        return num_lines

    def get_path_list(self) -> None:
        """Get path of files including subdirectories."""
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
            self.list_model.setStringList(paths)
            self.list_viewer.setCurrentIndex(self.list_model.index(0))

    def prev_row(self, stride: int = 1) -> None:
        """Select prev row in list viewer."""
        prev_row = self.list_viewer.currentIndex().row() - stride
        prev_row = max([prev_row, 0])
        self.list_viewer.setCurrentIndex(self.list_model.index(prev_row))

    def next_row(self, stride: int = 1) -> None:
        """Select next row in list viewer."""
        n_row = self.list_model.rowCount()
        if n_row == 0:
            return
        next_row = self.list_viewer.currentIndex().row() + stride
        next_row = min([next_row, n_row - 1])
        self.list_viewer.setCurrentIndex(self.list_model.index(next_row))

    def pg_up(self) -> None:
        """Scroll windows 1page backwards."""
        n_line = self.get_number_of_visible_lines()
        self.prev_row(n_line)

    def pg_down(self) -> None:
        """Scroll windows 1page forwards."""
        n_line = self.get_number_of_visible_lines()
        self.next_row(n_line)

    def pg_half_up(self) -> None:
        """Scroll windows half page backwards."""
        n_line = self.get_number_of_visible_lines()
        self.prev_row(n_line // 2)

    def pg_half_down(self) -> None:
        """Scroll windows half page forwards."""
        n_line = self.get_number_of_visible_lines()
        self.next_row(n_line // 2)

    def enter(self) -> None:
        """Select next row in list viewer."""
        idx = self.list_viewer.currentIndex()
        rel_path = idx.data(Qt.DisplayRole)
        if rel_path and isinstance(self.folder, str):
            path = osp.join(self.folder, rel_path)
            self.path_selected = path
        self.close()
