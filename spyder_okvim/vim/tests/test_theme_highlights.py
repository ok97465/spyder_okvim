"""Editor highlights follow Spyder themes without plugin color overrides."""

# Standard Libraries
from dataclasses import replace
from importlib import import_module
from types import SimpleNamespace

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Signal
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QPlainTextEdit, QWidget
from spyder.plugins.editor.widgets.codeeditor.codeeditor import CodeEditor
from spyder.utils.theme_manager import THEME_MANAGER

# Project Libraries
from spyder_okvim.spyder.config import PluginSettings
from spyder_okvim.utils.theme import contrast_ratio, selection_colors
from spyder_okvim.vim.cursor import VimCursor
from spyder_okvim.vim.search import SearchInfo


def assert_readable_format(format, background, preferred):
    """Preserve host backgrounds and readable preferred foregrounds."""
    foreground = format.foreground().color()
    assert format.background().color() == background
    assert contrast_ratio(foreground, background) >= 4.5
    if contrast_ratio(preferred, background) >= 4.5:
        assert foreground == preferred


class ThemeEditor(QPlainTextEdit):
    """Provide the editor's public selection and theme interfaces."""

    sig_theme_colors_changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.selections = {}

    def get_extra_selections(self, group):
        return self.selections.get(group, [])

    def set_extra_selections(self, group, selections):
        self.selections[group] = list(selections)

    def clear_extra_selections(self, group):
        self.selections.pop(group, None)


def apply_theme(editor, name, mode):
    """Use the installed theme's editor and interface colors without changing CONF."""
    theme = getattr(import_module(f"spyder_themes.{name}"), f"SpyderPalette{mode}")
    palette = QPalette(editor.palette())
    for role, color in (
        (QPalette.Base, theme.EDITOR_BACKGROUND),
        (QPalette.Text, theme.EDITOR_NORMAL[0]),
        (QPalette.Highlight, theme.COLOR_ACCENT_3),
        (QPalette.HighlightedText, theme.COLOR_TEXT_1),
    ):
        palette.setColor(role, QColor(color))
    editor.occurrence_color = QColor(theme.EDITOR_OCCURRENCE)
    editor.setPalette(palette)
    editor.sig_theme_colors_changed.emit({"occurrence": editor.occurrence_color})
    return palette


@pytest.fixture
def theme_session(qtbot):
    editor = ThemeEditor()
    qtbot.addWidget(editor)
    editor.setPlainText("foo bar foo")
    stack = SimpleNamespace(get_current_editor=lambda: editor)
    source = SimpleNamespace(
        get_current_editorstack=lambda: stack,
        get_widget=lambda: stack,
    )
    settings = PluginSettings()
    cursor = VimCursor(source, settings)
    search = SearchInfo(cursor)
    try:
        yield editor, cursor, search
    finally:
        search.close()
        cursor.close()
        cursor.deleteLater()


@pytest.mark.parametrize(
    "name,mode", [("spyder", "Light"), ("dracula", "Dark"), ("miami-nights", "Light")]
)
def test_default_highlights_follow_installed_theme(theme_session, name, mode):
    editor, cursor, search = theme_session
    palette = apply_theme(editor, name, mode)
    cursor.apply_settings(PluginSettings())
    cursor.create_selection(0, 3)
    assert_readable_format(
        cursor.vim_cursor.format,
        palette.color(QPalette.Text),
        palette.color(QPalette.Base),
    )
    assert_readable_format(
        cursor.selection.format,
        palette.color(QPalette.Highlight),
        palette.color(QPalette.HighlightedText),
    )
    cursor.highlight_yank(0, 3)
    yank = editor.get_extra_selections("hl_yank")[0]
    assert_readable_format(
        yank.format,
        palette.color(QPalette.Highlight),
        palette.color(QPalette.HighlightedText),
    )
    search.search("foo")
    match = search.selection_list[0]
    assert_readable_format(
        match.format, editor.occurrence_color, palette.color(QPalette.Text)
    )


