from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class MotionType(IntEnum):
    """Types of cursor motions."""

    BlockWise = 0
    LineWise = 1
    CharWise = 2
    CharWiseIncludingEnd = 3


@dataclass
class MotionInfo:
    """Information about a computed motion."""

    cursor_pos: int | None = None
    sel_start: int | None = None
    sel_end: int | None = None
    motion_type: MotionType = MotionType.LineWise
