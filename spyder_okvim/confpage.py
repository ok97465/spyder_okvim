# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
"""Spyder okvim configuration page."""

# Third party imports
from qtpy.QtCore import QRegExp, Qt
from qtpy.QtGui import QRegExpValidator
from qtpy.QtWidgets import (
    QGridLayout, QGroupBox, QLabel, QVBoxLayout,)
from spyder.api.preferences import PluginConfigPage
from spyder.config.base import _


class OkvimConfigPage(PluginConfigPage):
    def setup_page(self):
        """Create configuration page."""
        newcb = self.create_checkbox
        newce = self.create_coloredit

        color_group = QGroupBox("Color")
        color_layout = QGridLayout()

        conf_color_info = {
                'Cursor Fg': ('cursor_fg_color', 0, 0),
                'Cursor Bg': ('cursor_bg_color', 0, 2),
                'Selection Fg': ('select_fg_color', 1, 0),
                'Selection Bg': ('select_bg_color', 1, 2),
                'Search Fg': ('search_fg_color', 2, 0),
                'Search Bg': ('search_bg_color', 2, 2),
                }

        for name, (option_name, idx_row, idx_col) in conf_color_info.items():
            label, clayout = newce(name, option_name, without_layout=True)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            clayout.lineedit.setValidator(
                    QRegExpValidator(QRegExp(r"#[0-9abcdefABCDEF]{6}")))
            color_layout.addWidget(label, idx_row, idx_col)
            color_layout.addLayout(clayout, idx_row, idx_col + 1)
            color_group.setLayout(color_layout)

        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        options_layout.addWidget(newcb("ignorecase", "ignorecase"))
        options_layout.addWidget(newcb("smartcase", "smartcase"))

        options_group.setLayout(options_layout)
        options_layout.addStretch(1)

        layout = QVBoxLayout()
        layout.addWidget(color_group)
        layout.addWidget(options_group)
        layout.addStretch(1)

        self.setLayout(layout)
