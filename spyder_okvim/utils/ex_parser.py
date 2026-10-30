"""Small, widget-independent parsers for the supported Ex command syntax."""

from __future__ import annotations

from dataclasses import dataclass


class ExError(ValueError):
    """An invalid Ex command that should be reported in the command line."""


def _decimal_address(address):
    try:
        return int(address)
    except ValueError as error:
        raise ExError("Invalid line address") from error


@dataclass(frozen=True)
class ExHeader:
    """An unresolved line range and the command-name span in the original text."""

    addresses: tuple[str, ...]
    command: str
    argument: str
    command_start: int
    command_end: int
    argument_start: int

    @property
    def explicit_range(self):
        return bool(self.addresses)

    @property
    def line_number(self):
        """A standalone decimal address uses the existing ``:number`` motion."""
        if (
            not self.command
            and not self.argument
            and len(self.addresses) == 1
            and self.addresses[0].isascii()
            and self.addresses[0].isdigit()
        ):
            return _decimal_address(self.addresses[0])
        return None


@dataclass(frozen=True)
class SubstituteSpec:
    """Parsed substitution values; a saved count is never reused by repeats."""

    pattern: str
    replacement: str
    delimiter: str
    flags: str
    count: int | None = None


@dataclass(frozen=True)
class SubstituteGuideContext:
    """Read-only guidance for the field containing the command-line cursor."""

    stage: str
    delimiter: str
    addresses: tuple[str, ...] = ()
    raw_flags: str = ""
    effective_flags: str = ""
    missing_previous: bool = False
    unsupported: str = ""


@dataclass(frozen=True)
class SubstitutePreviewContext:
    """The whole incremental command, independent of the input cursor.

    An unfinished pattern is a search preview, even though pressing Enter on
    that spelling executes a deletion. Only a closed pattern can reuse an
    empty pattern from the last confirmed search.
    """

    header: ExHeader
    spec: SubstituteSpec
    pattern_closed: bool


def _skip_space(text, position):
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def _address(text, position):
    if position < len(text) and text[position] in ".$":
        return text[position], position + 1
    end = position
    while end < len(text) and "0" <= text[end] <= "9":
        end += 1
    if end == position:
        raise ExError("Expected a line address")
    return text[position:end], end


def is_substitute(command: str) -> bool:
    """Recognize substitution spellings and the Ex repeat commands."""
    return command in ("&", "&&", "~") or (
        bool(command) and "substitute".startswith(command)
    )


def scan_header(text: str, incomplete: bool = False) -> ExHeader:
    """Read a range and command from input without its initial colon.

    The substitution body is left intact; its delimiter, escapes, and flags do
    not belong to the header grammar. ``incomplete`` also accepts an unfinished
    range endpoint so Tab never has to validate a substitution body.
    """
    position = _skip_space(text, 0)
    addresses = ()
    if position < len(text) and text[position] == "%":
        addresses = ("%",)
        position = _skip_space(text, position + 1)
    elif position < len(text) and (
        "0" <= text[position] <= "9" or text[position] in ".$"
    ):
        address, position = _address(text, position)
        addresses = (address,)
        position = _skip_space(text, position)
        if position < len(text) and text[position] == ",":
            position = _skip_space(text, position + 1)
            if incomplete and position == len(text):
                addresses += ("",)
            else:
                address, position = _address(text, position)
                addresses += (address,)
                position = _skip_space(text, position)

    start = position
    while position < len(text) and (
        "a" <= text[position] <= "z" or "A" <= text[position] <= "Z"
    ):
        position += 1
    command = text[start:position]
    if not command and text[position : position + 1] in ("&", "~"):
        position += 2 if text.startswith("&&", position) else 1
        command = text[start:position]
    # q! is a command alias; the same punctuation after s is a delimiter.
    if command == "q" and position < len(text) and text[position] == "!":
        command += "!"
        position += 1
    end = position
    if (
        not incomplete
        and not is_substitute(command)
        and position < len(text)
        and not text[position].isspace()
    ):
        raise ExError("Command arguments must follow whitespace")
    argument_start = _skip_space(text, position)
    if not command and argument_start < len(text):
        raise ExError("Invalid command or line range")
    return ExHeader(
        addresses,
        command,
        text[argument_start:],
        start,
        end,
        argument_start,
    )


def resolve_range(
    header: ExHeader, current_line: int, line_count: int
) -> tuple[int, int]:
    """Resolve and validate an inclusive range of zero-based document blocks."""
    line_count = max(line_count, 1)
    if not header.addresses:
        return current_line, current_line
    if header.addresses == ("%",):
        return 0, line_count - 1

    def resolve(address):
        if address == ".":
            return current_line
        if address == "$":
            return line_count - 1
        if not address or not address.isascii() or not address.isdigit():
            raise ExError("Invalid line address")
        # Vim accepts address zero for :substitute as the first line.
        line = max(_decimal_address(address), 1) - 1
        if not 0 <= line < line_count:
            raise ExError(f"Line address out of range: {address}")
        return line

    start = resolve(header.addresses[0])
    end = resolve(header.addresses[-1])
    if start > end:
        raise ExError("Line range is reversed")
    return start, end


