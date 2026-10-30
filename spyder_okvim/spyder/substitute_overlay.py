"""Paint substitution results over source lines without editing the document."""

# Standard Libraries
import math
import weakref
from dataclasses import dataclass

# Third Party Libraries
from qtpy.QtCore import QEvent, QObject, QPointF, QRectF, Qt, Signal
from qtpy.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPalette,
    QPen,
    QTextCharFormat,
    QTextLayout,
    QTextOption,
)
from qtpy.QtWidgets import QWidget

# Project Libraries
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted


@dataclass(frozen=True)
class RenderedRow:
    """One preview paragraph clipped to its source paragraph's existing space."""

    block_number: int
    rect: QRectF
    origin: QPointF
    layout: QTextLayout
    overflow: bool
    deletions: tuple[QPointF, ...]


class _OverlayWidget(QWidget):
    """Passive viewport child; existing guides and editor popups stay above it."""

    def __init__(self, owner, viewport):
        super().__init__(viewport)
        self._owner = weakref.ref(owner)
        self.setObjectName("vimSubstituteOverlay")
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.hide()

    def paintEvent(self, event):
        owner = live_widget(self._owner)
        if owner is not None:
            with QPainter(self) as painter:
                painter.setClipRect(event.rect())
                owner._paint(painter)


