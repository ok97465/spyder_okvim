"""Shared keyboard, mouse and layout behavior for navigation pickers."""

from __future__ import annotations

# Third Party Libraries
from qtpy.QtCore import QEvent, QPoint, QRect, QStringListModel, Qt, QTimer
from qtpy.QtGui import QStandardItemModel
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QHeaderView,
    QLabel,
    QLayout,
    QListView,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
)
from spyder.config.gui import get_font


class _PopupDialog(QDialog):
    """Keep picker input and sizing in one place, independent of its contents."""

    def __init__(self, title, parent, *, min_width, max_height):
        super().__init__(parent)
        self._preferred_width = min_width or 560
        self._max_list_height = max_height or 600
        self._input_widget = None
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.timeout.connect(self.update_geometry)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setFont(get_font(font_size_delta=2))
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAccessibleName(title)
        self.setObjectName("okvimPicker")
        # Palette roles update with the host theme, including inactive selection.
        self.setStyleSheet(
            "QDialog#okvimPicker { background: palette(window); "
            "border: 1px solid palette(mid); }"
        )
        self.layout_ = QVBoxLayout(self)
        self.layout_.setSizeConstraint(QLayout.SetNoConstraint)
        self.help_label = QLabel(self)
        self.help_label.setWordWrap(True)
        self.help_label.setMinimumSize(0, 0)
        self.help_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.help_label.setAccessibleName("Picker keyboard help")
        self.set_navigation_help("open")

    def _setup_view(self):
        view = self.list_viewer
        view.setModel(self.list_model)
        view.setFont(self.font())
        view.setPalette(self.palette())
        view.setMinimumSize(0, 0)
        view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        view.setSelectionMode(QAbstractItemView.SingleSelection)
        view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        view.setTextElideMode(Qt.ElideMiddle)
        view.setAccessibleName(f"{self.windowTitle()} results")
        view.setAccessibleDescription(self.help_label.text())
        view.installEventFilter(self)
        view.clicked.connect(self._restore_input_focus)
        view.doubleClicked.connect(self._activate_index)
        self.layout_.addWidget(view)
        self.layout_.addWidget(self.help_label)
        for signal in (
            self.list_model.rowsInserted,
            self.list_model.rowsRemoved,
            self.list_model.modelReset,
        ):
            signal.connect(self._update_geometry_if_visible)

    def set_navigation_help(self, action, extra=""):
        """Describe the action Enter performs for this specific picker."""
        text = f"↑/↓ or Ctrl+N/P: select · Enter / double-click: {action} · Esc: cancel"
        self.help_label.setText(f"{text}\n{extra}" if extra else text)
        self.setToolTip(self.help_label.text())
        if hasattr(self, "list_viewer"):
            self.list_viewer.setAccessibleDescription(self.help_label.text())

    def set_input_widget(self, widget):
        """Let mouse selection preserve an optional search field's focus."""
        self._input_widget = widget
        widget.installEventFilter(self)
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.list_viewer.setFocusPolicy(Qt.NoFocus)

    def _restore_input_focus(self, *_):
        if self._input_widget is not None:
            self._input_widget.setFocus()

    def _activate_index(self, index):
        if index.isValid():
            self.list_viewer.setCurrentIndex(index)
            self.accept()

    def _select_row(self, row):
        count = self.list_model.rowCount()
        if not count:
            return
        row = max(0, min(row, count - 1))
        index = self.list_model.index(row, 0)
        self.list_viewer.setCurrentIndex(index)
        if isinstance(self.list_viewer, QTableView):
            self.list_viewer.selectRow(row)
        self.list_viewer.scrollTo(index)

    def get_number_of_visible_lines(self):
        height = self.list_viewer.sizeHintForRow(0)
        return max(1, self.list_viewer.viewport().height() // max(1, height))

    def prev_row(self, stride=1):
        self._select_row(self.list_viewer.currentIndex().row() - max(1, stride))

    def next_row(self, stride=1):
        self._select_row(self.list_viewer.currentIndex().row() + max(1, stride))

    def pg_up(self):
        self.prev_row(self.get_number_of_visible_lines())

    def pg_down(self):
        self.next_row(self.get_number_of_visible_lines())

    def pg_half_up(self):
        self.prev_row(self.get_number_of_visible_lines() // 2)

    def pg_half_down(self):
        self.next_row(self.get_number_of_visible_lines() // 2)

    @staticmethod
    def _handles_key(event):
        key, modifiers = event.key(), event.modifiers()
        if modifiers == Qt.ControlModifier:
            return key in (Qt.Key_N, Qt.Key_P, Qt.Key_F, Qt.Key_B, Qt.Key_D, Qt.Key_U)
        return modifiers == Qt.NoModifier and key in (
            Qt.Key_Up,
            Qt.Key_Down,
            Qt.Key_PageUp,
            Qt.Key_PageDown,
            Qt.Key_Return,
            Qt.Key_Enter,
            Qt.Key_Escape,
        )

    def eventFilter(self, obj, event):
        """Reserve shortcuts once; perform their action only on KeyPress."""
        if (
            (obj is self.list_viewer or obj is self._input_widget)
            and event.type() in (QEvent.ShortcutOverride, QEvent.KeyPress)
            and self._handles_key(event)
        ):
            event.accept()
            if event.type() == QEvent.KeyPress:
                self.keyPressEvent(event)
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        plain = {
            Qt.Key_Up: self.prev_row,
            Qt.Key_Down: self.next_row,
            Qt.Key_PageUp: self.pg_up,
            Qt.Key_PageDown: self.pg_down,
            Qt.Key_Return: self.accept,
            Qt.Key_Enter: self.accept,
            Qt.Key_Escape: self.reject,
        }
        control = {
            Qt.Key_P: self.prev_row,
            Qt.Key_N: self.next_row,
            Qt.Key_B: self.pg_up,
            Qt.Key_F: self.pg_down,
            Qt.Key_U: self.pg_half_up,
            Qt.Key_D: self.pg_half_down,
        }
        keys = control if event.modifiers() == Qt.ControlModifier else plain
        action = keys.get(event.key()) if self._handles_key(event) else None
        if action is not None:
            event.accept()
            action()
            return
        super().keyPressEvent(event)

    def _available_geometry(self):
        parent = self.parentWidget()
        parent_rect = None
        anchor = self.pos()
        if parent is not None and parent.isVisible():
            parent_rect = QRect(parent.mapToGlobal(QPoint(0, 0)), parent.size())
            if not parent_rect.contains(anchor):
                anchor = parent_rect.center()
        screen = QApplication.screenAt(anchor) or self.screen()
        available = screen.availableGeometry()
        if parent_rect is not None:
            intersection = available.intersected(parent_rect)
            if intersection.isValid():
                available = intersection
        return available.adjusted(8, 8, -8, -8)

    def update_geometry(self):
        """Fit rows and preferred width to the owning window and screen."""
        available = self._available_geometry()
        if available.width() <= 0 or available.height() <= 0:
            return
        # Keep the result list usable in tiny splits; help remains in tooltips
        # and accessible descriptions when there is no room for the footer.
        self.help_label.setVisible(
            available.width() >= 280 and available.height() >= 200
        )
        row_height = max(
            self.list_viewer.sizeHintForRow(0), self.fontMetrics().height() + 8
        )
        header_height = (
            self.list_viewer.horizontalHeader().sizeHint().height()
            if isinstance(self.list_viewer, QTableView)
            else 0
        )
        list_height = min(
            self._max_list_height,
            row_height * max(1, self.list_model.rowCount()) + header_height + 4,
        )
        width = min(self._preferred_width, available.width())
        self.resize(width, min(self.sizeHint().height(), available.height()))
        # Calculate wrapping after choosing the actual width.
        self.layout_.activate()
        extra_height = (
            self.layout_.sizeHint().height() - self.list_viewer.sizeHint().height()
        )
        self.resize(width, min(list_height + extra_height, available.height()))
        x = max(available.left(), min(self.x(), available.right() - self.width() + 1))
        y = max(available.top(), min(self.y(), available.bottom() - self.height() + 1))
        self.move(x, y)

    def _update_geometry_if_visible(self, *_):
        if self.isVisible() and not self._geometry_timer.isActive():
            self._geometry_timer.start(0)

    def showEvent(self, event):
        self.update_geometry()
        super().showEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.PaletteChange, QEvent.ApplicationPaletteChange):
            # Styled parents do not always propagate their palette to Qt views.
            if hasattr(self, "list_viewer"):
                self.list_viewer.setPalette(self.palette())


class PopupListDialog(_PopupDialog):
    """Picker for a simple list of strings."""

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        min_width: int | None = None,
        max_height: int = 600,
    ) -> None:
        super().__init__(title, parent, min_width=min_width, max_height=max_height)
        self.list_viewer = QListView(self)
        self.list_viewer.setUniformItemSizes(True)
        self.list_model = QStringListModel(self)
        self._setup_view()


class PopupTableDialog(_PopupDialog):
    """Picker for read-only rows of metadata."""

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        headers: list[str] | None = None,
        min_width: int | None = None,
        max_height: int = 600,
    ) -> None:
        super().__init__(title, parent, min_width=min_width, max_height=max_height)
        self.list_viewer = QTableView(self)
        self.list_viewer.setSelectionBehavior(QTableView.SelectRows)
        self.list_viewer.verticalHeader().setVisible(False)
        self.list_model = QStandardItemModel(self)
        if headers:
            self.list_model.setHorizontalHeaderLabels(headers)
        self._setup_view()
        header = self.list_viewer.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
