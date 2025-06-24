"""Manage the jump list for navigating positions."""

from dataclasses import dataclass


@dataclass
class Jump:
    file: str
    pos: int


class JumpList:
    """Simple jump list implementation."""

    def __init__(self, max_items: int = 100) -> None:
        self.max_items = max_items
        self.jumps: list[Jump] = []
        self.index: int = 0

    def push(self, file: str, pos: int) -> None:
        """Add a new jump location."""
        if self.index < len(self.jumps):
            self.jumps = self.jumps[: self.index]
        if self.jumps and self.jumps[-1].file == file and self.jumps[-1].pos == pos:
            return
        self.jumps.append(Jump(file, pos))
        if len(self.jumps) > self.max_items:
            self.jumps.pop(0)
        self.index = len(self.jumps)

    def back(self) -> Jump | None:
        """Return previous jump and update index."""
        if self.index <= 1:
            return None
        self.index -= 1
        return self.jumps[self.index - 1]

    def forward(self) -> Jump | None:
        """Return next jump and update index."""
        if self.index >= len(self.jumps):
            return None
        jump = self.jumps[self.index]
        self.index += 1
        return jump

    def pop_last(self) -> None:
        """Remove the most recently added jump if present."""
        if not self.jumps:
            return
        self.jumps.pop()
        if self.index > len(self.jumps):
            self.index = len(self.jumps)
