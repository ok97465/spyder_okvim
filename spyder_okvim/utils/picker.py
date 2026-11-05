"""Immutable picker values and bounded fuzzy search, independent of Qt.

Candidate snapshots keep the complete collected dataset. Search returns only the
best display rows, so later queries can still find candidates outside that list.
"""

from __future__ import annotations

# Standard Libraries
import heapq
from collections.abc import Callable
from dataclasses import dataclass

MAX_CANDIDATES = 100_000
MAX_CANDIDATE_BYTES = 32 * 1024 * 1024
MAX_SEARCH_LENGTH = 8192
MAX_QUERY_LENGTH = 256
MAX_DISPLAY_RESULTS = 1000
# Refinement changes ranking only; the first greedy pass decides match existence.
_MAX_WINDOW_REFINEMENTS = 64
_LINEAR_QUERY_THRESHOLD = 64
_LINEAR_FIELD_THRESHOLD = 2048


@dataclass(frozen=True)
class PickerTarget:
    """Navigation identity; blocks are zero-based and offsets use Qt UTF-16."""

    path: str
    block_number: int | None = None
    column_utf16: int = 0
    offset_utf16: int | None = None
    mark_name: str = ""
    history_index: int = 0
    history_version: int = 0
    commit: str = ""
    old_path: str = ""
    status: str = ""
    ref: str = ""
    upstream: str = ""


@dataclass(frozen=True)
class PickerEntry:
    id: str
    source_id: str
    label: str
    detail: str = ""
    search_text: str = ""
    ordinal: int = 0
    target: PickerTarget | None = None
    preview_kind: str = "code"


@dataclass(frozen=True)
class CandidateSnapshot:
    source_id: str
    scope_id: str
    dataset_version: int
    entries: tuple[PickerEntry, ...]
    completeness: str = "complete"


@dataclass(frozen=True)
class PickerMatch:
    entry: PickerEntry
    score: tuple
    label_matches: tuple[int, ...] = ()
    detail_matches: tuple[int, ...] = ()


@dataclass(frozen=True)
class SearchResult:
    matches: tuple[PickerMatch, ...]
    total_matches: int
    truncated: bool
    cancelled: bool = False


@dataclass
class _RankedEntry:
    """Reverse comparison keeps the worst retained candidate at heap[0]."""

    score: tuple
    index: int
    entry: PickerEntry

    def __lt__(self, other):
        return (self.score, self.index) > (other.score, other.index)


def _normalise(text: str) -> tuple[str, tuple[int, ...]]:
    """Casefold while retaining original character positions for painting."""
    folded = []
    positions = []
    for index, character in enumerate(text[:MAX_SEARCH_LENGTH]):
        piece = character.casefold()
        folded.append(piece)
        positions.extend([index] * len(piece))
    return "".join(folded), tuple(positions)


def _subsequence(
    query: str, text: str, cancel: Callable[[], bool] | None = None
) -> tuple[int, ...] | None:
    """Find a subsequence with bounded minimum-window refinement.

    Shrink forward matches backwards, then refine a bounded number of windows.
    Long fields/queries use one linear greedy window; their minimum-span ranking
    is approximate, while match existence remains exact. Exact substrings remain
    optimal and short-circuit repeated-character input.
    """
    exact = text.find(query)
    if exact >= 0:
        return tuple(range(exact, exact + len(query)))
    first = text.find(query[0])
    best = None
    best_span = len(text) + 1
    refinements = 0
    refinement_limit = (
        1
        if len(query) > _LINEAR_QUERY_THRESHOLD or len(text) > _LINEAR_FIELD_THRESHOLD
        else _MAX_WINDOW_REFINEMENTS
    )
    while first >= 0:
        if cancel is not None and cancel():
            return None
        cursor = first
        for character in query[1:]:
            cursor = text.find(character, cursor + 1)
            if cursor < 0:
                return best
        end = cursor
        positions = [end]
        for character in reversed(query[:-1]):
            cursor = text.rfind(character, first, cursor)
            positions.append(cursor)
        positions.reverse()
        span = end - cursor + 1
        if span < best_span:
            best = tuple(positions)
            best_span = span
        refinements += 1
        if refinements >= refinement_limit:
            return best
        first = text.find(query[0], cursor + 1)
    return best


def _field_matches(
    query: str, text: str, cancel: Callable[[], bool] | None = None
) -> tuple[int, ...]:
    folded, original = _normalise(text)
    matches = _subsequence(query, folded, cancel)
    return tuple(dict.fromkeys(original[i] for i in matches)) if matches else ()


def search(
    snapshot: CandidateSnapshot,
    query: str,
    cancel: Callable[[], bool] | None = None,
    limit: int = MAX_DISPLAY_RESULTS,
) -> SearchResult:
    """Rank all candidates, retaining only a bounded best-N display list.

    Empty queries use provider order. Nonempty queries ignore whitespace and
    case, then rank by bounded minimum-window score, start and stable textual
    ties. Refinement is approximate on long or repetitive fields. Returned rows
    are reversed so the best match is nearest the prompt.
    Cancellation returns no selectable partial result.
    """
    query = "".join(query.split()).casefold()[:MAX_QUERY_LENGTH]
    limit = max(0, min(limit, MAX_DISPLAY_RESULTS))
    total = 0
    heap = []

    for index, entry in enumerate(snapshot.entries):
        if index % 64 == 0 and cancel is not None and cancel():
            return SearchResult((), 0, False, cancelled=True)
        if query:
            text = entry.search_text or f"{entry.label} {entry.detail}"
            folded = text[:MAX_SEARCH_LENGTH].casefold()
            positions = _subsequence(query, folded, cancel)
            if positions is None:
                if cancel is not None and cancel():
                    return SearchResult((), 0, False, cancelled=True)
                continue
            score = (
                positions[-1] - positions[0] + 1,
                positions[0],
                folded,
                entry.ordinal,
            )
        else:
            score = (entry.ordinal, index)
        total += 1
        if not limit:
            continue
        if len(heap) < limit:
            heapq.heappush(heap, _RankedEntry(score, index, entry))
        elif (score, index) < (heap[0].score, heap[0].index):
            heapq.heapreplace(heap, _RankedEntry(score, index, entry))
    if cancel is not None and cancel():
        return SearchResult((), 0, False, cancelled=True)
    ranked_rows = sorted(heap, key=lambda row: (row.score, row.index), reverse=True)
    matches = []
    for row in ranked_rows:
        if cancel is not None and cancel():
            return SearchResult((), 0, False, cancelled=True)
        matches.append(
            PickerMatch(
                row.entry,
                row.score,
                _field_matches(query, row.entry.label, cancel) if query else (),
                _field_matches(query, row.entry.detail, cancel) if query else (),
            )
        )
    if cancel is not None and cancel():
        return SearchResult((), 0, False, cancelled=True)
    return SearchResult(tuple(matches), total, total > len(matches))
