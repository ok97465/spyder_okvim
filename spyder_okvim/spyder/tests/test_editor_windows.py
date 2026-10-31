"""Opt-in integration with the paired Spyder fork's real editor windows."""

# Standard Libraries
import gc
import os
import weakref
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QApplication, QMainWindow, QShortcut
from spyder.api.plugins import Plugins
from spyder.config.manager import CONF
from spyder.plugins.editor.plugin import Editor
from spyder.plugins.outlineexplorer.plugin import OutlineExplorer

# Project Libraries
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION
from spyder_okvim.spyder.plugin import OkVim, StatusBarVimWidget
from spyder_okvim.utils.qtcompat import widget_is_deleted
from tests.qt_support import reset_vim_state

pytestmark = pytest.mark.skipif(
    os.environ.get("SPYDER_OKVIM_WINDOW_INTEGRATION") != "1",
    reason="Set SPYDER_OKVIM_WINDOW_INTEGRATION=1 with the paired Spyder fork",
)


def _settle():
    QApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()


class _MainWindow(QMainWindow):
    """Supply only the outer app services missing from an Editor test."""

    is_window_widget = False
    CONF_SECTION = None
    PLUGIN_NAME = None

    def __getattr__(self, name):
        return [] if name.endswith("actions") else Mock()


class _StatusBarPlugin:
    def __init__(self, main):
        self.main = main
        self.STATUS_WIDGETS = {}

    def add_status_widget(self, widget):
        self.STATUS_WIDGETS[widget.ID] = widget
        self.main.statusBar().insertPermanentWidget(0, widget)


class _TestVim(OkVim):
    CONF_FILE = False


@pytest.fixture
def editor_windows(qtbot, tmp_path, vim_bot):
    """Use the real Editor, its dock and New-window widgets, with local files."""
    main = _MainWindow()
    editor = Editor(main, CONF)
    editor.on_initialize()
    editor.update_font()
    outline = OutlineExplorer(main, CONF)
    outline.on_initialize()
    statusbar = _StatusBarPlugin(main)
    services = {
        Plugins.Editor: editor,
        Plugins.OutlineExplorer: outline,
        Plugins.StatusBar: statusbar,
        Plugins.Application: Mock(),
    }

    def get_plugin(name, error=True):
        if name in (Plugins.IPythonConsole, Plugins.Projects, Plugins.Debugger):
            return None
        return services.get(name, Mock())

    main.get_plugin = get_plugin
    main.editor = editor
    main.status_bar = statusbar
    editor.on_outlineexplorer_available()
    widget = editor.get_widget()
    dock, area = editor.create_dockwidget(main)
    main.addDockWidget(area, dock)
    widget.sig_update_ancestor_requested.connect(lambda: widget.set_ancestor(main))
    widget.autosave.stop_autosave_timer()
    # Cursor history is independent of routing and deliberately retains every
    # navigation during stress tests; keep allocation checks about window UI.
    widget._EditorMainWidget__ignore_cursor_history = True
    for section, options in CONF_DEFAULTS:
        for key, value in options.items():
            CONF.set(section, key, value)
    CONF.set(CONF_SECTION, "highlight_yank_duration", 0)
    CONF.set(CONF_SECTION, "which_key_enabled", False)
    vim = _TestVim(main, CONF)
    main.spyder_okvim = vim
    vim.on_initialize()
    for name in ("first.py", "second.py"):
        editor.new(fname=str(tmp_path / name), text="alpha beta\nsecond line\n")
    main.resize(1100, 700)
    main.show()
    widget.set_ancestor(main)
    _settle()
    state = SimpleNamespace(
        main=main,
        editor=editor,
        widget=widget,
        vim=vim,
        qtbot=qtbot,
        commandline=vim.vim_cmd.commandline,
        vim_closed=False,
    )
    try:
        yield state
    finally:
        # Stop routing before destroying the remaining stacks and window UI.
        if widget.windowwidget is not None:
            widget.dock_window()
        for window in list(widget.editorwindows):
            if not widget_is_deleted(window):
                window.close()
        _settle()
        if not state.vim_closed:
            vim.on_close()
            _settle()
        editor.on_close()
        main.close()
        main.deleteLater()
        _settle()
        session_main, _, _, session_vim, _ = vim_bot
        session_main.show()
        session_main.activateWindow()
        session_vim.vim_cmd.commandline.setFocus()
        _settle()


def _focus_stack(state, stack):
    code = stack.get_current_editor()
    host = code.window()
    host.show()
    host.activateWindow()
    _settle()
    code.setFocus()
    _settle()
    assert QApplication.focusWidget() is code
    state.qtbot.keyClick(code, Qt.Key_Escape)
    _settle()
    assert QApplication.focusWidget() is state.commandline
    assert state.commandline.window() is host
    assert state.vim.vim_cmd.vim_status.get_editor() is code
    return code


