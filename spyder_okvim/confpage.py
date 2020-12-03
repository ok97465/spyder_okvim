# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
"""Spyder okvim configuration page."""

# Third party imports
from qtpy.QtCore import QRegExp, Qt
from qtpy.QtGui import QRegExpValidator, QKeySequence
from qtpy.QtWidgets import (
    QGridLayout, QGroupBox, QHBoxLayout, QVBoxLayout, QLineEdit)
from spyder.api.preferences import PluginConfigPage
from spyder.config.base import _


class OkvimConfigPage(PluginConfigPage):
    def setup_page(self):
        """Create configuration page."""
        newcb = self.create_checkbox
        newce = self.create_coloredit
        newsb = self.create_spinbox
        newle = self.create_lineedit

        color_group = QGroupBox('Color')
        color_layout = QGridLayout()

        conf_color_info = {
                'Cursor Fg': ('cursor_fg_color', 0, 0),
                'Cursor Bg': ('cursor_bg_color', 0, 2),
                'Selection Fg': ('select_fg_color', 1, 0),
                'Selection Bg': ('select_bg_color', 1, 2),
                'Search Fg': ('search_fg_color', 2, 0),
                'Search Bg': ('search_bg_color', 2, 2),
                'Highlight after yank Fg': ('yank_fg_color', 3, 0),
                'Highlight after yank Bg': ('yank_bg_color', 3, 2),
                }

        for name, (option_name, idx_row, idx_col) in conf_color_info.items():
            label, clayout = newce(name, option_name, without_layout=True)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            clayout.lineedit.setValidator(
                    QRegExpValidator(QRegExp(r'#[0-9abcdefABCDEF]{6}')))
            color_layout.addWidget(label, idx_row, idx_col)
            color_layout.addLayout(clayout, idx_row, idx_col + 1)
            color_group.setLayout(color_layout)

        options_group = QGroupBox('Options')
        options_layout = QVBoxLayout()
        options_layout.addWidget(newcb('ignorecase', 'ignorecase'))
        options_layout.addWidget(newcb('smartcase', 'smartcase'))

        hl_yank_layout = QHBoxLayout()
        hl_yank_layout.addWidget(newcb('highlight after yank',
                                       'highlight_yank'))
        hl_yank_layout.addWidget(newsb('(duration ', 'ms)',
                                       'highlight_yank_duration',
                                       min_=0, max_=2000, step=100))
        options_layout.addLayout(hl_yank_layout)

        options_group.setLayout(options_layout)

        leaderkey_group = QGroupBox('Leader Key Mapping')
        leaderkey_layout = QHBoxLayout()

        self.leaderkey_viewer = newle('Leader key', 'leader_key',
                                      alignment=Qt.Horizontal)
        self.leaderkey_viewer.textbox.setAlignment(Qt.AlignHCenter)
        self.leaderkey_viewer.textbox.setEnabled(False)

        self.leaderkey_edit = ShortcutLineEdit(
            self, self.leaderkey_viewer.textbox)

        leaderkey_layout.addWidget(self.leaderkey_viewer)
        leaderkey_layout.addWidget(self.leaderkey_edit)
        leaderkey_group.setLayout(leaderkey_layout)

        layout = QVBoxLayout()
        layout.addWidget(color_group)
        layout.addWidget(options_group)
        layout.addWidget(leaderkey_group)

        self.setLayout(layout)


class ShortcutLineEdit(QLineEdit):
    """QLineEdit that filters its key press and release events."""

    def __init__(self, parent, viewer):
        super().__init__(parent)
        self.setPlaceholderText('Press leader key...')
        self.viewer = viewer

    def keyPressEvent(self, event):
        """Override Qt method."""
        key = event.key()
        modifier = event.modifiers()

        if modifier != Qt.NoModifier:
            return
        if not key or key == Qt.Key_unknown:
            return

        key_str = QKeySequence(key).toString()
        self.viewer.setText(key_str)

