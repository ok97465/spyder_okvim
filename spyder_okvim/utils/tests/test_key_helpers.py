"""Regression tests for platform-specific command-key translation."""

# Third Party Libraries
import pytest
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent

# Project Libraries
from spyder_okvim.utils import key_helpers


@pytest.fixture
def translate_key(monkeypatch):
    """Change the platform only during translation, before Qt/pytest cleanup."""

    def translate(event, platform="darwin"):
        with monkeypatch.context() as patch:
            patch.setattr(key_helpers.sys, "platform", platform)
            return key_helpers.latin_command_key(event)

    return translate


@pytest.mark.parametrize(
    "virtual_key, modifiers, native_modifiers, expected",
    [
        (0x00, Qt.NoModifier, 0, "a"),
        (0x04, Qt.NoModifier, 0, "h"),
        (0x04, Qt.ShiftModifier, 0, "H"),
        (0x04, Qt.NoModifier, 1 << 16, "H"),
        (0x04, Qt.ShiftModifier, 1 << 16, "h"),
        (0x12, Qt.NoModifier, 1 << 16, "1"),
        (0x12, Qt.ShiftModifier, 1 << 16, "!"),
        (0x29, Qt.NoModifier, 0, ";"),
        (0x29, Qt.ShiftModifier, 0, ":"),
    ],
)
def test_macos_hangul_keys_respect_shift_and_caps_lock(
    translate_key, virtual_key, modifiers, native_modifiers, expected
):
    """Caps Lock affects letters, while Shift also selects punctuation."""
    event = QKeyEvent(
        QEvent.KeyPress, ord("ㅗ"), modifiers, 1, virtual_key, native_modifiers, "ㅗ"
    )

    translated = translate_key(event)

    assert translated.text() == expected
    assert translated.key() == ord(expected.upper())
    assert event.text() == "ㅗ"


@pytest.mark.parametrize("text", ["\u1112", "ㅗ", "한"])
def test_macos_hangul_character_ranges(translate_key, text):
    """Modern jamo, compatibility jamo, and syllables use the native key."""
    event = QKeyEvent(QEvent.KeyPress, ord(text), Qt.NoModifier, 1, 0x04, 0, text)

    assert translate_key(event).text() == "h"


def test_translated_key_preserves_native_event_metadata(translate_key):
    """Shortcut modifiers, repeat state, and native identity survive mapping."""
    modifiers = Qt.ControlModifier | Qt.ShiftModifier
    event = QKeyEvent(
        QEvent.KeyPress, ord("ㅗ"), modifiers, 0x23, 0x04, 0x1234, "ㅗ", True, 3
    )

    translated = translate_key(event)

    assert translated is not event
    assert translated.type() == event.type()
    assert translated.modifiers() == modifiers
    assert translated.nativeScanCode() == event.nativeScanCode()
    assert translated.nativeVirtualKey() == event.nativeVirtualKey()
    assert translated.nativeModifiers() == event.nativeModifiers()
    assert translated.isAutoRepeat()
    assert translated.count() == 3
    assert translated.key() == Qt.Key_H
    assert translated.text() == "H"


@pytest.mark.parametrize("text", ["", "h", "H", "/", "é", "😀", "한글"])
def test_non_hangul_or_multiple_characters_are_unchanged(translate_key, text):
    """Only individual Hangul characters need physical-key recovery."""
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_H, Qt.NoModifier, 1, 0x04, 0, text)

    assert translate_key(event) is event


@pytest.mark.parametrize("scan_code, virtual_key", [(0, 0x04), (1, 0xFF)])
def test_synthetic_or_unknown_macos_keys_are_unchanged(
    translate_key, scan_code, virtual_key
):
    """Native scan information and a known physical key are both required."""
    event = QKeyEvent(
        QEvent.KeyPress, ord("ㅗ"), Qt.NoModifier, scan_code, virtual_key, 0, "ㅗ"
    )

    assert translate_key(event) is event


@pytest.mark.parametrize(
    "platform, scan_code, virtual_key",
    [
        ("win32", 0xFFFF, 0x04),
        ("win32", 0xFFFF, 0x26),
        ("linux", 0x23, 0x04),
        ("linux", 0x23, 0x26),
        ("linux", 0x23, 0x48),
    ],
)
def test_other_platforms_never_apply_cocoa_virtual_key_mapping(
    translate_key, platform, scan_code, virtual_key
):
    """Native virtual-key namespaces must not be shared between platforms."""
    event = QKeyEvent(
        QEvent.KeyPress, Qt.Key_H, Qt.NoModifier, scan_code, virtual_key, 0, "ㅗ"
    )

    assert translate_key(event, platform) is event


