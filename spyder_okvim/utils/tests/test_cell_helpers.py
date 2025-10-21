# -*- coding: utf-8 -*-
"""Tests for the cell helper utilities."""

# Third Party Libraries
from qtpy.QtGui import QTextDocument

# Project Libraries
from spyder_okvim.utils.cell_helpers import get_document_cells


def _document_end(document: QTextDocument) -> int:
    """Return the exclusive end position of ``document``."""
    last_block = document.lastBlock()
    return last_block.position() + last_block.length()


def _set_editor_text(editor, qtbot, text: str, expected_cells: int) -> None:
    """Set editor text and wait until cell list matches ``expected_cells``."""
    editor.set_text(text)
    editor.highlighter.rehighlight()

    def _cells_ready() -> bool:
        return len(editor.get_cell_list()) == expected_cells

    qtbot.waitUntil(_cells_ready, timeout=2000)


def test_get_document_cells_with_headers(vim_bot):
    """Ensure cell regions are extracted from explicit headers."""
    _, _, editor, _, qtbot = vim_bot

    original_text = editor.toPlainText()
    original_cells = len(editor.get_cell_list())

    try:
        text = (
            "# %% Cell A\n"
            "a = 1\n"
            "\n"
            "# %%\n"
            "b = 2\n"
            "# %%% Subcell\n"
            "c = 3\n"
        )
        _set_editor_text(editor, qtbot, text, expected_cells=3)

        regions = get_document_cells(editor)

        assert [region.name for region in regions] == [
            "Cell A",
            "Unnamed Cell",
            "Subcell",
        ]
        assert [region.start_line for region in regions] == [0, 3, 5]
        assert [region.level for region in regions] == [0, 0, 1]
        assert all(region.has_header for region in regions)
        assert regions[-1].end_line == editor.document().blockCount() - 1
    finally:
        _set_editor_text(editor, qtbot, original_text, expected_cells=original_cells)


def test_get_document_cells_without_headers(vim_bot):
    """The entire file is treated as a single region when no headers exist."""
    _, _, editor, _, qtbot = vim_bot

    original_text = editor.toPlainText()
    original_cells = len(editor.get_cell_list())

    try:
        text = "print('hello')\nprint('world')\n"
        _set_editor_text(editor, qtbot, text, expected_cells=0)

        regions = get_document_cells(editor)
        assert len(regions) == 1

        region = regions[0]
        assert region.name is None
        assert region.level == 0
        assert region.start_line == 0
        assert region.end_line == editor.document().blockCount() - 1
        assert region.start_position == 0
        assert region.end_position == _document_end(editor.document())
        assert region.has_header is False
    finally:
        _set_editor_text(editor, qtbot, original_text, expected_cells=original_cells)
