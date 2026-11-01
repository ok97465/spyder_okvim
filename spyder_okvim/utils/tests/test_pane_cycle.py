"""Split cycling and previous focus stay local to live panes in one window."""

# Standard Libraries
import weakref
from types import SimpleNamespace

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtWidgets import QApplication, QLineEdit, QSplitter, QWidget

# Project Libraries
from spyder_okvim.utils.editor_windows import (
    focus_cycle,
    focus_neighbor,
    focus_previous,
    remember_pane,
)


class _Stack(QWidget):
    def __init__(self, host, geometry):
        super().__init__(host)
        self.setGeometry(*geometry)
        self.editor = QLineEdit(self)
        self.editor.resize(100, 25)
        self.show()

    def get_current_editor(self):
        return self.editor


@pytest.fixture
def cycle_panes(qtbot):
    host = QWidget()
    host.resize(700, 500)
    qtbot.addWidget(host)
    line = QLineEdit(host)
    line.setGeometry(0, 450, 300, 25)
    root = QSplitter(Qt.Horizontal, host)
    root.setGeometry(0, 0, 650, 420)
    first = _Stack(root, (0, 0, 300, 400))
    right = QSplitter(Qt.Vertical, root)
    second = _Stack(right, (0, 0, 300, 200))
    third = _Stack(right, (0, 0, 300, 200))
    root.setSizes([300, 300])
    right.setSizes([210, 200])
    # Registration order deliberately differs from splitter order.
    stacks = [third, first, second]
    state = SimpleNamespace(current=first, selected=[], stacks=stacks)

    def restore_input():
        focused = QApplication.focusWidget()
        for stack in stacks:
            if stack.editor is focused:
                state.current = stack
                state.selected.append(stack)
                remember_pane(state.status, stack)
                break
        line.setFocus()

    state.status = SimpleNamespace(
        get_editorstack=lambda: state.current,
        editor_widget=SimpleNamespace(
            get_widget=lambda: SimpleNamespace(editorstacks=stacks)
        ),
        pane_history=weakref.WeakKeyDictionary(),
        set_focus_to_vim=restore_input,
    )
    state.first, state.second, state.third = first, second, third
    state.host, state.line, state.root = host, line, root
    remember_pane(state.status, first)
    host.show()
    host.activateWindow()
    line.setFocus()
    QApplication.processEvents()
    return state


def test_cycle_uses_splitter_order_and_wraps(cycle_panes):
    state = cycle_panes
    for expected in (state.second, state.third, state.first):
        assert focus_cycle(state.status)
        assert state.current is expected
        assert QApplication.focusWidget() is state.line


def test_cycle_keeps_mirrored_t_branches_together(cycle_panes):
    state = cycle_panes
    root = QSplitter(Qt.Horizontal, state.host)
    root.setGeometry(0, 0, 650, 420)
    left = QSplitter(Qt.Vertical, root)
    left.addWidget(state.first)
    left.addWidget(state.second)
    root.addWidget(state.third)
    state.root.hide()
    root.show()
    root.setSizes([300, 300])
    left.setSizes([200, 200])
    QApplication.processEvents()

    for expected in (state.second, state.third, state.first):
        assert focus_cycle(state.status)
        assert state.current is expected


def test_cycle_follows_real_splitter_tree_for_grid(cycle_panes):
    state = cycle_panes
    for stack in state.stacks:
        stack.hide()
    root = QSplitter(Qt.Vertical, state.host)
    root.setGeometry(0, 0, 650, 420)
    top = QSplitter(Qt.Horizontal, root)
    bottom = QSplitter(Qt.Horizontal, root)
    top_left = _Stack(top, (0, 0, 200, 200))
    top_right = _Stack(top, (0, 0, 200, 200))
    bottom_left = _Stack(bottom, (0, 0, 200, 200))
    bottom_right = _Stack(bottom, (0, 0, 200, 200))
    panes = [top_left, top_right, bottom_left, bottom_right]
    state.stacks[:] = list(reversed(panes))
    state.current = top_left
    remember_pane(state.status, top_left)
    root.show()
    root.setSizes([210, 210])
    top.setSizes([325, 325])
    bottom.setSizes([325, 325])
    QApplication.processEvents()

    for expected in (top_right, bottom_left, bottom_right, top_left):
        assert focus_cycle(state.status)
        assert state.current is expected


def test_count_selects_absolute_pane_and_clamps(cycle_panes):
    state = cycle_panes
    assert focus_cycle(state.status, 3)
    assert state.current is state.third
    assert focus_cycle(state.status, 1)
    assert state.current is state.first
    assert focus_cycle(state.status, 100)
    assert state.current is state.third
    assert not focus_cycle(state.status, 3)


def test_previous_toggles_and_remembers_directional_focus(cycle_panes):
    state = cycle_panes
    assert not focus_previous(state.status)
    assert focus_neighbor(state.status, "l")
    assert state.current is state.second
    for expected in (state.first, state.second, state.first):
        assert focus_previous(state.status)
        assert state.current is expected


def test_previous_observes_host_focus_and_same_stack_rebinding(cycle_panes):
    state = cycle_panes
    # The plugin calls remember for mouse/editor focus as well as Vim commands.
    remember_pane(state.status, state.second)
    state.current = state.second
    remember_pane(state.status, state.second)
    assert focus_previous(state.status)
    assert state.current is state.first


def test_cycle_excludes_hidden_empty_deleted_and_other_windows(cycle_panes, qtbot):
    state = cycle_panes
    state.second.hide()
    empty = _Stack(state.host, (0, 0, 100, 100))
    empty.editor.deleteLater()
    empty.editor = None
    deleted = _Stack(state.host, (0, 0, 100, 100))
    deleted.deleteLater()
    other_host = QWidget()
    qtbot.addWidget(other_host)
    other = _Stack(other_host, (0, 0, 100, 100))
    other_host.show()
    state.stacks.extend((empty, deleted, other))
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    state.host.activateWindow()
    state.line.setFocus()
    QApplication.processEvents()

    assert focus_cycle(state.status)
    assert state.current is state.third
    assert focus_cycle(state.status)
    assert state.current is state.first


def test_previous_skips_closed_panes(cycle_panes):
    state = cycle_panes
    assert focus_cycle(state.status)
    assert focus_cycle(state.status)
    state.second.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    assert focus_previous(state.status)
    assert state.current is state.first
    assert focus_previous(state.status)
    assert state.current is state.third


def test_previous_history_does_not_cross_host_windows(cycle_panes, qtbot):
    state = cycle_panes
    other_host = QWidget()
    qtbot.addWidget(other_host)
    other = _Stack(other_host, (0, 0, 100, 100))
    other_host.show()
    remember_pane(state.status, other)
    state.stacks.append(other)

    assert not focus_previous(state.status)
    state.third.hide()
    state.second.hide()
    assert not focus_cycle(state.status)
    assert state.current is state.first
