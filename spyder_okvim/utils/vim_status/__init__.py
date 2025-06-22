"""Compatibility wrapper for :mod:`spyder_okvim.vim`."""

from spyder_okvim.vim import (
    VimState,
    FindInfo,
    InputCmdInfo,
    DotCmdInfo,
    KeyInfo,
    RegisterInfo,
    SearchInfo,
    MacroManager,
    InlineLabel,
    VimCursor,
    VimStatus,
)

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