def _skip_character_class(text, position):
    """Skip a pattern class, including a leading literal ] and POSIX classes."""
    position += 1
    if text[position : position + 1] == "^":
        position += 1
    if text[position : position + 1] == "]":
        position += 1
    while position < len(text):
        if text[position] == "\\":
            position += 2
        elif text.startswith("[:", position) and ":]" in text[position + 2 :]:
            position = text.index(":]", position + 2) + 2
        elif text[position] == "]":
            return position + 1
        else:
            position += 1
    return position


def _segment(text, start, delimiter, *, pattern=False):
    """Find an unescaped delimiter, ignoring delimiters in pattern classes."""
    position = start
    quoted = escaped = False
    while position < len(text):
        char = text[position]
        # Qt closes a literal span at \E even after another backslash.
        # Ex delimiter escaping still follows backslash parity in that span.
        if pattern and quoted and text.startswith(r"\E", position):
            quoted = False
        elif pattern and not escaped and text.startswith(r"\Q", position):
            quoted = True
        if char == delimiter and not escaped:
            return text[start:position], position + 1, True
        if pattern and not quoted and not escaped and char == "[":
            position = _skip_character_class(text, position)
        else:
            escaped = char == "\\" and not escaped
            position += 1
    return text[start:], len(text), False


def _decode_pattern(pattern, delimiter):
    """Remove delimiter quoting while keeping Qt regular-expression escapes."""
    result = []
    position = 0
    quoted = False
    while position < len(pattern):
        char = pattern[position]
        if quoted:
            # Qt's \Q...\E quotes backslashes too, except for its closing
            # \E. Advance one character so the latter is still recognized
            # when preceded by another literal backslash.
            if pattern.startswith(r"\E", position):
                result.append(r"\E")
                quoted = False
                position += 2
            elif char == "\\" and pattern[position + 1 : position + 2] == delimiter:
                result.append(delimiter)
                position += 2
            else:
                result.append(char)
                position += 1
            continue
        if char == "\\" and position + 1 < len(pattern):
            following = pattern[position + 1]
            if following == delimiter:
                # '-' is special inside classes, '#' in Qt extended mode.
                if delimiter in ".^$*+?{}[]()|#-":
                    result.append("\\")
                result.append(delimiter)
            else:
                result.append(char + following)
                if following == "Q":
                    quoted = True
            position += 2
        else:
            result.append(char)
            position += 1
    return "".join(result)


def _substitute_delimiter(delimiter):
    """Keep incomplete guidance and executable substitution syntax aligned."""
    return (
        33 <= ord(delimiter) <= 126
        and not delimiter.isalnum()
        and delimiter not in '\\"|'
    )


def parse_substitute(body: str, previous_flags: str = "") -> SubstituteSpec:
    """Parse ``/pattern/replacement/flags`` without altering replacement escapes."""
    if not body:
        raise ExError("Specify a substitution pattern and replacement")
    delimiter = body[0]
    if not _substitute_delimiter(delimiter):
        raise ExError("Invalid substitution delimiter")
    pattern, position, closed = _segment(body, 1, delimiter, pattern=True)
    if closed:
        replacement, position, closed = _segment(body, position, delimiter)
    else:
        # :s/pattern is a deletion, just like :s/pattern/.
        replacement = ""
    tail = body[position:] if closed else ""
    flags, count = _substitute_flags(tail, previous_flags)
    return SubstituteSpec(
        _decode_pattern(pattern, delimiter), replacement, delimiter, flags, count
    )


def _scan_substitute_flags(tail, previous_flags):
    """Apply flags and return where the optional count or comment begins."""
    keep_flags = tail.startswith("&")
    position = int(keep_flags)
    # r chooses the pattern for this command; Vim does not remember it with &.
    flags = list(previous_flags.replace("r", "")) if keep_flags else []
    while position < len(tail) and tail[position] in "giInecr":
        flag = tail[position]
        # Vim toggles g, c and e on every occurrence; the other flags are set.
        if flag in "gce" and flag in flags:
            flags.remove(flag)
        else:
            flags.append(flag)
        position += 1

    return "".join(flags), position


def _substitute_flags(tail, previous_flags):
    """Read flags and a count, optionally retaining the previous flags with &."""
    flags, position = _scan_substitute_flags(tail, previous_flags)
    position = start = _skip_space(tail, position)
    while position < len(tail) and "0" <= tail[position] <= "9":
        position += 1
    count = _decimal_address(tail[start:position]) if position > start else None
    if count is not None and not 1 <= count <= 2147483647:
        raise ExError("Substitution count must be a positive 32-bit number")
    position = _skip_space(tail, position)
    if position < len(tail) and tail[position] != '"':
        raise ExError(
            f"Unsupported substitution flag or trailing input: {tail[position:]}"
        )
    return flags, count


