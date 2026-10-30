"""Substitute results are painted in source space without changing editor state."""

from types import SimpleNamespace

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, QRect, Qt
from qtpy.QtGui import QColor, QFontDatabase, QImage, QPainter, QPalette, QTextLayout
from qtpy.QtWidgets import QPlainTextEdit

from spyder_okvim.spyder.substitute_overlay import SubstituteOverlay
from spyder_okvim.utils.qtcompat import widget_is_deleted
from spyder_okvim.utils.substitute_preview import PreviewRow


@pytest.fixture
def overlay_editor(qtbot):
    editor = QPlainTextEdit()
    editor.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
    editor.resize(560, 300)
    editor.setPlainText("first line\nfoo foo tail\nlast line")
    editor.show()
    qtbot.addWidget(editor)
    QCoreApplication.processEvents()
    overlay = SubstituteOverlay()
    overlay.set_editor(editor)
    yield editor, overlay
    overlay.cleanup()
    editor.close()


def publish(overlay, *rows, **metadata):
    result = SimpleNamespace(
        rows=rows,
        partial=False,
        output_truncated=False,
        omitted_blocks=(),
        confirm=False,
        read_only=False,
    )
    for name, value in metadata.items():
        setattr(result, name, value)
    overlay.set_result(result)
    QCoreApplication.processEvents()


def source_state(editor):
    document = editor.document()
    cursor = editor.textCursor()
    return (
        editor.toPlainText(),
        document.revision(),
        document.isModified(),
        document.availableUndoSteps(),
        document.availableRedoSteps(),
        cursor.position(),
        cursor.anchor(),
        editor.verticalScrollBar().value(),
        editor.horizontalScrollBar().value(),
    )


def paint_image(editor, overlay):
    image = QImage(editor.viewport().size(), QImage.Format_ARGB32)
    image.fill(QColor("#ff00ff"))
    with QPainter(image) as painter:
        overlay._paint(painter)
    return image


def test_results_share_one_source_line_without_editing_or_stealing_input(
    overlay_editor,
):
    editor, overlay = overlay_editor
    row = PreviewRow(1, "foo foo tail", "long long tail", ((0, 4), (5, 9)), ())
    before = source_state(editor)
    publish(overlay, row)
    painted = overlay.render_rows()
    assert len(painted) == 1
    assert painted[0].layout.text() == "long long tail"
    assert [item.length for item in painted[0].layout.formats()] == [4, 4]
    assert overlay.widget.parentWidget() is editor.viewport()
    assert not overlay.widget.isWindow()
    assert overlay.widget.testAttribute(Qt.WA_TransparentForMouseEvents)
    assert overlay.widget.focusPolicy() == Qt.NoFocus
    assert overlay.widget.geometry() == editor.viewport().rect()
    assert source_state(editor) == before
    assert not paint_image(editor, overlay).isNull()
    assert source_state(editor) == before


def test_noop_and_stale_source_rows_leave_original_rendering(overlay_editor):
    editor, overlay = overlay_editor
    publish(
        overlay,
        PreviewRow(0, "first line", "first line", (), ()),
        PreviewRow(1, "wrong old source", "new", ((0, 3),), ()),
    )
    assert overlay.render_rows() == ()
    publish(overlay, PreviewRow(1, "foo foo tail", "bar foo tail", ((0, 3),), ()))
    assert overlay.render_rows()
    editor.insertPlainText("external ")
    assert overlay.render_rows() == ()


def test_unchanged_fragments_keep_syntax_formats_after_length_changes(overlay_editor):
    editor, overlay = overlay_editor
    block = editor.document().findBlockByNumber(1)
    syntax = QTextLayout.FormatRange()
    syntax.start, syntax.length = 4, 3
    syntax.format.setForeground(QColor("#0b55cc"))
    syntax.format.setFontItalic(True)
    block.layout().setFormats([syntax])
    before = source_state(editor)
    row = PreviewRow(1, "foo foo tail", "longer foo tail", ((0, 6),), (), ((3, 12, 6),))
    publish(overlay, row)
    layout = overlay.render_rows()[0].layout
    mapped = layout.formats()[0]
    assert (mapped.start, mapped.length) == (7, 3)
    assert mapped.format.foreground().color() == QColor("#0b55cc")
    assert mapped.format.fontItalic()
    assert block.layout().formats()[0].start == 4
    assert source_state(editor) == before
    syntax.format.setForeground(QColor("#00aa44"))
    block.layout().setFormats([syntax])
    refreshed = overlay.render_rows()[0].layout
    assert refreshed is not layout
    assert refreshed.formats()[0].format.foreground().color() == QColor("#00aa44")


def test_repainting_and_clearing_restore_uncovered_source_pixels(overlay_editor):
    editor, overlay = overlay_editor
    block = editor.document().findBlockByNumber(1)
    top = editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
    bounds = QRect(0, int(top), 150, int(editor.blockBoundingGeometry(block).height()))
    source = editor.viewport().grab().toImage().copy(bounds)
    publish(overlay, PreviewRow(1, "foo foo tail", "longer after", ((0, 12),), ()))
    assert editor.viewport().grab().toImage().copy(bounds) != source
    publish(overlay, PreviewRow(2, "last line", "end", ((0, 3),), ()))
    assert editor.viewport().grab().toImage().copy(bounds) == source
    overlay.clear()
    QCoreApplication.processEvents()
    assert editor.viewport().grab().toImage().copy(bounds) == source


