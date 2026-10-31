"""Motion values shared by command, selection and editing code.

This module imports no Qt or Spyder objects. Coordinates describe the existing
Qt document, so integer positions are UTF-16 offsets rather than Python string
indices; applying them remains the caller's mode-specific responsibility.
"""

from __future__ import annotations

# Standard Libraries
from dataclasses import dataclass
from enum import IntEnum


class MotionType(IntEnum):
    """How an operator interprets a destination or an explicit object range.

    BlockWise denotes an explicit text-object span, not Visual block mode.
    CharWise excludes the destination from an operator's range, whereas
    CharWiseIncludingEnd includes it. LineWise expands to complete Qt blocks.
    Existing numeric values and spelling remain stable for callers.
    """

    BlockWise = 0
    LineWise = 1
    CharWise = 2
    CharWiseIncludingEnd = 3


@dataclass
class MotionInfo:
    """A UTF-16 cursor destination and/or explicit selection boundaries.

    ``cursor_pos`` is None when no destination exists or a text object supplies
    only a selection. ``sel_start`` and ``sel_end`` form a half-open character
    span [start, end); LineWise spans can end at a block's content end, with the
    applying policy adding the line separator as needed. None boundaries mean
    no matching object, not the beginning/end of the document.

    Instances remain mutable because inner objects and surround operations
    adjust delimiters before applying the final range. Constructing a motion
    does not change the cursor, document, registers or undo stack.
    """

    cursor_pos: int | None = None
    sel_start: int | None = None
    sel_end: int | None = None
    motion_type: MotionType = MotionType.LineWise
