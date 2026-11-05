"""Shared bounded content for picker metadata and independent previews.

This module owns no editor or widget. Workers read disk here; the GUI can supply
an immutable snapshot of a live document with :func:`from_text` instead.
"""

from __future__ import annotations

from array import array
from bisect import bisect_right
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
import codecs
import io
import os
import re
import sys
import threading
import tokenize

from spyder_okvim.utils.picker import PickerTarget


MAX_READ_BYTES = 1024 * 1024
MAX_PREVIEW_LINES = 2000
MAX_PREVIEW_CHARS = 200_000
MAX_CACHE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class ContentSnapshot:
    text: str
    identity: tuple = ()
    complete: bool = True
    message: str = ""

    @cached_property
    def _index(self) -> tuple[array, array]:
        """Compact indexes are built once and shared by all locations."""
        starts = array("I", [0])
        starts.extend(match.end() for match in re.finditer("\n", self.text))
        astral_ends = array("I")
        for match in re.finditer("[\U00010000-\U0010ffff]", self.text):
            astral_ends.append(match.start() + len(astral_ends) + 2)
        return starts, astral_ends


@dataclass(frozen=True)
class LocationMetadata:
    line_number: int | None
    column_number: int | None
    text: str = ""
    message: str = ""


@dataclass(frozen=True)
class ContentPreview:
    text: str
    first_line: int = 1
    target_line: int | None = None
    message: str = ""
    language: str = ""