@pytest.mark.parametrize(
    "key, scan_code, virtual_key, text",
    [
        (Qt.Key_H, 0x23, 0x48, "h"),
        (Qt.Key_J, 0x24, 0x4A, "j"),
        (Qt.Key_I, 0x17, 0x49, "i"),
        (Qt.Key_Return, 0x1C, 0x0D, "\r"),
    ],
)
def test_windows_latin_and_control_keys_keep_their_native_identity(
    translate_key, key, scan_code, virtual_key, text
):
    """Win32 VK_RETURN, for example, is Cocoa's W rather than Return."""
    event = QKeyEvent(
        QEvent.KeyPress, key, Qt.NoModifier, scan_code, virtual_key, 0, text
    )

    assert translate_key(event, "win32") is event


@pytest.mark.parametrize(
    "key, virtual_key",
    [
        (Qt.Key_H, 0x48),
        (ord("ㅗ"), 0x48),
        (0, ord("ㅗ")),
        (0, 0),
    ],
)
def test_windows_hangul_keys_recover_latin_commands(translate_key, key, virtual_key):
    """Hangul key text must not replace the physical h command."""
    event = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, 0x23, virtual_key, 0, "ㅗ")

    translated = translate_key(event, "win32")

    assert translated.key() == Qt.Key_H
    assert translated.text() == "h"
    assert event.text() == "ㅗ"


def test_windows_native_virtual_key_recovers_command_without_scan_code(translate_key):
    """Native Windows A-Z identity is usable when scan information is absent."""
    event = QKeyEvent(QEvent.KeyPress, 0, Qt.NoModifier, 0, 0x48, 0, "ㅗ")

    translated = translate_key(event, "win32")

    assert translated.key() == Qt.Key_H
    assert translated.text() == "h"


@pytest.mark.parametrize("virtual_key", [0, ord("ㅗ")])
def test_windows_hangul_without_native_key_identity_is_unchanged(
    translate_key, virtual_key
):
    """A Hangul character alone cannot establish a physical command key."""
    event = QKeyEvent(QEvent.KeyPress, 0, Qt.NoModifier, 0, virtual_key, 0, "ㅗ")

    assert translate_key(event, "win32") is event


def test_windows_native_virtual_key_takes_precedence_over_scan_code(translate_key):
    """Prefer a native letter identity over fallback scan-code interpretation."""
    event = QKeyEvent(QEvent.KeyPress, 0, Qt.NoModifier, 0x24, 0x48, 0, "ㅗ")

    translated = translate_key(event, "win32")

    assert translated.key() == Qt.Key_H
    assert translated.text() == "h"


@pytest.mark.parametrize(
    "modifiers, native_modifiers, expected",
    [
        (Qt.NoModifier, 0, "h"),
        (Qt.ShiftModifier, 0, "H"),
        (Qt.NoModifier, 0x100, "H"),
        (Qt.ShiftModifier, 0x100, "h"),
    ],
)
def test_windows_hangul_keys_respect_shift_and_caps_lock(
    translate_key, modifiers, native_modifiers, expected
):
    """Windows uses native Caps Lock bit 0x100, independently of Cocoa."""
    event = QKeyEvent(QEvent.KeyPress, 0, modifiers, 0x23, 0, native_modifiers, "ㅗ")

    translated = translate_key(event, "win32")

    assert translated.key() == Qt.Key_H
    assert translated.text() == expected
    assert translated.modifiers() == modifiers
    assert translated.nativeModifiers() == native_modifiers


def test_windows_translated_key_preserves_native_event_metadata(translate_key):
    """Windows recovery keeps native identity and repeat/shortcut semantics."""
    modifiers = Qt.ControlModifier | Qt.ShiftModifier
    event = QKeyEvent(QEvent.KeyPress, 0, modifiers, 0x23, 0, 0x202, "ㅗ", True, 3)

    translated = translate_key(event, "win32")

    assert translated is not event
    assert translated.type() == event.type()
    assert translated.modifiers() == modifiers
    assert translated.nativeScanCode() == 0x23
    assert translated.nativeVirtualKey() == 0
    assert translated.nativeModifiers() == 0x202
    assert translated.isAutoRepeat()
    assert translated.count() == 3
    assert translated.key() == Qt.Key_H
    assert translated.text() == "H"