def _exercise_vim(state, stack):
    """Check routing using real focus and key events, including editor input."""
    code = _focus_stack(state, stack)
    status = state.vim.vim_cmd.vim_status
    state.commandline.esc_pressed()
    original = "alpha beta\nsecond line\nthird alpha\n"
    code.set_text(original)
    status.cursor.set_cursor_pos(0)

    def keys(text):
        state.qtbot.keyClicks(QApplication.focusWidget(), text)
        _settle()

    keys("jlkh")
    assert code.textCursor().position() == 0
    keys("i")
    assert QApplication.focusWidget() is code
    keys("X")
    assert code.toPlainText() == "X" + original
    state.qtbot.keyClick(code, Qt.Key_Escape)
    _settle()
    assert QApplication.focusWidget() is state.commandline
    keys("u")
    assert code.toPlainText() == original
    keys("x")
    assert code.toPlainText() == original[1:]
    keys("u")
    assert code.toPlainText() == original
    keys("vly")
    assert state.vim.vim_cmd.status_label.text() == "NORMAL"
    keys("/alpha")
    state.qtbot.keyClick(state.commandline, Qt.Key_Return)
    _settle()
    assert code.textCursor().position() == original.rfind("alpha")
    keys(":2")
    state.qtbot.keyClick(state.commandline, Qt.Key_Return)
    _settle()
    assert code.textCursor().blockNumber() == 1
    # Check parent ancestry before mapTo so a routing regression reports a
    # useful assertion instead of crashing Qt with unrelated widget parents.
    assert all(label.window() is code.window() for label in status.labels_for_annotate)
    status.annotate_on_txt({0: "a", 6: "b"})
    status.hide_annotate_on_txt()


def test_substitute_overlay_is_released_when_editor_window_changes(editor_windows):
    """A painted preview cannot follow the shared prompt into another window."""
    state = editor_windows
    preview = state.vim.vim_cmd.substitute_preview
    window = state.widget.create_new_window()
    _settle()
    source_stack = state.widget.editorstacks[0]
    target_stack = window.editorwidget.editorstacks[0]
    source_stack.set_stack_index(0)
    target_stack.set_stack_index(1)
    source = _focus_stack(state, source_stack)
    source.set_text("foo foo\n")
    state.vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    state.qtbot.keyClicks(state.commandline, ":%s/foo/bar/g")
    state.qtbot.waitUntil(lambda: preview.result is not None)
    assert [row.after for row in preview.overlay.rows] == ["bar bar"]
    previous = preview.overlay.widget
    assert previous.isVisible()

    target = _focus_stack(state, target_stack)
    _settle()
    assert preview.result is None
    assert preview.overlay.rows == ()
    assert widget_is_deleted(previous)
    assert preview.overlay.widget.parentWidget() is target.viewport()
    assert source.toPlainText() == "foo foo\n"

    target.set_text("foo target\n")
    state.vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    state.qtbot.keyClicks(state.commandline, ":%s/foo/new/g")
    state.qtbot.waitUntil(lambda: preview.result is not None)
    assert [row.after for row in preview.overlay.rows] == ["new target"]
    window.close()
    _settle()
    assert preview.result is None
    assert source.toPlainText() == "foo foo\n"


@pytest.mark.parametrize("host", ["main", "undocked", "window"])
def test_yanky_shared_history_and_view_lifetime(editor_windows, host):
    """Cycle and picker state belong to one view, including detached hosts."""
    # Project Libraries
    from spyder_okvim.vim.state import VimState

    state = editor_windows
    if host == "undocked":
        state.widget.create_window()
    elif host == "window":
        state.widget.create_new_window()
    _settle()
    stack = state.widget.editorstacks[-1]
    stack.sig_split_vertically.emit()
    _settle()
    clone = state.widget.editorstacks[-1]
    assert clone is not stack
    code = _focus_stack(state, stack)
    widget = state.vim.vim_cmd
    status = widget.vim_status
    reset_vim_state(status)
    code.set_text("xy")
    status.cursor.set_cursor_pos(0)
    entry = status.yank_history.record("A", "charwise")
    status.set_register('"', "B", VimState.NORMAL)
    state.qtbot.keyClicks(state.commandline, "p")
    assert widget.put_controller.can_cycle()
    state.vim._use_stack(stack)
    assert widget.put_controller.can_cycle()
    code.highlighter.rehighlight()
    _settle()
    assert widget.put_controller.can_cycle()

    # A shared-document edit can arrive from a split without changing focus.
    other = clone.get_current_editor()
    cursor = other.textCursor()
    cursor.movePosition(QTextCursor.End)
    cursor.insertText("external")
    assert not widget.put_controller.can_cycle()
    assert status.yank_history.snapshot() == (entry,)

    state.qtbot.keyClicks(state.commandline, "p")
    widget.show_yank_history()
    dialog = widget._yank_picker.dialog
    assert dialog.parentWidget() is code.window()
    state.qtbot.keyClick(dialog.list_viewer, Qt.Key_Return)
    _settle()
    assert widget.put_controller.can_cycle()
    _focus_stack(state, clone)
    assert not widget.put_controller.can_cycle()
    assert status.yank_history.snapshot() == (entry,)
    widget.show_yank_history()
    request = widget._yank_picker
    popup = request.dialog
    before = other.toPlainText()
    _focus_stack(state, stack)
    assert widget._yank_picker is None
    assert widget_is_deleted(popup) or not popup.isVisible()
    assert other.toPlainText() == before


@pytest.mark.parametrize(
    "host, command", [("main", "vs"), ("undocked", "vsp"), ("window", "vsplit")]
)
def test_vsplit_uses_active_pane(editor_windows, host, command):
    """Split the current pane in each host, including an existing right pane."""
    state = editor_windows
    if host == "undocked":
        state.widget.create_window()
    elif host == "window":
        state.widget.create_new_window()
    _settle()
    stack = state.widget.editorstacks[-1]
    _focus_stack(state, stack)
    status = state.vim.vim_cmd.vim_status

    for index in range(2):
        stack.set_stack_index(index)
        _focus_stack(state, stack)
        status.cursor.set_cursor_pos(2)
        parent = stack.parentWidget()
        previous_count = parent.count()
        previous_stacks = set(state.widget.editorstacks)
        filename = stack.get_current_filename()
        state.qtbot.keyClicks(state.commandline, ":" + command)
        state.qtbot.keyClick(state.commandline, Qt.Key_Return)
        _settle()

        added = set(state.widget.editorstacks) - previous_stacks
        assert len(added) == 1
        target = added.pop()
        assert parent.count() == previous_count + 1
        assert parent.orientation() == Qt.Horizontal
        assert target.window() is stack.window()
        assert target.get_current_filename() == filename
        assert target.get_current_editor().textCursor().position() == 2
        assert status.get_editorstack() is target
        assert status.is_normal()
        assert state.commandline.hasFocus()
        assert state.commandline.text() == ""
        stack = target


