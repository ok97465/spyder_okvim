"""Safe references to widgets whose Qt ownership can outlive Python wrappers."""

# Standard Libraries
import weakref

# Third Party Libraries
from qtpy.QtCore import QCoreApplication, QEvent
from qtpy.QtWidgets import QWidget

# Project Libraries
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted


def test_live_widget_rejects_a_deleted_child_wrapper(qapp):
    parent = QWidget()
    child = QWidget(parent)
    reference = weakref.ref(child)
    assert live_widget(reference) is child
    assert not widget_is_deleted(child)

    # Qt deletes owned children even when Python still holds their wrappers.
    parent.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert reference() is child
    assert widget_is_deleted(child)
    assert live_widget(reference) is None
    assert live_widget(None) is None
