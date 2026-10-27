"""Bounded, in-memory history of immutable yank and delete values."""

# Standard Libraries
from collections import deque
from dataclasses import dataclass, field
from itertools import count


MAX_ENTRY_BYTES = 1024 * 1024
MAX_HISTORY_BYTES = 10 * 1024 * 1024
_entry_ids = count(1)
_KINDS = ("charwise", "linewise")
_SOURCES = ("yank", "delete", "clipboard")


@dataclass(frozen=True)
class YankEntry:
    """One value, independent of mutable Vim registers and Qt editors."""

    text: str
    kind: str = "charwise"
    source: str = "yank"
    id: int = field(default_factory=lambda: next(_entry_ids))
    byte_size: int = field(init=False)
    line_count: int = field(init=False)

    def __post_init__(self):
        if self.kind not in _KINDS:
            raise ValueError("Yank kind must be charwise or linewise")
        if self.source not in _SOURCES:
            raise ValueError("Unknown yank source")
        text = self.text.replace("\u2029", "\n")
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "byte_size", len(text.encode("utf-8")))
        lines = text.count("\n") + (0 if text.endswith("\n") else 1)
        object.__setattr__(self, "line_count", max(1, lines))

    @classmethod
    def from_register(cls, text, vim_type, source="yank"):
        """Copy a register value at the boundary with the Vim state model."""
        from .state import VimState

        kind = "linewise" if vim_type == VimState.VLINE else "charwise"
        return cls(text, kind, source)


class YankHistory:
    """Newest-first history with consecutive deduplication and byte limits."""

    def __init__(
        self,
        length=100,
        *,
        max_entry_bytes=MAX_ENTRY_BYTES,
        max_bytes=MAX_HISTORY_BYTES,
    ):
        self._validate_length(length)
        if max_entry_bytes < 1 or max_bytes < 1:
            raise ValueError("History byte limits must be positive")
        self.length = length
        self.max_entry_bytes = max_entry_bytes
        self.max_bytes = max_bytes
        self.byte_size = 0
        self.last_skip_reason = None
        self._entries = deque()

    @staticmethod
    def _validate_length(length):
        if isinstance(length, bool) or not isinstance(length, int) or length < 1:
            raise ValueError("History length must be a positive integer")

    def __len__(self):
        return len(self._entries)

    def record(self, text, kind, source="yank"):
        """Record one logical operation, returning only a newly added entry."""
        self.last_skip_reason = None
        if not text:
            self.last_skip_reason = "empty"
            return None
        text = text.replace("\u2029", "\n")
        if self._entries:
            newest = self._entries[0]
            if newest.text == text and newest.kind == kind:
                self.last_skip_reason = "duplicate"
                return None
        entry = YankEntry(text, kind, source)
        if entry.byte_size > min(self.max_entry_bytes, self.max_bytes):
            self.last_skip_reason = "oversize"
            return None
        self._entries.appendleft(entry)
        self.byte_size += entry.byte_size
        self._trim()
        return entry

    def _trim(self):
        while len(self._entries) > self.length or self.byte_size > self.max_bytes:
            self.byte_size -= self._entries.pop().byte_size

    def snapshot(self):
        """Return immutable references without copying their text payloads."""
        return tuple(self._entries)

    def resize(self, length):
        """Apply a positive count limit and evict the oldest entries."""
        self._validate_length(length)
        self.length = length
        self._trim()

    def clear(self):
        """Forget all entries while leaving existing snapshots unchanged."""
        self._entries.clear()
        self.byte_size = 0
        self.last_skip_reason = None
