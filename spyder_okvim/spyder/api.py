# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2021, Spyder Bot
#
# Licensed under the terms of the MIT license
# ----------------------------------------------------------------------------
"""Spyder Custom Layout API."""

# Third Party Libraries
from spyder.api.plugins import Plugins
from spyder.plugins.layout.api import BaseGridLayoutType


class SpyderCustomLayouts:
    CustomLayout = "spyder_custom_layout"


class CustomLayout(BaseGridLayoutType):
    """Custom layout for the SpyderCustomLayout plugin."""

    ID = SpyderCustomLayouts.CustomLayout

    def __init__(self, parent_plugin: Plugins) -> None:
        super().__init__(parent_plugin)

        # Explorer/Files and OutlineExplorer tabbed
        # self.add_area(
        #     [Plugins.OutlineExplorer, Plugins.Explorer],
        #     0, 0, row_span=2, visible=True, default=True)

        # Explorer/Files and OutlineExplorer divided
        self.add_area([Plugins.Explorer], 0, 0, visible=True, default=True)
        self.add_area([Plugins.OutlineExplorer], 1, 0, visible=True)

        # Triggers and error since there is an unassigned space between the
        # Editor (column 1) and the VariableExplorer (column 3)
        # self.add_area([Plugins.Editor], 0, 1)

        # Editor in the middle taken at least half of the space available
        self.add_area([Plugins.Editor], 0, 1, col_span=2, row_span=2)

        # VariableExplorer in the usual place (top-right)
        self.add_area([Plugins.VariableExplorer], 0, 3)

        # Triggers and error when loading the layout since the area will
        # overlap with the Editor (col_span=2 therefore column 1 and 2 will be
        # used by the Editor)
        # self.add_area([Plugins.IPythonConsole], 1, 2)

        # Valid area definition to put the IPython Console in the default place
        # bottom-right
        self.add_area([Plugins.IPythonConsole], 1, 3)

    @staticmethod
    def get_name() -> str:
        return "Spyder_okvim"
