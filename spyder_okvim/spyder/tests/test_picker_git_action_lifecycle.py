"""Git intent can expire; an already accepted mutation outlives its popup."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from qtpy.QtCore import Qt

from spyder_okvim.spyder.picker_git import GitResult
from spyder_okvim.spyder.picker_git_controller import PickerGitActions, _in_repository
from spyder_okvim.spyder.tests.test_picker_git_shortcuts import git_picker, _open
from spyder_okvim.spyder.tests.test_picker_git_integration import _git, _ready


class DeferredMutationService:
    """Expose callback ordering without sleeps or a blocked platform process."""

    def __init__(self):
        self.active = None
        self.requests = []

    @property
    def busy(self):
        return self.active is not None

    def submit(self, key, cwd, args, callback, **checks):
        assert not self.busy
        self.active = (key, cwd, tuple(args), callback, checks)
        self.requests.append(self.active)
        return True

    def finish(self, stdout=b"", error="", returncode=0):
        key, cwd, args, callback, checks = self.active
        self.active = None
        callback(GitResult(key, stdout, "", error, False, returncode))


@contextmanager
def deferred(state):
    actions = state.picker.actions
    original = actions.service
    service = DeferredMutationService()
    actions.service = service
    try:
        yield service
    finally:
        # Expire any held intent before releasing its deferred context callback.
        actions.invalidate_pending()
        while service.busy:
            service.finish(error="Test cleanup", returncode=1)
        actions.service = original
        actions.sync()


def finish_preflight(state, service):
    service.finish(_git(state.root, "symbolic-ref", "HEAD"))
    service.finish(_git(state.root, "rev-parse", "HEAD"))


def test_query_change_before_preflight_discards_write(git_picker):
    state = git_picker
    state.file.write_text("changed = 2\n")
    dialog = _open(state, "ts")
    with deferred(state) as service:
        state.bot.keyClick(dialog.prompt, Qt.Key_Tab)
        assert state.picker.actions.pending is not None
        assert len(service.requests) == 1
        dialog.prompt.setText("changed query")
        assert state.picker.actions.pending is None
        service.finish(_git(state.root, "symbolic-ref", "HEAD"))
        assert len(service.requests) == 1
        assert not state.picker.actions.busy
        assert _git(state.root, "diff", "--cached") == b""


def test_cancelled_confirmation_does_not_submit_mutation(git_picker, monkeypatch):
    state = git_picker
    dialog = _open(state, "tc")
    confirmations = []

    def cancel(request, branch):
        confirmations.append((request.action, branch))
        return False

    monkeypatch.setattr(state.picker.actions, "confirm", cancel)
    before = (_git(state.root, "rev-parse", "HEAD"), state.file.read_text())
    with deferred(state) as service:
        state.bot.keyClick(dialog.prompt, Qt.Key_R, Qt.ControlModifier)
        state.bot.keyClick(dialog.prompt, Qt.Key_H)
        finish_preflight(state, service)
        assert confirmations == [("reset_hard", "refs/heads/main")]
        assert len(service.requests) == 2
        assert not state.picker.actions.busy
        assert state.picker.phase == "active"
        assert dialog.actions_button.isEnabled()
        assert before == (_git(state.root, "rev-parse", "HEAD"), state.file.read_text())


def test_duplicate_enter_reserves_one_action_intent(git_picker):
    state = git_picker
    dialog = _open(state, "tc")
    with deferred(state) as service:
        state.bot.keyClick(dialog.prompt, Qt.Key_Return)
        request = state.picker.actions.pending
        state.bot.keyClick(dialog.prompt, Qt.Key_Return)
        assert state.picker.actions.pending is request
        assert len(service.requests) == 1
        assert not dialog.actions_button.isEnabled()
        assert state.picker.phase == "active"


def test_accepted_write_finishes_after_close_and_refreshes_replacement(git_picker):
    state = git_picker
    state.file.write_text("changed = 2\n")
    previous = _open(state, "ts")
    with deferred(state) as service:
        state.bot.keyClick(previous.prompt, Qt.Key_Tab)
        finish_preflight(state, service)
        assert state.picker.actions.running is not None
        assert service.active[2][0] == "add"
        previous.reject()
        state.bot.waitUntil(lambda: state.picker.phase == "closed")
        state.widget.open_picker("git_status")
        state.bot.waitUntil(lambda: _ready(state.picker))
        replacement = state.picker.dialog
        assert replacement is not previous
        assert not replacement.actions_button.isEnabled()
        assert state.picker.snapshot.entries[0].target.status == ".M"
        # Execute the already accepted temp-repository write, then deliver its
        # completion to a newer popup session. It must refresh that popup once.
        _git(state.root, *service.active[2])
        service.finish()
        state.bot.waitUntil(
            lambda: _ready(state.picker)
            and not state.picker.actions.busy
            and state.picker.snapshot.entries[0].target.status == "M."
        )
        assert state.picker.dialog is replacement
        assert replacement.actions_button.isEnabled()
        assert len(service.requests) == 3


def test_closed_widget_completion_returns_before_any_qt_access():
    picker = SimpleNamespace(widget=SimpleNamespace(_closed=True))
    actions = PickerGitActions.__new__(PickerGitActions)
    actions.picker = picker
    actions.running = object()
    actions._finished(object(), [], GitResult(1, b"", ""))
    assert actions.running is None


def test_buffer_repository_membership_resolves_symlink_aliases(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    alias = tmp_path / "project-link"
    try:
        alias.symlink_to(root, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Symlink creation unavailable: {error}")
    path = alias / "unsaved.py"
    assert _in_repository(str(path), str(root))
    assert _in_repository(str(root / "file.py"), str(alias))


def test_confirmation_context_change_cannot_submit_old_write(git_picker, monkeypatch):
    state = git_picker
    dialog = _open(state, "tc")

    def changed_while_confirming(request, branch):
        dialog.prompt.setText("a different query")
        return True

    monkeypatch.setattr(state.picker.actions, "confirm", changed_while_confirming)
    with deferred(state) as service:
        state.bot.keyClick(dialog.prompt, Qt.Key_R, Qt.ControlModifier)
        state.bot.keyClick(dialog.prompt, Qt.Key_H)
        finish_preflight(state, service)
        assert len(service.requests) == 2
        assert state.picker.actions.running is None
        assert state.picker.actions.pending is None
        assert not state.picker.actions.busy


def test_destroyed_widget_completion_returns_before_any_ui_access(qtbot):
    from qtpy.QtCore import QCoreApplication, QEvent
    from qtpy.QtWidgets import QWidget
    from spyder_okvim.utils.qtcompat import widget_is_deleted

    widget = QWidget()
    widget._closed = False
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert widget_is_deleted(widget)
    picker = SimpleNamespace(widget=widget)
    actions = PickerGitActions.__new__(PickerGitActions)
    actions.picker = picker
    actions.running = object()
    actions._finished(object(), [], GitResult(1, b"", ""))
    assert actions.running is None


def test_confirmation_recaptures_buffers_for_completion(git_picker, monkeypatch):
    from qtpy.QtWidgets import QPlainTextEdit, QWidget

    state = git_picker
    dialog = _open(state, "tc")
    actions = state.picker.actions
    path = state.root / "opened_during_confirmation.py"
    path.write_text("before\n")
    editor, stack = QPlainTextEdit(), QWidget()
    state.bot.addWidget(editor)
    state.bot.addWidget(stack)
    editor.setPlainText(path.read_text())
    editor.document().setModified(False)
    stack.data = [SimpleNamespace(filename=str(path), editor=editor)]
    stack.is_file_opened = lambda name: 0

    def reload(index):
        editor.setPlainText(path.read_text())
        editor.document().setModified(False)

    stack.reload = Mock(side_effect=reload)
    confirming = False

    def confirm(request, branch):
        nonlocal confirming
        confirming = True
        return True

    monkeypatch.setattr(actions, "_stacks", lambda: [stack] if confirming else [])
    monkeypatch.setattr(actions, "confirm", confirm)
    with deferred(state) as service:
        actions.request("reset_hard", dialog.selected_entry())
        finish_preflight(state, service)
        assert actions.running is not None
        path.write_text("after Git changed the file\n")
        service.finish()
        assert editor.toPlainText() == path.read_text()
        stack.reload.assert_called_once_with(0)


def test_index_action_does_not_inspect_or_stat_open_buffers(git_picker, monkeypatch):
    state = git_picker
    state.file.write_text("changed = 2\n")
    dialog = _open(state, "ts")
    buffers = Mock(side_effect=AssertionError("Index actions do not change disk files"))
    monkeypatch.setattr(state.picker.actions, "_buffers", buffers)
    with deferred(state) as service:
        state.picker.actions.request("stage_toggle", dialog.selected_entry())
        finish_preflight(state, service)
        assert service.active[2][0] == "add"
        _git(state.root, *service.active[2])
        service.finish()
        buffers.assert_not_called()


def test_checkout_without_prompt_captures_open_buffers_once(git_picker, monkeypatch):
    state = git_picker
    dialog = _open(state, "tc")
    actions = state.picker.actions
    buffers = Mock(return_value=[])
    monkeypatch.setattr(actions, "_buffers", buffers)
    with deferred(state) as service:
        actions.request("checkout", dialog.selected_entry())
        finish_preflight(state, service)
        assert actions.running is not None
        buffers.assert_called_once_with(str(state.root))


@pytest.mark.parametrize("close_first_view", [False, True])
def test_git_reload_uses_one_surviving_clone(
    qtbot, qapp, tmp_path, monkeypatch, close_first_view
):
    from qtpy.QtCore import QCoreApplication, QEvent
    from qtpy.QtGui import QTextDocument
    from qtpy.QtWidgets import QPlainTextDocumentLayout
    from qtpy.QtWidgets import QPlainTextEdit, QWidget

    path = tmp_path / "file.py"
    path.write_text("before\n")
    first = QPlainTextEdit()
    second = QPlainTextEdit()
    document = QTextDocument(qapp)
    document.setDocumentLayout(QPlainTextDocumentLayout(document))
    first.setDocument(document)
    second.setDocument(document)
    if not close_first_view:
        qtbot.addWidget(first)
    qtbot.addWidget(second)
    first.setPlainText(path.read_text())
    first.document().setModified(False)
    stacks = [QWidget(), QWidget()]
    reloads = []
    for stack, editor in zip(stacks, (first, second)):
        qtbot.addWidget(stack)
        stack.data = [SimpleNamespace(filename=str(path), editor=editor)]
        stack.is_file_opened = lambda name: 0

        def reload(index, editor=editor):
            reloads.append(editor)
            editor.setPlainText(path.read_text())
            editor.document().setModified(False)

        stack.reload = reload
    actions = PickerGitActions.__new__(PickerGitActions)
    actions.picker = SimpleNamespace(navigating=False, phase="closed")
    monkeypatch.setattr(actions, "_stacks", lambda: stacks)
    buffers = actions._buffers(str(tmp_path))
    if close_first_view:
        first.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    path.write_text("after Git changed the file\n")
    note = actions._reload_changed_buffers(
        SimpleNamespace(action="checkout_commit"), buffers
    )
    assert second.toPlainText() == path.read_text()
    assert len(reloads) == 1
    assert note == ""
