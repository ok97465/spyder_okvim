# -*- coding: utf-8 -*-
"""Widgets used to display inline annotations."""

import weakref

from qtpy.QtCore import QEvent, QRect, Qt
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import QLabel

from spyder_okvim.utils.qtcompat import live_widget
from spyder_okvim.utils.theme import selection_colors


ANNOTATION_STYLE = {
    "border_width": 1,
    "radius": 6,
    "padding_v": 1,
    "padding_h": 4,
    "font_weight": 600,
}


def annotation_style(widget):
    """Resolve matching label colors from the current editor's palette."""
    palette = widget.palette()
    foreground, background = selection_colors(widget)
    return {
        **ANNOTATION_STYLE,
        "background": background.name(),
        "text": foreground.name(),
        "border": palette.color(QPalette.Text).name(),
    }


def place_annotation(target, width, height, bounds, occupied):
    """Fit a label beside its target, returning None when nearby space is full.

    Keep the label close enough to identify its target. At the right edge,
    prefer the row above/below so clamping does not cover the target text.
    """
    x = min(max(target.left(), bounds.left()), bounds.right() - width + 1)
    if width > bounds.width() or height > bounds.height():
        return None
    y = target.top()
    offsets = [0] if x == target.left() else []
    for rows in range(1, 6):
        offsets.extend((-rows * height, rows * height))
    if x != target.left():
        offsets.append(0)
    for offset in offsets:
        rect = QRect(x, y + offset, width, height)
        if bounds.contains(rect) and not any(
            rect.intersects(other) for other in occupied
        ):
            return rect
    return None


class InlineLabel(QLabel):
    """Small floating label shown over the editor text."""

    def __init__(self, parent=None):
        """Create the label widget."""
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAlignment(Qt.AlignCenter)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAccessibleName("Jump target label")
        self.setAccessibleDescription("Type this label to jump to its target.")
        self._style_source_ref = None
        self._font_family = ""
        self._font_size = 10
        self._applying_style = False

    def set_style(self, font_family: str, font_size_pt: int, source=None):
        """Apply styling for display.

        Args:
            font_family: Font family name.
            font_size_pt: Size of the font in points.
        """
        source = source or self
        previous = live_widget(self._style_source_ref)
        if previous is not source:
            if previous is not None and previous is not self:
                previous.removeEventFilter(self)
            self._style_source_ref = weakref.ref(source)
            if source is not self:
                source.installEventFilter(self)
        self._font_family = font_family
        self._font_size = font_size_pt
        style = annotation_style(source)
        stylesheet = f"""QLabel {{
                background-color: {style["background"]};
                color: {style["text"]};
                border: {style["border_width"]}px solid {style["border"]};
                border-radius: {ANNOTATION_STYLE["radius"]}px;
                padding: {ANNOTATION_STYLE["padding_v"]}px {ANNOTATION_STYLE["padding_h"]}px;
                margin: 0px;
                font-family: {font_family};
                font-size: {font_size_pt}pt;
                font-weight: {ANNOTATION_STYLE["font_weight"]};
            }}"""
        if stylesheet != self.styleSheet():
            self._applying_style = True
            try:
                self.setStyleSheet(stylesheet)
            finally:
                self._applying_style = False

    def changeEvent(self, event):
        """Refresh visible annotations when the host palette changes."""
        super().changeEvent(event)
        if (
            event.type()
            in (
                QEvent.PaletteChange,
                QEvent.ApplicationPaletteChange,
                QEvent.StyleChange,
            )
            and live_widget(self._style_source_ref) is not None
            and not self._applying_style
        ):
            self.set_style(
                self._font_family,
                self._font_size,
                live_widget(self._style_source_ref),
            )

    def eventFilter(self, watched, event):
        if (
            event.type()
            in (
                QEvent.PaletteChange,
                QEvent.ApplicationPaletteChange,
                QEvent.StyleChange,
            )
            and not self._applying_style
        ):
            self.set_style(self._font_family, self._font_size, watched)
        return False
