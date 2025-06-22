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
from .macro import MacroManager
from .label import InlineLabel
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
    "InlineLabel",
    "VimCursor",
    "VimStatus",
]


