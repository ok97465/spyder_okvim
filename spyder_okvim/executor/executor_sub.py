"""Compatibility imports for the former collection of submode executors.

Implementations now live in operators, prefixes, search_prompt and leap_input.
Internal callers import those modules directly. Legacy class names remain here
so external imports keep resolving to the same implementation classes.
"""

from .leap_input import LeapInputExecutor as ExecutorSubCmdLeap
from .leap_input import LeapLabelExecutor as ExecutorSubCmdLeapSelect
from .operators import AroundTextObjectExecutor as ExecutorSubMotion_a
from .operators import ChangeOperatorExecutor as ExecutorSubMotion_c
from .operators import DeleteOperatorExecutor as ExecutorSubMotion_d
from .operators import InnerTextObjectExecutor as ExecutorSubMotion_i
from .operators import OperatorMotionExecutor as ExecutorSubMotion
from .operators import YankOperatorExecutor as ExecutorSubMotion_y
from .prefixes import FileExitExecutor as ExecutorSubCmd_Z
from .prefixes import FindCharacterExecutor as ExecutorSubCmd_f_t
from .prefixes import GPrefixExecutor as ExecutorSubCmd_g
from .prefixes import MarkNameExecutor as ExecutorSubCmd_alnum
from .prefixes import NextBlockExecutor as ExecutorSubCmd_closebrace
from .prefixes import NextStructureExecutor as ExecutorSubCmd_closesquarebracket
from .prefixes import OperatorGExecutor as ExecutorSubSubCmd_g
from .prefixes import PreviousBlockExecutor as ExecutorSubCmd_openbrace
from .prefixes import PreviousStructureExecutor as ExecutorSubCmd_opensquarebracket
from .prefixes import RegisterPrefixExecutor as ExecutorSubCmd_register
from .prefixes import ReplaceCharacterExecutor as ExecutorSubCmd_r
from .prefixes import ViewportPrefixExecutor as ExecutorSubCmd_z
from .prefixes import WindowPrefixExecutor as ExecutorSubCmd_window
from .search_prompt import SearchPromptExecutor as ExecutorSearch

__all__ = [
    "ExecutorSubCmdLeap",
    "ExecutorSubCmdLeapSelect",
    "ExecutorSubMotion_a",
    "ExecutorSubMotion_c",
    "ExecutorSubMotion_d",
    "ExecutorSubMotion_i",
    "ExecutorSubMotion",
    "ExecutorSubMotion_y",
    "ExecutorSubCmd_Z",
    "ExecutorSubCmd_f_t",
    "ExecutorSubCmd_g",
    "ExecutorSubCmd_alnum",
    "ExecutorSubCmd_closebrace",
    "ExecutorSubCmd_closesquarebracket",
    "ExecutorSubSubCmd_g",
    "ExecutorSubCmd_openbrace",
    "ExecutorSubCmd_opensquarebracket",
    "ExecutorSubCmd_register",
    "ExecutorSubCmd_r",
    "ExecutorSubCmd_z",
    "ExecutorSubCmd_window",
    "ExecutorSearch",
]
