"""Resolve plugin colors from host roles, keeping small text readable."""

# Third Party Libraries
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QPalette


def interface_palette(widget):
    """Resolve UI roles from Spyder's theme rather than the native Qt palette.

    Spyder 6.1 styles its interface with QSS. On Windows a styled dialog can
    still expose native light Base/Text/Mid roles, so copying its palette into
    inputs or a custom delegate mixes light colors with the dark stylesheet.
    Keep this separate from editor palettes, which follow the syntax scheme.
    """
    # Third Party Libraries
    from spyder.utils.palette import SpyderPalette

    palette = QPalette(widget.palette())
    background = QColor(SpyderPalette.COLOR_BACKGROUND_1)
    foreground = readable_color(SpyderPalette.COLOR_TEXT_1, background)
    muted = readable_color(SpyderPalette.COLOR_TEXT_3, background, foreground)
    selection = QColor(SpyderPalette.COLOR_ACCENT_2)
    selected_text = readable_color(foreground, selection, background)
    roles = {
        QPalette.Window: background,
        QPalette.Base: background,
        QPalette.AlternateBase: QColor(SpyderPalette.COLOR_BACKGROUND_2),
        QPalette.Button: QColor(SpyderPalette.COLOR_BACKGROUND_2),
        QPalette.WindowText: foreground,
        QPalette.Text: foreground,
        QPalette.ButtonText: foreground,
        QPalette.PlaceholderText: muted,
        QPalette.Highlight: selection,
        QPalette.HighlightedText: selected_text,
        QPalette.Link: readable_color(
            SpyderPalette.COLOR_ACCENT_5, background, foreground
        ),
        QPalette.ToolTipBase: background,
        QPalette.ToolTipText: foreground,
        QPalette.Light: QColor(SpyderPalette.COLOR_BACKGROUND_3),
        QPalette.Midlight: QColor(SpyderPalette.COLOR_BACKGROUND_3),
        QPalette.Mid: QColor(SpyderPalette.COLOR_BACKGROUND_4),
        QPalette.Dark: QColor(SpyderPalette.COLOR_BACKGROUND_5),
        QPalette.Shadow: QColor(SpyderPalette.COLOR_BACKGROUND_6),
    }
    for role, color in roles.items():
        # Set Active, Inactive and Disabled so unfocused tool windows never
        # fall back to the platform's light selection or text colors.
        palette.setColor(role, color)
    disabled = readable_color(
        SpyderPalette.COLOR_DISABLED, background, muted, minimum_ratio=3.0
    )
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, disabled)
    return palette


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
