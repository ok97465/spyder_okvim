"""Directional pane navigation uses layout geometry within the active window."""

# Standard Libraries
from types import SimpleNamespace

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent
from qtpy.QtWidgets import QApplication, QLineEdit, QWidget

# Project Libraries
from spyder_okvim.utils.editor_windows import focus_neighbor


class _Stack(QWidget):
    """Supply an editor in a lightweight pane with real Qt geometry and focus."""

    def __init__(self, host, geometry):
        super().__init__(host)
        self.setGeometry(*geometry)
        self.editor = QLineEdit(self)
        self.editor.setGeometry(0, 0, 100, 30)
        self.show()

    def get_current_editor(self):
        return self.editor


@pytest.fixture
def panes(qtbot):
    host = QWidget()
    host.resize(900, 850)
    qtbot.addWidget(host)
    commandline = QLineEdit(host)
    commandline.setGeometry(0, 800, 300, 30)
    stacks = []

    def add(geometry, parent=host):
        stack = _Stack(parent, geometry)
        stacks.append(stack)
        return stack

    def status(current):
        selected = []

        def restore_vim_input():
            selected.append(QApplication.focusWidget())
            commandline.setFocus()

        host.show()
        host.activateWindow()
        commandline.setFocus()
        QApplication.processEvents()
        return SimpleNamespace(
            get_editorstack=lambda: current,
            editor_widget=SimpleNamespace(
                get_widget=lambda: SimpleNamespace(editorstacks=stacks)
            ),
            set_focus_to_vim=restore_vim_input,
            selected=selected,
        )

    return SimpleNamespace(
        host=host, commandline=commandline, stacks=stacks, add=add, status=status
    )


@pytest.mark.parametrize("direction", ["h", "j", "k", "l"])
def test_focus_neighbor_in_each_direction(panes, direction):
    current = panes.add((200, 200, 150, 150))
    neighbors = {
        "h": panes.add((0, 200, 150, 150)),
        "j": panes.add((200, 400, 150, 150)),
        "k": panes.add((200, 0, 150, 150)),
        "l": panes.add((400, 200, 150, 150)),
    }
    status = panes.status(current)

    assert focus_neighbor(status, direction)

    assert status.selected == [neighbors[direction].editor]
    assert QApplication.focusWidget() is panes.commandline


def test_nested_layout_prefers_adjacent_aligned_pane(panes):
    current = panes.add((0, 0, 200, 300))
    panes.add((600, 0, 200, 300))  # Registered first, but farther to the right.
    panes.add((210, 310, 200, 300))  # Similar gap, but no vertical overlap.
    panes.add((210, 0, 200, 100))
    aligned = panes.add((210, 100, 200, 200))
    status = panes.status(current)

    assert focus_neighbor(status, "l")

    assert status.selected == [aligned.editor]


def test_neighbor_ignores_unavailable_panes_and_other_windows(panes, qtbot):
    current = panes.add((0, 0, 200, 300))
    hidden = panes.add((210, 0, 100, 300))
    hidden.hide()
    empty = panes.add((210, 0, 100, 300))
    empty.editor.deleteLater()
    empty.editor = None
    deleted = panes.add((210, 0, 100, 300))
    deleted.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    other_window = QWidget()
    other_window.resize(900, 850)
    qtbot.addWidget(other_window)
    panes.add((210, 0, 100, 300), parent=other_window)
    other_window.show()
    available = panes.add((400, 0, 200, 300))
    status = panes.status(current)

    assert focus_neighbor(status, "l")

    assert status.selected == [available.editor]


def test_edge_does_not_wrap_to_opposite_pane(panes):
    current = panes.add((0, 0, 200, 300))
    panes.add((210, 0, 200, 300))
    status = panes.status(current)

    assert not focus_neighbor(status, "h")

    assert status.selected == []
    assert QApplication.focusWidget() is panes.commandline


@pytest.mark.parametrize("direction", ["h", "j", "k", "l"])
def test_t_layout_does_not_move_sideways_into_a_staggered_pane(panes, direction):
    if direction in ("j", "k"):
        current = panes.add((0, 0, 200, 600))
        panes.add((210, 0, 200, 290))
        panes.add((210, 310, 200, 290))
    else:
        current = panes.add((0, 0, 600, 200))
        panes.add((0, 210, 290, 200))
        panes.add((310, 210, 290, 200))
    status = panes.status(current)

    assert not focus_neighbor(status, direction)

    assert status.selected == []
    assert QApplication.focusWidget() is panes.commandline


@pytest.mark.parametrize("direction", ["j", "l"])
def test_diagonal_pane_is_not_a_directional_neighbor(panes, direction):
    current = panes.add((0, 0, 200, 200))
    panes.add((210, 210, 200, 200))
    status = panes.status(current)

    assert not focus_neighbor(status, direction)

    assert status.selected == []
