"""Picker input and independent preview behavior with real Qt events."""

import pytest

from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import (
    QColor,
    QInputMethodEvent,
    QKeyEvent,
    QPalette,
    QSyntaxHighlighter,
)
from qtpy.QtWidgets import QPlainTextEdit, QWidget

from spyder_okvim.spyder.picker_dialog import PickerDialog
from spyder_okvim.spyder.picker_preview import ContentPreview
from spyder_okvim.utils.qtcompat import widget_is_deleted
from spyder_okvim.utils.picker import PickerEntry, PickerMatch, SearchResult


def results(count=3):
    entries = tuple(
        PickerEntry(str(i), "files", f"file{i}.py", "folder") for i in range(count)
    )
    return SearchResult(
        tuple(PickerMatch(entry, ()) for entry in entries), count, False
    )


@pytest.fixture(autouse=True)
def retain_dialogs(qtbot):
    # qtbot keeps weak references. Retain parentless dialogs until their queued
    # paint events have drained and close them before releasing Python cycles.
    qtbot.picker_dialogs = []
    yield
    for widget in qtbot.picker_dialogs:
        if not widget_is_deleted(widget):
            widget.close()
    QCoreApplication.processEvents()
    qtbot.picker_dialogs.clear()


def dialog(qtbot, **kwargs):
    widget = PickerDialog(**kwargs)
    qtbot.picker_dialogs.append(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.activateWindow()
    widget.focus_query()
    QCoreApplication.processEvents()
    return widget


def test_best_bottom_and_shortcut_override_runs_once(qtbot):
    picker = dialog(qtbot)
    picker.set_results(results())
    assert picker.selection_id() == "2"
    override = QKeyEvent(QEvent.ShortcutOverride, Qt.Key_P, Qt.ControlModifier)
    QCoreApplication.sendEvent(picker.prompt, override)
    assert override.isAccepted()
    assert picker.selection_id() == "2"
    press = QKeyEvent(QEvent.KeyPress, Qt.Key_P, Qt.ControlModifier)
    QCoreApplication.sendEvent(picker.prompt, press)
    assert picker.selection_id() == "1"


def test_stale_and_empty_results_cannot_accept(qtbot):
    picker = dialog(qtbot)
    accepted = []
    picker.accepted_entry.connect(accepted.append)
    picker.set_results(results())
    qtbot.keyClicks(picker.prompt, "changed")
    qtbot.keyClick(picker.prompt, Qt.Key_Return)
    assert accepted == []
    assert picker.isVisible()
    picker.set_results(results(0))
    qtbot.keyClick(picker.prompt, Qt.Key_Return)
    assert accepted == []
    picker.set_results(results(1))
    qtbot.keyClick(picker.prompt, Qt.Key_Return)
    assert [entry.id for entry in accepted] == ["0"]
    # The view emits a value; only its controller owns finishing the session.
    assert picker.isVisible()


def test_source_restore_and_jump_marker_do_not_reset_rows(qtbot):
    picker = dialog(qtbot)
    sources = []
    resets = []
    picker.source_changed.connect(sources.append)
    picker.model.modelReset.connect(lambda: resets.append(True))
    picker.set_source("jumps")
    picker.set_query("text")
    picker.set_results(results(), selected_id="1")
    assert not sources
    picker.set_current_id("2")
    assert len(resets) == 1
    assert picker.selection_id() == "1"
    assert picker.query() == "text"
    assert "immediately" in picker.help_label.text()
    moves = []
    picker.navigate_history.connect(moves.append)
    qtbot.keyClick(picker.prompt, Qt.Key_O, Qt.ControlModifier)
    qtbot.keyClick(picker.prompt, Qt.Key_I, Qt.ControlModifier)
    assert moves == [-1, 1]
    picker.set_source("files")
    qtbot.keyClick(picker.prompt, Qt.Key_O, Qt.ControlModifier)
    assert moves == [-1, 1]


def test_click_preserves_prompt_focus_and_geometry(qtbot):
    picker = dialog(qtbot)
    picker.set_results(results(40))
    original = picker.geometry()
    index = picker.model.index(35)
    picker.list_view.scrollTo(index)
    qtbot.mouseClick(
        picker.list_view.viewport(),
        Qt.LeftButton,
        pos=picker.list_view.visualRect(index).center(),
    )
    assert picker.prompt.hasFocus()
    assert picker.selection_id() == "35"
    picker.set_results(results(1))
    assert picker.geometry() == original


def test_preview_keeps_source_document_and_uses_original_line(qtbot):
    editor = QPlainTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("original text")
    cursor = editor.textCursor()
    cursor.setPosition(5)
    editor.setTextCursor(cursor)
    before = (
        editor.toPlainText(),
        editor.document().revision(),
        editor.textCursor().position(),
    )
    picker = dialog(qtbot, editor=editor)
    picker.set_preview(
        ContentPreview("one\ntwo\nthree", 81, 82, "bounded excerpt", "py")
    )
    assert picker.preview.document() is not editor.document()
    assert picker.preview.isReadOnly()
    assert not picker.preview.isUndoRedoEnabled()
    assert picker.preview.textCursor().blockNumber() == 1
    assert picker.preview.first_line == 81
    assert picker.preview_message.text() == "bounded excerpt"
    assert before == (
        editor.toPlainText(),
        editor.document().revision(),
        editor.textCursor().position(),
    )


def test_preview_scroll_keys_never_change_results(qtbot):
    picker = dialog(qtbot)
    picker.set_results(results())
    picker.set_preview(ContentPreview("\n".join(map(str, range(600)))))
    scrollbar = picker.preview.verticalScrollBar()
    scrollbar.setValue(0)
    qtbot.keyClick(picker.prompt, Qt.Key_D, Qt.ControlModifier)
    assert scrollbar.value() > 0
    assert picker.selection_id() == "2"
    picker.preview_button.setChecked(False)
    position = scrollbar.value()
    qtbot.keyClick(picker.prompt, Qt.Key_D, Qt.ControlModifier)
    assert scrollbar.value() == position
    assert "unavailable" in picker.help_label.text()
    picker.preview_button.setChecked(True)
    assert "scroll preview" in picker.help_label.text()


def test_preview_reuses_one_highlighter_across_selections_and_languages(qtbot):
    picker = dialog(qtbot)
    document = picker.preview.document()

    def attached_highlighters():
        return [
            highlighter
            for highlighter in document.findChildren(QSyntaxHighlighter)
            if highlighter.document() is document
        ]

    picker.set_preview(ContentPreview("def first():\n    pass", language="py"))
    first = attached_highlighters()
    assert len(first) == 1
    for _ in range(10):
        picker.set_preview(ContentPreview("def next():\n    pass", language="py"))
        assert attached_highlighters() == first

    picker.set_preview(ContentPreview("+added\n-removed", language="diff"))
    diff = attached_highlighters()
    assert len(diff) == 1
    picker.set_preview(ContentPreview("+another", language="patch"))
    assert attached_highlighters() == diff
    picker.set_preview(ContentPreview("def back():\n    pass", language="py"))
    assert attached_highlighters() == first
    picker.set_preview(ContentPreview("plain text", language="txt"))
    assert len(attached_highlighters()) == len(first)


def test_live_palette_does_not_reset_query_selection_or_preview(qtbot):
    picker = dialog(qtbot)
    picker.set_query("query")
    picker.set_results(results(), selected_id="1")
    picker.set_preview(ContentPreview("\n".join(map(str, range(600))), 40, 65))
    picker.preview.verticalScrollBar().setValue(20)
    scroll = picker.preview.verticalScrollBar().value()
    palette = QPalette(picker.palette())
    palette.setColor(QPalette.Base, QColor("#f8f8f8"))
    palette.setColor(QPalette.Text, QColor("#222222"))
    picker.setPalette(palette)
    QCoreApplication.sendEvent(picker, QEvent(QEvent.StyleChange))
    assert "#f8f8f8" in picker.styleSheet()
    assert picker.query() == "query"
    assert picker.selection_id() == "1"
    assert picker.preview.verticalScrollBar().value() == scroll


def test_small_parent_bounds_and_vertical_fallback(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(420, 340)
    parent.show()
    picker = dialog(qtbot, parent=parent)
    assert picker.width() <= parent.width()
    assert picker.height() <= parent.height()
    assert picker.splitter.orientation() == Qt.Vertical


def test_commit_detail_source_and_paging_controls(qtbot):
    picker = dialog(qtbot)
    loaded = []
    picker.load_more_requested.connect(lambda: loaded.append(True))
    picker.set_load_more_enabled(True)
    qtbot.mouseClick(picker.load_more_button, Qt.LeftButton)
    assert loaded == [True]
    picker.set_source("git_files")
    assert picker.source_selector.currentText() == "Commit files"
    picker.set_source("git_log")
    assert picker.source_selector.findData("git_files") < 0


@pytest.mark.parametrize("key", [Qt.Key_Return, Qt.Key_Escape])
def test_ime_composition_finishes_before_picker_accept_or_close(qtbot, key):
    picker = dialog(qtbot)
    picker.set_results(results())
    accepted = []
    picker.accepted_entry.connect(accepted.append)
    QCoreApplication.sendEvent(picker.prompt, QInputMethodEvent("한글", []))
    assert picker.prompt.is_composing
    QCoreApplication.sendEvent(
        picker.prompt, QKeyEvent(QEvent.ShortcutOverride, key, Qt.NoModifier)
    )
    qtbot.keyClick(picker.prompt, key)
    assert picker.isVisible()
    assert accepted == []
    # The native IME ends preedit with an empty input-method event. The next
    # Enter belongs to the picker rather than the earlier composition.
    QCoreApplication.sendEvent(picker.prompt, QInputMethodEvent("", []))
    assert not picker.prompt.is_composing
    qtbot.keyClick(picker.prompt, Qt.Key_Return)
    assert [entry.id for entry in accepted] == ["2"]


def test_result_publication_emits_one_selection(qtbot):
    picker = dialog(qtbot)
    selections = []
    picker.selection_changed.connect(selections.append)
    picker.set_results(results())
    assert len(selections) == 1
    assert selections[0].id == "2"


def test_explicit_history_view_rebinds_preview_font(qtbot):
    from qtpy.QtGui import QFont
    from qtpy.QtWidgets import QPlainTextEdit

    previous = QPlainTextEdit()
    current = QPlainTextEdit()
    qtbot.addWidget(previous)
    qtbot.addWidget(current)
    current.setFont(QFont("Courier New", 18))
    picker = dialog(qtbot, editor=previous)
    picker.set_preview(ContentPreview("source text"))
    picker.set_editor(current)
    assert picker.preview.font().pointSize() == 18
    assert picker.preview.toPlainText() == "source text"


@pytest.mark.parametrize("source", ["git_log", "git_file_log", "git_stash"])
def test_git_sources_describe_their_default_action(qtbot, source):
    picker = dialog(qtbot)
    picker.set_source(source)
    assert picker.source_selector.findData(source) >= 0
    action = "apply stash" if source == "git_stash" else "checkout commit"
    assert action in picker.help_label.text()


def test_focused_toolbar_enter_activates_control_without_accepting_result(qtbot):
    picker = dialog(qtbot)
    picker.set_results(results())
    accepted, refreshed = [], []
    picker.accepted_entry.connect(accepted.append)
    picker.refresh_requested.connect(lambda: refreshed.append(True))
    picker.refresh_button.setFocus()
    qtbot.keyClick(picker.refresh_button, Qt.Key_Return)
    assert refreshed == [True]
    assert accepted == []
    picker.preview_button.setFocus()
    qtbot.keyClick(picker.preview_button, Qt.Key_Return)
    assert not picker.preview_button.isChecked()
    assert accepted == []


@pytest.mark.parametrize("source", ["git_log", "git_file_log"])
@pytest.mark.parametrize(
    "key, action",
    [(Qt.Key_M, "reset_mixed"), (Qt.Key_S, "reset_soft"), (Qt.Key_H, "reset_hard")],
)
def test_commit_reset_prefix_executes_once_without_changing_query(
    qtbot, source, key, action
):
    picker = dialog(qtbot)
    picker.set_source(source)
    picker.set_results(results())
    actions = []
    picker.action_requested.connect(
        lambda action, entry: actions.append((action, entry.id))
    )
    reserved = QKeyEvent(QEvent.ShortcutOverride, Qt.Key_R, Qt.ControlModifier)
    QCoreApplication.sendEvent(picker.prompt, reserved)
    assert reserved.isAccepted()
    assert not actions
    qtbot.keyClick(picker.prompt, Qt.Key_R, Qt.ControlModifier)
    assert "m mixed" in picker.help_label.text()
    qtbot.keyClick(picker.prompt, key)
    assert actions == [(action, "2")]
    assert picker.query() == ""
    assert "m mixed" not in picker.help_label.text()


@pytest.mark.parametrize(
    "key, action",
    [
        (Qt.Key_T, "branch_track"),
        (Qt.Key_A, "branch_create"),
        (Qt.Key_D, "branch_delete"),
        (Qt.Key_R, "branch_rebase"),
        (Qt.Key_Y, "branch_merge"),
    ],
)
def test_branch_keys_emit_selected_action_once(qtbot, key, action):
    picker = dialog(qtbot)
    picker.set_source("git_branches")
    picker.set_results(results())
    picker.set_preview(ContentPreview("\n".join(map(str, range(600)))))
    scrollbar = picker.preview.verticalScrollBar()
    before = scrollbar.value()
    actions = []
    picker.action_requested.connect(
        lambda action, entry: actions.append((action, entry.id))
    )
    reserve = QKeyEvent(QEvent.ShortcutOverride, key, Qt.ControlModifier)
    QCoreApplication.sendEvent(picker.prompt, reserve)
    assert reserve.isAccepted()
    assert not actions
    qtbot.keyClick(picker.prompt, key, Qt.ControlModifier)
    assert actions == [(action, "2")]
    assert scrollbar.value() == before
    assert "Ctrl+D: delete" in picker.help_label.text()


def test_status_tab_stages_without_moving_focus_or_row(qtbot):
    picker = dialog(qtbot)
    picker.set_source("git_status")
    picker.set_results(results())
    actions = []
    picker.action_requested.connect(
        lambda action, entry: actions.append((action, entry.id))
    )
    qtbot.keyClick(picker.prompt, Qt.Key_Tab)
    assert actions == [("stage_toggle", "2")]
    assert picker.prompt.hasFocus()
    assert picker.selection_id() == "2"


def test_git_action_menu_and_changed_files_are_available_only_for_valid_selection(
    qtbot,
):
    picker = dialog(qtbot)
    picker.set_source("git_log")
    assert picker.actions_button.isVisible()
    assert not picker.actions_button.isEnabled()
    picker.set_results(results())
    actions = []
    picker.action_requested.connect(
        lambda action, entry: actions.append((action, entry.id))
    )
    assert picker.actions_button.isEnabled()
    menu = {action.data(): action for action in picker.actions_menu.actions()}
    assert set(menu) == {
        "checkout",
        "commit_files",
        "reset_mixed",
        "reset_soft",
        "reset_hard",
    }
    menu["reset_soft"].trigger()
    qtbot.keyClick(picker.prompt, Qt.Key_L, Qt.ControlModifier)
    assert actions == [("reset_soft", "2"), ("commit_files", "2")]
    picker.prompt.setText("stale")
    assert not picker.actions_button.isEnabled()
    menu["reset_hard"].trigger()
    assert actions == [("reset_soft", "2"), ("commit_files", "2")]


def test_mutation_busy_keeps_query_close_but_blocks_git_actions(qtbot):
    picker = dialog(qtbot)
    picker.set_source("git_status")
    picker.set_results(results())
    actions, accepted = [], []
    picker.action_requested.connect(lambda action, entry: actions.append(action))
    picker.accepted_entry.connect(accepted.append)
    picker.set_actions_busy(True)
    assert "Git operation running" in picker.help_label.text()
    assert not picker.actions_button.isEnabled()
    qtbot.keyClick(picker.prompt, Qt.Key_Tab)
    qtbot.keyClick(picker.prompt, Qt.Key_Return)
    assert not actions and not accepted
    qtbot.keyClicks(picker.prompt, "draft")
    assert picker.query() == "draft"
    qtbot.keyClick(picker.prompt, Qt.Key_Escape)
    assert not picker.isVisible()


@pytest.mark.parametrize("cancel", ["escape", "query", "source", "selection"])
def test_pending_reset_cancels_on_context_changes(qtbot, cancel):
    picker = dialog(qtbot)
    picker.set_source("git_log")
    picker.set_results(results())
    actions = []
    picker.action_requested.connect(lambda action, entry: actions.append(action))
    qtbot.keyClick(picker.prompt, Qt.Key_R, Qt.ControlModifier)
    assert picker._reset_pending
    if cancel == "escape":
        qtbot.keyClick(picker.prompt, Qt.Key_Escape)
        assert picker.isVisible()
    elif cancel == "query":
        picker.prompt.setText("query")
    elif cancel == "source":
        picker.set_source("git_stash")
    else:
        picker.select_id("1")
    assert not picker._reset_pending
    qtbot.keyClick(picker.prompt, Qt.Key_H)
    assert not actions


def test_git_action_buttons_do_not_overlap_in_narrow_header(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(420, 340)
    parent.show()
    picker = dialog(qtbot, parent=parent)
    picker.set_source("git_log")
    picker.set_load_more_enabled(True)
    picker.set_results(results())
    QCoreApplication.processEvents()
    visible = [button for button in picker._toolbar_buttons if button.isVisible()]
    for left, right in zip(visible, visible[1:]):
        assert left.geometry().right() < right.geometry().left()
    for button in visible:
        bottom_right = button.mapTo(picker, button.rect().bottomRight())
        assert picker.rect().contains(bottom_right)


def test_branch_creation_remains_available_with_current_empty_results(qtbot):
    picker = dialog(qtbot)
    picker.set_source("git_branches")
    picker.set_results(results(0))
    actions = []
    picker.action_requested.connect(
        lambda action, entry: actions.append((action, entry))
    )
    menu = {action.data(): action for action in picker.actions_menu.actions()}
    assert picker.actions_button.isEnabled()
    assert {name for name, action in menu.items() if action.isEnabled()} == {
        "branch_create"
    }
    qtbot.keyClick(picker.prompt, Qt.Key_A, Qt.ControlModifier)
    assert actions == [("branch_create", None)]
    qtbot.keyClick(picker.prompt, Qt.Key_D, Qt.ControlModifier)
    assert actions == [("branch_create", None)]
    picker.set_actions_busy(True)
    qtbot.keyClick(picker.prompt, Qt.Key_A, Qt.ControlModifier)
    assert not picker.actions_button.isEnabled()
    assert actions == [("branch_create", None)]
    picker.set_actions_busy(False)
    picker.prompt.setText("pending search")
    qtbot.keyClick(picker.prompt, Qt.Key_A, Qt.ControlModifier)
    assert not picker.actions_button.isEnabled()
    assert actions == [("branch_create", None)]
