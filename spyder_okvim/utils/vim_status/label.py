# -*- coding: utf-8 -*-
"""Widgets used to display inline annotations."""

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel


class InlineLabel(QLabel):
    """Small floating label shown over the editor text."""

    def __init__(self, parent=None):
        """Create the label widget."""
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

    def set_style(self, font_family: str, font_size_pt: int):
        """Apply styling for display.

        Args:
            font_family: Font family name.
            font_size_pt: Size of the font in points.
        """
        self.setStyleSheet(
            f"""QLabel {{
            background-color : #222b35;
            color : #cd4340;
            border: 1px solid #cd4340;
            padding : 0px;
            text-indent : 1px;
            margin : 0px;
            font-family: {font_family};
            font-size: {font_size_pt}pt;
            }}"""
        )




