"""Substitution decorations follow palettes without repeating editing work."""

from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import spyder_themes
from qtpy import API_NAME, QtCore
from qtpy.QtCore import QCoreApplication, QEvent, Signal
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QPlainTextEdit, QWidget

from spyder_okvim.spyder.substitute_preview import SubstitutePreviewController
from spyder_okvim.utils.substitute_confirm import SubstituteConfirm
from spyder_okvim.utils.substitute_preview import PreviewResult, PreviewRow
from spyder_okvim.utils.theme import contrast_ratio


class ThemeEditor(QPlainTextEdit):
    sig_theme_colors_changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.selections = {}

    def get_extra_selections(self, name):
        return self.selections.get(name, [])

    def set_extra_selections(self, name, selections):
        self.selections[name] = list(selections)

    def clear_extra_selections(self, name):
        self.selections.pop(name, None)


class InputWidget(QWidget):
    sig_input_started = Signal()
    sig_input_finished = Signal()
    sig_command_changed = Signal()
    sig_command_cancelled = Signal()


@pytest.fixture
def decorations(qtbot, monkeypatch):
    editor = ThemeEditor()
    editor.setPlainText("foo foo")
    # Keep the Python document wrapper alive, as CodeEditor does in production.
    _document = editor.document()
    editor.resize(420, 220)
    editor.show()
    qtbot.addWidget(editor)
    widget = InputWidget()
    qtbot.addWidget(widget)
    widget.is_processing_input = False
    widget.commandline = SimpleNamespace(text=lambda: "")
    status = widget.vim_status = SimpleNamespace(
        get_editor=lambda: editor,
        settings=SimpleNamespace(ignorecase=True, smartcase=True),
        cursor=Mock(),
        set_message=Mock(),
        input_cancelled=widget.sig_command_cancelled,
        cmd_line=SimpleNamespace(sync_input_method=Mock()),
    )
    monkeypatch.setattr(
        "spyder_okvim.spyder.substitute_preview.CONF",
        SimpleNamespace(get=lambda *args: True),
    )
    preview = SubstitutePreviewController(widget)
    preview.begin_session(SimpleNamespace(origin_line=0))
    preview._preview_lines = (0,)
    key = object()
    monkeypatch.setattr(preview, "_current_key", lambda: key)
    result = PreviewResult(
        ((0, 3), (4, 7)),
        2,
        1,
        False,
        (),
        False,
        False,
        rows=(PreviewRow(0, "foo foo", "bar bar", ((0, 3), (4, 7)), ()),),
    )
    preview._show(result, key)
    confirm = SubstituteConfirm(status, editor, ((0, 3, "bar"),), Mock())
    status.sub_mode = status.substitute_confirm = confirm
    confirm.start()
    try:
        yield editor, status, preview, confirm
    finally:
        confirm.cancel()
        preview.cleanup()


def installed_variants():
    variants = []
    for info in iter_modules(spyder_themes.__path__):
        module = import_module(f"spyder_themes.{info.name}")
        for mode in ("Dark", "Light"):
            if hasattr(module, f"SpyderPalette{mode}"):
                variants.append((info.name, mode))
    return variants


def state(editor):
    document = editor.document()
    cursor = editor.textCursor()
    return (
        editor.toPlainText(),
        document.revision(),
        document.availableUndoSteps(),
        document.availableRedoSteps(),
        cursor.position(),
        cursor.anchor(),
    )


