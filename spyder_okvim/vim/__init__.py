"""Expose Vim core classes.

The contents of this package were originally located under
``spyder_okvim.utils.vim_status``.  They were moved here to better reflect
their role as the core Vim implementation.  The old package still re-exports
these classes for backwards compatibility.
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


