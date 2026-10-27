"""Overflow hint menus keep every row reachable without taking focus."""

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QPoint, QRect, Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QAbstractScrollArea, QScrollArea, QWidget

# Project Libraries
from spyder_okvim.spyder.which_key_popup import WhichKeyPopup


@pytest.fixture
def popup(qtbot):
    viewport = QWidget()
    viewport.resize(360, 220)
    qtbot.addWidget(viewport)
    viewport.show()
    panel = WhichKeyPopup(viewport)
    panel.refresh_appearance(QFont("Courier New", 10))
    return viewport, panel


def _show_many_candidates(panel):
    panel.set_candidates(
        '"',
        [
            (str(index), f"Register {index}: saved content preview")
            for index in range(60)
        ],
    )
    panel.update_geometry()
    panel.show()
    QCoreApplication.processEvents()


def test_overflow_scrolls_to_the_last_wrapped_candidate(popup):
    viewport, panel = popup
    _show_many_candidates(panel)
    scroll = panel.findChild(QScrollArea)
    assert scroll is not None
    assert viewport.rect().contains(panel.geometry())
    assert scroll.verticalScrollBar().maximum() > 0
    for widget in (
        panel,
        scroll,
        scroll.viewport(),
        scroll.verticalScrollBar(),
        scroll.horizontalScrollBar(),
    ):
        assert widget.focusPolicy() == Qt.NoFocus

    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    QCoreApplication.processEvents()
    label = panel.candidate_labels[-1][1]
    bounds = QRect(label.mapTo(scroll.viewport(), QPoint(0, 0)), label.size())
    assert scroll.viewport().rect().contains(bounds)
    assert label.height() >= label.heightForWidth(label.width())


def test_small_menu_releases_the_overflow_surface(popup):
    viewport, panel = popup
    _show_many_candidates(panel)
    panel.set_candidates("g", [("g", "Go to line"), ("d", "Go to definition")])
    panel.update_geometry()
    QCoreApplication.processEvents()

    assert not panel.findChildren(QAbstractScrollArea)
    assert panel.body.parentWidget() is panel
    assert viewport.rect().contains(panel.geometry())
    for labels in panel.candidate_labels:
        for label in labels:
            bounds = QRect(label.mapTo(panel, QPoint(0, 0)), label.size())
            assert panel.contentsRect().contains(bounds)
    assert panel.height() < viewport.height() // 2


def test_resizing_restores_scrollable_and_compact_layouts(popup):
    viewport, panel = popup
    panel.set_candidates(
        '"',
        [(str(index), f"Register {index}: content preview") for index in range(14)],
    )
    for height in (600, 120, 600, 120):
        viewport.resize(360, height)
        panel.update_geometry()
        panel.show()
        QCoreApplication.processEvents()
        assert viewport.rect().contains(panel.geometry())
        scroll = panel.findChild(QScrollArea)
        if height == 600:
            assert scroll is None
            continue
        assert scroll is not None
        scrollbar = scroll.verticalScrollBar()
        assert scrollbar.maximum() > 0
        scrollbar.setValue(scrollbar.maximum())
        QCoreApplication.processEvents()
        last_description = panel.candidate_labels[-1][1]
        bounds = QRect(
            last_description.mapTo(scroll.viewport(), QPoint(0, 0)),
            last_description.size(),
        )
        assert scroll.viewport().rect().contains(bounds)
