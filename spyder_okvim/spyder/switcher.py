"""Vim navigation for Spyder's file and symbol switcher."""

# Standard Libraries
import sys
import weakref

# Third Party Libraries
from qtpy.QtCore import QCoreApplication, QEvent, QObject, Qt

# Project Libraries
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted


class SwitcherNavigation(QObject):
    """Attach navigation to a switcher without owning its lifetime."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._switcher = None

    def attach(self, switcher):
        """Follow one switcher, releasing any previous event filter."""
        if switcher is live_widget(self._switcher):
            return
        self.detach()
        if switcher is not None and not widget_is_deleted(switcher):
            self._switcher = weakref.ref(switcher)
            switcher.edit.installEventFilter(self)

    def detach(self):
        """Restore the switcher's own key handling; safe to repeat."""
        switcher = live_widget(self._switcher)
        self._switcher = None
        if switcher is not None and not widget_is_deleted(switcher.edit):
            switcher.edit.removeEventFilter(self)

    @staticmethod
    def _is_control_modifier(modifiers):
        """Accept physical Control under either macOS Qt key mapping."""
        if modifiers == Qt.ControlModifier:
            return True
        return (
            sys.platform == "darwin"
            and not QCoreApplication.testAttribute(Qt.AA_MacDontSwapCtrlAndMeta)
            and modifiers == Qt.MetaModifier
        )

    def eventFilter(self, watched, event):
        """Reserve Ctrl+P/N shortcuts and navigate once on the key press."""
        switcher = live_widget(self._switcher)
        if (
            event.type() not in (QEvent.ShortcutOverride, QEvent.KeyPress)
            or switcher is None
            or watched is not switcher.edit
            or not switcher.isVisible()
            or event.key() not in (Qt.Key_P, Qt.Key_N)
            or not self._is_control_modifier(event.modifiers())
        ):
            return super().eventFilter(watched, event)

        event.accept()
        if event.type() == QEvent.KeyPress and switcher.count():
            if event.key() == Qt.Key_P:
                switcher.previous_row()
            else:
                switcher.next_row()
        return True