def test_palette_refresh_recolors_ranges_without_searching_or_restarting_timer(
    theme_session, monkeypatch
):
    editor, cursor, search = theme_session
    apply_theme(editor, "spyder", "Light")
    cursor.apply_settings(replace(PluginSettings(), highlight_yank_duration=10000))
    cursor.create_selection(0, 3)
    cursor.highlight_yank(0, 3)
    timer = cursor._highlight_timers["hl_yank"][0]
    search.search("foo")
    selections = search.selection_list
    positions = search._positions

    def fail_search(*args):
        raise AssertionError("Changing appearance recomputed search matches")

    monkeypatch.setattr("spyder_okvim.vim.search.iter_block_matches", fail_search)
    palette = apply_theme(editor, "dracula", "Dark")
    QCoreApplication.sendEvent(editor, QEvent(QEvent.StyleChange))
    assert search.selection_list is selections
    assert search._positions is positions
    assert cursor._highlight_timers["hl_yank"][0] is timer
    assert timer.isActive()
    for group in ("vim_selection", "hl_yank"):
        selection = editor.get_extra_selections(group)[0]
        assert selection.cursor.selectedText() == "foo"
        assert selection.format.background().color() == palette.color(
            QPalette.Highlight
        )
    assert (
        search.selection_list[0].format.background().color() == editor.occurrence_color
    )
    assert_readable_format(
        search.selection_list[0].format,
        editor.occurrence_color,
        palette.color(QPalette.Text),
    )


def test_legacy_color_options_do_not_override_editor_theme(theme_session):
    editor, cursor, search = theme_session
    legacy_options = dict(
        cursor_fg_color="#102030",
        cursor_bg_color="#405060",
        select_fg_color="#112233",
        select_bg_color="#445566",
        yank_fg_color="#123456",
        yank_bg_color="#654321",
        search_fg_color="#abcdef",
        search_bg_color="#fedcba",
    )
    settings = SimpleNamespace(**{**vars(PluginSettings()), **legacy_options})
    cursor.apply_settings(settings)
    search.search("foo")
    palette = apply_theme(editor, "dracula", "Dark")
    assert_readable_format(
        cursor.vim_cursor.format,
        palette.color(QPalette.Text),
        palette.color(QPalette.Base),
    )
    assert_readable_format(
        cursor.selection.format,
        palette.color(QPalette.Highlight),
        palette.color(QPalette.HighlightedText),
    )
    assert cursor.yank_bg_color == palette.brush(QPalette.Highlight)
    assert (
        contrast_ratio(cursor.yank_fg_color.color(), cursor.yank_bg_color.color())
        >= 4.5
    )
    assert_readable_format(
        search.selection_list[0].format,
        editor.occurrence_color,
        palette.color(QPalette.Text),
    )


def test_search_without_occurrence_color_uses_selection_palette(theme_session):
    editor, _, search = theme_session
    palette = apply_theme(editor, "spyder", "Light")
    editor.occurrence_color = QColor()
    search.search("foo")
    assert search.color_bg.color() == palette.color(QPalette.Highlight)
    assert_readable_format(
        search.selection_list[0].format,
        palette.color(QPalette.Highlight),
        palette.color(QPalette.HighlightedText),
    )


