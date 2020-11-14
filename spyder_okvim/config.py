# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License

"""Spyder okvim default configuration."""

CONF_SECTION = 'okvim'

CONF_DEFAULTS = [
    (CONF_SECTION,
     {
      'ignorecase': True,
      'smartcase': True,
      'highlight_yank': True,
      'highlight_yank_duration': 400,
      'cursor_fg_color': "#000000",
      'cursor_bg_color': "#BBBBBB",
      'select_fg_color': "#A9B7C6",
      'select_bg_color': "#214283",
      'search_fg_color': "#A9B7C6",
      'search_bg_color': "#30652F",
      'yank_fg_color': "#A9B7C6",
      'yank_bg_color': "#7D7920"
     }
     ),
    ('shortcuts',
     {
     }
     ),
]

CONF_VERSION = '0.0.1'
