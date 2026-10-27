"""Qt compatibility helpers for cross-binding and Qt version differences."""

# Third Party Libraries
from qtpy import PYQT6, PYSIDE2, PYSIDE6


if PYSIDE2 or PYSIDE6:
    try:
        if PYSIDE6:
            from shiboken6 import isValid as _is_valid
        else:
            from shiboken2 import isValid as _is_valid
    except ImportError:  # pragma: no cover - optional binding internals
        _is_valid = None

    def widget_is_deleted(widget):
        """Check the underlying C++ object without accessing the widget."""
        return _is_valid is not None and not _is_valid(widget)

else:
    try:
        if PYQT6:
            from PyQt6 import sip
        else:
            from PyQt5 import sip
    except ImportError:  # pragma: no cover - standalone sip on older bindings
        try:
            import sip
        except ImportError:
            sip = None

    def widget_is_deleted(widget):
        """Check the underlying C++ object without accessing the widget."""
        return sip is not None and sip.isdeleted(widget)


def live_widget(reference):
    """Dereference a weak Qt widget reference only while its C++ object lives."""
    widget = reference() if reference is not None else None
    if widget is not None and not widget_is_deleted(widget):
        return widget
    return None


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