def test_control_w_navigates_nested_splits(editor_windows):
    """Direction keys switch panes, stop at edges, and keep Normal input."""
    state = editor_windows
    left = state.widget.editorstacks[0]
    _focus_stack(state, left)
    state.qtbot.keyClicks(state.commandline, ":vs")
    state.qtbot.keyClick(state.commandline, Qt.Key_Return)
    _settle()
    status = state.vim.vim_cmd.vim_status
    upper_right = status.get_editorstack()
    upper_right.sig_split_vertically.emit()
    _settle()
    lower_right = state.widget.editorstacks[-1]
    _focus_stack(state, upper_right)

    def navigate(key, expected):
        state.qtbot.keyClick(state.commandline, Qt.Key_W, Qt.ControlModifier)
        state.qtbot.keyClicks(state.commandline, key)
        _settle()
        assert status.get_editorstack() in expected
        assert status.is_normal()
        assert status.sub_mode is None
        assert state.commandline.hasFocus()
        assert state.commandline.text() == ""

    navigate("k", (upper_right,))
    navigate("l", (upper_right,))
    navigate("j", (lower_right,))
    navigate("j", (lower_right,))
    navigate("k", (upper_right,))
    navigate("h", (left,))
    navigate("h", (left,))
    navigate("j", (left,))
    navigate("k", (left,))
    navigate("l", (upper_right, lower_right))
    target = status.get_editor()
    status.cursor.set_cursor_pos(0)
    state.qtbot.keyClicks(state.commandline, "l")
    assert target.textCursor().position() == 1


@pytest.mark.parametrize("host", ["main", "undocked", "window"])
def test_control_w_closes_current_split(editor_windows, host):
    """Close the selected split and keep the final pane and its files open."""
    state = editor_windows
    if host == "undocked":
        state.widget.create_window()
    elif host == "window":
        state.widget.create_new_window()
    _settle()
    remaining = state.widget.editorstacks[-1]
    _focus_stack(state, remaining)
    status = state.vim.vim_cmd.vim_status
    filenames = remaining.get_filenames()
    state.qtbot.keyClicks(state.commandline, ":vs")
    state.qtbot.keyClick(state.commandline, Qt.Key_Return)
    _settle()
    closing = status.get_editorstack()
    assert closing is not remaining

    state.qtbot.keyClick(state.commandline, Qt.Key_W, Qt.ControlModifier)
    state.qtbot.keyClicks(state.commandline, "c")
    _settle()

    assert widget_is_deleted(closing)
    assert status.get_editorstack() is remaining
    assert remaining.get_filenames() == filenames
    assert status.is_normal()
    assert state.commandline.hasFocus()
    assert state.commandline.text() == ""
    status.cursor.set_cursor_pos(0)
    state.qtbot.keyClicks(state.commandline, "l")
    assert remaining.get_current_editor().textCursor().position() == 1

    stacks = list(state.widget.editorstacks)
    state.qtbot.keyClick(state.commandline, Qt.Key_W, Qt.ControlModifier)
    state.qtbot.keyClicks(state.commandline, "c")
    _settle()

    assert not widget_is_deleted(remaining)
    assert remaining.window().isVisible()
    assert state.widget.editorstacks == stacks
    assert remaining.get_filenames() == filenames
    assert status.get_editorstack() is remaining
    assert status.is_normal()
    assert state.commandline.hasFocus()


@pytest.fixture
def which_key_windows(editor_windows):
    """Enable hints only for their window-routing tests."""
    state = editor_windows
    previous_delay = CONF.get(CONF_SECTION, "which_key_delay")
    previous_leader = CONF.get(CONF_SECTION, "leader_key")
    CONF.set(CONF_SECTION, "which_key_enabled", True)
    CONF.set(CONF_SECTION, "which_key_delay", 40)
    CONF.set(CONF_SECTION, "leader_key", "Space")
    state.vim.apply_plugin_settings([])
    try:
        yield state
    finally:
        if not state.vim_closed:
            state.vim.vim_cmd.which_key.cancel()
            state.commandline.esc_pressed()
        CONF.set(CONF_SECTION, "which_key_enabled", False)
        CONF.set(CONF_SECTION, "which_key_delay", previous_delay)
        CONF.set(CONF_SECTION, "leader_key", previous_leader)
        if not state.vim_closed:
            state.vim.apply_plugin_settings([])


def _which_key_visible(controller):
    popup = controller.popup
    return popup is not None and not widget_is_deleted(popup) and popup.isVisible()


def _start_which_key(state, displayed):
    controller = state.vim.vim_cmd.which_key
    state.commandline.esc_pressed()
    state.qtbot.keyClick(state.commandline, Qt.Key_Space)
    if displayed:
        state.qtbot.waitUntil(lambda: _which_key_visible(controller))
    else:
        assert controller.timer.isActive()
        assert not _which_key_visible(controller)
    return controller


