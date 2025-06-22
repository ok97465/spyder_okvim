# -*- coding: utf-8 -*-
"""Implementation of EasyMotion overlays."""

# Standard Libraries
from itertools import product

# Third Party Libraries
from qtpy.QtCore import QCoreApplication, QEvent, QObject, Qt
from qtpy.QtGui import QColor, QPainter, QPen
from qtpy.QtWidgets import QPlainTextEdit, QWidget


class EasyMotionMarkerManager:
    """Manage overlay marker assignments."""

    def __init__(self):
        """Initialize empty marker sets."""
        self.position_list: list[int] = []
        self.name_list: list[str] = []

        self.marker_keys: list[str] = []
        self.init_marker_keys()
        self.motion_type = None

    def init_marker_keys(self):
        """Initialize markers."""
        keys1 = "hklyuiopnm,qwe"
        keys2 = "rtzxcvbasdgjf;"

        self.marker_keys = list(keys1)
        self.marker_keys += ["".join(pro) for pro in product(keys2, keys1)]

    def set_positions(self, position_list: list[int], motion_type):
        """Set positions."""
        self.name_list = []
        self.position_list = position_list
        self.name_list = self.marker_keys[: len(position_list)]
        self.motion_type = motion_type

    def handle_user_input(self, ch):
        """Process user input."""
        positions = []
        names = []
        for pos, name in zip(self.position_list, self.name_list):
            if name[0] != ch:
                continue
            positions.append(pos)
            if len(name) == 1:
                names.append(name)
                break
            else:
                names.append(name[1:])
        self.position_list = positions
        self.name_list = names


class EasyMotionPainter(QObject):
    """Draw overlay markers for EasyMotion in a text editor.

    Ref: github.com/serpheroth/QtCreator-EasyMotion

    """

    def __init__(self, editor: QPlainTextEdit = None):
        """Create painter.

        Args:
            editor: Widget receiving overlay rendering.
        """
        super().__init__()
        self.editor = editor
        self.positions = []
        self.names = []

    def eventFilter(self, viewport: QWidget, event: QEvent):
        if not viewport or event.type() != QEvent.Paint:
            return False
        # Handle the painter event last to prevent
        # the area painted by EasyMotion to be overridden
        viewport.removeEventFilter(self)
        QCoreApplication.sendEvent(viewport, event)
        viewport.installEventFilter(self)

        editor = self.editor
        tc = editor.textCursor()
        fm = editor.fontMetrics()

        pen_ch = QPen(QColor(220, 120, 120, 255))
        pen_border = QPen(QColor(0, 160, 100, 255), 1)

        with QPainter(viewport) as painter:
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.setBrush(QColor(57, 34, 79, 255))
            painter.setFont(editor.font())
            ch_width = fm.width(" ")

            for pos_ch, marker_name in zip(self.positions, self.names):
                tc.setPosition(pos_ch)

                rect = editor.cursorRect(tc)
                rect.setWidth(ch_width * len(marker_name))

                if rect.intersects(viewport.rect()):
                    painter.setPen(pen_border)
                    painter.drawRoundedRect(rect, 40, 40, Qt.RelativeSize)
                    painter.setPen(pen_ch)
                    text_height = rect.bottom() - fm.descent()
                    painter.drawText(rect.left(), text_height, marker_name)

        return True