@pytest.mark.parametrize("replacement", ["", "a", "😀한글"])
def test_empty_and_utf16_results_use_safe_text_positions(overlay_editor, replacement):
    editor, overlay = overlay_editor
    editor.setPlainText("foo")
    length = len(replacement.encode("utf-16-le")) // 2
    row = PreviewRow(
        0,
        "foo",
        replacement,
        ((0, length),) if replacement else (),
        () if replacement else (0,),
    )
    publish(overlay, row)
    rendered = overlay.render_rows()[0]
    assert rendered.layout.text() == replacement
    assert rendered.layout.lineCount() == 1
    assert bool(rendered.deletions) is (replacement == "")
    assert not paint_image(editor, overlay).isNull()
    assert editor.toPlainText() == "foo"


def test_nowrap_overflow_is_clipped_before_the_next_source_line(overlay_editor):
    editor, overlay = overlay_editor
    editor.setLineWrapMode(QPlainTextEdit.NoWrap)
    editor.resize(180, 200)
    row = PreviewRow(1, "foo foo tail", "long " * 200, ((0, 1000),), ())
    publish(overlay, row)
    rendered = overlay.render_rows()[0]
    assert rendered.overflow
    next_block = editor.document().findBlockByNumber(2)
    next_top = (
        editor.blockBoundingGeometry(next_block)
        .translated(editor.contentOffset())
        .top()
    )
    assert rendered.rect.bottom() <= next_top
    image = paint_image(editor, overlay)
    assert image.pixelColor(10, int(next_top + 2)) == QColor("#ff00ff")
    assert editor.toPlainText().endswith("last line")


def test_wrapped_result_keeps_original_line_height_and_tab_layout(overlay_editor):
    editor, overlay = overlay_editor
    editor.resize(200, 260)
    # The target block is deliberately wrapped; other paragraph heights remain
    # those of the real document even when the result needs many more rows.
    before = "\tword " * 12
    editor.setPlainText("start\n" + before + "\nnext")
    editor.setTabStopDistance(48)
    QCoreApplication.processEvents()
    block = editor.document().findBlockByNumber(1)
    original_lines = block.layout().lineCount()
    assert original_lines > 1
    height = editor.blockBoundingGeometry(block).height()
    publish(overlay, PreviewRow(1, before, "\tlonger " * 120, ((0, 960),), ()))
    rendered = overlay.render_rows()[0]
    assert rendered.layout.lineCount() == original_lines
    assert rendered.layout.textOption().tabStopDistance() == 48
    assert rendered.rect.height() <= height
    assert rendered.overflow
    assert editor.blockBoundingGeometry(block).height() == height


def test_scrolling_refreshes_coordinates_and_notifies_the_owner(overlay_editor):
    editor, overlay = overlay_editor
    editor.setLineWrapMode(QPlainTextEdit.NoWrap)
    source = "foo " + "tail " * 120
    editor.setPlainText("\n".join([source] * 100))
    publish(overlay, PreviewRow(30, source, "bar " + "tail " * 120, ((0, 3),), ()))
    assert not overlay.render_rows()
    changed = []
    overlay.sig_view_changed.connect(lambda: changed.append(True))
    editor.verticalScrollBar().setValue(30)
    QCoreApplication.processEvents()
    assert changed
    rendered = overlay.render_rows()[0]
    assert editor.viewport().rect().contains(rendered.rect.toRect())
    old_x = rendered.origin.x()
    editor.horizontalScrollBar().setValue(8)
    QCoreApplication.processEvents()
    assert overlay.render_rows()[0].origin.x() < old_x
    assert overlay.widget.geometry() == editor.viewport().rect()


def test_font_palette_and_resize_refresh_painting_without_changing_rows(overlay_editor):
    editor, overlay = overlay_editor
    row = PreviewRow(1, "foo foo tail", "bar foo tail", ((0, 3),), ())
    publish(overlay, row)
    previous = overlay.render_rows()[0].layout
    font = editor.font()
    font.setPointSizeF(font.pointSizeF() + 3)
    editor.setFont(font)
    palette = editor.palette()
    palette.setColor(QPalette.Base, QColor("#102030"))
    palette.setColor(QPalette.Text, QColor("#f0e0d0"))
    editor.setPalette(palette)
    editor.resize(400, 240)
    QCoreApplication.processEvents()
    current = overlay.render_rows()[0]
    assert current.layout is not previous
    assert current.layout.font() == editor.font()
    assert overlay.rows == (row,)
    assert overlay.widget.geometry() == editor.viewport().rect()
    image = paint_image(editor, overlay)
    assert image.pixelColor(200, int(current.rect.bottom() - 1)) == QColor("#102030")


def test_clear_switch_and_cleanup_release_the_previous_viewport(overlay_editor, qtbot):
    editor, overlay = overlay_editor
    publish(overlay, PreviewRow(1, "foo foo tail", "bar foo tail", ((0, 3),), ()))
    previous = overlay.widget
    overlay.clear()
    assert overlay.rows == ()
    assert not previous.isVisible()
    other = QPlainTextEdit()
    qtbot.addWidget(other)
    overlay.set_editor(other)
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert widget_is_deleted(previous)
    assert overlay.widget.parentWidget() is other.viewport()
    overlay.cleanup()
    overlay.cleanup()
    assert overlay.widget is None


def test_output_omissions_keep_source_visible_but_show_partial_indicator(
    overlay_editor,
):
    editor, overlay = overlay_editor
    publish(overlay, output_truncated=True, omitted_blocks=(1,))
    assert overlay.widget.isVisible()
    assert overlay.render_rows() == ()
    image = paint_image(editor, overlay)
    block = editor.document().findBlockByNumber(1)
    y = editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
    assert image.pixelColor(10, int(y + 3)) == QColor("#ff00ff")
