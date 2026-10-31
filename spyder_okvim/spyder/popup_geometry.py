"""Keep passive editor panels inside the viewport and clear of the cursor."""

# Third Party Libraries
from qtpy.QtCore import QRect


def popup_area(viewport):
    """Choose the larger space above or below the current editor line.

    All coordinates are viewport-local logical pixels, so Qt handles display
    scaling and moving an editor between screens. Plain QWidget hosts (used by
    previews and tests) can use their entire inner rectangle.
    """
    width, height = viewport.width(), viewport.height()
    margin = min(8, max(0, (min(width, height) - 1) // 2))
    area = QRect(
        margin, margin, max(1, width - 2 * margin), max(1, height - 2 * margin)
    )
    editor = viewport.parentWidget()
    cursor_rect = getattr(editor, "cursorRect", None)
    if cursor_rect is None:
        return area
    cursor = cursor_rect()
    if not area.intersects(cursor):
        return area
    gap = max(2, cursor.height() // 2)
    above = max(0, cursor.top() - gap - area.top())
    below = max(0, area.bottom() - cursor.bottom() - gap)
    # An exceptionally small viewport must still expose scrollable controls.
    if max(above, below) < 1:
        return area
    # Keep surrounding code and substitution previews visible even when a
    # long candidate list and field reference are displayed together.
    maximum_height = max(1, round(area.height() * 0.6))
    if above > below:
        area.setHeight(min(above, maximum_height))
    else:
        area.setTop(cursor.bottom() + gap + 1)
        if area.height() > maximum_height:
            area.setTop(area.bottom() - maximum_height + 1)
    return area
