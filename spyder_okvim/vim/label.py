# -*- coding: utf-8 -*-
"""Widgets used to display inline annotations."""

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel


ANNOTATION_STYLE = {
    "background": "#1f2933",
    "text": "#f8fafc",
    "border": "#38bdf8",
    "border_width": 1,
    "radius": 6,
    "padding_v": 1,
    "padding_h": 4,
    "font_weight": 600,
}


class InlineLabel(QLabel):
    """Small floating label shown over the editor text."""

    def __init__(self, parent=None):
        """Create the label widget."""
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAlignment(Qt.AlignCenter)

    def set_style(self, font_family: str, font_size_pt: int):
        """Apply styling for display.

        Args:
            font_family: Font family name.
            font_size_pt: Size of the font in points.
        """
        self.setStyleSheet(
            f"""QLabel {{
                background-color: {ANNOTATION_STYLE["background"]};
                color: {ANNOTATION_STYLE["text"]};
                border: {ANNOTATION_STYLE["border_width"]}px solid {ANNOTATION_STYLE["border"]};
                border-radius: {ANNOTATION_STYLE["radius"]}px;
                padding: {ANNOTATION_STYLE["padding_v"]}px {ANNOTATION_STYLE["padding_h"]}px;
                margin: 0px;
                font-family: {font_family};
                font-size: {font_size_pt}pt;
                font-weight: {ANNOTATION_STYLE["font_weight"]};
            }}"""
        )