@pytest.mark.parametrize("displayed", [False, True], ids=["pending", "visible"])
@pytest.mark.parametrize("target", ["tab", "split", "window"])
def test_which_key_cancels_on_view_change(which_key_windows, displayed, target):
    """Neither a timer nor a displayed hint can survive changing editor views."""
    state = which_key_windows
    source_stack = state.widget.editorstacks[0]
    if target == "split":
        state.widget.editorsplitter.split(Qt.Horizontal)
        _settle()
        target_stack = state.widget.editorstacks[-1]
    elif target == "window":
        window = state.widget.create_new_window()
        _settle()
        target_stack = window.editorwidget.editorstacks[0]
    else:
        target_stack = source_stack
    source = _focus_stack(state, source_stack)
    controller = _start_which_key(state, displayed)
    old_popup = controller.popup

    if target == "tab":
        source_stack.set_stack_index(1 - source_stack.get_stack_index())
    else:
        target_code = target_stack.get_current_editor()
        target_code.window().activateWindow()
        target_code.setFocus()
    _settle()

    assert not controller.timer.isActive()
    assert not _which_key_visible(controller)
    assert state.vim.vim_cmd.vim_status.sub_mode is None
    if old_popup is not None:
        assert widget_is_deleted(old_popup) or not old_popup.isVisible()
    state.qtbot.wait(60)
    assert not _which_key_visible(controller)

    code = _focus_stack(state, target_stack)
    assert code is not source
    _start_which_key(state, True)
    assert controller.popup.parentWidget() is code.viewport()
    assert controller.popup.window() is code.window()
    assert QApplication.focusWidget() is state.commandline


@pytest.mark.parametrize("displayed", [False, True], ids=["pending", "visible"])
def test_which_key_releases_closed_window(which_key_windows, displayed):
    """Closing the hint's host releases its viewport and prevents late display."""
    state = which_key_windows
    window = state.widget.create_new_window()
    _settle()
    stack = window.editorwidget.editorstacks[0]
    _focus_stack(state, stack)
    controller = _start_which_key(state, displayed)
    popup = controller.popup

    window.close()
    _settle()

    assert widget_is_deleted(window)
    assert not controller.timer.isActive()
    assert not _which_key_visible(controller)
    if popup is not None:
        assert widget_is_deleted(popup)
    state.qtbot.wait(60)
    assert not _which_key_visible(controller)
    code = _focus_stack(state, state.widget.editorstacks[0])
    _start_which_key(state, True)
    assert controller.popup.parentWidget() is code.viewport()


@pytest.fixture(params=["history", "guide"])
def commandline_popup_windows(editor_windows, request):
    """Exercise each popup with the real editor and window routing."""
    state = editor_windows
    state.popup_kind = request.param
    preferences = {
        name: CONF.get(CONF_SECTION, name, True)
        for name in (
            "commandline_history_enabled",
            "substitute_guide_enabled",
            "substitute_preview_enabled",
        )
    }
    for name in preferences:
        CONF.set(CONF_SECTION, name, name != "substitute_preview_enabled")
    state.vim.apply_plugin_settings([])
    state.commandline.histories["ex"][:] = ["write", "2"]
    try:
        yield state
    finally:
        for name, previous in preferences.items():
            CONF.set(CONF_SECTION, name, previous)
        if not state.vim_closed:
            state.commandline.esc_pressed()
            state.vim.apply_plugin_settings([])


def _commandline_panel(state, kind=None):
    controller = state.vim.vim_cmd.commandline_popup
    kind = state.popup_kind if kind is None else kind
    return controller.popup if kind == "history" else controller.guide_popup


def _commandline_popup_visible(state):
    popup = _commandline_panel(state)
    return popup is not None and not widget_is_deleted(popup) and popup.isVisible()


def _start_commandline_popup(state, kind=None):
    """Show a guide or select a history row without executing its command."""
    controller = state.vim.vim_cmd.commandline_popup
    kind = state.popup_kind if kind is None else kind
    state.commandline.esc_pressed()
    command = ":" if kind == "history" else ":s/alpha/beta/"
    state.qtbot.keyClicks(state.commandline, command)
    popup = _commandline_panel(state, kind)
    state.qtbot.waitUntil(lambda: popup is not None and popup.isVisible())
    if kind == "history":
        state.qtbot.keyClick(state.commandline, Qt.Key_N, Qt.ControlModifier)
        assert controller.selected_index == 0
    else:
        assert controller.selected_index is None
        assert controller.candidates == []
    assert state.commandline.text() == command
    return controller


@pytest.mark.parametrize("target", ["tab", "split", "window"])
def test_commandline_popup_follows_active_view(commandline_popup_windows, target):
    """View switches discard stale state and bind the next panel locally."""
    state = commandline_popup_windows
    source_stack = state.widget.editorstacks[0]
    if target == "split":
        state.widget.editorsplitter.split(Qt.Horizontal)
        _settle()
        target_stack = state.widget.editorstacks[-1]
    elif target == "window":
        window = state.widget.create_new_window()
        _settle()
        target_stack = window.editorwidget.editorstacks[0]
    else:
        target_stack = source_stack
    source = _focus_stack(state, source_stack)
    controller = _start_commandline_popup(state)
    old_popup = _commandline_panel(state)

    if target == "tab":
        source_stack.set_stack_index(1 - source_stack.get_stack_index())
    else:
        target_editor = target_stack.get_current_editor()
        target_editor.window().activateWindow()
        target_editor.setFocus()
    _settle()

    assert not _commandline_popup_visible(state)
    assert controller.selected_index is None
    assert controller.candidates == []
    assert widget_is_deleted(old_popup)
    assert state.vim.vim_cmd.vim_status.sub_mode is None
    code = _focus_stack(state, target_stack)
    assert code is not source
    _start_commandline_popup(state)
    popup = _commandline_panel(state)
    assert popup.parentWidget() is controller.host
    assert controller.host.parentWidget() is code.viewport()
    assert popup.window() is code.window()
    assert controller.host.rect().contains(popup.geometry())
    assert code.viewport().rect().contains(controller.host.geometry())
    assert QApplication.focusWidget() is state.commandline


