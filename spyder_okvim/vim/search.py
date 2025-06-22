# -*- coding: utf-8 -*-
"""Utilities for searching within the editor."""

from qtpy.QtCore import QRegularExpression
from qtpy.QtGui import (
    QBrush,
    QColor,
    QTextCursor,
    QValidator,
    QRegularExpressionValidator,
)

from spyder.config.manager import CONF

from spyder_okvim.spyder.config import CONF_SECTION


class SearchInfo:
    """Track search results inside the editor."""

    def __init__(self, vim_cursor):
        """Initialize the search state.

        Args:
            vim_cursor: Cursor helper used to draw selections.
        """
        self.color_fg = QBrush(QColor("#A9B7C6"))
        self.color_bg = QBrush(QColor("#30652F"))
        self.txt_searched = ""
        self.selection_list = []
        self.vim_cursor = vim_cursor
        self.ignorecase = True

        self.set_color()

    def set_color(self):
        """Refresh highlight colors from configuration."""
        self.color_fg = QBrush(QColor(CONF.get(CONF_SECTION, "search_fg_color")))
        self.color_bg = QBrush(QColor(CONF.get(CONF_SECTION, "search_bg_color")))

        for sel in self.selection_list:
            sel.format.setForeground(self.color_fg)
            sel.format.setBackground(self.color_bg)

    def get_sel_start_list(self):
        """Return start positions for valid selections."""
        cursor = self.vim_cursor.get_cursor()
        validator = QRegularExpressionValidator(
            QRegularExpression(self.txt_searched), None
        )

        tmp = []
        for sel in self.selection_list:
            cursor.setPosition(sel.cursor.selectionStart())
            cursor.setPosition(sel.cursor.selectionEnd(), QTextCursor.KeepAnchor)
            txt_sel = cursor.selectedText()

            if (validator.validate(txt_sel, 0)[0] == QValidator.Acceptable) or (
                self.ignorecase is True and txt_sel.lower() == self.txt_searched.lower()
            ):
                tmp.append(sel)
        self.selection_list = tmp

        self.vim_cursor.set_extra_selections(
            "vim_search", [i for i in self.selection_list]
        )

        return [i.cursor.selectionStart() for i in self.selection_list]


