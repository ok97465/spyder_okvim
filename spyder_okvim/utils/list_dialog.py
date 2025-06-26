from __future__ import annotations

# Third Party Libraries
from qtpy.QtCore import QStringListModel, Qt
from qtpy.QtGui import QStandardItem, QStandardItemModel
from qtpy.QtWidgets import (
    QDialog,
    QListView,
    QTableView,
    QVBoxLayout,
    QHeaderView,
    QAbstractItemView,
)
from spyder.config.gui import get_font


class PopupListDialog(QDialog):
    """Base dialog for displaying a list of items."""

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        min_width: int | None = None,
        max_height: int = 600,
        font_delta: int = 10,
    ) -> None:
        super().__init__(parent)
        font = get_font(font_size_delta=2)

        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowOpacity(0.95)
        self.setFont(font)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.list_viewer = QListView(self)
        self.list_viewer.setUniformItemSizes(True)
        if min_width:
            self.list_viewer.setMinimumWidth(min_width)
        if max_height:
            self.list_viewer.setFixedHeight(max_height)
        self.list_model = QStringListModel()
        self.list_viewer.setModel(self.list_model)
        self.list_viewer.setFont(font)
        self.list_viewer.setStyleSheet("QListView { color: #f0f0f0; }")

        self.layout_ = QVBoxLayout()
        self.layout_.addWidget(self.list_viewer)
        self.setLayout(self.layout_)

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------
    def get_number_of_visible_lines(self) -> int:
        """Return the number of visible lines in the list."""
        num_lines = 0
        lv = self.list_viewer
        height = lv.visualRect(lv.model().index(0, 0)).height()
        if height > 0:
            num_lines = lv.viewport().height() // height
        return num_lines

    def prev_row(self, stride: int = 1) -> None:
        """Select the previous row."""
        row = self.list_viewer.currentIndex().row() - stride
        row = max(row, 0)
        self.list_viewer.setCurrentIndex(self.list_model.index(row))

    def next_row(self, stride: int = 1) -> None:
        """Select the next row."""
        n_row = self.list_model.rowCount()
        if n_row == 0:
            return
        row = self.list_viewer.currentIndex().row() + stride
        row = min(row, n_row - 1)
        self.list_viewer.setCurrentIndex(self.list_model.index(row))

    def pg_up(self) -> None:
        """Scroll one page up."""
        self.prev_row(self.get_number_of_visible_lines())

    def pg_down(self) -> None:
        """Scroll one page down."""
        self.next_row(self.get_number_of_visible_lines())

    def pg_half_up(self) -> None:
        """Scroll half a page up."""
        self.prev_row(self.get_number_of_visible_lines() // 2)

    def pg_half_down(self) -> None:
        """Scroll half a page down."""
        self.next_row(self.get_number_of_visible_lines() // 2)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # noqa: D401
        """Handle vim-like navigation keys."""
        key = event.key()
        mod = event.modifiers()
        if mod == Qt.ControlModifier and key == Qt.Key_P:
            self.prev_row()
            return
        if mod == Qt.ControlModifier and key == Qt.Key_N:
            self.next_row()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.accept()
            return
        if key == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)


class PopupTableDialog(QDialog):
    """Base dialog for displaying tabular data."""

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        headers: list[str] | None = None,
        min_width: int | None = None,
        max_height: int = 600,
    ) -> None:
        super().__init__(parent)
        font = get_font(font_size_delta=2)

        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowOpacity(0.95)
        self.setFont(font)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.list_viewer = QTableView(self)
        self.list_viewer.setSelectionBehavior(QTableView.SelectRows)
        self.list_viewer.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_viewer.verticalHeader().setVisible(False)
        self.list_viewer.horizontalHeader().setStretchLastSection(True)
        if min_width:
            self.list_viewer.setMinimumWidth(min_width)
        if max_height:
            self.list_viewer.setFixedHeight(max_height)
        self.list_model = QStandardItemModel()
        if headers:
            self.list_model.setHorizontalHeaderLabels(headers)
        self.list_viewer.setModel(self.list_model)
        self.list_viewer.setFont(font)
        self.list_viewer.setStyleSheet("QTableView { color: #f0f0f0; }")
        self.list_viewer.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self.list_viewer.horizontalHeader().setStretchLastSection(True)

        self.layout_ = QVBoxLayout()
        self.layout_.addWidget(self.list_viewer)
        self.setLayout(self.layout_)

    # ------------------------------------------------------------------
    # Navigation helpers (same as :class:`PopupListDialog`)
    # ------------------------------------------------------------------
    def get_number_of_visible_lines(self) -> int:
        """Return the number of visible lines in the table."""
        num_lines = 0
        lv = self.list_viewer
        height = lv.visualRect(self.list_model.index(0, 0)).height()
        if height > 0:
            num_lines = lv.viewport().height() // height
        return num_lines

    def prev_row(self, stride: int = 1) -> None:
        """Select the previous row."""
        row = self.list_viewer.currentIndex().row() - stride
        row = max(row, 0)
        self.list_viewer.setCurrentIndex(self.list_model.index(row, 0))
        self.list_viewer.selectRow(row)

    def next_row(self, stride: int = 1) -> None:
        """Select the next row."""
        n_row = self.list_model.rowCount()
        if n_row == 0:
            return
        row = self.list_viewer.currentIndex().row() + stride
        row = min(row, n_row - 1)
        self.list_viewer.setCurrentIndex(self.list_model.index(row, 0))
        self.list_viewer.selectRow(row)

    def pg_up(self) -> None:
        """Scroll one page up."""
        self.prev_row(self.get_number_of_visible_lines())

    def pg_down(self) -> None:
        """Scroll one page down."""
        self.next_row(self.get_number_of_visible_lines())

    def pg_half_up(self) -> None:
        """Scroll half a page up."""
        self.prev_row(self.get_number_of_visible_lines() // 2)

    def pg_half_down(self) -> None:
        """Scroll half a page down."""
        self.next_row(self.get_number_of_visible_lines() // 2)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # noqa: D401
        """Handle vim-like navigation keys."""
        key = event.key()
        mod = event.modifiers()
        if mod == Qt.ControlModifier and key == Qt.Key_P:
            self.prev_row()
            return
        if mod == Qt.ControlModifier and key == Qt.Key_N:
            self.next_row()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.accept()
            return
        if key == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
