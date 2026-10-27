"""Opt-in integration with the paired Spyder fork's real editor windows."""

# Standard Libraries
import gc
import os
from types import SimpleNamespace
from unittest.mock import Mock
import weakref

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtWidgets import QApplication, QMainWindow, QShortcut
from spyder.api.plugins import Plugins
from spyder.config.manager import CONF
from spyder.plugins.editor.plugin import Editor
from spyder.plugins.outlineexplorer.plugin import OutlineExplorer

# Project Libraries
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION
from spyder_okvim.spyder.plugin import OkVim, StatusBarVimWidget
from spyder_okvim.utils.qtcompat import widget_is_deleted


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