def test_unknown_low_contrast_theme_refreshes_existing_highlights(theme_session):
    """New theme palettes need no registration to keep plugin text readable."""
    editor, cursor, search = theme_session
    cursor.apply_settings(replace(PluginSettings(), highlight_yank_duration=10000))
    cursor.draw_vim_cursor()
    cursor.create_selection(0, 3)
    cursor.highlight_yank(0, 3)
    cursor.highlight_put(4, 7)
    search.search("foo")
    positions = search._positions
    selection_ranges = {
        group: [
            (item.cursor.selectionStart(), item.cursor.selectionEnd())
            for item in editor.get_extra_selections(group)
        ]
        for group in ("vim_cursor", "vim_selection", "hl_yank", "hl_put")
    }
    timers = {group: job[0] for group, job in cursor._highlight_timers.items()}

    for base, text, fill, selected_text, occurrence in (
        ("#eeeeee", "#dddddd", "#888888", "#777777", "#cccccc"),
        ("#222222", "#333333", "#555555", "#666666", "#444444"),
    ):
        palette = QPalette(editor.palette())
        for role, color in (
            (QPalette.Base, base),
            (QPalette.Text, text),
            (QPalette.Highlight, fill),
            (QPalette.HighlightedText, selected_text),
        ):
            palette.setColor(role, QColor(color))
        editor.occurrence_color = QColor(occurrence)
        editor.setPalette(palette)
        editor.sig_theme_colors_changed.emit({})
        assert search._positions is positions
        for group, ranges in selection_ranges.items():
            selections = editor.get_extra_selections(group)
            assert [
                (item.cursor.selectionStart(), item.cursor.selectionEnd())
                for item in selections
            ] == ranges
            background, preferred = (
                (text, base) if group == "vim_cursor" else (fill, selected_text)
            )
            for item in selections:
                assert_readable_format(
                    item.format, QColor(background), QColor(preferred)
                )
        for group, timer in timers.items():
            assert cursor._highlight_timers[group][0] is timer
            assert timer.isActive()
        for match in search.selection_list:
            assert_readable_format(match.format, QColor(occurrence), QColor(text))
        current = editor.get_extra_selections("vim_search_current")[0]
        assert_readable_format(current.format, QColor(fill), QColor(selected_text))


def test_cursor_close_detaches_theme_observers_and_stops_timers(
    theme_session, monkeypatch
):
    editor, cursor, _ = theme_session
    cursor.apply_settings(replace(PluginSettings(), highlight_yank_duration=10000))
    cursor.highlight_yank(0, 3)
    cursor.close()
    assert not cursor._highlight_timers
    assert not editor.get_extra_selections("hl_yank")
    assert cursor._theme_editor is None

    def unexpected_refresh(*args):
        raise AssertionError("Closed cursor still observes editor appearance")

    monkeypatch.setattr(cursor, "refresh_appearance", unexpected_refresh)
    cursor.get_editor()
    apply_theme(editor, "dracula", "Dark")
    QCoreApplication.sendEvent(editor, QEvent(QEvent.StyleChange))
    cursor.close()


