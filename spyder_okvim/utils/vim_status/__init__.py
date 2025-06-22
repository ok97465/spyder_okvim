"""Expose main classes used to keep track of Vim state.

This package splits the old :mod:`vim_status` module into several focused
modules.  Classes from those modules are re-exported here so external code can
keep importing them from ``spyder_okvim.utils.vim_status``.
"""

from .state import (
    VimState,
    FindInfo,
    InputCmdInfo,
    DotCmdInfo,
    KeyInfo,
    RegisterInfo,
)
from .search import SearchInfo
from .macro import MacroManager, ManagerMacro
from .label import InlineLabel, LabelOnTxt
from .cursor import VimCursor
from .status import VimStatus

__all__ = [
    "VimState",
    "FindInfo",
    "InputCmdInfo",
    "DotCmdInfo",
    "KeyInfo",
    "RegisterInfo",
    "SearchInfo",
    "MacroManager",
    "ManagerMacro",
    "InlineLabel",
    "LabelOnTxt",
    "VimCursor",
    "VimStatus",
]
