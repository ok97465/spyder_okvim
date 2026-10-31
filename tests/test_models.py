"""Pure state/register contracts run without Qt, Spyder or GUI fixtures."""

# Standard Libraries
import subprocess
import sys
from pathlib import Path

# Third Party Libraries
import pytest

# Project Libraries
from spyder_okvim.utils.commandline import parse_path_argument
from spyder_okvim.utils.search_helpers import resolve_ignorecase
from spyder_okvim.vim.registers import Registers
from spyder_okvim.vim.state import (
    DotCmdInfo,
    InputCmdInfo,
    InputSource,
    KeyInfo,
    VimState,
)


def test_models_import_without_qt_or_spyder():
    """Block GUI imports so a passing import cannot rely on installed bindings."""
    script = """
import importlib.abc
import sys
sys.path.insert(0, sys.argv[1])
class RejectGUI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'qtpy', 'PySide6', 'PyQt5', 'spyder'}:
            raise AssertionError('Unexpected GUI dependency: ' + fullname)
sys.meta_path.insert(0, RejectGUI())
from spyder_okvim.vim import InputCmdInfo, KeyInfo, VimState
from spyder_okvim.vim.registers import Registers
from spyder_okvim.utils.ex_parser import scan_header
from spyder_okvim.utils.search_helpers import resolve_ignorecase
from spyder_okvim.utils.commandline import command_candidates
assert scan_header('s/a/b/').command == 's'
assert command_candidates(':w', 2, ('w', 'wq'))
assert resolve_ignorecase('FOO', ignorecase=True, smartcase=True) is False
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(Path(__file__).resolve().parents[1])],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr


def test_explicit_count_text_survives_command_snapshots():
    """Implicit one and explicit one stay distinguishable during dot replay."""
    assert InputCmdInfo(num_str="2", cmd="x").count_text == "2"
    command = InputCmdInfo("", "x")
    repeat = DotCmdInfo()
    repeat.cmd = command.cmd
    repeat.count_text = command.count_text
    assert repeat.to_cmd_string(1, "") == "x"
    command.count_text = "1"
    repeat.count_text = command.count_text
    assert repeat.to_cmd_string(1, "") == "1x"
    assert repeat.num_str == "1"
    repeat.num_str = ""
    assert repeat.count_text == ""


def test_recorded_keys_expose_their_input_destination():
    """Named sources retain the historical replay values and identifier alias."""
    key = KeyInfo(65, "a", 0, InputSource.COMMAND_LINE)
    assert key.source is InputSource.COMMAND_LINE
    assert key.identifier == 0
    key.identifier = 1
    assert key.source is InputSource.EDITOR
    assert KeyInfo(65, "a", 0, identifier=0).source is InputSource.COMMAND_LINE


def test_path_syntax_preserves_home_and_suffix_without_resolving_them(monkeypatch):
    """The parser accepts literal home syntax without consulting the environment."""
    # Standard Libraries
    import os.path

    def forbidden(*args):
        raise AssertionError("Path syntax must not expand the user home")

    monkeypatch.setattr(os.path, "expanduser", forbidden)
    text = ':e "~/docs/old/keep"'
    argument = parse_path_argument(text, text.index("old") + 2, ("e",))
    assert argument.directory_prefix == "~/docs/"
    assert argument.prefix == "ol"
    assert argument.replacement_prefix == ':e "~/docs/'
    assert argument.suffix == '/keep"'


@pytest.mark.parametrize(
    "pattern,ignorecase,smartcase,override,expected",
    [
        ("foo", True, True, None, True),
        ("Foo", True, True, None, False),
        ("Foo", True, False, None, True),
        ("foo", False, True, None, False),
        ("Foo", False, True, True, True),
        ("foo", True, False, False, False),
    ],
)
def test_case_policy_uses_only_explicit_options(
    pattern, ignorecase, smartcase, override, expected
):
    assert (
        resolve_ignorecase(
            pattern, override, ignorecase=ignorecase, smartcase=smartcase
        )
        is expected
    )


def test_register_clipboard_and_history_have_separate_effects():
    """Injected clipboard operations do not turn individual writes into edits."""
    clipboard = ["external"]
    messages = []
    registers = Registers(
        lambda: clipboard[0],
        lambda text: clipboard.__setitem__(0, text),
        messages.append,
    )
    registers.set_register("+", "clipboard", VimState.NORMAL)
    assert clipboard == ["clipboard"]
    assert registers.history.snapshot() == ()
    assert registers.get_register("+").content == "clipboard"
    registers.update_registers('"', "deleted", VimState.NORMAL, is_yank=False)
    assert registers.get_register("-").content == "deleted"
    assert registers.get_register('"').content == "deleted"
    assert len(registers.history.snapshot()) == 1
    registers.update_registers("_", "ignored", VimState.NORMAL, is_yank=False)
    assert registers.get_register('"').content == "deleted"
    assert len(registers.history.snapshot()) == 1
    assert messages == []
