"""A focused composer for staged commits and HEAD message edits."""

from __future__ import annotations

from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QInputMethodEvent, QTextCursor
from qtpy.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLayout,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
)


class _MessageEditor(QPlainTextEdit):
    """Track preedit separately from the message that Git would receive."""

    is_composing = False

    def inputMethodEvent(self, event):
        self.is_composing = bool(event.preeditString())
        super().inputMethodEvent(event)


class CommitMessageDialog(QDialog):
    """Compose a multiline message without changing what is staged."""

    def __init__(
        self, parent=None, *, branch: str, summary: str, message: str = "", amend=False
    ):
        super().__init__(parent)
        self._submitted = False
        title = "Edit HEAD commit message" if amend else "Commit staged changes"
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setMinimumSize(0, 0)
        if parent is not None:
            self.setPalette(parent.palette())
            self.setFont(parent.font())

        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetNoConstraint)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        branch_name = branch.removeprefix("refs/heads/") or "detached HEAD"
        self.branch_label = QLabel(f"Branch: {branch_name}", self)
        self.branch_label.setTextFormat(Qt.PlainText)
        self.branch_label.setWordWrap(True)
        self.branch_label.setAccessibleName("Commit branch")
        layout.addWidget(self.branch_label)

        scope_label = QLabel(
            (
                "Only the HEAD commit message changes. The commit ID will change."
                if amend
                else "Only staged changes are included."
            ),
            self,
        )
        scope_label.setAccessibleDescription(
            "Staged changes, working files and unsaved buffers are kept."
            if amend
            else "Unstaged changes and unsaved buffers are not included in the commit."
        )
        scope_label.setWordWrap(True)
        layout.addWidget(scope_label)

        summary_title = "Commit being edited" if amend else "Staged changes"
        summary_label = QLabel(summary_title, self)
        self.summary_view = QPlainTextEdit(self)
        self.summary_view.setReadOnly(True)
        self.summary_view.setPlainText(summary)
        self.summary_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.summary_view.setMinimumSize(0, 0)
        self.summary_view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.summary_view.setAccessibleName(
            "HEAD commit summary" if amend else "Staged changes summary"
        )
        self.summary_view.setAccessibleDescription(
            "Read-only identity of the HEAD commit whose message will be changed."
            if amend
            else "Read-only summary of all staged changes included in this commit."
        )
        summary_label.setBuddy(self.summary_view)
        layout.addWidget(summary_label)
        layout.addWidget(self.summary_view, 1)

        message_label = QLabel("Commit message", self)
        self.message_edit = _MessageEditor(self)
        self.message_edit.setMinimumSize(0, 60)
        self.message_edit.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.message_edit.setPlaceholderText("Summary\n\nOptional description")
        self.message_edit.setAccessibleName("Commit message")
        self.message_edit.setAccessibleDescription(
            "Enter a summary and optional description. "
            + (
                "Enter adds a line; Ctrl+Enter saves the HEAD commit message."
                if amend
                else "Enter adds a line; Ctrl+Enter commits staged changes."
            )
        )
        message_label.setBuddy(self.message_edit)
        layout.addWidget(message_label)
        layout.addWidget(self.message_edit, 2)

        hint = QLabel(
            (
                "Ctrl+Enter: save message · Esc: cancel"
                if amend
                else "Ctrl+Enter: commit · Esc: cancel"
            ),
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        for label in (
            self.branch_label,
            scope_label,
            summary_label,
            message_label,
            hint,
        ):
            policy = label.sizePolicy()
            policy.setVerticalPolicy(QSizePolicy.Fixed)
            label.setSizePolicy(policy)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel, self)
        self.commit_button = buttons.addButton(
            "Save message" if amend else "Commit", QDialogButtonBox.AcceptRole
        )
        self.commit_button.setAccessibleName(title)
        for button in buttons.buttons():
            button.setAutoDefault(False)
            button.setDefault(False)
            button.installEventFilter(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.message_edit.textChanged.connect(self._update_commit_enabled)
        self.message_edit.installEventFilter(self)
        self.summary_view.installEventFilter(self)
        self.message_edit.setPlainText(message)
        self.message_edit.moveCursor(QTextCursor.End)
        self._update_commit_enabled()
        self.setTabOrder(self.message_edit, self.commit_button)
        self.message_edit.setFocus(Qt.OtherFocusReason)

        width, height = 620, 480
        if parent is not None:
            width = min(width, max(320, parent.width() - 32))
            height = min(height, max(300, parent.height() - 32))
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, round(available.width() * 0.9))
            height = min(height, round(available.height() * 0.9))
        self.resize(width, height)

    def message(self):
        """Return the draft unchanged, including when the dialog was cancelled."""
        return self.message_edit.toPlainText()

    def _update_commit_enabled(self):
        message = self.message()
        self.commit_button.setEnabled(bool(message.strip()) and "\0" not in message)

    def accept(self):
        if self._submitted:
            return
        if self.message_edit.is_composing:
            QApplication.inputMethod().commit()
            return
        self._update_commit_enabled()
        if self.commit_button.isEnabled():
            self._submitted = True
            super().accept()

    def _handle_key(self, event):
        if event.type() not in (QEvent.ShortcutOverride, QEvent.KeyPress):
            return False
        key, modifiers = event.key(), event.modifiers()
        enter = key in (Qt.Key_Return, Qt.Key_Enter)
        submit = enter and modifiers == Qt.ControlModifier
        cancel = key == Qt.Key_Escape and modifiers == Qt.NoModifier
        compose_enter = (
            enter and modifiers == Qt.NoModifier and self.message_edit.is_composing
        )
        if not (submit or cancel or compose_enter):
            return False
        event.accept()
        if event.type() == QEvent.ShortcutOverride or event.isAutoRepeat():
            return True
        if self.message_edit.is_composing:
            if cancel:
                QApplication.inputMethod().reset()
                self.message_edit.inputMethodEvent(QInputMethodEvent())
            else:
                QApplication.inputMethod().commit()
        elif cancel:
            self.reject()
        elif submit:
            self.accept()
        return True

    def eventFilter(self, watched, event):
        if self._handle_key(event):
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if not self._handle_key(event):
            super().keyPressEvent(event)
