"""Validate replacement text and compute Ex substitutions without editing UI."""

from __future__ import annotations

from dataclasses import dataclass
from unicodedata import category

from qtpy.QtCore import QRegularExpression

# QTextDocument paragraphs and Unicode line separators must never be inserted
# by this first, line-preserving implementation.
_LINE_SEPARATORS = frozenset("\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029")


@dataclass(frozen=True)
class SubstitutionPlan:
    """Original-order edits with absolute UTF-16 offsets and target totals."""

    edits: tuple[tuple[int, int, str], ...]
    match_count: int
    line_count: int
    last_line: int | None


def tokenize_replacement(replacement: str, delimiter: str):
    """Return literal strings and integer capture references, validating once."""
    if replacement.startswith(r"\="):
        raise ValueError("Expression replacements are not supported")
    if any(char in _LINE_SEPARATORS for char in replacement):
        raise ValueError("Line breaks in replacements are not supported")
    tokens = []
    literal = []

    def capture(number):
        if literal:
            tokens.append("".join(literal))
            literal.clear()
        tokens.append(number)

    index = 0
    while index < len(replacement):
        char = replacement[index]
        if char == "&":
            capture(0)
        elif char == "\\":
            index += 1
            if index == len(replacement):
                literal.append("\\")
                break
            escaped = replacement[index]
            if escaped in (delimiter, "&", "\\"):
                literal.append(escaped)
            elif escaped == "t":
                literal.append("\t")
            elif escaped == "b":
                literal.append("\b")
            elif escaped in "0123456789":
                capture(int(escaped))
            elif escaped in "rnuUlLeE":
                raise ValueError(f"Unsupported replacement escape: \\{escaped}")
            else:
                # Vim drops the backslash for otherwise unrecognized escapes.
                literal.append(escaped)
        else:
            literal.append(char)
        index += 1
    if literal:
        tokens.append("".join(literal))
    return tuple(tokens)


def _check_boundary(source: bytes, offset: int):
    """Reject an offset between the UTF-16 halves of a non-BMP character."""
    byte_offset = offset * 2
    if byte_offset < 0 or byte_offset > len(source):
        raise ValueError("Invalid UTF-16 match offset")
    if 0 < byte_offset < len(source):
        before = source[byte_offset - 2] | source[byte_offset - 1] << 8
        after = source[byte_offset] | source[byte_offset + 1] << 8
        if 0xD800 <= before <= 0xDBFF and 0xDC00 <= after <= 0xDFFF:
            raise ValueError("Pattern splits a UTF-16 surrogate pair")


def _expand_replacement(tokens, source, match):
    """Expand only referenced captures, preserving original NBSP characters."""
    captures = {}
    pieces = []
    for token in tokens:
        if not isinstance(token, int):
            pieces.append(token)
            continue
        if token not in captures:
            start, end = match.capturedStart(token), match.capturedEnd(token)
            if start == -1:
                # Vim expands both absent and unmatched groups to empty text.
                captures[token] = ""
            else:
                _check_boundary(source, start)
                _check_boundary(source, end)
                captures[token] = source[start * 2 : end * 2].decode("utf-16-le")
        pieces.append(captures[token])
    replacement = "".join(pieces)
    if any(char in _LINE_SEPARATORS for char in replacement):
        raise ValueError("Line breaks in replacements are not supported")
    return replacement


def _next_character(source, offset):
    """Advance UTF-16 past a character and its composing marks, as Vim does."""
    position = offset
    while position * 2 < len(source):
        unit = int.from_bytes(source[position * 2 : position * 2 + 2], "little")
        width = 2 if 0xD800 <= unit <= 0xDBFF else 1
        char = source[position * 2 : (position + width) * 2].decode(
            "utf-16-le", "surrogatepass"
        )
        if position != offset and category(char) not in ("Mn", "Me"):
            break
        position += width
    return position


