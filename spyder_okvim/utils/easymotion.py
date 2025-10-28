# -*- coding: utf-8 -*-
"""Implementation of EasyMotion overlays."""

# Standard Libraries
from itertools import product

# Third Party Libraries
from qtpy.QtCore import QCoreApplication, QEvent, QObject, Qt
from qtpy.QtGui import QColor, QPainter, QPen
from qtpy.QtWidgets import QPlainTextEdit, QWidget

# Project Libraries
from spyder_okvim.utils.qtcompat import text_width
from spyder_okvim.vim.label import ANNOTATION_STYLE


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

        font = editor.font()
        font.setBold(True)

        border_width = ANNOTATION_STYLE["border_width"]
        padding_h = ANNOTATION_STYLE["padding_h"]
        padding_v = ANNOTATION_STYLE["padding_v"]
        radius = ANNOTATION_STYLE["radius"]

        text_color = QColor(ANNOTATION_STYLE["text"])
        border_color = QColor(ANNOTATION_STYLE["border"])
        background_color = QColor(ANNOTATION_STYLE["background"])

        pen_text = QPen(text_color)
        pen_border = QPen(border_color, border_width)

        with QPainter(viewport) as painter:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setBrush(background_color)
            painter.setFont(font)
            ch_width = text_width(fm, " ")

            for pos_ch, marker_name in zip(self.positions, self.names):
                tc.setPosition(pos_ch)

                rect = editor.cursorRect(tc)
                text_width_px = max(text_width(fm, marker_name), ch_width)
                total_width = text_width_px + 2 * (padding_h + border_width)
                total_height = fm.height() + 2 * (padding_v + border_width)

                rect.setWidth(total_width)
                rect.setHeight(total_height)
                rect.translate(-(border_width + padding_h), -(border_width + padding_v))

                if rect.intersects(viewport.rect()):
                    painter.setPen(pen_border)
                    painter.drawRoundedRect(rect, radius, radius)
                    painter.setPen(pen_text)
                    painter.drawText(rect, Qt.AlignCenter, marker_name)

        return True
