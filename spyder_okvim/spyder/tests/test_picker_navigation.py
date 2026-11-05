"""Navigation, stale result and shared-content contracts of the picker."""

from threading import Event
from types import SimpleNamespace

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QKeyEvent

from spyder_okvim.spyder import picker as picker_module
from spyder_okvim.spyder import picker_preview as content_module
from spyder_okvim.spyder.picker_providers import collect_files
from spyder_okvim.utils.jump_list import JumpList
from tests.qt_support import reset_vim_state


def _published(controller):
    return (
        controller.phase == "active"
        and controller.snapshot is not None
        and controller.result_token == controller._search_token()
    )


@pytest.fixture
def navigation(vim_bot, monkeypatch, tmp_path):
    main, stack, _, vim, qtbot = vim_bot
    widget = vim.vim_cmd
    status = widget.vim_status
    controller = widget.picker
    previous = stack.get_current_filename()
    filenames = set(stack.get_filenames())
    reset_vim_state(status)
    original_position = stack.get_current_editor().textCursor().position()
    monkeypatch.setattr(main.projects, "get_active_project_path", lambda: str(tmp_path))
    state = SimpleNamespace(
        main=main,
        stack=stack,
        widget=widget,
        status=status,
        controller=controller,
        qtbot=qtbot,
        root=tmp_path,
    )
    try:
        yield state
    finally:
        controller.cancel()
        qtbot.waitUntil(lambda: not any(controller.work.active.values()), timeout=5000)
        qtbot.waitUntil(lambda: not controller.git.busy, timeout=5000)
        stack.set_current_filename(previous)
        for filename in set(stack.get_filenames()) - filenames:
            index = stack.is_file_opened(filename)
            if index is not None:
                with monkeypatch.context() as cleanup_patch:
                    cleanup_patch.setattr(
                        stack,
                        "get_main_widget",
                        lambda: SimpleNamespace(can_close_file=lambda filename: True),
                    )
                    stack.close_file(index, force=True)
        stack.set_current_filename(previous)
        status.cursor.set_cursor_pos(original_position)
        QCoreApplication.processEvents()
        main.activateWindow()
        widget.commandline.setFocus()
        QCoreApplication.processEvents()


def _open_files(state):
    # Exercise the retained Ctrl+P commandline entry point.
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_P, Qt.ControlModifier)
    state.widget.commandline.keyPressEvent(event)
    state.qtbot.waitUntil(lambda: _published(state.controller))
    return state.controller.dialog


def test_files_ctrl_p_opens_once_and_records_actual_destination(
    navigation, monkeypatch
):
    state = navigation
    path = state.root / "target.py"
    path.write_text("target = 1\n")
    origin_path = state.stack.get_current_filename()
    state.status.cursor.set_cursor_pos(2)
    opened = []

    def open_file(filename):
        opened.append(filename)
        state.stack.load(filename, processevents=False)

    monkeypatch.setattr(state.status.host, "open_file", open_file)
    dialog = _open_files(state)
    state.qtbot.keyClick(dialog.prompt, Qt.Key_Return)
    state.qtbot.waitUntil(lambda: state.controller.phase == "closed")
    assert opened == [str(path)]
    assert state.stack.get_current_filename() == str(path)
    assert [(jump.file, jump.pos) for jump in state.status.jump_list.jumps] == [
        (origin_path, 2),
        (str(path), 0),
    ]


def test_failed_file_open_keeps_history_and_reports_failure(navigation, monkeypatch):
    state = navigation
    path = state.root / "target.py"
    path.write_text("target = 1\n")
    origin = state.status.get_current_location()
    monkeypatch.setattr(state.status.host, "open_file", lambda filename: None)
    messages = []
    monkeypatch.setattr(
        state.status, "set_message", lambda text, *args: messages.append(text)
    )
    dialog = _open_files(state)
    state.qtbot.keyClick(dialog.prompt, Qt.Key_Return)
    state.qtbot.waitUntil(lambda: state.controller.phase == "closed")
    assert state.status.get_current_location() == origin
    assert not state.status.jump_list.jumps
    assert any("could not be opened" in message for message in messages)


