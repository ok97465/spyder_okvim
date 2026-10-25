"""Editor undocking keeps Vim input in the active window without accumulation."""

# Standard Libraries
import gc
import weakref

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, QTimer, Qt
from qtpy.QtWidgets import QApplication, QMainWindow, QShortcut

# Project Libraries
from spyder_okvim.spyder.plugin import StatusBarVimWidget
from spyder_okvim.spyder.vim_widgets import _widget_is_deleted


def _process_events():
    """Include deferred deletion so closed windows cannot mask an ownership leak."""
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()


@pytest.fixture
def undock_bot(vim_bot):
    """Preserve the session editor and exercise real Qt input/focus handling."""
    main, stack, _, vim, qtbot = vim_bot
    previous_index = stack.get_stack_index()
    stack.set_stack_index(0)
    editor = stack.get_current_editor()
    original_text = editor.toPlainText()
    commandline = vim.vim_cmd.commandline
    status = vim.vim_cmd.vim_status
    status.reset_for_test()
    _process_events()
    status_widget = commandline.parentWidget()
    assert isinstance(status_widget, StatusBarVimWidget)
    original_parent = status_widget.parentWidget()

    def dock():
        main.layout().insertWidget(0, main.editor)
        main.editor.show()
        _process_events()

    try:
        yield main, stack, editor, vim, qtbot, status_widget, dock
    finally:
        dock()
        commandline.esc_pressed()
        status.finish_insert(apply_count=False)
        status.disconnect_from_editor()
        editor.set_text(original_text)
        stack.set_stack_index(previous_index)
        main.show()
        main.activateWindow()
        commandline.setFocus()
        _process_events()
        assert status_widget.parentWidget() is original_parent


def _exercise_vim(main, editor, vim, qtbot, window):
    """Use the focused widget, including the Editor -> Esc -> commandline path."""
    status = vim.vim_cmd.vim_status
    commandline = vim.vim_cmd.commandline
    original = "alpha beta\nsecond line\nthird alpha\n"
    commandline.esc_pressed()
    editor.set_text(original)
    status.cursor.set_cursor_pos(0)
    window.show()
    window.activateWindow()
    _process_events()
    editor.setFocus()
    _process_events()
    assert QApplication.focusWidget() is editor
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key_Escape)
    _process_events()
    assert QApplication.focusWidget() is commandline
    assert commandline.window() is editor.window()
    assert vim.vim_cmd.status_label.text() == "NORMAL"

    def keys(text):
        qtbot.keyClicks(QApplication.focusWidget(), text)
        _process_events()

    keys("jlkh")
    assert editor.textCursor().position() == 0
    assert editor.toPlainText() == original

    keys("i")
    assert QApplication.focusWidget() is editor
    keys("X")
    assert editor.toPlainText() == "X" + original
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key_Escape)
    _process_events()
    assert QApplication.focusWidget() is commandline
    keys("u")
    assert editor.toPlainText() == original

    status.cursor.set_cursor_pos(0)
    keys("x")
    assert editor.toPlainText() == original[1:]
    keys("u")
    assert editor.toPlainText() == original

    status.cursor.set_cursor_pos(0)
    keys("vl")
    assert vim.vim_cmd.status_label.text() == "VISUAL"
    selection = editor.get_extra_selections("vim_selection")
    assert len(selection) == 1
    assert selection[0].cursor.selectedText() == "al"
    keys("y")
    assert vim.vim_cmd.status_label.text() == "NORMAL"

    keys("/alpha")
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key_Return)
    _process_events()
    assert editor.textCursor().position() == original.rfind("alpha")
    assert commandline.text() == ""

    keys(":2")
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key_Return)
    _process_events()
    assert editor.textCursor().blockNumber() == 1
    assert status.sub_mode is None
    assert editor.toPlainText() == original


@pytest.mark.parametrize("close_to_dock", [False, True])
def test_repeated_undock_dock_vim_and_widget_lifetime(undock_bot, close_to_dock):
    """Repeated reparenting preserves Vim behavior and releases every old window."""
    main, stack, editor, vim, qtbot, status_widget, dock = undock_bot
    commandline = vim.vim_cmd.commandline
    status = vim.vim_cmd.vim_status
    ui = (commandline, vim.vim_cmd.msg_label, vim.vim_cmd.status_label)
    shortcuts = tuple(stack.findChildren(QShortcut))
    timers = tuple(status.findChildren(QTimer))
    status_widgets = {
        id(widget)
        for widget in QApplication.allWidgets()
        if isinstance(widget, StatusBarVimWidget)
    }
    destroyed = []
    window_refs = []

    class DockingWindow(QMainWindow):
        def closeEvent(self, event):
            super().closeEvent(event)
            if close_to_dock:
                dock()

    for cycle in range(30):
        floating = DockingWindow()
        floating.setAttribute(Qt.WA_DeleteOnClose)
        floating.destroyed.connect(lambda: destroyed.append(True))
        window_refs.append(weakref.ref(floating))
        floating.setCentralWidget(main.editor)
        _process_events()
        try:
            assert status_widget.window() is floating
            assert ui == (
                vim.vim_cmd.commandline,
                vim.vim_cmd.msg_label,
                vim.vim_cmd.status_label,
            )
            _exercise_vim(main, editor, vim, qtbot, floating)

            # Spyder's window-close signal docks the same Editor widget before
            # the delete-on-close window is destroyed. Exercise that ordering too.
            if close_to_dock:
                floating.close()
            else:
                dock()
                floating.close()
            _process_events()
            assert _widget_is_deleted(floating)
            assert not _widget_is_deleted(commandline)
            assert status_widget.window() is main
            _exercise_vim(main, editor, vim, qtbot, main)
            assert tuple(stack.findChildren(QShortcut)) == shortcuts
            assert tuple(status.findChildren(QTimer)) == timers
            assert {
                id(widget)
                for widget in QApplication.allWidgets()
                if isinstance(widget, StatusBarVimWidget)
            } == status_widgets
        finally:
            dock()
            if not _widget_is_deleted(floating):
                floating.close()
                floating.deleteLater()
                _process_events()
        del floating

    gc.collect()
    assert len(destroyed) == 30
    assert all(ref() is None for ref in window_refs)


def test_inline_hints_follow_the_undocked_editor(undock_bot):
    """Leap labels stay on the editor's window after docking in either direction."""
    main, _, editor, vim, _, _, dock = undock_bot
    status = vim.vim_cmd.vim_status
    floating = QMainWindow()
    try:
        for window in (floating, main, floating, main):
            if window is floating:
                floating.setCentralWidget(main.editor)
            else:
                dock()
            window.show()
            _process_events()
            editor.set_text("alpha beta\nsecond line\n")
            labels = status.labels_for_annotate[:2]
            assert all(label.window() is editor.window() for label in labels)
            status.annotate_on_txt({0: "a", 6: "b"})
            _process_events()
            assert all(label.window() is editor.window() for label in labels)
            assert all(label.isVisible() for label in labels)
            status.hide_annotate_on_txt()
    finally:
        dock()
        floating.close()
        floating.deleteLater()
        _process_events()
