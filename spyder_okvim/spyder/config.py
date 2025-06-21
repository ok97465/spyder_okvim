# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License

"""Spyder okvim default configuration."""

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
            "use_sneak": True,
            "highlight_yank": True,
            "highlight_yank_duration": 400,
            "cursor_fg_color": "#000000",
            "cursor_bg_color": "#BBBBBB",
            "select_fg_color": "#A9B7C6",
            "select_bg_color": "#214283",
            "search_fg_color": "#A9B7C6",
            "search_bg_color": "#30652F",
            "yank_fg_color": "#17172d",
            "yank_bg_color": "#5cacee",
            "leader_key": "Space",
        },
    )
]

CONF_VERSION = "0.9"