class SubstituteOverlay(QObject):
    """Own rendering only; calculation and Ex session validation stay outside.

    Preview text uses the editor's font, tabs and wrapping width. It occupies
    the source paragraph's existing height, so a longer result cannot cover the
    next paragraph. Clipped results carry an ellipsis and a partial-preview
    badge. The actual document layout and scroll ranges remain unchanged.
    """

    sig_view_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editor = None
        self._revision = None
        self._widget = None
        self._result = None
        self._layouts = {}
        self._connections = []
        self._closed = False

    @property
    def widget(self):
        widget = self._widget
        return widget if widget is not None and not widget_is_deleted(widget) else None

    @property
    def rows(self):
        return self._result.rows if self._result is not None else ()

    def set_editor(self, editor):
        """Dispose of the previous viewport child before following another view."""
        if self._closed or editor is live_widget(self._editor):
            return
        self.clear()
        previous_editor = live_widget(self._editor)
        if previous_editor is not None:
            previous_editor.viewport().removeEventFilter(self)
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._connections = []
        widget = self.widget
        self._widget = None
        if widget is not None:
            widget.deleteLater()
        self._editor = None
        if editor is None or widget_is_deleted(editor):
            return
        viewport = editor.viewport()
        self._editor = weakref.ref(editor)
        self._widget = _OverlayWidget(self, viewport)
        viewport.installEventFilter(self)
        self._connections = [
            (editor.updateRequest, self._view_changed),
            (editor.verticalScrollBar().valueChanged, self._view_changed),
            (editor.horizontalScrollBar().valueChanged, self._view_changed),
            (editor.destroyed, self._editor_destroyed),
        ]
        for signal, slot in self._connections:
            signal.connect(slot)
        self.refresh_geometry()

    def set_result(self, result):
        """Publish bounded rows, keeping the original source revision as a guard."""
        editor = live_widget(self._editor)
        if self._closed or editor is None:
            return
        document = editor.document()
        self._revision = document.revision()
        self._result = result
        self._layouts.clear()
        widget = self.widget
        if widget is not None:
            if result.rows or result.output_truncated or result.omitted_blocks:
                self.refresh_geometry()
                widget.show()
                widget.lower()
                widget.update()
            else:
                widget.hide()

    def clear(self):
        """Release result text and hide immediately, including during cancellation."""
        self._result = None
        self._revision = None
        self._layouts.clear()
        widget = self.widget
        if widget is not None:
            widget.hide()
            widget.update()

    def refresh_geometry(self):
        widget = self.widget
        if widget is not None:
            widget.setGeometry(widget.parentWidget().rect())
            widget.update()

    def _view_changed(self, *args):
        # Folding can expose new blocks without a scrollbar-value change.
        # The owner coalesces these notifications and compares coverage, so a
        # decoration-only update never starts another calculation.
        self.refresh_geometry()
        self.sig_view_changed.emit()

    def _editor_destroyed(self, *args):
        self.clear()
        self._editor = None
        self._widget = None
        self._connections = []

    def eventFilter(self, watched, event):
        widget = self.widget
        if widget is not None and watched is widget.parentWidget():
            if event.type() in (QEvent.Resize, QEvent.FontChange):
                self._layouts.clear()
                self._view_changed()
            elif event.type() in (QEvent.PaletteChange, QEvent.StyleChange):
                self._layouts.clear()
                self.refresh_geometry()
        return super().eventFilter(watched, event)

    def _valid_editor(self):
        editor = live_widget(self._editor)
        if editor is None or editor.document().revision() != self._revision:
            return None
        return editor

    @staticmethod
    def _colors(editor):
        palette = editor.palette()
        background = palette.color(QPalette.Base)
        foreground = palette.color(QPalette.Text)
        accent = palette.color(QPalette.Highlight)
        tint = QColor(
            round(background.red() * 0.75 + accent.red() * 0.25),
            round(background.green() * 0.75 + accent.green() * 0.25),
            round(background.blue() * 0.75 + accent.blue() * 0.25),
        )
        return background, foreground, accent, tint

    @staticmethod
    def _syntax_formats(source_formats, source_spans):
        """Move unchanged syntax formats using the calculator's UTF-16 map."""
        formats = []
        index = 0
        source_formats = sorted(source_formats, key=lambda item: item.start)
        for source_start, source_end, output_start in source_spans:
            while (
                index < len(source_formats)
                and source_formats[index].start + source_formats[index].length
                <= source_start
            ):
                index += 1
            current = index
            while (
                current < len(source_formats)
                and source_formats[current].start < source_end
            ):
                source = source_formats[current]
                start = max(source_start, source.start)
                end = min(source_end, source.start + source.length)
                if start < end:
                    target = QTextLayout.FormatRange()
                    target.start = output_start + start - source_start
                    target.length = end - start
                    target.format = QTextCharFormat(source.format)
                    formats.append(target)
                current += 1
        return formats

    def _layout_row(self, editor, block, row):
        source_layout = block.layout()
        if source_layout is None or not source_layout.lineCount():
            return None
        line_count = source_layout.lineCount()
        first_line = source_layout.lineAt(0)
        line_height = max(1, math.ceil(first_line.height()))
        if line_count > 1:
            line_height = source_layout.lineAt(1).y() - first_line.y()
        width = max(1.0, first_line.width())
        option = QTextOption(source_layout.textOption())
        option.setTabStopDistance(editor.tabStopDistance())
        font = editor.font()
        _background, foreground, _accent, tint = self._colors(editor)
        source_formats = source_layout.formats()
        key = (
            row,
            font.toString(),
            width,
            line_count,
            first_line.x(),
            line_height,
            editor.tabStopDistance(),
            option.wrapMode(),
            foreground.rgba(),
            tint.rgba(),
            tuple(
                (item.start, item.length, QTextCharFormat(item.format))
                for item in source_formats
            ),
        )
        cached = self._layouts.get(row.block_number)
        if cached is not None and cached[0] == key:
            return cached[1:]
        layout = QTextLayout(row.after, font)
        layout.setTextOption(option)
        formats = self._syntax_formats(source_formats, row.source_spans)
        for start, end in row.replacements:
            changed = QTextLayout.FormatRange()
            changed.start, changed.length = start, end - start
            changed.format.setForeground(foreground)
            changed.format.setBackground(tint)
            formats.append(changed)
        layout.setFormats(formats)
        layout.beginLayout()
        for number in range(line_count):
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(width)
            line.setPosition(
                QPointF(first_line.x(), first_line.y() + number * line_height)
            )
        layout.endLayout()
        text_length = len(row.after.encode("utf-16-le")) // 2
        last = layout.lineAt(layout.lineCount() - 1) if layout.lineCount() else None
        overflow = bool(last and last.textStart() + last.textLength() < text_length)
        self._layouts[row.block_number] = key, layout, overflow
        return layout, overflow

    def render_rows(self):
        """Resolve positions from current layout; never read or edit command input."""
        editor = self._valid_editor()
        if editor is None or self._result is None:
            return ()
        viewport = editor.viewport()
        visible = QRectF(viewport.rect())
        offset = editor.contentOffset()
        rendered = []
        for row in self.rows:
            block = editor.document().findBlockByNumber(row.block_number)
            if (
                not block.isValid()
                or not block.isVisible()
                or block.text() != row.before
                or row.before == row.after
            ):
                continue
            geometry = editor.blockBoundingGeometry(block).translated(offset)
            rect = QRectF(
                0, geometry.top(), visible.width(), geometry.height()
            ).intersected(visible)
            if rect.isEmpty():
                continue
            calculated = self._layout_row(editor, block, row)
            if calculated is None:
                continue
            layout, overflow = calculated
            origin = geometry.topLeft()
            deletions = []
            for position in row.deletions:
                line = layout.lineForTextPosition(position)
                if line.isValid():
                    x = line.cursorToX(position)
                    # PyQt returns (x, position); PySide returns x directly.
                    x = x[0] if isinstance(x, tuple) else x
                    deletions.append(origin + QPointF(x, line.y()))
            for index in range(layout.lineCount()):
                line = layout.lineAt(index)
                right = origin.x() + line.x() + line.naturalTextWidth()
                if right > visible.right() + 0.5:
                    overflow = True
            rendered.append(
                RenderedRow(
                    row.block_number, rect, origin, layout, overflow, tuple(deletions)
                )
            )
        return tuple(rendered)

    def _paint(self, painter):
        editor = self._valid_editor()
        if editor is None or self._result is None:
            return
        background, foreground, accent, _tint = self._colors(editor)
        painter.setFont(editor.font())
        rows = self.render_rows()
        for row in rows:
            painter.save()
            painter.setClipRect(row.rect, Qt.IntersectClip)
            painter.fillRect(row.rect, background)
            painter.fillRect(
                QRectF(row.rect.left(), row.rect.top(), 2, row.rect.height()), accent
            )
            painter.setPen(foreground)
            row.layout.draw(painter, row.origin)
            painter.setPen(QPen(QColor("#e76f51"), 2))
            for point in row.deletions:
                bottom = point + QPointF(0, editor.fontMetrics().height() - 1)
                painter.drawLine(point, bottom)
                painter.drawLine(point + QPointF(-2, 0), point + QPointF(2, 0))
            if row.overflow:
                width = max(editor.fontMetrics().horizontalAdvance("…") + 6, 12)
                marker = QRectF(
                    row.rect.right() - width,
                    row.rect.bottom() - editor.fontMetrics().height(),
                    width,
                    editor.fontMetrics().height(),
                )
                painter.fillRect(marker, background)
                painter.setPen(accent)
                painter.drawText(marker, Qt.AlignCenter, "…")
            painter.restore()
        self._paint_badge(painter, editor, rows)

    def _paint_badge(self, painter, editor, rows):
        result = self._result
        partial = (
            result.partial or result.output_truncated or bool(result.omitted_blocks)
        )
        partial |= any(row.overflow for row in rows)
        text = "Partial preview" if partial else "Preview"
        if result.confirm:
            text += " · All approved"
        if result.read_only:
            text += " · Read-only"
        font = QFont(editor.font())
        font.setPointSizeF(max(7, font.pointSizeF() - 1))
        painter.setFont(font)
        metrics = painter.fontMetrics()
        width = min(editor.viewport().width() - 8, metrics.horizontalAdvance(text) + 12)
        if width < 20:
            return
        rect = QRectF(
            editor.viewport().width() - width - 4, 4, width, metrics.height() + 4
        )
        background, foreground, accent, _tint = self._colors(editor)
        painter.setBrush(background)
        painter.setPen(accent)
        painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(foreground)
        painter.drawText(
            rect.adjusted(5, 0, -5, 0), Qt.AlignVCenter | Qt.AlignRight, text
        )

    def cleanup(self):
        if not self._closed:
            self.set_editor(None)
            self._closed = True
