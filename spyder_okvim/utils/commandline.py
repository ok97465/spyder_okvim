"""Read-only command-line candidates and filesystem completion."""

from __future__ import annotations

# Standard Libraries
import os
from dataclasses import dataclass, replace
from functools import lru_cache

# Project Libraries
from spyder_okvim.utils.ex_parser import (
    ExError,
    is_substitute,
    parse_substitute,
    scan_header,
    scan_substitute_fields,
    scan_substitute_guide,
)

PATH_COMPLETION_EXTENSIONS = frozenset({".py", ".json", ".toml"})


@dataclass(frozen=True)
class CompletionCandidate:
    """A display label and the complete input to apply on explicit acceptance.

    Cursor positions are Python indices. Labels may abbreviate display text;
    ``text`` always preserves the literal replacement input.
    """

    source: str
    label: str
    apply_scope: str
    text: str
    cursor_position: int


@dataclass(frozen=True)
class PathArgument:
    """Parsed path spelling before home expansion or directory resolution.

    Prefix/suffix and cursor positions use Python string indices. Parsing this
    value never reads the environment or enumerates directories.
    """

    command: str
    explicit_range: bool
    directory_prefix: str
    prefix: str
    replacement_prefix: str
    suffix: str


@dataclass(frozen=True)
class PathCompletionRequest:
    """Immutable lookup data, parsed without enumerating the filesystem.

    ``replacement_prefix`` preserves the prompt, quotes, and typed directory
    spelling. ``suffix`` preserves the rest of the path and closing quote.
    """

    command: str
    explicit_range: bool
    directory: str
    prefix: str
    replacement_prefix: str
    suffix: str


def merge_candidates(*groups):
    """Combine equal applications, keeping group order and all their sources."""
    candidates = {}
    for group in groups:
        for candidate in group:
            key = candidate.text, candidate.cursor_position
            if key not in candidates:
                candidates[key] = candidate
                continue
            previous = candidates[key]
            sources = dict.fromkeys(
                previous.source.split(", ") + candidate.source.split(", ")
            )
            # The first row determines its label and application-scope display.
            candidates[key] = replace(previous, source=", ".join(sources))
    return list(candidates.values())


def _completion_header(text, cursor_position):
    if not 0 <= cursor_position <= len(text) or not text.startswith(":"):
        return None
    try:
        return scan_header(text[1:], incomplete=True)
    except ExError:
        return None


def command_candidates(text, cursor_position, commands):
    """Complete command names without looking up paths or history files."""
    header = _completion_header(text, cursor_position)
    if header is None:
        return []
    start, end = header.command_start + 1, header.command_end + 1
    if not start <= cursor_position <= end:
        return []
    prefix = text[start:cursor_position]
    # Single-symbol repeat commands follow the existing named command order.
    commands = sorted(
        set(commands), key=lambda name: (not name[0].isalpha(), name.casefold(), name)
    )
    return [
        (text[:start] + name + text[end:], start + len(name))
        for name in commands
        if name.startswith(prefix)
    ]


def completion_items(text, cursor_position, commands, base_directory):
    """Complete a command or a path on explicit Tab input.

    Each path argument is treated as one path, preserving spaces, quotes, and
    any suffix after the cursor. Only its current directory is scanned; results
    include supported file extensions and directories, excluding
    ``__pycache__`` folders. File contents are never inspected.
    """
    commands = tuple(commands)
    names = command_candidates(text, cursor_position, commands)
    if names:
        return [
            CompletionCandidate("command", value, "command", value, cursor)
            for value, cursor in names
        ]
    request = parse_path_completion(text, cursor_position, commands, base_directory)
    return path_completion_items(request) if request is not None else []


def parse_path_completion(text, cursor_position, commands, base_directory):
    """Prepare a filesystem request while preserving the user's path spelling.

    Syntax parsing is independent of home expansion. Only this preparation
    boundary resolves the parsed directory against the supplied working path;
    scanning remains in ``path_completion_items`` and its background worker.
    """
    argument = parse_path_argument(text, cursor_position, commands)
    if argument is None:
        return None
    directory = os.path.expanduser(argument.directory_prefix or ".")
    if not os.path.isabs(directory):
        directory = os.path.join(base_directory, directory)
    return PathCompletionRequest(
        argument.command,
        argument.explicit_range,
        directory,
        argument.prefix,
        argument.replacement_prefix,
        argument.suffix,
    )


