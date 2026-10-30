"""History candidates and a non-focusable command-line history panel."""

# Third Party Libraries
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QLayout,
    QListWidget,
    QVBoxLayout,
)
from spyder.utils.palette import SpyderPalette


def history_candidates(history, prefix):
    """Return unique literal prefix matches, with the latest entry first.

    The caller supplies one history kind and the editable body, so prompt
    parsing and the stored history's duplicate policy remain unchanged.
    """
    candidates = []
    seen = set()
    for body in reversed(history):
        if body not in seen and body.startswith(prefix):
            candidates.append(body)
            seen.add(body)
    return candidates


class HistoryPopup(QFrame):
    """Display scrollable history rows without taking command-line focus."""

    MAX_VISIBLE_ROWS = 8

    def __init__(self, viewport):
        super().__init__(viewport)
        self.setObjectName("commandlineHistoryPopup")
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._candidates = ()

        self.header = QLabel("History", self)
        self.header.setTextFormat(Qt.PlainText)
        self.header.setFocusPolicy(Qt.NoFocus)
        self.header.setMinimumSize(0, 0)

        self.list_widget = QListWidget(self)
        self.list_widget.setObjectName("commandlineHistoryList")
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        self.list_widget.viewport().setFocusPolicy(Qt.NoFocus)
        self.list_widget.verticalScrollBar().setFocusPolicy(Qt.NoFocus)
        self.list_widget.horizontalScrollBar().setFocusPolicy(Qt.NoFocus)
        self.list_widget.setFrameShape(QFrame.NoFrame)
        self.list_widget.setMinimumSize(0, 0)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self.list_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setTextElideMode(Qt.ElideRight)
        self.list_widget.setUniformItemSizes(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 5, 6, 5)
        layout.setSpacing(3)
        layout.setSizeConstraint(QLayout.SetNoConstraint)
        layout.addWidget(self.header)
        layout.addWidget(self.list_widget)
        self.hide()

    def set_candidates(self, candidates):
        """Replace the rows and clear selection, keeping their literal text."""
        candidates = tuple(candidates)
        if candidates != self._candidates:
            self._candidates = candidates
            self.list_widget.clear()
            self.list_widget.addItems(candidates)
        self.select(None)
        self.list_widget.verticalScrollBar().setValue(0)

    def select(self, index):
        """Highlight a row and scroll it into view, or clear the highlight."""
        if index is None:
            self.list_widget.setCurrentRow(-1)
            self.list_widget.clearSelection()
            return
        self.list_widget.setCurrentRow(index)
        item = self.list_widget.item(index)
        if item is not None:
            self.list_widget.scrollToItem(item)

    def refresh_appearance(self, font):
        """Follow the command line's appearance and report any actual change."""
        previous_font = self.font()
        self.setFont(font)
        stylesheet = (
            "QFrame#commandlineHistoryPopup {"
            f"background-color: {SpyderPalette.COLOR_BACKGROUND_1};"
            f"border: 1px solid {SpyderPalette.COLOR_BACKGROUND_4};"
            "border-radius: 4px; }"
            "QFrame#commandlineHistoryPopup QLabel {"
            f"color: {SpyderPalette.COLOR_TEXT_1};"
            "background: transparent; border: none; padding: 0; }"
            "QListWidget#commandlineHistoryList {"
            f"color: {SpyderPalette.COLOR_TEXT_1};"
            f"background-color: {SpyderPalette.COLOR_BACKGROUND_1};"
            "border: none; outline: none; }"
            "QListWidget#commandlineHistoryList::item { padding: 2px 4px; }"
            "QListWidget#commandlineHistoryList::item:selected {"
            f"color: {SpyderPalette.COLOR_TEXT_1};"
            f"background-color: {SpyderPalette.COLOR_BACKGROUND_4}; }}"
        )
        # Reapplying an unchanged stylesheet repolishes every child.
        stylesheet_changed = stylesheet != self.styleSheet()
        if stylesheet_changed:
            self.setStyleSheet(stylesheet)
        # Stylesheet widgets do not reliably inherit their parent's font.
        self.header.setFont(font)
        self.list_widget.setFont(font)
        return stylesheet_changed or self.font() != previous_font

    def update_geometry(self):
        """Fit the panel near the command line at the viewport's lower edge."""
        self.ensurePolished()
        viewport = self.parentWidget()
        width, height = viewport.width(), viewport.height()
        margin = min(8, max(0, (min(width, height) - 1) // 2))
        available_width = max(1, width - 2 * margin)
        available_height = max(1, height - 2 * margin)
        margins = self.layout().contentsMargins() + self.contentsMargins()
        horizontal_padding = margins.left() + margins.right()
        vertical_padding = margins.top() + margins.bottom()
        row_height = self.list_widget.sizeHintForRow(0)
        if row_height <= 0:
            row_height = self.list_widget.fontMetrics().height() + 4
        visible_rows = min(self.MAX_VISIBLE_ROWS, len(self._candidates))
        wanted_height = (
            self.header.sizeHint().height()
            + self.layout().spacing()
            + row_height * visible_rows
            + vertical_padding
        )
        row_width = max(0, self.list_widget.sizeHintForColumn(0))
        scrollbar_width = self.list_widget.verticalScrollBar().sizeHint().width()
        wanted_width = max(row_width, self.header.sizeHint().width())
        popup_width = min(
            available_width, wanted_width + horizontal_padding + scrollbar_width
        )
        popup_height = min(available_height, wanted_height)
        self.setGeometry(
            margin,
            height - margin - popup_height,
            popup_width,
            popup_height,
        )
        self.layout().activate()
        item = self.list_widget.currentItem()
        if item is not None:
            self.list_widget.scrollToItem(item)
