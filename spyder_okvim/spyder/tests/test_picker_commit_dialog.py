"""Commit composition preserves drafts and requires an explicit valid submit."""

from unittest.mock import Mock

import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QInputMethodEvent, QKeyEvent
from qtpy.QtWidgets import QApplication, QDialog, QLabel, QWidget

from spyder_okvim.spyder.picker_commit_dialog import CommitMessageDialog


def composer(qtbot, **kwargs):
    values = dict(branch="refs/heads/main", summary=" file.py | 2 +-\n 1 file changed")
    values.update(kwargs)
    widget = CommitMessageDialog(**values)
    qtbot.addWidget(widget)
    widget.show()
    widget.activateWindow()
    widget.message_edit.setFocus()
    QCoreApplication.processEvents()
    return widget


def test_multiline_unicode_draft_and_accessible_read_only_summary(qtbot):
    message = "수정: 한글 메시지\n\nDetailed body with 'quotes' and $shell text.\n"
    dialog = composer(qtbot, message=message)
    assert dialog.message() == message
    assert dialog.commit_button.isEnabled()
    assert dialog.summary_view.isReadOnly()
    assert "file.py" in dialog.summary_view.toPlainText()
    assert dialog.summary_view.accessibleName() == "Staged changes summary"
    assert "all staged changes" in dialog.summary_view.accessibleDescription()
    assert dialog.message_edit.accessibleName() == "Commit message"
    assert dialog.branch_label.text() == "Branch: main"
    assert dialog.message_edit.textCursor().position() == len(message)


def test_amend_composer_explains_message_only_edit_and_submits(qtbot):
    dialog = composer(qtbot, amend=True, message="Existing subject\n\nExisting body")
    assert dialog.windowTitle() == "Edit HEAD commit message"
    assert dialog.summary_view.accessibleName() == "HEAD commit summary"
    assert dialog.commit_button.text() == "Save message"
    assert (
        "saves the HEAD commit message" in dialog.message_edit.accessibleDescription()
    )
    labels = dialog.findChildren(QLabel)
    assert any("commit ID will change" in label.text() for label in labels)
    assert any("Staged changes" in label.accessibleDescription() for label in labels)
    qtbot.keyClick(dialog.message_edit, Qt.Key_Return, Qt.ControlModifier)
    assert dialog.result() == QDialog.Accepted


@pytest.mark.parametrize("message", ["", " \t\n", "valid\0invalid"])
def test_blank_and_nul_messages_cannot_commit(qtbot, message):
    dialog = composer(qtbot, message=message)
    accepted = Mock()
    dialog.accepted.connect(accepted)
    assert not dialog.commit_button.isEnabled()
    qtbot.keyClick(dialog.message_edit, Qt.Key_Return, Qt.ControlModifier)
    dialog.accept()
    assert dialog.isVisible()
    accepted.assert_not_called()


def test_plain_enter_adds_newline_without_committing(qtbot):
    dialog = composer(qtbot)
    qtbot.keyClicks(dialog.message_edit, "Summary")
    qtbot.keyClick(dialog.message_edit, Qt.Key_Return)
    qtbot.keyClicks(dialog.message_edit, "Body")
    assert dialog.message() == "Summary\nBody"
    assert dialog.isVisible()


@pytest.mark.parametrize("key", [Qt.Key_Return, Qt.Key_Enter])
def test_control_enter_submits_once_and_reserves_shortcut(qtbot, key):
    dialog = composer(qtbot, message="A staged commit")
    accepted = Mock()
    dialog.accepted.connect(accepted)
    override = QKeyEvent(QEvent.ShortcutOverride, key, Qt.ControlModifier)
    QCoreApplication.sendEvent(dialog.message_edit, override)
    assert override.isAccepted()
    accepted.assert_not_called()
    qtbot.keyClick(dialog.message_edit, key, Qt.ControlModifier)
    assert dialog.result() == QDialog.Accepted
    accepted.assert_called_once_with()
    dialog.accept()
    accepted.assert_called_once_with()


