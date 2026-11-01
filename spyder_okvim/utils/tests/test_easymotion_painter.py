"""EasyMotion's real viewport painting follows the current editor theme."""

from qtpy.QtCore import QRect
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QPlainTextEdit

from spyder_okvim.utils.easymotion import EasyMotionPainter


def test_visible_markers_repaint_with_editor_palette(qtbot):
    editor = QPlainTextEdit("Jump targets")
    qtbot.addWidget(editor)
    editor.resize(320, 180)
    editor.show()
    painter = EasyMotionPainter(editor)
    painter.positions = [0]
    painter.names = ["h"]
    painter.label_rects = {0: QRect(30, 30, 70, 40)}
    viewport = editor.viewport()
    viewport.installEventFilter(painter)
    try:
        for background, foreground in (
            ("#234567", "#ffffff"),
            ("#f9e7a0", "#112233"),
        ):
            palette = QPalette(editor.palette())
            palette.setColor(QPalette.Base, QColor("#ededed"))
            palette.setColor(QPalette.Text, QColor("#334455"))
            palette.setColor(QPalette.Highlight, QColor(background))
            palette.setColor(QPalette.HighlightedText, QColor(foreground))
            editor.setPalette(palette)
            viewport.update()
            # Grabbing the viewport executes the installed Paint event filter,
            # including drawing on a real Qt paint device.
            snapshot = viewport.grab().toImage()
            colors = {
                snapshot.pixelColor(x, y).name()
                for x in range(snapshot.width())
                for y in range(snapshot.height())
            }
            assert background in colors
            assert foreground in colors
    finally:
        viewport.removeEventFilter(painter)