def test_commandline_popup_releases_closed_editor(commandline_popup_windows):
    """Closing the active tab disposes its panel before the editor is deleted."""
    state = commandline_popup_windows
    stack = state.widget.editorstacks[0]
    stack.set_stack_index(1)
    code = _focus_stack(state, stack)
    controller = _start_commandline_popup(state)
    popup = _commandline_panel(state)

    stack.close_file(1, force=True)
    _settle()

    assert stack.get_current_editor() is not code
    # Spyder detaches closed editors before their final deferred deletion.
    code.deleteLater()
    _settle()
    assert widget_is_deleted(code)
    assert widget_is_deleted(popup)
    assert not _commandline_popup_visible(state)
    assert controller.selected_index is None
    replacement = _focus_stack(state, stack)
    _start_commandline_popup(state)
    assert _commandline_panel(state).parentWidget() is controller.host
    assert controller.host.parentWidget() is replacement.viewport()


def test_commandline_popup_releases_closed_window(commandline_popup_windows):
    """A detached window cannot retain its panel after closing."""
    state = commandline_popup_windows
    window = state.widget.create_new_window()
    _settle()
    stack = window.editorwidget.editorstacks[0]
    _focus_stack(state, stack)
    controller = _start_commandline_popup(state)
    popup = _commandline_panel(state)

    window.close()
    _settle()

    assert widget_is_deleted(window)
    assert widget_is_deleted(popup)
    assert not _commandline_popup_visible(state)
    assert controller.selected_index is None
    code = _focus_stack(state, state.widget.editorstacks[0])
    _start_commandline_popup(state)
    assert _commandline_panel(state).parentWidget() is controller.host
    assert controller.host.parentWidget() is code.viewport()


def test_commandline_popup_cleanup_disconnects_callbacks(commandline_popup_windows):
    """Cleanup removes both panels and ignores later input and viewport events."""
    state = commandline_popup_windows
    code = _focus_stack(state, state.widget.editorstacks[0])
    controller = _start_commandline_popup(state)
    other_kind = "guide" if state.popup_kind == "history" else "history"
    _start_commandline_popup(state, other_kind)
    popups = controller.popup, controller.guide_popup

    controller.cleanup()
    _settle()
    assert all(widget_is_deleted(popup) for popup in popups)
    assert controller.popup is None
    assert controller.guide_popup is None
    assert controller.candidates == []
    assert controller.selected_index is None
    state.commandline.esc_pressed()
    state.commandline.setText(":s/")
    state.vim.vim_cmd.sig_input_finished.emit()
    code.resize(max(1, code.width() - 1), code.height())
    _settle()
    controller.sync()
    assert controller.popup is None
    assert controller.guide_popup is None
    assert controller.candidates == []


@pytest.mark.parametrize("close_to_dock", [False, True])
def test_commandline_popup_tracks_docking_host(
    commandline_popup_windows, close_to_dock
):
    """The same viewport follows docking and handles the new host's events."""
    state = commandline_popup_windows
    stack = state.widget.editorstacks[0]
    code = _focus_stack(state, stack)
    controller = _start_commandline_popup(state)

    state.widget.create_window()
    _settle()
    floating = state.widget.windowwidget
    assert not _commandline_popup_visible(state)
    assert _focus_stack(state, stack) is code
    _start_commandline_popup(state)
    assert _commandline_panel(state).window() is floating
    QApplication.sendEvent(floating, QEvent(QEvent.WindowDeactivate))
    assert not _commandline_popup_visible(state)
    assert controller.selected_index is None

    _start_commandline_popup(state)
    if close_to_dock:
        floating.close()
    else:
        state.widget.dock_window()
    _settle()
    assert widget_is_deleted(floating)
    assert not _commandline_popup_visible(state)
    assert _focus_stack(state, stack) is code
    _start_commandline_popup(state)
    assert _commandline_panel(state).window() is state.main
    QApplication.sendEvent(state.main, QEvent(QEvent.WindowDeactivate))
    assert not _commandline_popup_visible(state)


@pytest.mark.parametrize("undocked", [False, True])
def test_commandline_popup_shutdown_in_new_window(commandline_popup_windows, undocked):
    """Plugin shutdown releases both popups before the window UI is deleted."""
    state = commandline_popup_windows
    if undocked:
        state.widget.create_window()
        _settle()
    window = state.widget.create_new_window()
    _settle()
    _focus_stack(state, window.editorwidget.editorstacks[0])
    controller = _start_commandline_popup(state)
    other_kind = "guide" if state.popup_kind == "history" else "history"
    _start_commandline_popup(state, other_kind)
    popups = controller.popup, controller.guide_popup

    state.vim.on_close()
    state.vim_closed = True
    _settle()

    assert all(widget_is_deleted(popup) for popup in popups)
    if not widget_is_deleted(controller):
        assert controller.popup is None
        assert controller.guide_popup is None
    assert widget_is_deleted(state.commandline)
    window.close()
    _settle()
    assert widget_is_deleted(window)


