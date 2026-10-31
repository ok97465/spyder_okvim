"""Helpers for command keys delivered by an active input method."""

# Standard Libraries
import sys

# Third Party Libraries
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent

# macOS ANSI virtual key codes, with their unshifted and shifted characters.
_MACOS_LATIN_KEYS = {
    0x00: "aA",
    0x01: "sS",
    0x02: "dD",
    0x03: "fF",
    0x04: "hH",
    0x05: "gG",
    0x06: "zZ",
    0x07: "xX",
    0x08: "cC",
    0x09: "vV",
    0x0B: "bB",
    0x0C: "qQ",
    0x0D: "wW",
    0x0E: "eE",
    0x0F: "rR",
    0x10: "yY",
    0x11: "tT",
    0x12: "1!",
    0x13: "2@",
    0x14: "3#",
    0x15: "4$",
    0x16: "6^",
    0x17: "5%",
    0x18: "=+",
    0x19: "9(",
    0x1A: "7&",
    0x1B: "-_",
    0x1C: "8*",
    0x1D: "0)",
    0x1E: "]}",
    0x1F: "oO",
    0x20: "uU",
    0x21: "[{",
    0x22: "iI",
    0x23: "pP",
    0x25: "lL",
    0x26: "jJ",
    0x27: "'\"",
    0x28: "kK",
    0x29: ";:",
    0x2A: "\\|",
    0x2B: ",<",
    0x2C: "/?",
    0x2D: "nN",
    0x2E: "mM",
    0x2F: ".>",
    0x32: "`~",
}


# Windows set-1 scan codes retain the physical letter when an IME character
# event has no Latin Qt key or native virtual key.
_WINDOWS_LATIN_KEYS = {
    first_scan + offset: letter + letter.upper()
    for first_scan, row in [
        (0x10, "qwertyuiop"),
        (0x1E, "asdfghjkl"),
        (0x2C, "zxcvbnm"),
    ]
    for offset, letter in enumerate(row)
}


def latin_command_key(event: QKeyEvent) -> QKeyEvent:
    """Recover command keys while the Korean input source stays active.

    Native key codes preserve the physical key when Qt delivers Hangul text
    even with IME composition disabled. Windows character events can lack a
    virtual key, so they use scan codes rather than Cocoa's virtual-key table.
    Synthetic and already Latin events retain their original interpretation.
    """
    text = event.text()
    if (
        sys.platform not in ("darwin", "win32")
        or len(text) != 1
        or not (
            "\u1100" <= text <= "\u11ff"
            or "\u3130" <= text <= "\u318f"
            or "\uac00" <= text <= "\ud7af"
        )
    ):
        return event
    if sys.platform == "win32":
        virtual_key = event.nativeVirtualKey()
        if ord("A") <= virtual_key <= ord("Z"):
            letter = chr(virtual_key)
            characters = letter.lower() + letter
        else:
            characters = _WINDOWS_LATIN_KEYS.get(event.nativeScanCode())
        caps_lock = bool(event.nativeModifiers() & 0x100)
    else:
        if not event.nativeScanCode():
            return event
        characters = _MACOS_LATIN_KEYS.get(event.nativeVirtualKey())
        caps_lock = bool(event.nativeModifiers() & (1 << 16))
    if characters is None:
        return event
    shifted = bool(event.modifiers() & Qt.ShiftModifier)
    if characters[0].isalpha() and caps_lock:
        shifted = not shifted
    text = characters[int(shifted)]
    return QKeyEvent(
        event.type(),
        ord(text.upper()),
        event.modifiers(),
        event.nativeScanCode(),
        event.nativeVirtualKey(),
        event.nativeModifiers(),
        text,
        event.isAutoRepeat(),
        event.count(),
    )


def key_event_from_info(info):
    """Build an ignored KeyPress event from recorded native key values."""
    event = QKeyEvent(QEvent.KeyPress, info.key_code, info.modifiers, info.text)
    event.ignore()
    return event
