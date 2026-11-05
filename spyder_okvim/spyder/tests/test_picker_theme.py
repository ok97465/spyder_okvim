"""Picker colors when Spyder styles a native light Qt application with QSS."""

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QPlainTextEdit, QWidget
from spyder.utils import palette as spyder_palette
from spyder.utils.syntaxhighlighters import COLOR_SCHEME_DEFAULT_VALUES

from spyder_okvim.spyder.picker_dialog import PickerDialog
from spyder_okvim.spyder.picker_preview import ContentPreview
from spyder_okvim.utils import theme
from spyder_okvim.utils.picker import PickerEntry, PickerMatch, SearchResult
from spyder_okvim.utils.theme import contrast_ratio


@pytest.fixture
def styled_host(qapp, qtbot, monkeypatch):
    """Match Windows: native light roles beneath Spyder's window stylesheet."""
    original = QPalette(qapp.palette())
    native = QPalette(original)
    for role, value in (
        (QPalette.Window, "white"),
        (QPalette.Base, "white"),
        (QPalette.Mid, "white"),
        (QPalette.Text, "black"),
        (QPalette.WindowText, "black"),
    ):
        native.setColor(role, QColor(value))
    qapp.setPalette(native)
    host = QWidget()
    qtbot.addWidget(host)
    host.resize(1000, 800)
    dialogs = []

    def set_theme(palette_class):
        import qdarkstyle

        monkeypatch.setattr(spyder_palette, "SpyderPalette", palette_class)
        host.setStyleSheet(qdarkstyle.load_stylesheet(palette=palette_class))
        QCoreApplication.processEvents()

    def create(palette_class, *, editor=None):
        set_theme(palette_class)
        host.show()
        picker = PickerDialog(host, editor=editor)
        picker.setAttribute(Qt.WA_DeleteOnClose, False)
        qtbot.addWidget(picker)
        dialogs.append(picker)
        picker.show()
        qtbot.waitExposed(picker)
        QCoreApplication.processEvents()
        return picker

    yield create, set_theme
    for picker in dialogs:
        picker.close()
    host.close()
    QCoreApplication.processEvents()
    qapp.setPalette(original)


def assert_readable_surface(widget, dark):
    palette = widget.palette()
    for group in (QPalette.Active, QPalette.Inactive):
        background = palette.color(group, QPalette.Base)
        foreground = palette.color(group, QPalette.Text)
        assert (background.lightness() < 128) == dark
        assert contrast_ratio(foreground, background) >= 4.5


@pytest.mark.parametrize(
    "palette_class, dark",
    [
        (spyder_palette.SpyderPaletteDark, True),
        (spyder_palette.SpyderPaletteLight, False),
    ],
)
def test_picker_native_roles_and_rendered_border_follow_spyder(
    styled_host, palette_class, dark
):
    create, _ = styled_host
    picker = create(palette_class)
    picker.set_results(SearchResult((), 0, False))
    for widget in (picker.prompt, picker.list_view, picker.list_view.viewport()):
        assert_readable_surface(widget, dark)

    # A native white Mid role must never become the dark picker's outer border.
    border = picker.grab().toImage().pixelColor(0, picker.height() // 2)
    assert border == QColor(palette_class.COLOR_BACKGROUND_4)
    viewport = picker.list_view.viewport()
    blank = (
        viewport.grab()
        .toImage()
        .pixelColor(viewport.width() // 2, viewport.height() // 2)
    )
    assert (blank.lightness() < 128) == dark


@pytest.mark.parametrize(
    "palette_class, dark",
    [
        (spyder_palette.SpyderPaletteDark, True),
        (spyder_palette.SpyderPaletteLight, False),
    ],
)
def test_picker_dropdown_menu_and_labels_keep_readable_theme_colors(
    styled_host, palette_class, dark
):
    create, _ = styled_host
    picker = create(palette_class)
    picker.set_source("git_branches")
    picker.source_selector.showPopup()
    QCoreApplication.processEvents()
    assert_readable_surface(picker.source_selector.view(), dark)
    picker.source_selector.hidePopup()
    picker.actions_menu.popup(
        picker.actions_button.mapToGlobal(picker.actions_button.rect().bottomLeft())
    )
    QCoreApplication.processEvents()
    for widget in (picker.actions_menu, picker.help_label, picker.refresh_button):
        palette = widget.palette()
        background = palette.color(QPalette.Window)
        if background.alpha() == 0:
            background = picker.palette().color(QPalette.Base)
        foreground = palette.color(QPalette.WindowText)
        assert (background.lightness() < 128) == dark
        assert contrast_ratio(foreground, background) >= 4.5
    picker.actions_menu.close()


def test_theme_refresh_preserves_picker_input_results_and_preview(styled_host):
    create, set_theme = styled_host
    picker = create(spyder_palette.SpyderPaletteDark)
    picker.set_query("unchanged")
    entry = PickerEntry("one", "files", "one.py", "project")
    picker.set_results(SearchResult((PickerMatch(entry, ()),), 1, False))
    picker.set_preview(ContentPreview("\n".join(map(str, range(500))), 10, 20))
    picker.preview.verticalScrollBar().setValue(12)
    before = (
        picker.query(),
        picker.selection_id(),
        picker.preview.toPlainText(),
        picker.preview.verticalScrollBar().value(),
    )
    set_theme(spyder_palette.SpyderPaletteLight)
    picker.setPalette(theme.interface_palette(picker))
    QCoreApplication.sendEvent(picker, QEvent(QEvent.StyleChange))
    assert_readable_surface(picker.prompt, False)
    assert_readable_surface(picker.list_view, False)
    assert before == (
        picker.query(),
        picker.selection_id(),
        picker.preview.toPlainText(),
        picker.preview.verticalScrollBar().value(),
    )


def test_dark_picker_keeps_light_editor_preview_scheme(styled_host, qtbot):
    editor = QPlainTextEdit()
    qtbot.addWidget(editor)
    scheme = dict(COLOR_SCHEME_DEFAULT_VALUES)
    scheme.update(background="#fff6dd", normal=("#242424", False, False))
    editor.color_scheme = scheme
    create, _ = styled_host
    picker = create(spyder_palette.SpyderPaletteDark, editor=editor)
    picker.set_preview(ContentPreview("def example():\n    return 1", language="py"))
    QCoreApplication.processEvents()
    assert_readable_surface(picker.prompt, True)
    assert picker.preview.palette().color(QPalette.Base) == QColor("#fff6dd")
    assert picker.preview.palette().color(QPalette.Text) == QColor("#242424")