@pytest.mark.parametrize("undocked", [False, True])
@pytest.mark.parametrize("window_count", [1, 2])
def test_new_windows_splits_and_cloned_tabs(editor_windows, undocked, window_count):
    """Route to every stack/tab with an independent main pane and New windows."""
    state = editor_windows
    widget = state.widget
    original_stack = widget.editorstacks[0]
    if undocked:
        widget.create_window()
        _settle()
    detached = widget.windowwidget
    windows = [widget.create_new_window() for _ in range(window_count)]
    _settle()
    splitters = [widget.editorsplitter] + [
        window.editorwidget.editorsplitter for window in windows
    ]
    for index, splitter in enumerate(splitters):
        splitter.split(Qt.Horizontal if index % 2 else Qt.Vertical)
        _settle()

    all_stacks = list(widget.editorstacks)
    assert len(all_stacks) == 2 * (window_count + 1)
    for stack in all_stacks + list(reversed(all_stacks)):
        for index in (0, 1, 0):
            stack.set_stack_index(index)
            _exercise_vim(state, stack)
            # All views of this filename share the document after New window
            # and Split, while the other tab remains independently editable.
            filename = stack.get_current_filename()
            for clone in all_stacks:
                matching = clone.get_index_from_filename(filename)
                assert (
                    clone.data[matching].editor.toPlainText()
                    == stack.get_current_editor().toPlainText()
                )
        _focus_stack(state, stack)
        first = stack.get_current_filename()
        state.qtbot.keyClicks(state.commandline, "gt")
        _settle()
        assert stack.get_current_filename() != first
        assert state.vim.vim_cmd.vim_status.get_editor() is stack.get_current_editor()
        assert state.commandline.window() is stack.window()
        state.qtbot.keyClicks(state.commandline, "gT")
        _settle()
        assert stack.get_current_filename() == first

    # Change the primary pane's dock state while Vim belongs first to the
    # primary pane and then to a New window. Independent completion widgets
    # must remain alive and attached to their own host throughout both moves.
    for owner in (original_stack, windows[-1].editorwidget.editorstacks[0]):
        _focus_stack(state, owner)
        if widget.windowwidget is None:
            widget.create_window()
        else:
            widget.dock_window()
        _settle()
        for stack in all_stacks:
            code = stack.get_current_editor()
            assert not widget_is_deleted(code.completion_widget)
            assert code.completion_widget.parentWidget().window() is code.window()
        _exercise_vim(state, owner)
    detached = widget.windowwidget

    for stack in all_stacks:
        code = _focus_stack(state, stack)
        for position in (0, 4):
            code.set_text("x=1\n")
            state.vim.vim_cmd.vim_status.cursor.set_cursor_pos(position)
            code._LSPMixin__cursor_position_before_format = position
            _settle()
            # Keep Vim focus here so this routing test also works with stock
            # Spyder; the paired fork tests its additional focus-restore hook.
            code._apply_document_edits(
                {
                    "params": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 1, "character": 0},
                            },
                            "newText": "x\n",
                        }
                    ]
                }
            )
            _settle()
            assert code.toPlainText() == "x\n"
            assert QApplication.focusWidget() is state.commandline
            assert state.vim.vim_cmd.vim_status.get_editor() is code

    # Close split panes in every host after each has owned Vim input.
    split_stacks = [splitter.widget(1).editorstack for splitter in splitters]
    for stack in reversed(split_stacks):
        _focus_stack(state, stack)
        stack.close_split()
        _settle()
        assert widget_is_deleted(stack)
    assert len(widget.editorstacks) == window_count + 1

    # Closing a file from a secondary window updates every clone and keeps
    # command routing valid after the original CodeEditor is removed.
    active_stack = windows[-1].editorwidget.editorstacks[0]
    _focus_stack(state, active_stack)
    active_stack.close_file(1, force=True)
    _settle()
    assert all(len(stack.data) == 1 for stack in widget.editorstacks)
    for stack in list(widget.editorstacks):
        _exercise_vim(state, stack)

    # Close the inactive window first when two exist, then the currently
    # active window. Neither operation may close or redock the main pane.
    for window in windows:
        if window is windows[-1]:
            _focus_stack(state, window.editorwidget.editorstacks[0])
        else:
            _focus_stack(state, original_stack)
        window.close()
        _settle()
        assert widget_is_deleted(window)
        assert widget.windowwidget is detached
        if detached is not None:
            assert not widget_is_deleted(detached)
    assert not widget.editorwindows
    _exercise_vim(state, original_stack)
    if undocked:
        widget.dock_window()
        _settle()
        _exercise_vim(state, original_stack)


def test_repeated_new_window_creation_and_close(editor_windows):
    """New windows can repeatedly own Vim input without retaining their UI."""
    state = editor_windows
    widget = state.widget
    original_stack = widget.editorstacks[0]
    baseline_status_ids = {
        id(item)
        for item in QApplication.allWidgets()
        if isinstance(item, StatusBarVimWidget)
    }
    old_windows = []
    old_stacks = []
    shortcut_counts = []
    history_keys = set(widget.last_focused_editorstack)
    for cycle in range(30):
        if cycle % 2:
            widget.create_window()
            _settle()
        detached = widget.windowwidget
        windows = [widget.create_new_window() for _ in range(2)]
        _settle()
        for window in windows:
            stack = window.editorwidget.editorstacks[0]
            _exercise_vim(state, stack)
            old_stacks.append(weakref.ref(stack))
        _exercise_vim(state, original_stack)
        for window in reversed(windows):
            _focus_stack(state, window.editorwidget.editorstacks[0])
            old_windows.append(weakref.ref(window))
            window.close()
            _settle()
            assert widget_is_deleted(window)
            assert widget.windowwidget is detached
        _exercise_vim(state, original_stack)
        if detached is not None:
            widget.dock_window()
            _settle()
        shortcut_counts.append(len(state.main.findChildren(QShortcut)))
        assert {
            id(item)
            for item in QApplication.allWidgets()
            if isinstance(item, StatusBarVimWidget)
        } == baseline_status_ids
        assert len(widget.editorstacks) == 1
        assert set(widget.last_focused_editorstack) == history_keys
        del window, windows, stack
    gc.collect()
    assert len(set(shortcut_counts)) == 1
    assert all(ref() is None for ref in old_windows)
    assert all(ref() is None for ref in old_stacks)