def from_text(
    text: str, identity: tuple = (), complete: bool = True
) -> ContentSnapshot:
    """Create bounded immutable content from text already captured on the GUI."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Bound memory in UTF-8 bytes, including non-BMP characters. A partial final
    # character is omitted rather than replaced, preserving the valid prefix.
    raw = text[:MAX_READ_BYTES].encode("utf-8", errors="replace")
    if len(raw) > MAX_READ_BYTES or len(text) > MAX_READ_BYTES:
        text = raw[:MAX_READ_BYTES].decode("utf-8", errors="ignore")
        complete = False
    message = "Content read limit reached" if not complete else ""
    return ContentSnapshot(text, identity, complete, message)


def _utf16_offset(position: int, astral_ends: array) -> int:
    """Convert a Python position using the shared compact astral index."""
    low, high = 0, len(astral_ends)
    while low < high:
        middle = (low + high) // 2
        if astral_ends[middle] - middle - 1 <= position:
            low = middle + 1
        else:
            high = middle
    return position + low


def locate(content: ContentSnapshot, target: PickerTarget) -> LocationMetadata:
    """Resolve original coordinates, or explain why the prefix is insufficient.

    A truncated prefix never turns an unreachable offset into a guessed first
    line. Compact indexes avoid rescanning a file for every mark/jump.
    """
    if content.message and not content.text and content.complete:
        return LocationMetadata(None, None, message=content.message)
    text = content.text
    starts, astral_ends = content._index
    if target.offset_utf16 is not None:
        offset = max(0, target.offset_utf16)
        length_utf16 = len(text) + len(astral_ends)
        if offset > length_utf16 or (not content.complete and offset >= length_utf16):
            message = (
                "Location preview limited by content read limit"
                if not content.complete
                else "Location no longer exists"
            )
            return LocationMetadata(None, None, message=message)
        previous_astral = bisect_right(astral_ends, offset)
        position = offset - previous_astral
        if (
            previous_astral < len(astral_ends)
            and astral_ends[previous_astral] == offset + 1
        ):
            # Match Qt helper behavior for an offset splitting a surrogate pair.
            position -= 1
            offset -= 1
        block_number = bisect_right(starts, position) - 1
        start = starts[block_number]
        start_utf16 = _utf16_offset(start, astral_ends)
        column = offset - start_utf16
    else:
        block_number = max(0, target.block_number or 0)
        if block_number >= len(starts):
            message = (
                "Location preview limited by content read limit"
                if not content.complete
                else "Location no longer exists"
            )
            return LocationMetadata(None, None, message=message)
        start = starts[block_number]
        start_utf16 = _utf16_offset(start, astral_ends)
        column = max(0, target.column_utf16)
    end = starts[block_number + 1] - 1 if block_number + 1 < len(starts) else len(text)
    if block_number + 1 == len(starts) and not content.complete:
        return LocationMetadata(
            None, None, message="Location preview limited by content read limit"
        )
    line = text[start : min(end, start + MAX_PREVIEW_CHARS)]
    if column > _utf16_offset(end, astral_ends) - start_utf16:
        return LocationMetadata(
            block_number + 1,
            None,
            line,
            "Column no longer exists",
        )
    return LocationMetadata(block_number + 1, column + 1, line)


def preview(content: ContentSnapshot, target: PickerTarget) -> ContentPreview:
    """Build a bounded window around a location without changing its target."""
    location = locate(content, target)
    if location.line_number is None:
        return ContentPreview("", message=location.message or content.message)
    starts, _ = content._index
    line_count = len(starts) - (not content.complete)
    wanted = location.line_number - 1
    start = max(0, wanted - MAX_PREVIEW_LINES // 2)
    end = min(line_count, start + MAX_PREVIEW_LINES)
    stop = starts[end] - 1 if end < len(starts) else len(content.text)
    rendered = content.text[starts[start] : stop]
    message = content.message or location.message
    if len(rendered) > MAX_PREVIEW_CHARS:
        # Keep the requested source line visible even if earlier long lines
        # alone would consume the entire display budget.
        start = wanted
        end = min(line_count, start + MAX_PREVIEW_LINES)
        stop = starts[end] - 1 if end < len(starts) else len(content.text)
        rendered = content.text[
            starts[start] : min(stop, starts[start] + MAX_PREVIEW_CHARS)
        ]
        message = "Preview display limit reached"
    elif start or end < line_count:
        message = message or "Preview window; omitted surrounding lines"
    suffix = os.path.splitext(target.path)[1].lower()
    language = {".py": "py", ".pyw": "py", ".diff": "diff", ".patch": "diff"}.get(
        suffix, ""
    )
    return ContentPreview(rendered, start + 1, location.line_number, message, language)


def _disk_identity(path: str) -> tuple:
    stat = os.stat(path)
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _decode(raw: bytes, complete: bool) -> str:
    """Handle BOMs and Python coding cookies before the UTF-8/Latin-1 fallback."""
    if raw.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        encoding = "utf-32"
    elif raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encoding = "utf-16"
    else:
        # Reject NUL-containing binary input before trying legacy encodings.
        if b"\x00" in raw:
            raise ValueError("Binary file; code preview unavailable")
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        except (SyntaxError, LookupError):
            encoding = "utf-8"
    try:
        decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
        return decoder.decode(raw, final=complete)
    except (UnicodeError, LookupError):
        # Spyder supports legacy files as well. Latin-1 is lossless for bytes
        # without a detected encoding; no replacement characters shift offsets.
        return raw.decode("latin-1")


class ContentService:
    """Thread-safe bounded LRU keyed by path and disk identity.

    Failed, cancelled or unstable reads are never cached. Concurrent callers may
    read the same file, but the shared content lane normally serialises them.
    """

    def __init__(self, max_cache_bytes: int = MAX_CACHE_BYTES):
        self.max_cache_bytes = max(0, max_cache_bytes)
        self._cache: OrderedDict[tuple, tuple[ContentSnapshot, int]] = OrderedDict()
        self._cache_bytes = 0
        self._lock = threading.Lock()

    @property
    def cache_bytes(self) -> int:
        with self._lock:
            return self._cache_bytes

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._cache_bytes = 0

    def read(
        self, path: str, cancel: Callable[[], bool] | None = None
    ) -> ContentSnapshot:
        if cancel is not None and cancel():
            return ContentSnapshot("", message="Cancelled")
        try:
            path = os.path.abspath(path)
            identity = _disk_identity(path)
            key = (path, identity)
            with self._lock:
                cached = self._cache.get(key)
                if cached is not None:
                    self._cache.move_to_end(key)
                    return cached[0]
            with open(path, "rb") as stream:
                raw = stream.read(MAX_READ_BYTES + 1)
            if cancel is not None and cancel():
                return ContentSnapshot("", message="Cancelled")
            if identity != _disk_identity(path):
                return ContentSnapshot(
                    "", message="File changed while reading; refresh to retry"
                )
            complete = len(raw) <= MAX_READ_BYTES
            raw = raw[:MAX_READ_BYTES]
            text = _decode(raw, complete)
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            result = ContentSnapshot(
                text,
                (path, *identity),
                complete,
                "Content read limit reached" if not complete else "",
            )
        except (OSError, ValueError) as error:
            return ContentSnapshot("", message=str(error))
        # Include the compact coordinate indexes in the LRU budget as well.
        starts, astral_ends = result._index
        size = (
            sys.getsizeof(text)
            + sys.getsizeof(starts)
            + sys.getsizeof(astral_ends)
            + 256
        )
        if size <= self.max_cache_bytes:
            with self._lock:
                # Remove obsolete versions of a path instead of retaining them.
                for obsolete in [k for k in self._cache if k[0] == path]:
                    self._cache_bytes -= self._cache.pop(obsolete)[1]
                self._cache[key] = (result, size)
                self._cache_bytes += size
                while self._cache_bytes > self.max_cache_bytes:
                    _, (_, removed_size) = self._cache.popitem(last=False)
                    self._cache_bytes -= removed_size
        return result
