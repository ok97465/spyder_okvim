"""On-demand completion of Ex command names and single path arguments."""

# Standard Libraries
import os
import re
from collections.abc import Iterable

# Third Party Libraries
from spyder.utils.encoding import is_text_file


def completion_candidates(
    text: str,
    cursor_position: int,
    commands: Iterable[str],
    base_directory: str,
) -> list[tuple[str, int]]:
    """Return complete input strings and Python-indexed cursor positions.

    Arguments are treated as one path so spaces need no shell escaping. An
    existing opening/closing quote is preserved. Only the directory containing
    the current path component is scanned, and only when this function is called.
    Paths include text files and directories, excluding ``__pycache__`` folders.
    """
    if not 0 <= cursor_position <= len(text):
        return []
    match = re.fullmatch(r":\s*(\S*)(\s+)(.*)|:\s*(\S*)", text, re.DOTALL)
    if match is None:
        return []
    command = match.group(1) if match.group(1) is not None else match.group(4)
    command_group = 1 if match.group(1) is not None else 4
    command_start, command_end = match.span(command_group)
    supported = sorted(set(commands))
    if command_start <= cursor_position <= command_end:
        prefix = text[command_start:cursor_position]
        return [
            (
                text[:command_start] + item + text[command_end:],
                command_start + len(item),
            )
            for item in supported
            if item.startswith(prefix)
        ]
    if command not in supported or match.group(3) is None:
        return []

    path_start, path_end = match.span(3)
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