def test_escape_cancels_and_keeps_draft(qtbot):
    dialog = composer(qtbot, message="Keep this draft\n\nBody")
    rejected = Mock()
    dialog.rejected.connect(rejected)
    qtbot.keyClick(dialog.message_edit, Qt.Key_Escape)
    assert dialog.result() == QDialog.Rejected
    assert dialog.message() == "Keep this draft\n\nBody"
    rejected.assert_called_once_with()


def test_control_enter_finishes_ime_before_submitting(qtbot, monkeypatch):
    dialog = composer(qtbot, message="Summary ")
    QCoreApplication.sendEvent(dialog.message_edit, QInputMethodEvent("한", []))
    assert dialog.message_edit.is_composing

    def commit_composition():
        event = QInputMethodEvent()
        event.setCommitString("한")
        QCoreApplication.sendEvent(dialog.message_edit, event)

    commit = Mock(side_effect=commit_composition)
    monkeypatch.setattr(QApplication.inputMethod(), "commit", commit)
    qtbot.keyClick(dialog.message_edit, Qt.Key_Return, Qt.ControlModifier)
    commit.assert_called_once_with()
    assert dialog.isVisible()
    assert not dialog.message_edit.is_composing
    assert "한" in dialog.message()
    qtbot.keyClick(dialog.message_edit, Qt.Key_Return, Qt.ControlModifier)
    assert dialog.result() == QDialog.Accepted


def test_escape_cancels_ime_before_cancelling_dialog(qtbot, monkeypatch):
    dialog = composer(qtbot, message="Saved draft")
    QCoreApplication.sendEvent(dialog.message_edit, QInputMethodEvent("한", []))
    reset = Mock()
    monkeypatch.setattr(QApplication.inputMethod(), "reset", reset)
    qtbot.keyClick(dialog.message_edit, Qt.Key_Escape)
    reset.assert_called_once_with()
    assert dialog.isVisible()
    assert not dialog.message_edit.is_composing
    assert dialog.message() == "Saved draft"
    qtbot.keyClick(dialog.message_edit, Qt.Key_Escape)
    assert not dialog.isVisible()


def test_parent_appearance_and_small_layout(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(400, 360)
    font = parent.font()
    font.setPointSize(13)
    parent.setFont(font)
    dialog = composer(qtbot, parent=parent, branch="", summary="x\n" * 200)
    assert dialog.font() == parent.font()
    assert dialog.palette() == parent.palette()
    assert "detached HEAD" in dialog.branch_label.text()
    assert dialog.width() <= parent.width()
    assert dialog.height() <= parent.height()
    assert dialog.summary_view.verticalScrollBar().maximum() > 0


@pytest.mark.parametrize("resize_before_show", [False, True])
def test_compact_layout_reserves_multiline_message_space(qtbot, resize_before_show):
    parent = QWidget()
    qtbot.addWidget(parent)
    font = parent.font()
    font.setPointSize(12)
    parent.setFont(font)
    dialog = CommitMessageDialog(
        parent,
        branch="main",
        message="Summary\n\nDetails",
        summary=" file.py | 2 +-\n" * 20,
    )
    qtbot.addWidget(dialog)
    if not resize_before_show:
        dialog.show()
        QCoreApplication.processEvents()
    dialog.resize(360, 320)
    dialog.show()
    QCoreApplication.processEvents()
    assert dialog.message_edit.height() >= 60
    assert dialog.summary_view.height() > 0
    labels = dialog.findChildren(QLabel)
    scope = next(label for label in labels if label.text().startswith("Only staged"))
    hint = next(label for label in labels if label.text().startswith("Ctrl+Enter"))
    assert scope.text() == "Only staged changes are included."
    assert hint.text() == "Ctrl+Enter: commit · Esc: cancel"
    assert "Enter adds a line" in dialog.message_edit.accessibleDescription()
    for label in labels:
        assert label.height() >= label.heightForWidth(label.width())
    layout = dialog.layout()
    widgets = [layout.itemAt(index).widget() for index in range(layout.count())]
    for previous, following in zip(widgets, widgets[1:]):
        assert previous.geometry().bottom() < following.geometry().top()
