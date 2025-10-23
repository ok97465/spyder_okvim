"""Qt compatibility helpers for cross-binding and Qt version differences."""


def exec_dialog(dialog):
    """Execute a modal dialog using the available Qt method."""
    exec_method = getattr(dialog, "exec_", None)
    if exec_method is None:
        exec_method = getattr(dialog, "exec", None)
    if exec_method is None:
        raise AttributeError("Dialog object has no exec or exec_ method.")
    return exec_method()


def text_width(metrics, text: str) -> int:
    """Return text width for both Qt5 and Qt6 font metrics APIs."""
    if hasattr(metrics, "horizontalAdvance"):
        return metrics.horizontalAdvance(text)
    return metrics.width(text)