def scan_substitute_preview(
    text: str, previous: SubstituteSpec | None = None
) -> SubstitutePreviewContext | None:
    """Read a complete command line without treating unfinished input as final.

    Repeated substitutions and unsupported/incomplete headers have no preview.
    Invalid completed flag tails raise ``ExError`` so a caller can discard the
    old result without reporting an execution error while the user types.
    """
    if not text.startswith(":"):
        return None
    try:
        header = scan_header(text[1:])
    except ExError:
        return None
    body = header.argument
    if (
        not header.command
        or not "substitute".startswith(header.command)
        or not body
        or not _substitute_delimiter(body[0])
    ):
        return None
    delimiter = body[0]
    pattern, position, pattern_closed = _segment(body, 1, delimiter, pattern=True)
    replacement, replacement_closed = "", False
    if pattern_closed:
        replacement, position, replacement_closed = _segment(body, position, delimiter)
    tail = body[position:] if replacement_closed else ""
    flags, count = _substitute_flags(
        tail, previous.flags if previous is not None else ""
    )
    return SubstitutePreviewContext(
        header,
        SubstituteSpec(
            _decode_pattern(pattern, delimiter), replacement, delimiter, flags, count
        ),
        pattern_closed,
    )


def has_substitute_delimiter(text: str) -> bool:
    """Recognize explicit substitution input even when its body is invalid."""
    if not text.startswith(":"):
        return False
    try:
        header = scan_header(text[1:])
    except ExError:
        return False
    return bool(
        header.command
        and "substitute".startswith(header.command)
        and header.argument
        and _substitute_delimiter(header.argument[0])
    )


def scan_substitute_guide(
    text: str, cursor_position: int, previous: SubstituteSpec | None = None
) -> SubstituteGuideContext | None:
    """Inspect an unfinished ``:s`` command without executing or resolving it.

    ``cursor_position`` is a Python string index, including the initial colon.
    The Qt caller converts its UTF-16 cursor position before calling this pure
    function. A cursor immediately after a delimiter belongs to the next field.
    """
    if not text.startswith(":"):
        return None
    try:
        header = scan_header(text[1:], incomplete=True)
    except ExError:
        return None
    if not header.command or not "substitute".startswith(header.command):
        return None
    body = header.argument
    if not body or not _substitute_delimiter(body[0]):
        return None

    body_start = 1 + header.argument_start  # Include the prompt's initial colon.
    cursor = max(0, min(cursor_position, len(text))) - body_start
    if cursor < 1:
        return None
    delimiter = body[0]
    _, pattern_end, pattern_closed = _segment(body, 1, delimiter, pattern=True)
    if not pattern_closed or cursor < pattern_end:
        return SubstituteGuideContext("pattern", delimiter, header.addresses)
    _, replacement_end, replacement_closed = _segment(body, pattern_end, delimiter)
    if not replacement_closed or cursor < replacement_end:
        return SubstituteGuideContext("replacement", delimiter, header.addresses)

    tail = body[replacement_end:]
    tail_cursor = cursor - replacement_end
    previous_flags = previous.flags if previous is not None else ""
    flags, flags_end = _scan_substitute_flags(tail, previous_flags)
    count_start = count_end = _skip_space(tail, flags_end)
    while count_end < len(tail) and "0" <= tail[count_end] <= "9":
        count_end += 1
    trailing_start = _skip_space(tail, count_end)
    stage = "flags"
    unsupported = ""
    if trailing_start < len(tail) and tail_cursor >= trailing_start:
        if tail[trailing_start] == '"':
            return None
        stage = "unsupported"
        unsupported = tail[trailing_start:]
    elif count_end > count_start and tail_cursor >= count_start:
        stage = "count"

    # Describe active behavior rather than the executor's saved flag spelling.
    active = set(flags) - {"i", "I", "r"}
    last_case = next((flag for flag in reversed(flags) if flag in "iI"), "")
    if last_case:
        active.add(last_case)
    if "n" in active:
        active.discard("c")
    return SubstituteGuideContext(
        stage,
        delimiter,
        header.addresses,
        raw_flags=tail[:flags_end],
        effective_flags="".join(flag for flag in "gciIne" if flag in active),
        missing_previous=tail.startswith("&") and previous is None,
        unsupported=unsupported,
    )


def resolve_substitute(
    header: ExHeader, previous: SubstituteSpec | None, search_pattern: str
) -> SubstituteSpec:
    """Resolve a new or repeated substitution without changing saved state."""
    body = header.argument
    previous_flags = previous.flags if previous is not None else ""
    repeat = (
        header.command in ("&", "&&", "~")
        or not body
        or body[0].isalnum()
        or body[0] == '"'
    )
    if repeat:
        if previous is None:
            raise ExError("No previous substitute")
        tail = "&" + body if header.command == "&&" else body
        flags, count = _substitute_flags(tail, previous_flags)
        pattern = (
            search_pattern
            if header.command == "~" or "r" in flags
            else previous.pattern
        )
        replacement, delimiter = previous.replacement, previous.delimiter
    else:
        spec = parse_substitute(body, previous_flags)
        pattern = spec.pattern or search_pattern
        replacement, delimiter, flags, count = (
            spec.replacement,
            spec.delimiter,
            spec.flags,
            spec.count,
        )
    if not pattern:
        raise ExError("No previous search pattern")
    return SubstituteSpec(pattern, replacement, delimiter, flags, count)
