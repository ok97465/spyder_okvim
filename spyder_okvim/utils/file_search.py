# -*- coding: utf-8 -*-
"""Dialog for locating files inside a project tree."""
from __future__ import annotations

# Standard Libraries
import os.path as osp
import re

# Third Party Libraries
from qtpy.QtCore import QDir, QDirIterator, QModelIndex, Qt
from qtpy.QtGui import QStandardItem
from qtpy.QtWidgets import QLabel, QLineEdit, QWidget

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
        best = min(regex.finditer(txt), key=lambda x: len(x.group(1)), default=None)
        if best is not None:
            suggestions.append((len(best.group(1)), txt))

    return [z[-1] for z in sorted(suggestions)]


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
        self.folder = folder
        self.path_selected = ""
        self.path_list = []
        self.results_old = {}

        # Set edit
        self.edit = QLineEdit(self, textChanged=self.update_list)
        self.edit.setFont(self.font())
        self.edit.setAccessibleName("Path Finder search")
        self.edit.setAccessibleDescription("Fuzzy search files in the current project")
        self.set_input_widget(self.edit)
        self.set_navigation_help("open file")
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        self.status_label.setAccessibleName("Path Finder search status")

        self.layout_.insertWidget(0, self.edit)
        self.layout_.insertWidget(1, self.status_label)

        self.collect_paths()
        self.update_list()

        self.edit.setFocus()

    def get_selected_path(self) -> str:
        """Return the file path chosen by the user."""
        return self.path_selected

    def collect_paths(self) -> None:
        """Populate the list of discoverable file paths."""
        self.path_list.clear()
        self.results_old.clear()
        self._valid_project = bool(self.folder and osp.isdir(self.folder))
        if not self._valid_project:
            self.edit.setPlaceholderText("Open a project to find files")
        else:
            self.edit.setPlaceholderText("Search project files")
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
        self.path_selected = ""
        self.list_viewer.clearSelection()
        self.list_viewer.setCurrentIndex(QModelIndex())
        self.list_model.setRowCount(0)
        query = self.edit.text()
        query = query.replace(" ", "")
        paths = self.results_old.get(query, None)

        if paths is None:
            collections = self.results_old.get(query[:-1], self.path_list)
            paths = fuzzyfinder(query, collections)
            self.results_old[query] = paths

        if paths:
            for path in paths:
                basename = osp.basename(path)
                dirname = osp.dirname(path)
                item = QStandardItem(basename)
                item.setData(path, Qt.UserRole)
                row = [item, QStandardItem(dirname)]
                for it in row:
                    it.setEditable(False)
                    it.setToolTip(osp.join(self.folder, path))
                self.list_model.appendRow(row)
            self.list_viewer.setCurrentIndex(self.list_model.index(0, 0))
            self.list_viewer.selectRow(0)
            message = f"{len(paths)} results"
        elif not self._valid_project:
            message = (
                "No project is open."
                if self.folder is None
                else "Project folder is unavailable."
            )
        elif not self.path_list:
            message = "No files in this project."
        else:
            message = f"No results for “{self.edit.text()}”"
        self.status_label.setText(message)
        self.status_label.setAccessibleDescription(message)

    def accept(self) -> None:
        """Open only a valid row from the current result set."""
        idx = self.list_viewer.currentIndex()
        item = self.list_model.item(idx.row(), 0) if idx.isValid() else None
        rel_path = item.data(Qt.UserRole) if item else None
        if rel_path and isinstance(self.folder, str):
            path = osp.join(self.folder, rel_path)
            self.path_selected = path
            super().accept()

    def reject(self) -> None:
        self.path_selected = ""
        super().reject()
