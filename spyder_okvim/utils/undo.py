"""Group Vim changes with Spyder's undo stack or Qt's native undo history."""

# Standard Libraries
from contextlib import contextmanager
from dataclasses import replace

# Project Libraries
from spyder_okvim.utils.qtcompat import widget_is_deleted


def undo_owner(editor):
    """Find the editor that records a shared document's Spyder undo history.

    Spyder's cloned views replace their document after creating their own
    undo stack. The original document retains its owning editor through Qt's
    document-control parent, and only that editor records its changes.
    """
    document = editor.document()
    parent = document.parent()
    while parent is not None and not widget_is_deleted(parent):
        get_document = getattr(parent, "document", None)
        if (
            callable(get_document)
            and get_document() is document
            and getattr(parent, "undo_stack", None) is not None
        ):
            return parent
        parent = parent.parent()
    return editor


def editor_undo(editor):
    """Undo through the shared history and restore the active view's cursor."""
    owner = undo_owner(editor)
    owner.undo()
    if owner is not editor:
        editor.setTextCursor(owner.textCursor())


def editor_redo(editor):
    """Redo through the shared history and restore the active view's cursor."""
    owner = undo_owner(editor)
    owner.redo()
    if owner is not editor:
        editor.setTextCursor(owner.textCursor())


def _custom_undo(editor):
    """Return an undo owner's Spyder stack and pending-edit flush method."""
    stack = getattr(editor, "undo_stack", None)
    commit = getattr(editor, "_commit_pending_edit", None)
    if stack is not None and callable(commit):
        return stack, commit
    return None, None


def undo_available(editor):
    """Include pending Spyder edits when checking whether a change can undo."""
    stack, commit = _custom_undo(undo_owner(editor))
    if stack is not None:
        commit()
        return stack.can_undo()
    return editor.document().isUndoAvailable()


def notify_document_change(editor):
    """Let Spyder notify its language server from the recorded edit once."""
    stack, commit = _custom_undo(undo_owner(editor))
    if stack is not None:
        commit()
    else:
        editor.document_did_change()


class UndoGroup:
    """One Vim change, optionally delivered through several document events.

    Spyder 6.2 disables QTextDocument's undo history and records EditBlock
    values itself. Keep its document notifications intact, then consolidate
    the captured entries when the Vim change finishes. Native Qt editors use
    beginEditBlock/joinPreviousEditBlock for the same lifetime.
    """

    def __init__(self, editor, cursor=None, *, join_previous=False):
        self.editor = editor
        self.cursor = cursor if cursor is not None else editor.textCursor()
        self.join_previous = join_previous
        self._started = False
        self._stack = None
        self._commit = None
        self._base_index = None
        self._has_edit = False
        self._initial_revision = None
        self._owner = None
        self._before_cursors = None

    def _view_cursors(self):
        cursor = self.editor.textCursor()
        return {
            "main_cursor": (cursor.selectionStart(), cursor.selectionEnd()),
            "extra_cursors": tuple(
                (cursor.selectionStart(), cursor.selectionEnd())
                for cursor in getattr(self.editor, "extra_cursors", ())
            ),
        }

    def start(self):
        """Separate this change from earlier pending editor input."""
        if self._started:
            return
        self._started = True
        self._initial_revision = self.cursor.document().revision()
        self._owner = undo_owner(self.editor)
        if self._owner is not self.editor:
            self._before_cursors = self._view_cursors()
        self._stack, self._commit = _custom_undo(self._owner)
        if self._stack is not None:
            self._commit()
            self._base_index = self._stack.index
            if self.join_previous and self._stack.can_undo():
                self._base_index -= 1

    @contextmanager
    def edit_block(self):
        """Deliver one event while retaining the enclosing Vim undo group."""
        self.start()
        document = self.cursor.document()
        revision = document.revision()
        join = (
            self.join_previous or self._has_edit or revision != self._initial_revision
        )
        if join:
            self.cursor.joinPreviousEditBlock()
        else:
            self.cursor.beginEditBlock()
        try:
            yield
        finally:
            self.cursor.endEditBlock()
            self._has_edit = self._has_edit or document.revision() != revision

    def finish(self):
        """Commit one custom-stack entry without editing document contents."""
        if not self._started:
            return
        self._started = False
        if (
            self._stack is None
            or widget_is_deleted(self.editor)
            or widget_is_deleted(self._owner)
        ):
            return
        self._commit()
        count = self._stack.index - self._base_index
        if count <= 0 or (count == 1 and self._owner is self.editor):
            return
        edits = [self._stack.get_previous() for _ in range(count)]
        edits.reverse()
        combined = replace(
            edits[0],
            deltas=[delta for edit in edits for delta in edit.deltas],
            after=edits[-1].after,
            timestamp=edits[-1].timestamp,
        )
        if self._owner is not self.editor:
            before = combined.before
            if not self.join_previous:
                before = replace(before, **self._before_cursors)
            combined = replace(
                combined,
                before=before,
                after=replace(combined.after, **self._view_cursors()),
            )
        self._stack.push(combined)


@contextmanager
def undo_block(editor, cursor=None, *, join_previous=False):
    """Group an ordinary synchronous Vim edit into one undo entry."""
    group = UndoGroup(editor, cursor, join_previous=join_previous)
    try:
        with group.edit_block():
            yield
    finally:
        group.finish()
