# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""Spyder OkVim Plugin."""

from .plugin import OkVim as PLUGIN_CLASS  # pylint: disable=C0103
PLUGIN_CLASS

VERSION_INFO = (0, 0, 1, 'dev0')
__version__ = '.'.join(map(str, VERSION_INFO))
