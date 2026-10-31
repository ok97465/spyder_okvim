"""Finite candidate scans and visible-line results for substitute overlays."""

from __future__ import annotations

# Standard Libraries
from dataclasses import dataclass
from itertools import chain
from time import monotonic

# Project Libraries
from spyder_okvim.utils import substitute


@dataclass(frozen=True)
class PreviewLimits:
    """Internal budgets, replaceable with small values in focused tests."""

    max_lines: int = 5000
    max_matches: int = 2000
    max_line_chars: int = 20000
    max_scan_chars: int = 500000
    max_command_chars: int = 16000
    max_preview_lines: int = 100
    max_output_chars: int = 20000
    max_expansion_chars: int = 20000


@dataclass(frozen=True)
class PreviewRow:
    """One changed paragraph, with output positions measured in UTF-16 units."""

    block_number: int
    before: str
    after: str
    replacements: tuple[tuple[int, int], ...]
    deletions: tuple[int, ...]
    source_spans: tuple[tuple[int, int, int], ...] = ()


@dataclass(frozen=True)
class PreviewResult:
    """Candidate spans, bounded visible results and scan coverage.

    Requested viewport rows are scanned first. The first/last line numbers bound
    visited rows and do not imply that every intervening row was examined.
    """

    spans: tuple[tuple[int, int], ...]
    match_count: int
    matched_lines: int
    partial: bool
    reasons: tuple[str, ...]
    count_only: bool
    confirm: bool
    read_only: bool = False
    first_line: int = 1
    last_line: int = 1
    scanned_lines: int = 0
    rows: tuple[PreviewRow, ...] = ()
    output_truncated: bool = False
    omitted_blocks: tuple[int, ...] = ()


def safe_highlight_span(source, start, end):
    """Widen UTF-16-unit matches to displayable character boundaries."""
    try:
        substitute.validate_utf16_boundary(source, start)
    except ValueError:
        start -= 1
    try:
        substitute.validate_utf16_boundary(source, end)
    except ValueError:
        end += 1
    return start, end