@pytest.mark.parametrize("name,mode", installed_variants())
def test_substitution_decorations_follow_installed_theme(decorations, name, mode):
    editor, status, preview, confirm = decorations
    module = import_module(f"spyder_themes.{name}")
    theme = getattr(module, f"SpyderPalette{mode}")
    qss = Path(module.__file__).parent / mode.lower() / f"{mode.lower()}style.qss"
    before = state(editor)
    result = preview.result
    spans = [
        selection.cursor.selectedText()
        for selection in editor.get_extra_selections("vim_substitute_preview")
    ]
    editor.setStyleSheet(qss.read_text())
    palette = QPalette(editor.palette())
    palette.setColor(QPalette.Base, QColor(theme.EDITOR_BACKGROUND))
    palette.setColor(QPalette.Text, QColor(theme.EDITOR_NORMAL[0]))
    editor.setPalette(palette)
    editor.occurrence_color = QColor(theme.EDITOR_OCCURRENCE)
    editor.sig_theme_colors_changed.emit({})

    selection = editor.get_extra_selections("vim_substitute")[0]
    assert selection.format.background().color() == palette.color(QPalette.Highlight)
    assert (
        contrast_ratio(
            selection.format.foreground().color(), selection.format.background().color()
        )
        >= 4.5
    )
    matches = editor.get_extra_selections("vim_substitute_preview")
    assert [selection.cursor.selectedText() for selection in matches] == spans
    assert all(
        selection.format.background().color() == editor.occurrence_color
        for selection in matches
    )
    assert all(
        contrast_ratio(
            selection.format.foreground().color(), selection.format.background().color()
        )
        >= 4.5
        for selection in matches
    )
    background, _, accent, _ = preview.overlay._colors(editor)
    assert contrast_ratio(accent, background) >= 3.0
    assert preview.result is result
    assert preview.overlay.rows == result.rows
    assert confirm.active
    assert state(editor) == before
    status.cursor.set_cursor_pos_without_end.assert_called_once_with(0)
    status.set_message.assert_called_once_with("replace? (y/n/a/l/q)")


def test_future_palette_and_theme_signal_do_not_recalculate_or_repeat_prompt(
    decorations, monkeypatch
):
    editor, status, preview, confirm = decorations
    monkeypatch.setattr(
        "spyder_okvim.spyder.substitute_preview.prepare_substitution",
        Mock(side_effect=AssertionError("Appearance change repeated calculation")),
    )
    before = state(editor)
    result = preview.result
    palette = QPalette(editor.palette())
    for role, color in (
        (QPalette.Base, "#f4e9df"),
        (QPalette.Text, "#223344"),
        (QPalette.Highlight, "#e9d9c9"),
        (QPalette.HighlightedText, "#eedecd"),
    ):
        palette.setColor(role, QColor(color))
    editor.setPalette(palette)
    editor.occurrence_color = QColor("#e8dac7")
    editor.sig_theme_colors_changed.emit({})
    QCoreApplication.sendEvent(editor, QEvent(QEvent.StyleChange))
    assert preview.result is result
    assert state(editor) == before
    assert not preview._timer.isActive()
    assert not preview._chunk_timer.isActive()
    for group in ("vim_substitute", "vim_substitute_preview"):
        for selection in editor.get_extra_selections(group):
            assert (
                contrast_ratio(
                    selection.format.foreground().color(),
                    selection.format.background().color(),
                )
                >= 4.5
            )
    status.cursor.set_cursor_pos_without_end.assert_called_once_with(0)
    status.set_message.assert_called_once()


def test_cancel_and_cleanup_disconnect_appearance_observers(decorations):
    editor, status, preview, confirm = decorations
    signal = (
        QtCore.SIGNAL("sig_theme_colors_changed(QVariantMap)")
        if API_NAME.startswith("PySide")
        else editor.sig_theme_colors_changed
    )
    assert editor.receivers(signal) == 3
    confirm.cancel()
    preview.cancel()
    assert editor.receivers(signal) == 1
    preview.cleanup()
    assert editor.receivers(signal) == 0
    editor.sig_theme_colors_changed.emit({})
    QCoreApplication.sendEvent(editor, QEvent(QEvent.PaletteChange))
    assert not editor.get_extra_selections("vim_substitute")
    assert not editor.get_extra_selections("vim_substitute_preview")
