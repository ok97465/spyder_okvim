"""Public Vim values and services, loaded only when requested.

Pure model imports never load Qt, Spyder or editor services. The historical
package exports stay available for consumers while implementation imports can
name their owning modules directly.
"""

# Standard Libraries
from importlib import import_module

_EXPORTS = {
    "VimState": "state",
    "FindInfo": "state",
    "InputCmdInfo": "state",
    "DotCmdInfo": "state",
    "KeyInfo": "state",
    "InputSource": "state",
    "RegisterInfo": "state",
    "SearchInfo": "search",
    "MacroManager": "macro",
    "InlineLabel": "label",
    "VimCursor": "cursor",
    "VimStatus": "status",
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    """Resolve a historical public export without eager UI imports."""
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value