def test_mode_label_repairs_low_contrast_after_palette_change_and_reparent(qtbot):
    from spyder_okvim.spyder.vim_widgets import VimStateLabel
    from spyder_okvim.vim.state import VimState

    parent, other_parent = QWidget(), QWidget()
    qtbot.addWidget(parent)
    qtbot.addWidget(other_parent)
    label = VimStateLabel(parent)
    qtbot.addWidget(label)
    label.change_state(VimState.NORMAL)

    def assert_display(background, foreground):
        label.ensurePolished()
        assert (
            f"color: {foreground}; background-color: {background};"
            in label.styleSheet()
        )
        assert label.palette().color(QPalette.Window) == QColor(background)
        assert label.palette().color(QPalette.WindowText) == QColor(foreground)
        assert (
            contrast_ratio(
                label.palette().color(QPalette.WindowText),
                label.palette().color(QPalette.Window),
            )
            >= 4.5
        )
        assert label.text() == "NORMAL"

    parent.setStyleSheet("QWidget { color: palette(text); }")
    for background, selected_text, fallback, expected in (
        ("#f4f4f4", "#123456", "#000000", "#123456"),
        ("#888888", "#777777", "#000000", "#000000"),
        ("#555555", "#666666", "#ffffff", "#ffffff"),
    ):
        palette = QPalette(parent.palette())
        palette.setColor(QPalette.Highlight, QColor(background))
        palette.setColor(QPalette.HighlightedText, QColor(selected_text))
        palette.setColor(QPalette.Text, QColor(fallback))
        parent.setPalette(palette)
        QCoreApplication.processEvents()
        assert_display(background, expected)

    palette = QPalette(other_parent.palette())
    palette.setColor(QPalette.Highlight, QColor("#223344"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    other_parent.setPalette(palette)
    label.setParent(other_parent)
    assert_display("#223344", "#ffffff")
    assert label._palette_parent_ref() is other_parent

    palette.setColor(QPalette.Highlight, QColor("#000000"))
    parent.setPalette(palette)
    parent.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert_display("#223344", "#ffffff")
    label.setParent(None)
    assert label._palette_parent_ref is None


def test_mode_label_follows_application_theme_palette(qtbot, qapp):
    from spyder_okvim.spyder.vim_widgets import VimStateLabel

    original = QPalette(qapp.palette())
    parent = QWidget()
    qtbot.addWidget(parent)
    label = VimStateLabel(parent)
    try:
        for background, foreground in (
            ("#ffeebb", "#112233"),
            ("#223344", "#ffffff"),
        ):
            palette = QPalette(original)
            palette.setColor(QPalette.Highlight, QColor(background))
            palette.setColor(QPalette.HighlightedText, QColor(foreground))
            qapp.setPalette(palette)
            QCoreApplication.processEvents()
            label.ensurePolished()
            assert label.palette().color(QPalette.Window) == QColor(background)
            assert label.palette().color(QPalette.WindowText) == QColor(foreground)
    finally:
        qapp.setPalette(original)
        QCoreApplication.processEvents()


@pytest.mark.parametrize("variant", THEME_MANAGER.get_available_theme_variants())
def test_real_codeeditor_highlights_match_theme_stylesheet(qtbot, variant):
    """Exercise 6.2 theme ids, syntax colors and QSS polishing together."""
    theme_name, mode = variant.rsplit("/", 1)
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.setStyleSheet(THEME_MANAGER._load_stylesheet(theme_name, mode))
    editor = CodeEditor(parent)
    editor.setup_editor(language="Python", color_scheme=variant)
    editor.set_text("foo bar foo")
    editor.set_color_scheme(variant)
    editor.ensurePolished()
    from spyder_okvim.spyder.vim_widgets import VimStateLabel

    mode_label = VimStateLabel(parent)
    mode_label.ensurePolished()
    mode_foreground, mode_background = selection_colors(parent)
    assert mode_label.palette().color(QPalette.Window) == mode_background
    assert mode_label.palette().color(QPalette.WindowText) == mode_foreground
    assert contrast_ratio(mode_foreground, mode_background) >= 4.5
    stack = SimpleNamespace(get_current_editor=lambda: editor)
    source = SimpleNamespace(
        get_current_editorstack=lambda: stack,
        get_widget=lambda: stack,
    )
    cursor = VimCursor(source, PluginSettings())
    search = SearchInfo(cursor)
    try:
        cursor.draw_vim_cursor()
        search.search("foo")
        palette = editor.palette()
        assert palette.color(QPalette.Base) == editor.highlighter.get_background_color()
        assert palette.color(QPalette.Text) == editor.highlighter.get_foreground_color()
        assert_readable_format(
            cursor.vim_cursor.format,
            palette.color(QPalette.Text),
            palette.color(QPalette.Base),
        )
        assert_readable_format(
            cursor.selection.format,
            palette.color(QPalette.Highlight),
            palette.color(QPalette.HighlightedText),
        )
        assert cursor.selection.format.background().color() == palette.color(
            QPalette.Highlight
        )
        assert (
            search.selection_list[0].format.background().color()
            == editor.occurrence_color
        )
        assert_readable_format(
            search.selection_list[0].format,
            editor.occurrence_color,
            palette.color(QPalette.Text),
        )
    finally:
        search.close()
        cursor.close()
        cursor.deleteLater()
        editor.close()