@pytest.mark.parametrize("prefix", ["3i", "vl", "/alpha", ":2", "2"])
def test_switch_windows_with_pending_vim_state(editor_windows, prefix):
    """Changing windows cannot apply a previous view's unfinished command."""
    state = editor_windows
    widget = state.widget
    windows = [widget.create_new_window() for _ in range(2)]
    _settle()
    stacks = [widget.editorstacks[0]] + [
        window.editorwidget.editorstacks[0] for window in windows
    ]
    status = state.vim.vim_cmd.vim_status
    for source, target in zip(stacks, stacks[1:] + stacks[:1]):
        source.set_stack_index(0)
        target.set_stack_index(1)
        code = _focus_stack(state, source)
        state.commandline.esc_pressed()
        code.set_text("alpha beta\nsecond line\n")
        status.cursor.set_cursor_pos(0)
        state.qtbot.keyClicks(state.commandline, prefix)
        _settle()
        if prefix == "3i":
            assert QApplication.focusWidget() is code
            state.qtbot.keyClicks(code, "X")
            _settle()

        target_code = target.get_current_editor()
        untouched = target_code.toPlainText()
        _focus_stack(state, target)
        assert state.commandline.text() == ""
        assert status.sub_mode is None
        assert not status.is_visual_mode
        assert state.vim.vim_cmd.status_label.text() == "NORMAL"
        assert target_code.toPlainText() == untouched
        assert not code.get_extra_selections("vim_selection")
        status.cursor.set_cursor_pos(0)
        state.qtbot.keyClicks(state.commandline, "l")
        _settle()
        assert target_code.textCursor().position() == 1
        assert target_code.toPlainText() == untouched


def test_closing_last_tab_and_creating_file_in_new_window(editor_windows, tmp_path):
    """Transiently empty cloned stacks and replacement tabs preserve routing."""
    state = editor_windows
    window = state.widget.create_new_window()
    _settle()
    stack = window.editorwidget.editorstacks[0]
    _focus_stack(state, stack)
    # User-facing close-last-tab creates Spyder's replacement untitled file.
    stack.close_file(1, force=True)
    _settle()
    stack.close_file(0, force=True)
    _settle()
    assert stack.get_current_editor() is not None
    _exercise_vim(state, stack)
    state.editor.new(
        fname=str(tmp_path / "created_in_new_window.py"),
        editorstack=stack,
        text="created = True\n",
    )
    _settle()
    _exercise_vim(state, stack)
    _exercise_vim(state, state.widget.editorstacks[0])


def test_register_dot_macro_and_commandline_click_across_windows(editor_windows):
    """Shared Vim history targets the selected view and survives host changes."""
    state = editor_windows
    new_window = state.widget.create_new_window()
    _settle()
    source_stack = state.widget.editorstacks[0]
    target_stack = new_window.editorwidget.editorstacks[0]
    source_stack.set_stack_index(0)
    target_stack.set_stack_index(1)
    source = _focus_stack(state, source_stack)
    source.set_text("abcd\n")
    state.vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    state.qtbot.keyClicks(state.commandline, "qaxq")
    _settle()
    assert source.toPlainText() == "bcd\n"

    target = _focus_stack(state, target_stack)
    target.set_text("wxyz\n")
    state.vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    state.qtbot.keyClicks(state.commandline, "@a")
    state.qtbot.waitUntil(lambda: target.toPlainText() == "xyz\n", timeout=2000)
    _settle()
    assert source.toPlainText() == "bcd\n"
    state.qtbot.keyClicks(state.commandline, ".")
    _settle()
    assert target.toPlainText() == "yz\n"

    source = _focus_stack(state, source_stack)
    source.set_text("one\ntwo\n")
    state.vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    state.qtbot.keyClicks(state.commandline, '"byy')
    _settle()
    target = _focus_stack(state, target_stack)
    target.set_text("target\n")
    state.vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    state.qtbot.keyClicks(state.commandline, '"bP')
    _settle()
    assert target.toPlainText() == "one\ntarget\n"

    for stack in (source_stack, target_stack, source_stack, target_stack):
        code = _focus_stack(state, stack)
        state.qtbot.keyClicks(state.commandline, "i")
        _settle()
        assert QApplication.focusWidget() is code
        state.qtbot.mouseClick(state.commandline, Qt.LeftButton)
        _settle()
        assert QApplication.focusWidget() is state.commandline
        assert state.vim.vim_cmd.vim_status.get_editor() is code
        assert state.vim.vim_cmd.status_label.text() == "NORMAL"


def test_queued_search_cannot_mutate_another_window(editor_windows):
    """Switching/closing during a pending search invalidates old view work."""
    state = editor_windows
    new_window = state.widget.create_new_window()
    _settle()
    source_stack = state.widget.editorstacks[0]
    target_stack = new_window.editorwidget.editorstacks[0]
    source_stack.set_stack_index(0)
    target_stack.set_stack_index(1)
    source = _focus_stack(state, source_stack)
    source.set_text("alpha beta\nalpha tail\n")
    state.vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    state.qtbot.keyClicks(state.commandline, "/alpha")
    _settle()
    source.insertPlainText(" ")
    target = _focus_stack(state, target_stack)
    state.vim.vim_cmd.vim_status.cursor.set_cursor_pos(2)
    original = target.toPlainText()
    position = target.textCursor().position()
    state.qtbot.wait(200)
    _settle()
    assert target.toPlainText() == original
    assert target.textCursor().position() == position
    assert state.vim.vim_cmd.vim_status.sub_mode is None

    state.qtbot.keyClicks(state.commandline, "/line")
    _settle()
    target.insertPlainText(" ")
    new_window.close()
    _settle()
    assert widget_is_deleted(new_window)
    source = _focus_stack(state, source_stack)
    position = source.textCursor().position()
    state.qtbot.wait(200)
    _settle()
    assert source.textCursor().position() == position
    assert state.vim.vim_cmd.vim_status.sub_mode is None


