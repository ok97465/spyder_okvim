# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""OkVim Plugin."""
# Third party imports
import qtawesome as qta
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QKeySequence, QFont
from qtpy.QtWidgets import QHBoxLayout, QShortcut, QVBoxLayout, QWidget
from spyder.api.plugins import SpyderPluginWidget
from spyder.config.base import _
from spyder.utils.icon_manager import MAIN_FG_COLOR

# Local imports
from spyder_okvim.config import CONF_DEFAULTS, CONF_SECTION
from spyder_okvim.confpage import OkvimConfigPage
from spyder_okvim.widgets.okvim import VimWidget


class StatusBarVimWidget(QWidget):
    """Status bar widget for okvim."""

    def __init__(self, parent, msg_label, status_label, cmd_line):
        """Status bar widget base."""
        super(StatusBarVimWidget, self).__init__(parent)

        width_msg = msg_label.width()
        width_status = status_label.width()
        width_cmd = cmd_line.width()
        spacing_post = 32
        spacing = 5

        width_total = width_msg + width_status + width_cmd

        layout = QHBoxLayout()
        layout.setSpacing(spacing)
        layout.addWidget(msg_label, int(width_msg / width_total * 100))
        layout.addWidget(status_label, int(width_status / width_total * 100))
        layout.addWidget(cmd_line, int(width_cmd / width_total * 100))
        layout.addSpacing(spacing_post)
        layout.setContentsMargins(0, 0, 0, 0)

        width_total += 2 * spacing + spacing_post

        self.setLayout(layout)
        self.setFixedWidth(width_total)


class OkVim(SpyderPluginWidget):  # pylint: disable=R0904
    """Implements a Vim-like command mode."""

    focus_changed = Signal()
    CONF_SECTION = CONF_SECTION
    CONFIGWIDGET_CLASS = OkvimConfigPage
    CONF_DEFAULTS = CONF_DEFAULTS

    def __init__(self, parent):
        SpyderPluginWidget.__init__(self, parent)
        self.main = parent
        self.vim_cmd = VimWidget(self.main.editor, self.main)
        layout = QVBoxLayout()
        layout.addWidget(self.vim_cmd)
        self.setLayout(layout)

        status_bar_widget = StatusBarVimWidget(
                parent,
                self.vim_cmd.msg_label,
                self.vim_cmd.status_label,
                self.vim_cmd.commandline)
        status = self.main.statusBar()
        status.insertPermanentWidget(0, status_bar_widget)

    # %% SpyderPlugin API
    def get_plugin_title(self):
        """Return widget title."""
        return _("Okvim")

    def get_plugin_icon(self):
        """Return widget icon."""
        return qta.icon('mdi.vimeo', color=MAIN_FG_COLOR)

    def register_plugin(self):
        """Register plugin in Spyder's main window."""
        super(OkVim, self).register_plugin()

        sc = QShortcut(QKeySequence("Esc"),
                       self.vim_cmd.editor_widget.editorsplitter,
                       self.vim_cmd.commandline.setFocus)
        sc.setContext(Qt.WidgetWithChildrenShortcut)

    def get_focus_widget(self):
        """Return vim command line and give it focus."""
        return self.vim_cmd.commandline

    def get_plugin_actions(self):
        """Return plugin actions."""
        return []

# ------ SpyderPluginMixin API
    def switch_to_plugin(self):
        """Switch to plots pane plugin by shortcut key.

        This method is called when pressing plugin's shortcut key
        """
        self.vim_cmd.commandline.setFocus()

    def apply_plugin_settings(self, options):
        """Apply the config settings."""
        self.vim_cmd.vim_status.search.set_color()
        self.vim_cmd.vim_status.cursor.set_config_from_conf()
        self.vim_cmd.set_leader_key()

