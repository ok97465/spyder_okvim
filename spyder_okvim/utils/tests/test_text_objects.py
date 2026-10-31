"""Text-object contracts independent of Vim state and Spyder editor services."""

# Third Party Libraries
import pytest
from qtpy.QtGui import QTextCursor, QTextDocument

# Project Libraries
from spyder_okvim.utils.text_objects import TextObjects


def selected_text(document, motion):
    """Read a calculated half-open range without altering its input cursor."""
    selection = QTextCursor(document)
    selection.setPosition(motion.sel_start)
    selection.setPosition(motion.sel_end, QTextCursor.KeepAnchor)
    return selection.selectedText().replace("\u2029", "\n")


@pytest.mark.parametrize(
    "text,position,method,args,expected",
    [
        ('before "value" after', 10, "inner_quote", ('"',), "value"),
        ("before (outer (inner)) after", 17, "around_bracket", (1, "("), "(inner)"),
        ("one.two   next", 2, "around_WORD", (1,), "one.two   "),
        ("first\nline\n\nsecond", 2, "inner_paragraph", (1,), "first\nline"),
        ("😀 `value` after", 5, "inner_quote", ("`",), "value"),
    ],
)
def test_text_objects_leave_supplied_cursor_and_document_unchanged(
    qapp, text, position, method, args, expected
):
    """A caller can provide its actual cursor without granting editing access."""
    document = QTextDocument(text)
    cursor = QTextCursor(document)
    cursor.setPosition(position)
    original_position = cursor.position()
    original_anchor = cursor.anchor()
    original_revision = document.revision()
    original_undo = document.isUndoAvailable()
    objects = TextObjects(lambda: cursor)

    motion = getattr(objects, method)(*args)

    assert selected_text(document, motion) == expected
    assert (cursor.position(), cursor.anchor()) == (original_position, original_anchor)
    assert document.toPlainText() == text
    assert document.revision() == original_revision
    assert document.isUndoAvailable() == original_undo


def test_text_object_provider_follows_current_document(qapp):
    """One calculator resolves each request against the provider's current view."""
    first = QTextDocument('"first"')
    second = QTextDocument('"second"')
    current_cursor = QTextCursor(first)
    objects = TextObjects(lambda: current_cursor)

    first_motion = objects.inner_quote('"')
    current_cursor = QTextCursor(second)
    second_motion = objects.inner_quote('"')

    assert selected_text(first, first_motion) == "first"
    assert selected_text(second, second_motion) == "second"