def test_query_change_blocks_old_enter_and_empty_enter(navigation, monkeypatch):
    state = navigation
    (state.root / "only.py").write_text("only = 1\n")
    actions = []
    monkeypatch.setattr(state.status.host, "open_file", actions.append)
    dialog = _open_files(state)
    assert dialog.selected_entry() is not None
    dialog.prompt.setText("no-such-result")
    # The previously selected row remains visible while asynchronous search is
    # pending, but cannot be accepted during the debounce or after no matches.
    state.qtbot.keyClick(dialog.prompt, Qt.Key_Return)
    assert state.controller.phase == "active"
    assert not actions
    state.qtbot.waitUntil(lambda: _published(state.controller))
    assert dialog.model.rowCount() == 0
    state.qtbot.keyClick(dialog.prompt, Qt.Key_Return)
    assert state.controller.phase == "active"
    assert not actions


def test_blocked_collection_keeps_source_input_and_reopen_lane_bounded(
    navigation, monkeypatch
):
    state = navigation
    (state.root / "target.py").write_text("target = 1\n")
    entered, release = Event(), Event()
    invocations = []

    def blocked(root, version, cancel):
        invocations.append(version)
        if len(invocations) == 1:
            entered.set()
            release.wait(5)
        return collect_files(root, version, cancel)

    monkeypatch.setattr(picker_module, "collect_files", blocked)
    monkeypatch.setattr(state.status.bookmark_manager, "list_bookmarks", lambda: [])
    state.widget.open_picker("files")
    try:
        state.qtbot.waitUntil(entered.is_set)
        original_task = state.controller.work.active["collect"]
        state.controller.dialog.prompt.setText("target")
        state.qtbot.keyClick(state.controller.dialog.prompt, Qt.Key_Return)
        state.widget.open_picker("marks")
        state.qtbot.waitUntil(lambda: _published(state.controller))
        assert state.controller.source == "marks"
        assert state.controller.dialog.model.rowCount() == 0
        state.widget.open_picker("files")
        assert state.controller.dialog.query() == "target"
        for _ in range(3):
            state.controller.cancel()
            state.widget.open_picker("files")
            assert state.controller.work.active["collect"] is original_task
            assert state.controller.work.pending["collect"] is not None
        state.controller.dialog.prompt.setText("target")
        assert len(invocations) == 1
    finally:
        release.set()
    state.qtbot.waitUntil(lambda: _published(state.controller), timeout=5000)
    assert state.controller.source == "files"
    assert state.controller.dialog.query() == "target"
    assert state.controller.dialog.selected_entry().target.path == str(
        state.root / "target.py"
    )
    assert len(invocations) == 2


def test_same_closed_file_marks_share_metadata_and_preview_read(
    navigation, monkeypatch
):
    state = navigation
    path = state.root / "marks.py"
    path.write_text("first\nsecond\nthird\n")
    marks = [
        (name, {"file": str(path), "line": number, "col": 0})
        for number, name in enumerate(("A", "B", "C"))
    ]
    monkeypatch.setattr(state.status.bookmark_manager, "list_bookmarks", lambda: marks)
    state.controller.content.clear()
    reads = []
    original_open = open

    def counted_open(filename, *args, **kwargs):
        if str(filename) == str(path):
            reads.append(filename)
        return original_open(filename, *args, **kwargs)

    monkeypatch.setattr(content_module, "open", counted_open, raising=False)
    state.widget.open_picker("marks")
    state.qtbot.waitUntil(
        lambda: _published(state.controller)
        and not state.controller.metadata
        and state.controller._content_active is None
    )
    dialog = state.controller.dialog
    state.qtbot.waitUntil(lambda: "first" in dialog.preview.toPlainText())
    for entry in state.controller.snapshot.entries:
        dialog.select_id(entry.id)
        state.controller._preview_timer.stop()
        state.controller._preview()
        state.qtbot.waitUntil(lambda: state.controller._content_active is None)
    assert len(reads) == 1
    assert all(
        word
        in " ".join(entry.search_text for entry in state.controller.snapshot.entries)
        for word in ("first", "second", "third")
    )


