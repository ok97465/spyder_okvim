# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License

"""Spyder okvim default configuration."""

# Standard Libraries
from dataclasses import dataclass, fields

# Third Party Libraries
from qtpy.QtCore import Qt

CONF_SECTION = "spyder_okvim"

KEYCODE2STR = {
    Qt.Key_Return: "\r",
    Qt.Key_Enter: "\r",
    Qt.Key_Space: " ",
    Qt.Key_Backspace: "\b",
}

CONF_DEFAULTS = [
    (
        CONF_SECTION,
        {
            "ignorecase": True,
            "smartcase": True,
            "use_leap": True,
            "highlight_yank": True,
            "highlight_yank_duration": 400,
            "yanky_enabled": True,
            "yank_history_length": 100,
            "highlight_put": True,
            "leader_key": "Space",
            "which_key_enabled": True,
            "which_key_delay": 300,
            "commandline_completion_enabled": True,
            "commandline_history_enabled": True,
            "substitute_guide_enabled": True,
            "substitute_preview_enabled": True,
        },
    )
]

# Previous releases used Spyder's fallback version because CONF_ was misspelled.
# Keep that version to preserve existing plugin options.
CONF_VERSION = "0.0.0"


@dataclass(frozen=True)
class PluginSettings:
    """Applied search/cursor options, independent of the configuration store.

    Refresh the snapshot at the plugin's settings boundary. In-flight requests
    retain the values that produced their pattern and cursor presentation.
    """

    ignorecase: bool = True
    smartcase: bool = True
    use_leap: bool = True
    highlight_yank: bool = True
    highlight_yank_duration: int = 400
    highlight_put: bool = True


def read_settings():
    """Read applied options and normalize highlight duration at the host boundary."""
    # Third Party Libraries
    from spyder.config.manager import CONF

    defaults = PluginSettings()
    values = {
        field.name: CONF.get(
            CONF_SECTION, field.name, default=getattr(defaults, field.name)
        )
        for field in fields(PluginSettings)
    }
    try:
        values["highlight_yank_duration"] = max(
            0, int(values["highlight_yank_duration"])
        )
    except (TypeError, ValueError):
        values["highlight_yank_duration"] = defaults.highlight_yank_duration
    return PluginSettings(**values)


def register_selection_layers():
    """Register Spyder drawing order once during plugin/view initialization."""
    # Third Party Libraries
    from spyder.plugins.editor.api.decoration import DRAW_ORDERS

    DRAW_ORDERS.update(
        {
            "vim_search": 6,
            "vim_search_current": 7,
            "hl_put": 7,
            "hl_yank": 7,
            "vim_substitute_preview": 7,
            "vim_surround_preview": 8,
            "vim_selection": 8,
            "vim_cursor": 9,
            "vim_substitute": 10,
        }
    )


def bookmarks_path():
    """Return the existing bookmark storage path without changing its schema."""
    # Standard Libraries
    import os.path as osp

    # Third Party Libraries
    from spyder.config.manager import CONF

    return osp.join(CONF.get_plugin_config_path(CONF_SECTION), "bookmarks.json")
