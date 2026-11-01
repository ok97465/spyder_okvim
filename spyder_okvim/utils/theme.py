"""Resolve plugin colors from host roles, keeping small text readable."""

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QPalette


def _opaque_over(color, background):
    """Composite a possibly translucent color over an opaque background."""
    color = QColor(color)
    if color.alpha() == 255:
        return color
    alpha = color.alphaF()
    return QColor(
        *(
            round(a * alpha + b * (1 - alpha))
            for a, b in zip(color.getRgb()[:3], background.getRgb()[:3])
        )
    )


def contrast_ratio(foreground, background):
    """Return the sRGB relative-luminance contrast, or zero for invalid colors."""
    foreground, background = QColor(foreground), QColor(background)
    if not foreground.isValid() or not background.isValid():
        return 0.0
    background = _opaque_over(background, QColor(Qt.white))
    foreground = _opaque_over(foreground, background)

    def luminance(color):
        channels = (value / 255 for value in color.getRgb()[:3])
        linear = (
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        )
        return sum(
            weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear)
        )

    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def readable_color(preferred, background, *fallbacks, minimum_ratio=4.5):
    """Prefer theme colors, falling back to readable black or white if needed.

    Keep the preferred role unchanged whenever it meets the requested contrast.
    Theme-provided alternatives take priority over neutral extremes. For a
    requested ratio that no candidate can meet, return the strongest candidate.
    """
    background = QColor(background)
    candidates = [
        QColor(color) for color in (preferred, *fallbacks, Qt.black, Qt.white)
    ]
    candidates = [color for color in candidates if color.isValid()]
    for color in candidates:
        if contrast_ratio(color, background) >= minimum_ratio:
            return color
    return max(candidates, key=lambda color: contrast_ratio(color, background))


def selection_colors(widget):
    """Use the host selection background with legible foreground text."""
    palette = widget.palette()
    background = _opaque_over(
        palette.color(QPalette.Highlight), palette.color(QPalette.Base)
    )
    foreground = readable_color(
        palette.color(QPalette.HighlightedText),
        background,
        palette.color(QPalette.Text),
        palette.color(QPalette.Base),
    )
    return foreground, background


def occurrence_colors(widget):
    """Follow syntax occurrence colors, falling back to the host selection."""
    occurrence = getattr(widget, "occurrence_color", None)
    background = QColor(occurrence) if occurrence is not None else QColor()
    if not background.isValid():
        return selection_colors(widget)
    palette = widget.palette()
    background = _opaque_over(background, palette.color(QPalette.Base))
    foreground = readable_color(
        palette.color(QPalette.Text),
        background,
        palette.color(QPalette.Base),
        palette.color(QPalette.HighlightedText),
    )
    return foreground, background
