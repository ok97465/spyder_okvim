# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""OkVim Plugin."""
# Third party imports
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QShortcut, QVBoxLayout
from spyder.api.plugins import SpyderPluginWidget
from spyder.config.base import _

# Local imports
from spyder_okvim.widgets.okvim import VimWidget


class OkVim(SpyderPluginWidget):  # pylint: disable=R0904
    """Implements a Vim-like command mode."""

    focus_changed = Signal()
    CONF_SECTION = "okvim"
    CONF_FILE = False
    CONFIGWIDGET_CLASS = None

    def __init__(self, parent):
        SpyderPluginWidget.__init__(self, parent)
        self.main = parent
        self.vim_cmd = VimWidget(self.main.editor, self.main)
        layout = QVBoxLayout()
        layout.addWidget(self.vim_cmd)
        self.setLayout(layout)
        status = self.main.statusBar()
        status.insertPermanentWidget(0, self.vim_cmd.commandline)
        status.insertPermanentWidget(0, self.vim_cmd.status_label)

    # %% SpyderPlugin API
    def get_plugin_title(self):
        """Return widget title."""
        return _("okvim")

    def get_plugin_icon(self):
        """Return widget icon."""
        return  # self.get_icon('vim.png')

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