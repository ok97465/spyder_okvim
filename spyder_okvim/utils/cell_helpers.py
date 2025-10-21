# -*- coding: utf-8 -*-
"""Utilities to inspect Spyder code cells."""

from __future__ import annotations

# Standard Libraries
from dataclasses import dataclass
from typing import TYPE_CHECKING

# Third Party Libraries
from qtpy.QtGui import QTextDocument

if TYPE_CHECKING:  # pragma: no cover - imports for typing only
    from spyder.plugins.editor.widgets.codeeditor.codeeditor import CodeEditor


@dataclass(frozen=True)
class CellRegion:
    """Describe a Spyder code cell within a document."""

    index: int
    name: str | None
    level: int
    header: str | None
    block_number: int
    start_line: int
    end_line: int
    start_position: int
    end_position: int

    @property
    def has_header(self) -> bool:
        """Return ``True`` when this region originates from a cell header."""
        return self.header is not None


def _document_end_position(document: QTextDocument) -> int:
    """Return the exclusive document end position."""
    last_block = document.lastBlock()
    return last_block.position() + last_block.length()


def _safe_block(document: QTextDocument, block_number: int):
    """Return a valid text block for ``block_number``."""
    block = document.findBlockByNumber(block_number)
    if block.isValid():
        return block
    return document.lastBlock()


def _fallback_region(document: QTextDocument) -> list[CellRegion]:
    """Return a single region covering the entire document."""
    end_line = document.lastBlock().blockNumber()
    return [
        CellRegion(
            index=0,
            name=None,
            level=0,
            header=None,
            block_number=0,
            start_line=0,
            end_line=end_line,
            start_position=0,
            end_position=_document_end_position(document),
        )
    ]


def get_document_cells(editor: CodeEditor | None) -> list[CellRegion]:
    """Return all cell regions defined in ``editor``.

    Args:
        editor: The active Spyder code editor instance.

    Returns:
        A list of :class:`CellRegion` objects ordered by their appearance in
        the document. When no explicit cell headers are present the whole file
        is returned as a single region.
    """
    if editor is None:
        return []

    document = editor.document()
    cell_entries = editor.get_cell_list()
    if not cell_entries:
        return _fallback_region(document)

    regions: list[CellRegion] = []
    total_blocks = document.blockCount()

    for idx, (block_number, oedata) in enumerate(cell_entries):
        start_block = _safe_block(document, block_number)
        start_line = start_block.blockNumber()
        start_pos = start_block.position()

        if idx + 1 < len(cell_entries):
            next_block_number = cell_entries[idx + 1][0]
            end_line = min(total_blocks - 1, max(block_number, next_block_number - 1))
            end_pos = _safe_block(document, next_block_number).position()
        else:
            end_line = total_blocks - 1
            end_pos = _document_end_position(document)

        name = getattr(oedata, "def_name", None) or None
        header = getattr(oedata, "text", None) or None
        level = getattr(oedata, "cell_level", 0)

        regions.append(
            CellRegion(
                index=idx,
                name=name,
                level=level,
                header=header,
                block_number=block_number,
                start_line=start_line,
                end_line=end_line,
                start_position=start_pos,
                end_position=end_pos,
            )
        )

    return regions

