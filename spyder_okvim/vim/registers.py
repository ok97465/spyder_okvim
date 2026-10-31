"""Register rules and yank history, with clipboard operations supplied by callers.

A register write and a logical yank/delete are different operations. Automatic
register rotation happens once per edit; put/history cycling never records.
"""

# Standard Libraries
from collections import defaultdict

from .state import RegisterInfo, VimState
from .yank_history import YankHistory


class Registers:
    """Own register values and bounded, immutable history without Qt imports."""

    def __init__(self, read_clipboard, write_clipboard, report_message):
        self.values = defaultdict(RegisterInfo)
        self.history = YankHistory()
        self.enabled = True
        self._read_clipboard = read_clipboard
        self._write_clipboard = write_clipboard
        self._report_message = report_message

    def set_register(self, name, content, register_type):
        """Write one register, appending uppercase names to their lowercase pair."""
        if name == "_":
            return None

        if "A" <= name <= "Z":
            name = name.lower()
            previous = self.values[name]
            if previous.type == VimState.VLINE:
                if register_type != VimState.VLINE:
                    content += "\n"
                register_type = VimState.VLINE
            elif register_type == VimState.VLINE and previous.content:
                content = "\n" + content
            content = previous.content + content

        # Use independent values so history rotation cannot mutate other registers.
        info = RegisterInfo()
        info.name = name
        info.content = content
        info.type = register_type
        if name == "+":
            self._write_clipboard(content)
        else:
            self.values[name] = info
        return info

    def update_registers(
        self, name, content, register_type, *, is_yank, force_numbered=False
    ):
        """Store a yank/delete and update the unnamed and automatic registers."""
        if name == "_" or not content:
            return

        info = self.set_register(name, content, register_type)
        if is_yank:
            if name == '"':
                self.set_register("0", content, register_type)
        else:
            is_small_delete = register_type != VimState.VLINE and "\n" not in content
            if not is_small_delete or force_numbered:
                for number in range(9, 1, -1):
                    previous = self.values[str(number - 1)]
                    self.set_register(str(number), previous.content, previous.type)
                self.set_register("1", content, register_type)
            if is_small_delete and name == '"':
                self.set_register("-", content, register_type)

        # Appends expose the combined value; deletion history keeps only this delete.
        self.set_register('"', info.content, info.type)
        if self.enabled:
            kind = "linewise" if register_type == VimState.VLINE else "charwise"
            self.history.record(content, kind, "yank" if is_yank else "delete")
            if self.history.last_skip_reason == "oversize":
                self._report_message("Yank history: value exceeds the memory limit")

    def get_register(self, name):
        """Get content from register_dict."""
        if name in ("+", "_"):
            info = RegisterInfo()
            info.name = name
            if name == "+":
                info.content = self._read_clipboard()
            return info
        else:
            return self.values[name.lower()]
