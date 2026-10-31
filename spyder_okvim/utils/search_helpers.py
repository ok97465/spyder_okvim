"""Explicit search-case policy and Qt matching with UTF-16 offsets."""

from __future__ import annotations

# Standard Libraries
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Third Party Libraries
    from qtpy.QtCore import QRegularExpression


def resolve_ignorecase(
    text: str,
    override: bool | None = None,
    *,
    ignorecase: bool = True,
    smartcase: bool = True,
) -> bool:
    """Resolve explicit case options without reading global configuration.

    A substitution's final i/I flag overrides both options. Otherwise smartcase
    disables ignorecase when the pattern contains an uppercase character.
    """
    if override is not None:
        return override
    return ignorecase and not (smartcase and text.lower() != text)


def compile_pattern(text: str, ignorecase: bool) -> QRegularExpression:
    """Create the expression shared by search and Ex substitution."""
    # Third Party Libraries
    from qtpy.QtCore import QRegularExpression

    pattern = QRegularExpression(text)
    if ignorecase:
        pattern.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
    return pattern


def iter_block_matches(pattern, text: str, global_matches: bool = True):
    """Yield original Qt matches with UTF-16 offsets, including empty matches.

    Normalize NBSP for matching, as QTextDocument.find does. Consumers that
    expand captures should obtain their text from the unmodified paragraph.
    Qt's iterator owns empty-match advancement and same-start match ordering.
    """
    text = text.replace("\u00a0", " ")
    if global_matches:
        matches = pattern.globalMatch(text)
        while matches.hasNext():
            yield matches.next()
    else:
        match = pattern.match(text)
        if match.hasMatch():
            yield match
