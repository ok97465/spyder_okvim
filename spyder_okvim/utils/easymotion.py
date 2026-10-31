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
from spyder_okvim.vim.label import ANNOTATION_STYLE, annotation_style, place_annotation


def _marker_layout(editor, positions, names):
    """Keep only nonoverlapping labels close to their visible targets."""
    cursor = editor.textCursor()
    metrics = editor.fontMetrics()
    padding_h = ANNOTATION_STYLE["padding_h"] + ANNOTATION_STYLE["border_width"]
    padding_v = ANNOTATION_STYLE["padding_v"] + ANNOTATION_STYLE["border_width"]
    occupied = []
    layout = []
    for position, name in zip(positions, names):
        cursor.setPosition(position)
        target = editor.cursorRect(cursor)
        if not target.intersects(editor.viewport().rect()):
            continue
        width = max(text_width(metrics, name), text_width(metrics, " ")) + 2 * padding_h
        height = metrics.height() + 2 * padding_v
        target.translate(-padding_h, -padding_v)
        rect = place_annotation(
            target, width, height, editor.viewport().rect(), occupied
        )
        if rect is not None:
            occupied.append(rect)
            layout.append((position, name, rect))
    return layout


class EasyMotionMarkerManager:
    """Manage overlay marker assignments."""

    def __init__(self):
        """Initialize empty marker sets."""
        self.position_list: list[int] = []
        self.name_list: list[str] = []

        self.marker_keys: list[str] = []
        self.init_marker_keys()
        self.motion_type = None
        self._targets = []
        self._prefix = ""
        self.total_count = 0
        self.visible_count = 0
        self.label_rects = {}

    def init_marker_keys(self):
        """Initialize markers."""
        keys1 = "hklyuiopnm,qwe"
        keys2 = "rtzxcvbasdgjf;"

        self.marker_keys = list(keys1)
        self.marker_keys += ["".join(pro) for pro in product(keys2, keys1)]

    def set_positions(self, position_list: list[int], motion_type):
        """Set positions."""
        self.total_count = len(position_list)
        self._targets = list(zip(position_list, self.marker_keys))
        self._prefix = ""
        self.position_list = [position for position, _ in self._targets]
        self.name_list = [label for _, label in self._targets]
        self.motion_type = motion_type
        self.visible_count = len(self._targets)
        self.label_rects = {}

    def fit_to_editor(self, editor):
        """Exclude targets whose labels cannot be drawn without overlap."""
        layout = _marker_layout(editor, self.position_list, self.name_list)
        self._targets = [(position, name) for position, name, _ in layout]
        self.position_list = [position for position, _ in self._targets]
        self.name_list = [name for _, name in self._targets]
        self.visible_count = len(self._targets)
        self.label_rects = {position: rect for position, _name, rect in layout}

    def handle_user_input(self, ch):
        """Process user input."""
        if ch == "\b":
            self._prefix = self._prefix[:-1]
        else:
            self._prefix += ch
        matching = [
            (position, label)
            for position, label in self._targets
            if label.startswith(self._prefix)
        ]
        self.position_list = [position for position, _ in matching]
        self.name_list = [label[len(self._prefix) :] or label for _, label in matching]


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
        self.settings = None
        self.label_rects = {}

    def eventFilter(self, viewport: QWidget, event: QEvent):
        if not viewport or event.type() != QEvent.Paint:
            return False
        # Handle the painter event last to prevent
        # the area painted by EasyMotion to be overridden
        viewport.removeEventFilter(self)
        QCoreApplication.sendEvent(viewport, event)
        viewport.installEventFilter(self)

        editor = self.editor

        font = editor.font()
        font.setBold(True)

        border_width = ANNOTATION_STYLE["border_width"]
        radius = ANNOTATION_STYLE["radius"]

        style = annotation_style(editor, self.settings)
        text_color = QColor(style["text"])
        border_color = QColor(style["border"])
        background_color = QColor(style["background"])

        pen_text = QPen(text_color)
        pen_border = QPen(border_color, border_width)

        with QPainter(viewport) as painter:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setBrush(background_color)
            painter.setFont(font)
            for position, marker_name in zip(self.positions, self.names):
                rect = self.label_rects.get(position)
                if rect is None:
                    continue
                painter.setPen(pen_border)
                painter.drawRoundedRect(rect, radius, radius)
                painter.setPen(pen_text)
                painter.drawText(rect, Qt.AlignCenter, marker_name)

        return True
