"""Non-focusable viewport panel for command-prefix hints."""

# Third Party Libraries
from qtpy.QtCore import Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from spyder.utils.palette import SpyderPalette

# Project Libraries
from spyder_okvim.utils.qtcompat import text_width
from spyder_okvim.spyder.popup_geometry import popup_area


def display_key(key):
    """Use readable names for special keys without changing letter case."""
    return {
        " ": "Space",
        "\r": "Enter",
        "\n": "Enter",
        "\b": "Backspace",
        "\t": "Tab",
        "\x1b": "Esc",
    }.get(key, key)


class WhichKeyPopup(QFrame):
    """A compact, non-focusable panel with columns fitted to the editor."""

    def __init__(self, viewport):
        super().__init__(viewport)
        self.setObjectName("whichKeyPopup")
        self.setAccessibleName("Next command keys")
        self.setAccessibleDescription("Available keys for the pending Vim command")
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._contents = None
        self.candidate_labels = []
        self.column_count = 2

        self.header = QLabel(self)
        self.header.setTextFormat(Qt.PlainText)
        self.header.setFocusPolicy(Qt.NoFocus)
        self.header.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        self.body = QWidget(self)
        self.body.setObjectName("whichKeyBody")
        self.body.setFocusPolicy(Qt.NoFocus)
        self._grid = QGridLayout(self.body)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(2)
        for column in range(self.column_count):
            self._grid.setColumnStretch(column * 2 + 1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        layout.setSizeConstraint(QLayout.SetNoConstraint)
        layout.addWidget(self.header)
        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("whichKeyScroll")
        self._scroll.setFrameShape(QFrame.NoFrame)
        for widget in (
            self._scroll,
            self._scroll.viewport(),
            self._scroll.verticalScrollBar(),
            self._scroll.horizontalScrollBar(),
        ):
            widget.setFocusPolicy(Qt.NoFocus)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setMinimumSize(0, 0)
        self._scroll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self._scroll.setWidget(self.body)
        layout.addWidget(self._scroll)
        self.hide()

    def set_candidates(self, prefix, candidates):
        """Rebuild the rows only when their keys or descriptions change."""
        candidates = tuple(candidates)
        contents = (prefix, candidates)
        if contents == self._contents:
            return
        self._contents = contents
        self._scroll.verticalScrollBar().setValue(0)
        self.header.setText(f"Prefix: {display_key(prefix)}")
        while self._grid.count():
            widget = self._grid.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.candidate_labels = []
        for index, (key, description) in enumerate(candidates):
            row, group = divmod(index, self.column_count)
            column = group * 2
            key_label = QLabel(display_key(key), self.body)
            key_label.setObjectName("whichKeyKey")
            description_label = QLabel(description, self.body)
            for label in (key_label, description_label):
                label.setTextFormat(Qt.PlainText)
                label.setFocusPolicy(Qt.NoFocus)
                label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            description_label.setWordWrap(True)
            description_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self._grid.addWidget(key_label, row, column, Qt.AlignTop)
            self._grid.addWidget(description_label, row, column + 1)
            key_label.show()
            description_label.show()
            self.candidate_labels.append((key_label, description_label))
        self._grid.invalidate()

    def _set_column_count(self, count):
        """Reflow existing labels without recreating their content."""
        if count == self.column_count:
            return
        self.column_count = count
        while self._grid.count():
            self._grid.takeAt(0)
        for column in range(4):
            self._grid.setColumnStretch(column, int(column < count * 2 and column % 2))
        for index, (key_label, description_label) in enumerate(self.candidate_labels):
            row, group = divmod(index, count)
            self._grid.addWidget(key_label, row, group * 2, Qt.AlignTop)
            self._grid.addWidget(description_label, row, group * 2 + 1)
        self._grid.invalidate()

    def refresh_appearance(self, font):
        """Use a smaller UI font and the palette applied by Spyder."""
        compact_font = QFont(font)
        if font.pointSizeF() > 0:
            compact_font.setPointSizeF(max(8.0, font.pointSizeF() * 0.85))
            font_size = f"{compact_font.pointSizeF()}pt"
        else:
            compact_font.setPixelSize(max(10, round(font.pixelSize() * 0.85)))
            font_size = f"{compact_font.pixelSize()}px"
        self.setFont(compact_font)
        self.setStyleSheet(
            "QFrame#whichKeyPopup {"
            f"background-color: {SpyderPalette.COLOR_BACKGROUND_1};"
            f"border: 1px solid {SpyderPalette.COLOR_BACKGROUND_4};"
            f"font-size: {font_size}; border-radius: 4px; }}"
            "QFrame#whichKeyPopup QLabel {"
            f"color: {SpyderPalette.COLOR_TEXT_1}; font-size: {font_size};"
            "background: transparent; border: none; padding: 0; margin: 0; }"
            "QFrame#whichKeyPopup QLabel#whichKeyKey {"
            f"color: {SpyderPalette.COLOR_ACCENT_4}; font-weight: bold; }}"
            "QWidget#whichKeyBody {"
            f"background-color: {SpyderPalette.COLOR_BACKGROUND_1}; }}"
            "QScrollArea#whichKeyScroll { background: transparent; border: none; }"
        )

    def _preferred_width(self, horizontal_padding):
        """Measure unwrapped rows so short menus use only the space they need."""
        key_widths = [0] * self.column_count
        description_widths = [0] * self.column_count
        for index, (key_label, description_label) in enumerate(self.candidate_labels):
            key_label.ensurePolished()
            description_label.ensurePolished()
            group = index % self.column_count
            key_widths[group] = max(key_widths[group], key_label.sizeHint().width())
            description_widths[group] = max(
                description_widths[group],
                text_width(description_label.fontMetrics(), description_label.text()),
            )
        return (
            sum(key_widths)
            + sum(description_widths)
            + self._grid.horizontalSpacing() * (self.column_count * 2 - 1)
            + horizontal_padding
        )

    def update_geometry(self):
        """Fit wrapped rows, allowing overflow menus to scroll without focus."""
        self.ensurePolished()
        viewport = self.parentWidget()
        area = popup_area(viewport)
        available_width = area.width()
        available_height = area.height()
        # Use text metrics so high DPI and larger UI fonts switch sooner.
        column_minimum = text_width(self.fontMetrics(), "M" * 22)
        self._set_column_count(1 if available_width < 2 * column_minimum else 2)
        margins = self.layout().contentsMargins() + self.contentsMargins()
        horizontal_padding = margins.left() + margins.right()
        vertical_padding = margins.top() + margins.bottom()
        wanted_width = self._preferred_width(horizontal_padding)
        popup_width = min(wanted_width, available_width)
        body_height = self._grid.totalHeightForWidth(
            max(1, popup_width - horizontal_padding)
        )
        fixed_height = (
            self.header.sizeHint().height() + self.layout().spacing() + vertical_padding
        )
        wanted_height = body_height + fixed_height
        overflowing = wanted_height > available_height
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOn if overflowing else Qt.ScrollBarAlwaysOff
        )
        if overflowing:
            scrollbar_width = self._scroll.verticalScrollBar().sizeHint().width()
            popup_width = min(wanted_width + scrollbar_width, available_width)
            body_height = self._grid.totalHeightForWidth(
                max(1, popup_width - horizontal_padding - scrollbar_width)
            )
            wanted_height = body_height + fixed_height
        self.body.setMinimumHeight(max(0, body_height))
        popup_height = min(wanted_height, available_height)
        self.setGeometry(
            area.left(),
            area.bottom() - popup_height + 1,
            popup_width,
            popup_height,
        )
        self.layout().activate()
