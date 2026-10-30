"""Load and atomically save bounded Ex and search histories."""

# Standard Libraries
import json
import logging
import os
import tempfile

HISTORY_LIMIT = 100
logger = logging.getLogger(__name__)


def load_history(path):
    """Restore valid entries, tolerating a missing or damaged history file."""
    histories = {"ex": [], "search": []}
    try:
        with open(path, encoding="utf-8") as stream:
            stored = json.load(stream)
    except (OSError, ValueError, RecursionError):
        return histories
    if not isinstance(stored, dict):
        return histories
    for kind in histories:
        entries = stored.get(kind)
        if not isinstance(entries, list):
            continue
        history = histories[kind]
        for entry in reversed(entries):
            if not isinstance(entry, str) or not entry:
                continue
            # Recalled text must not submit a command or break UTF-8 saves.
            if "\r" in entry or "\n" in entry:
                continue
            if kind == "ex" and not entry.strip():
                continue
            try:
                entry.encode("utf-8")
            except UnicodeEncodeError:
                continue
            history.append(entry)
            if len(history) == HISTORY_LIMIT:
                break
        history.reverse()
    return histories


def save_history(path, histories):
    """Atomically write histories and report success without raising I/O errors."""
    temporary_path = None
    try:
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=folder, suffix=".tmp", delete=False
        ) as stream:
            temporary_path = stream.name
            json.dump(histories, stream, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary_path, path)
        temporary_path = None
    except (OSError, UnicodeError):
        logger.warning("Unable to save command-line history", exc_info=True)
        return False
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
    return True
