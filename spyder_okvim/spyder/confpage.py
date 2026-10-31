# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
"""Spyder okvim configuration page."""

# Third Party Libraries
from qtpy.QtCore import QRegularExpression, Qt
from qtpy.QtGui import QKeySequence, QRegularExpressionValidator
from qtpy.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLineEdit, QVBoxLayout
from spyder.api.preferences import PluginConfigPage


class OkvimConfigPage(PluginConfigPage):
    """Preferences page for configuring OkVim."""

    def setup_page(self):
        """Create configuration page for the plugin."""
        newcb = self.create_checkbox
        newce = self.create_coloredit
        newsb = self.create_spinbox
        newle = self.create_lineedit

        color_group = QGroupBox("Color")
        color_layout = QGridLayout()

        conf_color_info = {
            "Cursor Fg": ("cursor_fg_color", 0, 0),
            "Cursor Bg": ("cursor_bg_color", 0, 2),
            "Selection Fg": ("select_fg_color", 1, 0),
            "Selection Bg": ("select_bg_color", 1, 2),
            "Search Fg": ("search_fg_color", 2, 0),
            "Search Bg": ("search_bg_color", 2, 2),
            "Highlight after yank Fg": ("yank_fg_color", 3, 0),
            "Highlight after yank Bg": ("yank_bg_color", 3, 2),
            "Jump label Fg (empty: theme)": ("annotation_fg_color", 4, 0),
            "Jump label Bg (empty: theme)": ("annotation_bg_color", 4, 2),
            "Jump label border (empty: theme)": ("annotation_border_color", 5, 0),
            "Mode Fg (empty: theme)": ("mode_fg_color", 6, 0),
            "Mode Bg (empty: theme)": ("mode_bg_color", 6, 2),
        }
        theme_color_options = {
            "annotation_fg_color",
            "annotation_bg_color",
            "annotation_border_color",
            "mode_fg_color",
            "mode_bg_color",
        }

        for name, (option_name, idx_row, idx_col) in conf_color_info.items():
            label, clayout = newce(name, option_name, without_layout=True)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            clayout.lineedit.setValidator(
                QRegularExpressionValidator(
                    QRegularExpression(
                        r"(?:#[0-9abcdefABCDEF]{6})?"
                        if option_name in theme_color_options
                        else r"#[0-9abcdefABCDEF]{6}"
                    )
                )
            )
            color_layout.addWidget(label, idx_row, idx_col)
            color_layout.addLayout(clayout, idx_row, idx_col + 1)
            color_group.setLayout(color_layout)

        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        options_layout.addWidget(newcb("ignorecase", "ignorecase"))
        options_layout.addWidget(newcb("smartcase", "smartcase"))
        options_layout.addWidget(newcb("enable Leap two-char search (s/z)", "use_leap"))
        self.commandline_completion_enabled = newcb(
            "Show command-line completion suggestions (:)",
            "commandline_completion_enabled",
            default=True,
        )
        options_layout.addWidget(self.commandline_completion_enabled)
        self.commandline_history_enabled = newcb(
            "Show command-line history suggestions (:, /, ?)",
            "commandline_history_enabled",
            default=True,
        )
        options_layout.addWidget(self.commandline_history_enabled)
        self.substitute_guide_enabled = newcb(
            "Show substitute command guide (:s)",
            "substitute_guide_enabled",
            default=True,
        )
        options_layout.addWidget(self.substitute_guide_enabled)
        self.substitute_preview_enabled = newcb(
            "Enable incremental substitute preview (:s)",
            "substitute_preview_enabled",
            default=True,
        )
        options_layout.addWidget(self.substitute_preview_enabled)

        hl_yank_layout = QHBoxLayout()
        hl_yank_layout.addWidget(newcb("highlight after yank", "highlight_yank"))
        hl_yank_layout.addWidget(
            newsb(
                "(duration ",
                "ms)",
                "highlight_yank_duration",
                min_=0,
                max_=2000,
                step=100,
            )
        )
        options_layout.addLayout(hl_yank_layout)

        options_group.setLayout(options_layout)

        yanky_group = QGroupBox("Yank history")
        yanky_layout = QVBoxLayout()
        self.yanky_enabled = newcb(
            "Enable yank history and paste cycling", "yanky_enabled", default=True
        )
        self.yank_history_length = newsb(
            "Maximum entries",
            "",
            "yank_history_length",
            default=100,
            min_=1,
            max_=10000,
            step=10,
        )
        self.highlight_put = newcb(
            "Highlight pasted text (uses yank colors and duration)",
            "highlight_put",
            default=True,
        )
        self.yanky_enabled.checkbox.toggled.connect(self.yank_history_length.setEnabled)
        self.yank_history_length.setEnabled(self.yanky_enabled.checkbox.isChecked())
        yanky_layout.addWidget(self.yanky_enabled)
        yanky_layout.addWidget(self.yank_history_length)
        yanky_layout.addWidget(self.highlight_put)
        yanky_group.setLayout(yanky_layout)

        leaderkey_group = QGroupBox("Leader Key Mapping")
        leaderkey_layout = QHBoxLayout()

        self.leaderkey_viewer = newle(
            "Leader key", "leader_key", alignment=Qt.Horizontal
        )
        self.leaderkey_viewer.textbox.setAlignment(Qt.AlignHCenter)
        self.leaderkey_viewer.textbox.setEnabled(False)

        self.leaderkey_edit = ShortcutLineEdit(self, self.leaderkey_viewer.textbox)

        leaderkey_layout.addWidget(self.leaderkey_viewer)
        leaderkey_layout.addWidget(self.leaderkey_edit)
        leaderkey_group.setLayout(leaderkey_layout)

        which_key_group = QGroupBox("Which-key")
        which_key_layout = QVBoxLayout()
        self.which_key_enabled = newcb(
            "Enable which-key hints", "which_key_enabled", default=True
        )
        self.which_key_delay = newsb(
            "Show hints after",
            "ms",
            "which_key_delay",
            default=300,
            min_=0,
            max_=2000,
            step=50,
        )
        self.which_key_enabled.checkbox.toggled.connect(self.which_key_delay.setEnabled)
        self.which_key_delay.setEnabled(self.which_key_enabled.checkbox.isChecked())
        which_key_layout.addWidget(self.which_key_enabled)
        which_key_layout.addWidget(self.which_key_delay)
        which_key_group.setLayout(which_key_layout)

        layout = QVBoxLayout()
        layout.addWidget(color_group)
        layout.addWidget(options_group)
        layout.addWidget(yanky_group)
        layout.addWidget(leaderkey_group)
        layout.addWidget(which_key_group)

        self.setLayout(layout)


class ShortcutLineEdit(QLineEdit):
    """QLineEdit that filters its key press and release events."""

    def __init__(self, parent, viewer):
        """Create line edit used to record a leader key sequence.

        Args:
            parent: Parent widget.
            viewer: Line edit that displays the captured shortcut.
        """
        super().__init__(parent)
        self.setPlaceholderText("Press leader key...")
        self.viewer = viewer

    def keyPressEvent(self, event):
        """Filter key presses to capture a valid shortcut.

        Args:
            event: Key event captured by Qt.
        """
        key = event.key()
        modifier = event.modifiers()

        if modifier != Qt.NoModifier:
            return
        if not key or key == Qt.Key_unknown:
            return

        key_str = QKeySequence(key).toString()
        self.viewer.setText(key_str)
