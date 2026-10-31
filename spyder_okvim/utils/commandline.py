"""Read-only command-line candidates and explicit filesystem completion."""

from __future__ import annotations

# Standard Libraries
import os
from dataclasses import dataclass, replace
from functools import lru_cache

# Third Party Libraries
from spyder.utils.encoding import is_text_file

from spyder_okvim.utils.ex_parser import (
    ExError,
    is_substitute,
    parse_substitute,
    scan_header,
    scan_substitute_fields,
    scan_substitute_guide,
)


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


def merge_candidates(*groups):
    """Combine equal applications, keeping group order and all their sources."""
    candidates = []
    positions = {}
    for group in groups:
        for candidate in group:
            key = candidate.text, candidate.cursor_position
            if key not in positions:
                positions[key] = len(candidates)
                candidates.append(candidate)
                continue
            index = positions[key]
            previous = candidates[index]
            sources = list(
                dict.fromkeys(
                    previous.source.split(", ") + candidate.source.split(", ")
                )
            )
            # The first row determines its label and application-scope display.
            candidates[index] = replace(previous, source=", ".join(sources))
    return candidates


def _completion_header(text, cursor_position):
    if not 0 <= cursor_position <= len(text) or not text.startswith(":"):
        return None
    try:
        return scan_header(text[1:], incomplete=True)
    except ExError:
        return None


def _supported_commands(commands):
    # Single-symbol repeat commands follow the existing named command order.
    return sorted(
        set(commands), key=lambda name: (not name[0].isalpha(), name.casefold(), name)
    )


def command_candidates(text, cursor_position, commands):
    """Complete command names without looking up paths or history files."""
    header = _completion_header(text, cursor_position)
    if header is None:
        return []
    start, end = header.command_start + 1, header.command_end + 1
    if not start <= cursor_position <= end:
        return []
    prefix = text[start:cursor_position]
    return [
        (text[:start] + name + text[end:], start + len(name))
        for name in _supported_commands(commands)
        if name.startswith(prefix)
    ]


def completion_items(text, cursor_position, commands, base_directory):
    """Complete a command or a path on explicit Tab input.

    Each path argument is treated as one path, preserving spaces, quotes, and
    any suffix after the cursor. Only its current directory is scanned; results
    include text files and directories, excluding ``__pycache__`` folders.
    """
    commands = tuple(commands)
    names = command_candidates(text, cursor_position, commands)
    if names:
        return [
            CompletionCandidate("command", value, "command", value, cursor)
            for value, cursor in names
        ]
    return [
        CompletionCandidate("path", value, "path", value, cursor)
        for value, cursor in path_candidates(
            text, cursor_position, commands, base_directory
        )
    ]


def path_candidates(text, cursor_position, commands, base_directory):
    """Complete a single path argument, scanning only its current directory."""
    header = _completion_header(text, cursor_position)
    if header is None:
        return []
    command = header.command
    command_start, command_end = header.command_start + 1, header.command_end + 1
    if command_start <= cursor_position <= command_end:
        return []
    if (
        command not in commands
        or is_substitute(command)
        or command_end == len(text)
        or not text[command_end].isspace()
    ):
        return []

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
        return []

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
    directory = os.path.expanduser(directory_prefix or ".")
    if not os.path.isabs(directory):
        directory = os.path.join(base_directory, directory)

    results = []
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
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
                        or not entry.is_file()
                        or not is_text_file(entry.path)
                    ):
                        continue
                except OSError:
                    continue
                name = entry.name
                # The preserved suffix already supplies the separator when
                # completing an intermediate directory component.
                if is_directory and not suffix.startswith(separators):
                    name += os.sep
                replacement = text[:path_start] + directory_prefix + name
                results.append((replacement + suffix, len(replacement)))
    except OSError:
        return []
    return sorted(results)


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
