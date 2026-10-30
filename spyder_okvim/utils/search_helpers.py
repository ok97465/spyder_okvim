from __future__ import annotations

from qtpy.QtCore import QRegularExpression

from spyder.config.manager import CONF

from spyder_okvim.spyder.config import CONF_SECTION


def resolve_ignorecase(text: str, override: bool | None = None) -> bool:
    """Resolve search case settings without modifying global configuration."""
    if override is not None:
        return override
    ignorecase = CONF.get(CONF_SECTION, "ignorecase")
    smartcase = CONF.get(CONF_SECTION, "smartcase")
    return ignorecase and not (smartcase and text.lower() != text)


def compile_pattern(text: str, ignorecase: bool) -> QRegularExpression:
    """Create the expression shared by search and Ex substitution."""
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
