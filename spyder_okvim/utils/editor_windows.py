"""Move Vim input between neighboring editor panes."""

# Third Party Libraries
from qtpy.QtCore import QPoint, QRect

# Project Libraries
from spyder_okvim.utils.qtcompat import widget_is_deleted


def _neighbor_score(source, target, direction):
    """Rank panes beyond the requested edge by distance and center alignment."""
    horizontal = direction in ("h", "l")
    if horizontal:
        start, end = source.left(), source.right() + 1
        other_start, other_end = target.left(), target.right() + 1
        cross_start, cross_end = source.top(), source.bottom() + 1
        other_cross_start, other_cross_end = target.top(), target.bottom() + 1
    else:
        start, end = source.top(), source.bottom() + 1
        other_start, other_end = target.top(), target.bottom() + 1
        cross_start, cross_end = source.left(), source.right() + 1
        other_cross_start, other_cross_end = target.left(), target.right() + 1

    forward = direction in ("j", "l")
    gap = other_start - end if forward else start - other_end
    overlap = min(cross_end, other_cross_end) - max(cross_start, other_cross_start)
    if gap < 0 or overlap <= 0:
        return None
    alignment = abs(other_cross_start + other_cross_end - cross_start - cross_end)
    return gap, alignment


def focus_neighbor(vim_status, direction: str) -> bool:
    """Focus a visible neighboring pane in the same window, without wrapping.

    Only panes beyond the requested edge with perpendicular overlap qualify.
    Nearer panes win, with center alignment breaking ties in nested splits.
    Return whether a target was found, restoring Vim input after selecting it.
    """
    if direction not in ("h", "j", "k", "l"):
        raise ValueError(f"Unknown editor direction: {direction!r}")

    current = vim_status.get_editorstack()
    if current is None or widget_is_deleted(current) or not current.isVisible():
        return False
    host = current.window()
    source_rect = QRect(current.mapTo(host, QPoint()), current.size())
    widget = vim_status.editor_widget.get_widget()
    best_score = None
    target_editor = None
    for stack in getattr(widget, "editorstacks", ()):
        if (
            stack is None
            or stack is current
            or widget_is_deleted(stack)
            or not stack.isVisible()
            or stack.window() is not host
        ):
            continue
        editor = stack.get_current_editor()
        if editor is None or widget_is_deleted(editor):
            continue
        rect = QRect(stack.mapTo(host, QPoint()), stack.size())
        score = _neighbor_score(source_rect, rect, direction)
        if score is not None and (best_score is None or score < best_score):
            best_score = score
            target_editor = editor

    if target_editor is None:
        return False
    target_editor.setFocus()
    vim_status.set_focus_to_vim()
    return True
