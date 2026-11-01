"""Navigate live editor panes and retain per-window focus history."""

# Standard Libraries
import weakref

# Third Party Libraries
from qtpy.QtCore import QPoint, QRect
from qtpy.QtWidgets import QSplitter

# Project Libraries
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted


def remember_pane(vim_status, stack):
    """Record focus changes without keeping closed panes or windows alive."""
    if stack is None or widget_is_deleted(stack):
        return
    history = vim_status.pane_history.setdefault(stack.window(), [])
    history[:] = [
        reference
        for reference in history
        if live_widget(reference) is not None and reference() is not stack
    ]
    history.append(weakref.ref(stack))


def _splitter_path(pane):
    """Return child indices from the root splitter to this pane."""
    path = []
    parent = pane.parentWidget()
    while parent is not None:
        if isinstance(parent, QSplitter):
            path.append(parent.indexOf(pane))
        pane, parent = parent, parent.parentWidget()
    return tuple(reversed(path))


def _visible_panes(vim_status):
    """List usable panes within the active window."""
    current = vim_status.get_editorstack()
    if current is None or widget_is_deleted(current) or not current.isVisible():
        return []
    host = current.window()
    widget = vim_status.editor_widget.get_widget()
    panes = []
    for stack in getattr(widget, "editorstacks", ()):
        if (
            stack is None
            or widget_is_deleted(stack)
            or not stack.isVisible()
            or stack.window() is not host
        ):
            continue
        editor = stack.get_current_editor()
        if editor is not None and not widget_is_deleted(editor):
            panes.append(stack)
    return panes


def _focus_pane(vim_status, stack):
    """Select a usable pane and restore Vim input after the host rebinds it."""
    remember_pane(vim_status, vim_status.get_editorstack())
    stack.get_current_editor().setFocus()
    remember_pane(vim_status, stack)
    vim_status.set_focus_to_vim()
    return True


def focus_cycle(vim_status, number=None):
    """Cycle to the next split, or select a one-based split number with a count."""
    panes = _visible_panes(vim_status)
    current = vim_status.get_editorstack()
    if current not in panes:
        return False
    panes.sort(key=_splitter_path)
    index = (
        (panes.index(current) + 1) % len(panes)
        if number is None
        else min(max(number, 1), len(panes)) - 1
    )
    if panes[index] is current:
        return False
    return _focus_pane(vim_status, panes[index])


def focus_previous(vim_status):
    """Return to the previous available split in this host, without crossing windows."""
    panes = _visible_panes(vim_status)
    current = vim_status.get_editorstack()
    if current not in panes:
        return False
    for reference in reversed(vim_status.pane_history.get(current.window(), ())):
        target = live_widget(reference)
        if target is not current and target in panes:
            return _focus_pane(vim_status, target)
    return False


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

    panes = _visible_panes(vim_status)
    current = vim_status.get_editorstack()
    if not panes:
        return False
    host = current.window()
    source_rect = QRect(current.mapTo(host, QPoint()), current.size())
    best_score = None
    target_stack = None
    for stack in panes:
        if stack is current:
            continue
        rect = QRect(stack.mapTo(host, QPoint()), stack.size())
        score = _neighbor_score(source_rect, rect, direction)
        if score is not None and (best_score is None or score < best_score):
            best_score = score
            target_stack = stack

    if target_stack is None:
        return False
    return _focus_pane(vim_status, target_stack)
