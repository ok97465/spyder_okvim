# -*- coding: utf-8 -*-
"""Implementation of EasyMotion overlays."""

# Standard Libraries
from itertools import product

# Third Party Libraries
from qtpy.QtCore import QCoreApplication, QEvent, QObject, Qt
from qtpy.QtGui import QColor, QPainter, QPen
from qtpy.QtWidgets import QPlainTextEdit, QWidget

# Project Libraries
from spyder_okvim.utils.qtcompat import text_width, widget_is_deleted
from spyder_okvim.vim.label import ANNOTATION_STYLE, annotation_style, place_annotation


def _marker_layout(editor, positions, names):
    """Keep only nonoverlapping labels close to their visible targets."""
    cursor = editor.textCursor()
    metrics = editor.fontMetrics()
    padding_h = ANNOTATION_STYLE["padding_h"] + ANNOTATION_STYLE["border_width"]
    padding_v = ANNOTATION_STYLE["padding_v"] + ANNOTATION_STYLE["border_width"]
    bounds = editor.viewport().rect()
    min_width = text_width(metrics, " ")
    height = metrics.height() + 2 * padding_v
    occupied = []
    layout = []
    for position, name in zip(positions, names):
        cursor.setPosition(position)
        target = editor.cursorRect(cursor)
        if not target.intersects(bounds):
            continue
        width = max(text_width(metrics, name), min_width) + 2 * padding_h
        target.translate(-padding_h, -padding_v)
        rect = place_annotation(target, width, height, bounds, occupied)
        if rect is not None:
            occupied.append(rect)
            layout.append((position, name, rect))
    return layout


class EasyMotionMarkerManager:
    """Manage overlay marker assignments."""

    def __init__(self):
        """Initialize empty marker sets."""
        single_keys = "hklyuiopnm,qwe"
        prefixes = "rtzxcvbasdgjf;"
        self.marker_keys = list(single_keys)
        self.marker_keys.extend(
            prefix + key for prefix, key in product(prefixes, single_keys)
        )
        self.position_list: list[int] = []
        self.name_list: list[str] = []
        self.motion_type = None
        self._targets = []
        self._prefix = ""
        self.total_count = 0
        self.visible_count = 0
        self.label_rects = {}

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

    def __init__(self):
        super().__init__()
        self.editor = None
        self._markers = None

    def show_markers(
        self, editor: QPlainTextEdit | None, markers: EasyMotionMarkerManager
    ):
        """Bind the overlay and repaint after the visible markers change."""
        if editor is None:
            self.clear()
            return
        viewport = editor.viewport()
        if editor is not self.editor:
            self.clear()
            self.editor = editor
            viewport.installEventFilter(self)
        self._markers = markers
        viewport.update()

    def clear(self):
        """Remove the overlay, including when Qt has already deleted the editor."""
        editor, self.editor = self.editor, None
        self._markers = None
        if editor is not None and not widget_is_deleted(editor):
            viewport = editor.viewport()
            viewport.removeEventFilter(self)
            viewport.update()

    def eventFilter(self, viewport: QWidget, event: QEvent):
        editor = self.editor
        if editor is None or event.type() != QEvent.Paint:
            return False
        # Handle the painter event last to prevent
        # the area painted by EasyMotion to be overridden
        viewport.removeEventFilter(self)
        QCoreApplication.sendEvent(viewport, event)
        if self.editor is not editor or widget_is_deleted(viewport):
            return True
        viewport.installEventFilter(self)
        markers = self._markers

        font = editor.font()
        font.setBold(True)

        border_width = ANNOTATION_STYLE["border_width"]
        radius = ANNOTATION_STYLE["radius"]

        style = annotation_style(editor)
        text_color = QColor(style["text"])
        border_color = QColor(style["border"])
        background_color = QColor(style["background"])

        pen_text = QPen(text_color)
        pen_border = QPen(border_color, border_width)

        with QPainter(viewport) as painter:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setBrush(background_color)
            painter.setFont(font)
            for position, marker_name in zip(markers.position_list, markers.name_list):
                rect = markers.label_rects.get(position)
                if rect is None:
                    continue
                painter.setPen(pen_border)
                painter.drawRoundedRect(rect, radius, radius)
                painter.setPen(pen_text)
                painter.drawText(rect, Qt.AlignCenter, marker_name)

        return True