def parse_path_argument(text, cursor_position, commands):
    """Parse a path and its literal suffix without consulting user files/home."""
    header = _completion_header(text, cursor_position)
    if header is None:
        return None
    command = header.command
    command_start, command_end = header.command_start + 1, header.command_end + 1
    if command_start <= cursor_position <= command_end:
        return None
    if (
        command not in commands
        or is_substitute(command)
        or command_end == len(text)
        or not text[command_end].isspace()
    ):
        return None

    path_start, path_end = header.argument_start + 1, len(text)
    if path_start < path_end and text[path_start] in "\"'":
        quote = text[path_start]
        path_start += 1
        closing = text.find(quote, path_start)
        if closing != -1:
            path_end = closing
            if cursor_position == closing + 1:
                cursor_position = closing
    if not path_start <= cursor_position <= path_end:
        return None

    before_cursor = text[path_start:cursor_position]
    separators = (os.sep,) if os.altsep is None else (os.sep, os.altsep)
    component_start = (
        max((before_cursor.rfind(sep) for sep in separators), default=-1) + 1
    )
    directory_prefix = before_cursor[:component_start]
    prefix = before_cursor[component_start:]
    # Preserve components following the component under the cursor, while
    # replacing its entire old spelling rather than duplicating its remainder.
    component_end = cursor_position
    while component_end < path_end and text[component_end] not in separators:
        component_end += 1
    suffix = text[component_end:]
    return PathArgument(
        command,
        header.explicit_range,
        directory_prefix,
        prefix,
        text[:path_start] + directory_prefix,
        suffix,
    )


def path_completion_items(request, cancelled=None):
    """Scan one directory using extension and entry-type checks only."""
    if cancelled is not None and cancelled():
        return []
    separators = (os.sep,) if os.altsep is None else (os.sep, os.altsep)
    prefix, suffix = request.prefix, request.suffix
    results = []
    try:
        with os.scandir(request.directory) as entries:
            for entry in entries:
                if cancelled is not None and cancelled():
                    return []
                if not entry.name.startswith(prefix):
                    continue
                if entry.name.startswith(".") and not prefix.startswith("."):
                    continue
                try:
                    is_directory = entry.is_dir()
                    if is_directory:
                        if entry.name == "__pycache__":
                            continue
                    elif (
                        suffix.startswith(separators)
                        or os.path.splitext(entry.name)[1].casefold()
                        not in PATH_COMPLETION_EXTENSIONS
                        or not entry.is_file()
                    ):
                        continue
                except OSError:
                    continue
                name = entry.name
                # The preserved suffix already supplies the separator when
                # completing an intermediate directory component.
                if is_directory and not suffix.startswith(separators):
                    name += os.sep
                replacement = request.replacement_prefix + name
                value = replacement + suffix
                results.append(
                    CompletionCandidate("path", value, "path", value, len(replacement))
                )
    except OSError:
        return []
    if cancelled is not None and cancelled():
        return []
    results = sorted(
        results, key=lambda candidate: (candidate.text, candidate.cursor_position)
    )
    return [] if cancelled is not None and cancelled() else results


@lru_cache(maxsize=1)
def _substitute_history_fields(history):
    """Parse only the latest in-memory history snapshot, newest entries first."""
    fields = []
    for body in reversed(history):
        text = ":" + body
        spans = scan_substitute_fields(text)
        if spans is None or not spans.pattern_closed:
            continue
        # An empty pattern depends on search state. An explicit replacement
        # is unambiguous even when its optional closing delimiter is absent.
        try:
            spec = parse_substitute(spans.header.argument)
        except ExError:
            continue
        if not spec.pattern:
            continue
        fields.append(
            (
                spans.delimiter,
                text[slice(*spans.pattern_span)],
                text[slice(*spans.replacement_span)],
            )
        )
    return tuple(fields)


def substitute_field_candidates(history, text, cursor_position):
    """Complete the active raw field using a cached in-memory Ex history.

    Only a changed history snapshot is reparsed. Completion preserves the other
    fields and any trailing flags, using the same delimiter as the saved input.
    """
    if not 0 <= cursor_position <= len(text):
        return []
    context = scan_substitute_guide(text, cursor_position)
    if context is None or context.raw_span is None:
        return []
    start, end = context.raw_span
    prefix = text[start:cursor_position]
    candidates = []
    seen = set()
    for delimiter, pattern, replacement in _substitute_history_fields(tuple(history)):
        value = pattern if context.stage == "pattern" else replacement
        if delimiter != context.delimiter or value in seen:
            continue
        if not value.startswith(prefix):
            continue
        trailing_backslashes = len(value) - len(value.rstrip("\\"))
        if text[end : end + 1] == delimiter and trailing_backslashes % 2:
            # An unfinished saved replacement can end in a lone escape.
            # In a closed target it would swallow that field's delimiter.
            continue
        seen.add(value)
        result = text[:start] + value + text[end:]
        candidates.append(
            CompletionCandidate(
                "field history",
                value or "(빈 문자열: 삭제)",
                context.stage,
                result,
                start + len(value),
            )
        )
    return candidates