def test_external_editor_switch_cancels_picker(navigation):
    state = navigation
    (state.root / "target.py").write_text("target = 1\n")
    _open_files(state)
    origin = state.stack.get_current_filename()
    other = next(
        filename for filename in state.stack.get_filenames() if filename != origin
    )
    state.stack.set_current_filename(other)
    state.qtbot.waitUntil(lambda: state.controller.phase == "closed")
    assert state.stack.get_current_filename() == other


def test_internal_jump_navigation_keeps_picker_and_metadata(navigation):
    state = navigation
    origin = state.stack.get_current_filename()
    other = next(
        filename for filename in state.stack.get_filenames() if filename != origin
    )
    history = JumpList()
    history.push(other, 1)
    history.push(origin, 2)
    state.status.jump_list = history
    state.widget.open_picker("jumps")
    state.qtbot.waitUntil(lambda: _published(state.controller))
    state.qtbot.waitUntil(
        lambda: not state.controller.metadata
        and state.controller._content_active is None
    )
    snapshot_entries = state.controller.snapshot.entries
    version = state.controller.host.history_version
    dialog = state.controller.dialog
    state.qtbot.keyClick(dialog.prompt, Qt.Key_O, Qt.ControlModifier)
    assert state.controller.phase == "active"
    assert state.stack.get_current_filename() == other
    assert history.index == 1
    assert state.controller.host.history_version == version
    assert state.controller.snapshot.entries is snapshot_entries
    state.qtbot.keyClick(dialog.prompt, Qt.Key_I, Qt.ControlModifier)
    assert state.controller.phase == "active"
    assert state.stack.get_current_filename() == origin
    assert history.index == 2


@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("missing", [False, True])
def test_failed_immediate_jump_preserves_current_location(
    navigation, monkeypatch, direction, missing
):
    state = navigation
    path = state.root / "unavailable.py"
    if not missing:
        path.write_text("unavailable = 1\n")
    origin = state.stack.get_current_filename()
    position = state.stack.get_current_editor().textCursor().position()
    history = JumpList()
    values = [(str(path), 1), (origin, position)]
    if direction > 0:
        values.reverse()
    for filename, offset in values:
        history.push(filename, offset)
    original_index = 2 if direction < 0 else 1
    history.index = original_index
    state.status.jump_list = history
    monkeypatch.setattr(state.status.host, "open_file", lambda filename: None)
    state.widget.open_picker("jumps")
    state.qtbot.waitUntil(lambda: _published(state.controller))
    dialog = state.controller.dialog
    key = Qt.Key_O if direction < 0 else Qt.Key_I
    state.qtbot.keyClick(dialog.prompt, key, Qt.ControlModifier)
    assert state.controller.phase == "active"
    assert state.stack.get_current_filename() == origin
    assert state.stack.get_current_editor().textCursor().position() == position
    assert history.index == original_index
    assert "could not be opened" in state.widget.msg_label.text()


def test_failed_metadata_read_is_not_retried_until_refresh(navigation, monkeypatch):
    state = navigation
    path = str(state.root / "unavailable.py")
    marks = [("A", {"file": path, "line": 0, "col": 0})]
    monkeypatch.setattr(state.status.bookmark_manager, "list_bookmarks", lambda: marks)
    reads = []

    def failed_read(filename, cancel):
        reads.append(filename)
        raise OSError("unavailable filesystem")

    monkeypatch.setattr(state.controller.content, "read", failed_read)
    state.widget.open_picker("marks")
    state.qtbot.waitUntil(lambda: bool(reads))
    state.qtbot.waitUntil(
        lambda: not state.controller.metadata
        and state.controller._content_active is None,
        timeout=1000,
    )
    assert state.controller.metadata_limited
    assert (
        "Text search partially limited" in state.controller.dialog.status_label.text()
    )
    assert len(reads) <= 2  # Metadata and the independent selected preview.
    before_refresh = len(reads)
    state.controller.refresh()
    state.qtbot.waitUntil(lambda: len(reads) > before_refresh)