def _output_marks(source, edits):
    """Map changes and unchanged syntax fragments to output UTF-16 positions."""
    replacements, deletions, source_spans = [], [], []
    delta, previous_end = 0, 0

    for start, end, replacement in edits:
        encoded = replacement.encode("utf-16-le")
        if encoded == source[start * 2 : end * 2]:
            continue
        if previous_end < start:
            source_spans.append((previous_end, start, previous_end + delta))
        width = len(encoded) // 2
        if replacement:
            replacements.append((start + delta, start + delta + width))
        else:
            deletions.append(start + delta)
        delta += width - (end - start)
        previous_end = end
    if previous_end < len(source) // 2:
        source_spans.append((previous_end, len(source) // 2, previous_end + delta))
    return tuple(replacements), tuple(deletions), tuple(source_spans)


class SubstitutePreview:
    """Yield between bounded lines/matches without mutating the source document.

    ``preview_lines`` contains visible, zero-based block numbers. Only those
    lines expand replacements, and they are visited before the remaining range.
    Omitting it retains the inexpensive candidate-only scan. The owner checks
    document/session identity before each step and before publishing results.
    A single Qt regex call still has no hard timeout.
    """

    def __init__(self, document, prepared, *, limits=None, preview_lines=None):
        self.prepared = prepared
        self.limits = limits or PreviewLimits()
        requested = list(
            dict.fromkeys(
                number
                for number in preview_lines or ()
                if prepared.first_line <= number <= prepared.last_line
            )
        )
        priority_lines = requested[: self.limits.max_preview_lines]
        self._preview_lines = frozenset(priority_lines)
        self._omitted_blocks = (
            requested[self.limits.max_preview_lines :]
            if prepared.replacement_prepared and not prepared.count_only
            else []
        )
        self.done = False
        self._spans = []
        self._rows = []
        self._reasons = []
        self._partial = False
        if self._omitted_blocks:
            self._reasons.append("visible line limit")
        self._match_count = self._matched_lines = self._scanned_lines = 0
        self._scan_chars = self._output_chars = self._expansion_chars = 0
        self._expansion_exhausted = False
        self._first_scanned = self._last_scanned = None
        self._iterator = self._scan(document, priority_lines)

    @property
    def result(self):
        first = self._first_scanned
        last = self._last_scanned
        return PreviewResult(
            tuple(self._spans),
            self._match_count,
            self._matched_lines,
            self._partial or not self.done,
            tuple(self._reasons),
            self.prepared.count_only,
            self.prepared.confirm,
            first_line=(first if first is not None else self.prepared.first_line) + 1,
            last_line=(last if last is not None else self.prepared.first_line) + 1,
            scanned_lines=self._scanned_lines,
            rows=tuple(self._rows),
            output_truncated=bool(self._omitted_blocks),
            omitted_blocks=tuple(self._omitted_blocks),
        )

    def step(self, max_milliseconds=8):
        """Perform a short chunk, returning whether the scan has finished."""
        if self.done:
            return True
        deadline = monotonic() + max(0, max_milliseconds) / 1000
        # Always make progress, including when tests use a zero time budget.
        for _ in range(128):
            try:
                next(self._iterator)
            except StopIteration:
                self.done = True
                return True
            except ValueError:
                # A later invalid capture must discard earlier visible results.
                self._spans.clear()
                self._rows.clear()
                self._match_count = self._matched_lines = 0
                self._omit("invalid result", partial=True)
                self.done = True
                raise
            if monotonic() >= deadline:
                break
        return False

    def _omit(self, reason, *, partial=False):
        if reason not in self._reasons:
            self._reasons.append(reason)
        self._partial |= partial

    def _omit_output(self, block_number, reason):
        if block_number not in self._omitted_blocks:
            self._omitted_blocks.append(block_number)
        self._omit(reason)

    def _scan(self, document, priority_lines):
        prepared, limits = self.prepared, self.limits
        if (
            len(prepared.spec.pattern) + len(prepared.spec.replacement)
            > limits.max_command_chars
        ):
            self._omit("command length limit", partial=True)
            return
        remaining_lines = (
            number
            for number in range(prepared.first_line, prepared.last_line + 1)
            if number not in self._preview_lines
        )
        for number in chain(priority_lines, remaining_lines):
            if self._scanned_lines >= limits.max_lines:
                self._omit("line limit", partial=True)
                return
            block = document.findBlockByNumber(number)
            self._scanned_lines += 1
            self._first_scanned = (
                number
                if self._first_scanned is None
                else min(self._first_scanned, number)
            )
            self._last_scanned = (
                number
                if self._last_scanned is None
                else max(self._last_scanned, number)
            )
            original = block.text()
            if len(original) > limits.max_line_chars:
                self._omit("long line omitted", partial=True)
                if number in self._preview_lines:
                    self._omit_output(number, "long line omitted")
                yield
                continue
            if self._scan_chars + len(original) > limits.max_scan_chars:
                self._omit("scan character limit", partial=True)
                return
            self._scan_chars += len(original)
            source = original.encode("utf-16-le")
            render = (
                number in self._preview_lines
                and prepared.replacement_prepared
                and not prepared.count_only
            )
            edits = [] if render else None
            output_size = len(original)
            output_reason = None
            if render and self._output_chars + len(original) > limits.max_output_chars:
                edits = None
                output_reason = "output character limit"
            elif render and self._expansion_exhausted:
                edits = None
                output_reason = "replacement expansion limit"
            found = False
            for match in substitute.iter_substitution_matches(
                prepared.pattern, original, prepared.global_matches
            ):
                if self._match_count >= limits.max_matches:
                    self._omit("match limit", partial=True)
                    if render:
                        self._omit_output(number, "incomplete line")
                    return
                self._match_count += 1
                if not found:
                    self._matched_lines += 1
                    found = True
                    if output_reason is not None:
                        self._omit_output(number, output_reason)
                start, end = match.capturedStart(), match.capturedEnd()
                safe_start, safe_end = safe_highlight_span(source, start, end)
                self._spans.append(
                    (block.position() + safe_start, block.position() + safe_end)
                )
                if edits is not None:
                    try:
                        edit = substitute.substitution_match(
                            prepared.tokens,
                            source,
                            match,
                            max_chars=min(
                                limits.max_expansion_chars - self._expansion_chars,
                                limits.max_output_chars
                                - self._output_chars
                                - len(original),
                            ),
                        )
                    except substitute.ReplacementLimitExceeded:
                        # Once bounded expansion fails, spend no further work
                        # retrying the same oversized replacement on later rows.
                        self._expansion_exhausted = True
                        self._expansion_chars = limits.max_expansion_chars
                        edits = None
                        self._omit_output(number, "replacement expansion limit")
                    else:
                        start, end, replacement = edit
                        self._expansion_chars += len(replacement)
                        output_size += len(replacement) - len(
                            source[start * 2 : end * 2].decode("utf-16-le")
                        )
                        edits.append(edit)
                yield
            if found and edits is not None:
                if (
                    self._output_chars + len(original) + output_size
                    > limits.max_output_chars
                ):
                    self._omit_output(number, "output character limit")
                else:
                    after = substitute.assemble_substitution_line(source, edits).decode(
                        "utf-16-le"
                    )
                    if after != original:
                        replacements, deletions, source_spans = _output_marks(
                            source, edits
                        )
                        self._rows.append(
                            PreviewRow(
                                number,
                                original,
                                after,
                                replacements,
                                deletions,
                                source_spans,
                            )
                        )
                        self._output_chars += len(original) + len(after)
            yield