def _iter_reset_start_matches(pattern, text, source):
    r"""Restart at reported ends when \K hides text consumed before a match."""
    length = len(source) // 2
    offset, previous_end = 0, -1
    while offset <= length:
        # Strict encoding already validated the subject. Reuse that result,
        # also allowing count-only matches using Qt's UTF-16-unit escape \C.
        match = pattern.match(
            text,
            offset,
            QRegularExpression.NormalMatch,
            QRegularExpression.DontCheckSubjectStringMatchOption,
        )
        if not match.hasMatch():
            return
        start, end = match.capturedStart(), match.capturedEnd()
        if start == end == previous_end:
            offset = _next_character(source, end)
            if offset >= length:
                return
            continue
        yield match
        if end == length:
            return
        offset = previous_end = end


def _iter_matches(pattern, text, global_matches):
    """Follow Vim's empty-match progression with Qt's native UTF-16 iterator."""
    text = text.replace("\u00a0", " ")
    if not global_matches:
        match = pattern.match(text)
        if match.hasMatch():
            yield match
        return

    source = text.encode("utf-16-le")
    if r"\K" in pattern.pattern():
        # Qt's empty-match retries differ from Vim when \K resets the start.
        # Keep repeated Python-to-QString conversions out of the normal path.
        yield from _iter_reset_start_matches(pattern, text, source)
        return
    length = len(source) // 2
    previous_end, minimum_start = -1, 0
    matches = pattern.globalMatch(text)
    while matches.hasNext():
        match = matches.next()
        start, end = match.capturedStart(), match.capturedEnd()
        if start < minimum_start:
            # Qt retries consuming alternatives after an empty match. Restart
            # if that retry swallowed positions where Vim can still match.
            if end > minimum_start:
                matches = pattern.globalMatch(text, minimum_start)
            continue
        if start == end == previous_end:
            minimum_start = _next_character(source, end)
            if minimum_start >= length:
                return
            continue
        yield match
        if end == length:
            return
        previous_end = end
        minimum_start = _next_character(source, end) if start == end else end
        if minimum_start >= length:
            return


def build_substitution_plan(
    document,
    first_line: int,
    last_line: int,
    pattern,
    tokens,
    *,
    global_matches: bool = False,
    count_only: bool = False,
    confirm: bool = False,
) -> SubstitutionPlan:
    """Compute edits in an inclusive block range, using Vim's match progression.

    Count-only execution ignores replacements and never allocates edit lists.
    Confirmation retains every target, including unchanged replacements.
    """
    if not pattern.isValid():
        raise ValueError(f"Invalid pattern: {pattern.errorString()}")
    if not 0 <= first_line <= last_line < document.blockCount():
        raise ValueError("Invalid line range")
    edits = None if count_only else []
    match_count = line_count = 0
    last_target = None
    block = document.findBlockByNumber(first_line)
    for line in range(first_line, last_line + 1):
        original = block.text()
        source = None
        block_edits = None if count_only else []
        found = False
        for match in _iter_matches(pattern, original, global_matches):
            match_count += 1
            found = True
            if count_only:
                continue
            if source is None:
                source = original.encode("utf-16-le")
            start, end = match.capturedStart(), match.capturedEnd()
            _check_boundary(source, start)
            _check_boundary(source, end)
            replacement = _expand_replacement(tokens, source, match)
            if (
                confirm
                or replacement.encode("utf-16-le") != source[start * 2 : end * 2]
            ):
                block_edits.append(
                    (
                        block.position() + start,
                        block.position() + end,
                        replacement,
                    )
                )
        if found:
            line_count += 1
            last_target = line
        if block_edits:
            if confirm:
                edits.extend(block_edits)
                block = block.next()
                continue
            # Several adjacent replacements can cancel each other. Assemble a
            # single paragraph for comparison only, keeping small edit spans
            # for the actual document mutation and its cursor/mark tracking.
            pieces = []
            previous = 0
            for start, end, replacement in block_edits:
                start = (start - block.position()) * 2
                end = (end - block.position()) * 2
                pieces.extend((source[previous:start], replacement.encode("utf-16-le")))
                previous = end
            pieces.append(source[previous:])
            if b"".join(pieces) != source:
                edits.extend(block_edits)
        block = block.next()
    return SubstitutionPlan(
        tuple(edits) if edits is not None else (), match_count, line_count, last_target
    )