def test_reopen_during_finishing_invalidates_accepted_action(navigation, monkeypatch):
    state = navigation
    (state.root / "target.py").write_text("target = 1\n")
    opened = []
    monkeypatch.setattr(state.status.host, "open_file", opened.append)
    previous = _open_files(state)
    state.qtbot.keyClick(previous.prompt, Qt.Key_Return)
    assert state.controller.phase == "finishing"
    # This request precedes the queued action/focus handoff of the old session.
    state.widget.open_picker("files")
    replacement = state.controller.dialog
    assert replacement is not previous
    state.qtbot.waitUntil(lambda: _published(state.controller))
    assert state.controller.phase == "active"
    assert state.controller.dialog is replacement
    assert not opened
    assert not state.status.jump_list.jumps


def test_source_switch_restores_query_and_selection_in_same_shell(
    navigation, monkeypatch
):
    state = navigation
    for name in ("alpha.py", "beta.py"):
        (state.root / name).write_text("value = 1\n")
    calls = []

    def counted_collect(root, version, cancel):
        calls.append(root)
        return collect_files(root, version, cancel)

    monkeypatch.setattr(picker_module, "collect_files", counted_collect)
    monkeypatch.setattr(state.status.bookmark_manager, "list_bookmarks", lambda: [])
    dialog = _open_files(state)
    dialog.prompt.setText("beta")
    state.qtbot.waitUntil(lambda: _published(state.controller))
    selected = dialog.selection_id()
    state.widget.open_picker("files")
    assert state.controller.dialog is dialog
    assert dialog.query() == "beta"
    state.widget.open_picker("marks")
    state.qtbot.waitUntil(lambda: _published(state.controller))
    assert dialog.query() == ""
    dialog.prompt.setText("mark query")
    state.qtbot.waitUntil(lambda: _published(state.controller))
    state.widget.open_picker("files")
    state.qtbot.waitUntil(lambda: _published(state.controller))
    assert state.controller.dialog is dialog
    assert dialog.query() == "beta"
    assert dialog.selection_id() == selected
    assert len(calls) == 1


def test_changed_jump_contents_refresh_before_immediate_navigation(navigation):
    state = navigation
    filename = state.stack.get_current_filename()
    state.status.jump_list.push(filename, 1)
    state.status.jump_list.push(filename, 2)
    state.widget.open_picker("jumps")
    state.qtbot.waitUntil(lambda: _published(state.controller))
    version = state.controller.host.history_version
    state.status.jump_list.push(filename, 3)
    state.qtbot.keyClick(state.controller.dialog.prompt, Qt.Key_O, Qt.ControlModifier)
    state.qtbot.waitUntil(lambda: _published(state.controller))
    assert state.controller.host.history_version > version
    assert len(state.controller.snapshot.entries) == 3
    assert state.status.jump_list.index == 3
    state.qtbot.keyClick(state.controller.dialog.prompt, Qt.Key_O, Qt.ControlModifier)
    assert state.status.jump_list.index == 2


def test_source_combo_preserves_selection_after_it_invalidates_rows(navigation):
    state = navigation
    for name in ("alpha.py", "beta.py"):
        (state.root / name).write_text("value = 1\n")
    dialog = _open_files(state)
    dialog.select_id("beta.py")
    selected = dialog.selection_id()
    dialog.source_selector.setCurrentIndex(dialog.source_selector.findData("marks"))
    state.qtbot.waitUntil(lambda: _published(state.controller))
    dialog.source_selector.setCurrentIndex(dialog.source_selector.findData("files"))
    state.qtbot.waitUntil(lambda: _published(state.controller))
    assert dialog.selection_id() == selected