def test_window_activation_restores_normal_and_respects_editor_click(editor_windows):
    """Title-bar activation preserves Normal; a subsequent click enters Insert."""
    state = editor_windows
    windows = [state.widget.create_new_window() for _ in range(2)]
    _settle()
    stacks = [state.widget.editorstacks[0]] + [
        window.editorwidget.editorstacks[0] for window in windows
    ]
    codes = [_focus_stack(state, stack) for stack in stacks]
    for index in (0, 1, 2, 0, 2, 1):
        stack = stacks[index]
        stack.window().activateWindow()
        _settle()
        assert QApplication.focusWidget() is state.commandline
        assert state.commandline.window() is stack.window()
        assert state.vim.vim_cmd.vim_status.get_editor() is codes[index]
        code = codes[index]
        original = code.toPlainText()
        state.vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
        state.qtbot.keyClicks(state.commandline, "l")
        _settle()
        assert code.textCursor().position() == 1
        assert code.toPlainText() == original
        state.qtbot.mouseClick(code.viewport(), Qt.LeftButton)
        _settle()
        assert QApplication.focusWidget() is code
        assert state.vim.vim_cmd.status_label.text() == "INSERT"
        state.qtbot.keyClicks(code, "Z")
        assert code.toPlainText().count("Z") == original.count("Z") + 1
        state.qtbot.keyClick(code, Qt.Key_Escape)
        _settle()
        assert QApplication.focusWidget() is state.commandline
        state.qtbot.keyClicks(state.commandline, "u")
        _settle()
        assert code.toPlainText() == original


def test_macro_playback_cannot_edit_a_newly_focused_window(editor_windows):
    """Queued macro events remain tied to the document where playback began."""
    state = editor_windows
    window = state.widget.create_new_window()
    _settle()
    source_stack = state.widget.editorstacks[0]
    target_stack = window.editorwidget.editorstacks[0]
    source_stack.set_stack_index(0)
    target_stack.set_stack_index(1)
    source = _focus_stack(state, source_stack)
    source.set_text("a" * 600 + "\n")
    state.vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    state.qtbot.keyClicks(state.commandline, "qaxq")
    _settle()
    target = target_stack.get_current_editor()
    target.set_text("TARGET\n")
    original = target.toPlainText()
    state.qtbot.keyClicks(state.commandline, "200@a")
    window.activateWindow()
    target.setFocus()
    state.qtbot.waitUntil(
        lambda: not state.vim.vim_cmd.worker_macro.isRunning(), timeout=3000
    )
    _settle()
    assert target.toPlainText() == original


def test_recording_stops_and_disconnects_on_window_change(editor_windows):
    """Recording cannot retain a closed editor or mix views' Insert input."""
    state = editor_windows
    window = state.widget.create_new_window()
    _settle()
    source_stack = window.editorwidget.editorstacks[0]
    target_stack = state.widget.editorstacks[0]
    source_stack.set_stack_index(0)
    target_stack.set_stack_index(1)
    source = _focus_stack(state, source_stack)
    state.qtbot.keyClicks(state.commandline, "qa")
    _settle()
    manager = state.vim.vim_cmd.vim_status.manager_macro
    assert manager.is_recording
    assert manager.editor_connected is source
    target = _focus_stack(state, target_stack)
    assert not manager.is_recording
    assert manager.editor_connected is None
    recorded = list(manager.registers["a"])
    window.close()
    _settle()
    assert widget_is_deleted(window)
    state.qtbot.keyClicks(state.commandline, "i")
    state.qtbot.keyClicks(target, "X")
    state.qtbot.keyClick(target, Qt.Key_Escape)
    _settle()
    assert manager.registers["a"] == recorded


@pytest.mark.parametrize("undocked", [False, True])
@pytest.mark.parametrize("displayed", [False, True], ids=["pending", "visible"])
def test_plugin_shutdown_with_shared_ui_in_new_window(
    which_key_windows, undocked, displayed
):
    """Shutdown cancels hints and releases shared UI before deleting windows."""
    state = which_key_windows
    if undocked:
        state.widget.create_window()
        _settle()
    detached = state.widget.windowwidget
    windows = [state.widget.create_new_window() for _ in range(2)]
    _settle()
    _exercise_vim(state, windows[-1].editorwidget.editorstacks[0])
    assert state.commandline.window() is windows[-1]
    state.qtbot.keyClicks(state.commandline, "qa")
    manager = state.vim.vim_cmd.vim_status.manager_macro
    assert manager.is_recording
    controller = _start_which_key(state, displayed)
    popup = controller.popup
    timer = controller.timer
    state.vim.on_close()
    state.vim_closed = True
    if not widget_is_deleted(timer):
        assert not timer.isActive()
    _settle()
    if not widget_is_deleted(controller):
        assert not controller.timer.isActive()
        assert controller.popup is None
    if popup is not None:
        assert widget_is_deleted(popup)
    assert widget_is_deleted(state.commandline)
    assert not manager.is_recording
    assert manager.editor_connected is None
    for window in windows:
        window.close()
        _settle()
        assert widget_is_deleted(window)
        assert state.widget.windowwidget is detached
    if detached is not None:
        state.widget.dock_window()
        _settle()
        assert widget_is_deleted(detached)
