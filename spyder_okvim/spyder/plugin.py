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
from qtpy.QtGui import QFont, QIcon, QKeySequence
from qtpy.QtWidgets import QHBoxLayout, QShortcut, QVBoxLayout, QWidget
from spyder.api.plugins import Plugins, SpyderDockablePlugin, SpyderPluginV2
from spyder.api.widgets.main_container import PluginMainContainer
from spyder.api.widgets.status import StatusBarWidget
from spyder.utils.icon_manager import MAIN_FG_COLOR

# Local imports
from spyder_okvim.spyder.api import CustomLayout
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION
from spyder_okvim.spyder.confpage import OkvimConfigPage
from spyder_okvim.spyder.widgets import SpyderCustomLayoutWidget, VimWidget


class StatusBarVimWidget(StatusBarWidget):
    """Status bar widget for okvim."""

    ID = "okvim_in_statusbar"

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

    def set_layout(self):
        """."""
        pass

    # ---- Status bar widget API
    def set_icon(self):
        """Set the icon for the status bar widget."""
        pass

    def set_value(self, value):
        """Set formatted text value."""
        pass

    def update_tooltip(self):
        """Update tooltip for widget."""
        pass

    def mouseReleaseEvent(self, event):
        """Override Qt method to allow for click signal."""
        super(StatusBarWidget, self).mousePressEvent(event)
        pass

    # ---- API to be defined by user
    def get_tooltip(self):
        """Return the widget tooltip text."""
        return ''

    def get_icon(self):
        """Return the widget tooltip text."""
        return None


class OkVim(SpyderDockablePlugin):  # pylint: disable=R0904
    """Implements a Vim-like command mode."""

    focus_changed = Signal()
    NAME = "spyder_okvim"
    REQUIRES = [Plugins.StatusBar]
    OPTIONAL = []
    WIDGET_CLASS = SpyderCustomLayoutWidget
    CONF_SECTION = CONF_SECTION
    CONFIGWIDGET_CLASS = OkvimConfigPage
    CONF_DEFAULTS = CONF_DEFAULTS
    CUSTOM_LAYOUTS = [CustomLayout]

    def __init__(self, parent, configuration=None):
        """."""
        super().__init__(parent, configuration)
        self.main = parent
        self.vim_cmd = VimWidget(self.main.editor, self.main)

        status_bar_widget = StatusBarVimWidget(
                parent,
                self.vim_cmd.msg_label,
                self.vim_cmd.status_label,
                self.vim_cmd.commandline)
        statusbar = self.get_plugin(Plugins.StatusBar)
        statusbar.add_status_widget(status_bar_widget)

    # --- SpyderDockablePlugin API
    # ------------------------------------------------------------------------
    def get_name(self):
        """Return name."""
        return "Okvim"

    def get_description(self):
        """Return description."""
        return "A plugin for Spyder to enable Vim keybindings"

    def get_icon(self):
        """Return widget icon."""
        return qta.icon('mdi.vimeo', color=MAIN_FG_COLOR)

    def on_initialize(self):
        """."""
        sc = QShortcut(QKeySequence("Esc"),
                       self.vim_cmd.editor_widget.editorsplitter,
                       self.vim_cmd.commandline.setFocus)
        sc.setContext(Qt.WidgetWithChildrenShortcut)

    def check_compatibility(self):
        """."""
        valid = True
        message = ""  # Note: Remember to use _("") to localize the string
        return valid, message

    def on_close(self, cancellable=True):
        """."""
        return True

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

