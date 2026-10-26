"""Delayed, read-only hints for the active command-prefix executor."""

# Standard Libraries
import weakref

# Third Party Libraries
from qtpy.QtCore import QEvent, QObject, Qt, QTimer
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
from spyder.config.manager import CONF
from spyder.utils.palette import SpyderPalette

# Project Libraries
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.vim.state import VimState


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
    """A compact, non-focusable two-column panel inside the viewport."""

    def __init__(self, viewport):
        super().__init__(viewport)
        self.setObjectName("whichKeyPopup")
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._contents = None
        self._scroll = None
        self.candidate_labels = []
        self.column_count = 2

        self.header = QLabel(self)
        self.header.setTextFormat(Qt.PlainText)
        self.header.setFocusPolicy(Qt.NoFocus)
        self.header.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        self.body = QWidget(self)
        self._body = self.body
        self._body.setObjectName("whichKeyBody")
        self._body.setFocusPolicy(Qt.NoFocus)
        self._grid = QGridLayout(self._body)
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
        layout.addWidget(self._body)
        self.hide()

    def set_candidates(self, prefix, candidates):
        """Rebuild the rows only when their keys or descriptions change."""
        contents = (prefix, tuple(candidates))
        if contents == self._contents:
            return
        self._contents = contents
        if self._scroll is not None:
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
            key_label = QLabel(display_key(key), self._body)
            key_label.setObjectName("whichKeyKey")
            key_label.setTextFormat(Qt.PlainText)
            key_label.setFocusPolicy(Qt.NoFocus)
            key_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            description_label = QLabel(description, self._body)
            description_label.setTextFormat(Qt.PlainText)
            description_label.setFocusPolicy(Qt.NoFocus)
            description_label.setWordWrap(True)
            description_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            description_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self._grid.addWidget(key_label, row, column, Qt.AlignTop)
            self._grid.addWidget(description_label, row, column + 1)
            self.candidate_labels.append((key_label, description_label))

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

    def _set_scrolling(self, enabled):
        """Add a scrolling surface only when the candidate rows cannot fit."""
        if enabled and self._scroll is None:
            self.layout().removeWidget(self._body)
            scroll = QScrollArea(self)
            scroll.setObjectName("whichKeyScroll")
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setFocusPolicy(Qt.NoFocus)
            scroll.viewport().setFocusPolicy(Qt.NoFocus)
            scroll.verticalScrollBar().setFocusPolicy(Qt.NoFocus)
            scroll.horizontalScrollBar().setFocusPolicy(Qt.NoFocus)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            scroll.setWidgetResizable(True)
            scroll.setMinimumSize(0, 0)
            scroll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
            scroll.setWidget(self._body)
            self.layout().addWidget(scroll)
            self._scroll = scroll
            scroll.show()
        elif not enabled and self._scroll is not None:
            scroll = self._scroll
            self.layout().removeWidget(scroll)
            scroll.takeWidget()
            self._body.setParent(self)
            self._body.setMinimumHeight(0)
            self.layout().addWidget(self._body)
            self._body.show()
            self._scroll = None
            scroll.hide()
            scroll.setParent(None)
            scroll.deleteLater()

    def update_geometry(self):
        """Fit wrapped rows, allowing overflow menus to scroll without focus."""
        self.ensurePolished()
        viewport = self.parentWidget()
        width, height = viewport.width(), viewport.height()
        margin = min(8, max(0, (min(width, height) - 1) // 2))
        available_width = max(1, width - 2 * margin)
        available_height = max(1, height - 2 * margin)
        margins = self.layout().contentsMargins()
        frame_margins = self.contentsMargins()
        horizontal_padding = (
            margins.left()
            + margins.right()
            + frame_margins.left()
            + frame_margins.right()
        )
        vertical_padding = (
            margins.top()
            + margins.bottom()
            + frame_margins.top()
            + frame_margins.bottom()
        )
        key_widths = [0] * self.column_count
        description_widths = [0] * self.column_count
        for index, (key_label, description_label) in enumerate(self.candidate_labels):
            key_label.ensurePolished()
            description_label.ensurePolished()
            group = index % self.column_count
            key_widths[group] = max(key_widths[group], key_label.sizeHint().width())
            description_widths[group] = max(
                description_widths[group],
                description_label.fontMetrics().horizontalAdvance(
                    description_label.text()
                ),
            )
        wanted_width = (
            sum(key_widths)
            + sum(description_widths)
            + self._grid.horizontalSpacing() * (self.column_count * 2 - 1)
            + horizontal_padding
        )
        popup_width = min(wanted_width, available_width)
        body_width = max(1, popup_width - horizontal_padding)
        body_height = self._grid.totalHeightForWidth(body_width)
        fixed_height = (
            self.header.sizeHint().height() + self.layout().spacing() + vertical_padding
        )
        wanted_height = body_height + fixed_height
        self._set_scrolling(wanted_height > available_height)
        if self._scroll is not None:
            scrollbar_width = self._scroll.verticalScrollBar().sizeHint().width()
            popup_width = min(wanted_width + scrollbar_width, available_width)
            body_width = max(1, popup_width - horizontal_padding - scrollbar_width)
            body_height = self._grid.totalHeightForWidth(body_width)
            self._body.setMinimumHeight(body_height)
            wanted_height = body_height + fixed_height
        popup_height = min(wanted_height, available_height)
        self.setGeometry(
            margin,
            height - margin - popup_height,
            popup_width,
            popup_height,
        )
        self.layout().activate()
        if self._scroll is not None:
            # Use the actual viewport after layout, including the scrollbar's
            # platform-specific width, so the final wrapped row stays reachable.
            body_height = self._grid.totalHeightForWidth(
                self._scroll.viewport().width()
            )
            self._body.setMinimumHeight(body_height)


class WhichKeyController(QObject):
    """Observe completed input and schedule one hint for the current wait."""

    def __init__(self, vim_widget, widget_is_deleted):
        super().__init__(vim_widget)
        self._vim = weakref.ref(vim_widget)
        self._widget_is_deleted = widget_is_deleted
        self._editor = None
        self._viewport = None
        self._context = None
        self._settings = None
        self._closed = False
        self.popup = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._show_hints)
        self.enabled = True
        self.delay = 300
        self.apply_settings()

    def _live(self, reference):
        widget = reference() if reference is not None else None
        if widget is not None and not self._widget_is_deleted(widget):
            return widget
        return None

    def apply_settings(self):
        """Read preferences once on initialization or configuration apply."""
        if self._closed:
            return False
        vim = self._live(self._vim)
        if vim is None:
            return False
        enabled = bool(CONF.get(CONF_SECTION, "which_key_enabled", True))
        delay = max(0, min(2000, int(CONF.get(CONF_SECTION, "which_key_delay", 300))))
        settings = (enabled, delay, vim.leader_key)
        if settings == self._settings:
            return False
        self.cancel()
        self.enabled, self.delay = enabled, delay
        self._settings = settings
        self.sync()
        return True

    def set_editor(self, editor):
        """Release the previous viewport before following the selected editor."""
        if self._closed:
            return
        if editor is not None and self._widget_is_deleted(editor):
            editor = None
        viewport = editor.viewport() if editor is not None else None
        if viewport is self._live(self._viewport):
            self._editor = weakref.ref(editor) if editor is not None else None
            return
        self.cancel()
        previous = self._live(self._viewport)
        if previous is not None:
            previous.removeEventFilter(self)
            try:
                previous.destroyed.disconnect(self._viewport_destroyed)
            except (TypeError, RuntimeError):
                pass
        popup = self.popup
        self.popup = None
        if popup is not None and not self._widget_is_deleted(popup):
            popup.hide()
            popup.deleteLater()
        self._editor = weakref.ref(editor) if editor is not None else None
        self._viewport = weakref.ref(viewport) if viewport is not None else None
        if viewport is not None:
            viewport.installEventFilter(self)
            viewport.destroyed.connect(self._viewport_destroyed)

    def _viewport_destroyed(self, *args):
        self.cancel()
        self._editor = None
        self._viewport = None
        self.popup = None

    def _current_context(self):
        vim = self._live(self._vim)
        if vim is None or not self.enabled or self._closed:
            return None
        status = vim.vim_status
        commandline = vim.commandline
        if (
            self._widget_is_deleted(commandline)
            or status.vim_state
            not in (VimState.NORMAL, VimState.VISUAL, VimState.VLINE)
            or status.running_dot_cmd
            or getattr(vim, "_macro_playing", False)
            or not commandline.hasFocus()
            or not commandline.isActiveWindow()
        ):
            return None
        executor = status.sub_mode
        prefix = (
            vim.leader_key
            if executor is vim.executor_leader_key
            else getattr(executor, "hint_prefix", None)
        )
        if prefix is None:
            return None
        editor = self._live(self._editor)
        viewport = self._live(self._viewport)
        if (
            editor is None
            or viewport is None
            or status.get_editor() is not editor
            or not viewport.isVisible()
            or editor.window() is not commandline.window()
        ):
            return None
        return (self._editor, executor, status.vim_state, prefix)

    def sync(self):
        """Schedule only a new, valid wait; repeated observations keep its delay."""
        if self._closed:
            return
        vim = self._live(self._vim)
        if vim is None:
            self.cancel()
            return
        if getattr(vim, "_input_depth", 0):
            return
        context = self._current_context()
        if context is None:
            self.cancel()
        elif context != self._context:
            self.cancel()
            self._context = context
            self.timer.start(self.delay)
        elif not self.timer.isActive():
            # A displayed panel is hidden while handling input. If the same
            # wait survives, it has already earned its delay.
            self._show_hints()

    def begin_input(self):
        """Hide stale rows during dispatch without moving a pending deadline."""
        popup = self.popup
        if popup is not None and not self._widget_is_deleted(popup):
            popup.hide()

    def cancel(self):
        """Idempotently stop pending hints and hide an existing panel."""
        self.timer.stop()
        self._context = None
        popup = self.popup
        if popup is not None and not self._widget_is_deleted(popup):
            popup.hide()

    def _show_hints(self):
        vim = self._live(self._vim)
        if vim is None or getattr(vim, "_input_depth", 0):
            self.cancel()
            return
        context = self._current_context()
        if context is None or context != self._context:
            self.cancel()
            return
        candidates = context[1].get_hint_candidates()
        if not candidates:
            self.cancel()
            return
        viewport = self._live(self._viewport)
        if self.popup is None or self._widget_is_deleted(self.popup):
            self.popup = WhichKeyPopup(viewport)
        self.popup.set_candidates(context[3], candidates)
        self.popup.refresh_appearance(vim.commandline.font())
        self.popup.update_geometry()
        self.popup.raise_()
        self.popup.show()

    def eventFilter(self, watched, event):
        if watched is self._live(self._viewport):
            if event.type() in (QEvent.Hide, QEvent.Close, QEvent.WindowDeactivate):
                self.cancel()
            elif event.type() == QEvent.Resize:
                popup = self.popup
                if popup is not None and not self._widget_is_deleted(popup):
                    popup.update_geometry()
        return super().eventFilter(watched, event)

    def cleanup(self):
        """Disconnect the timer and detach viewport UI before plugin shutdown."""
        if self._closed:
            return
        self.cancel()
        self.set_editor(None)
        self.timer.timeout.disconnect(self._show_hints)
        self._closed = True
