"""Surround input with non-destructive, document-bound range previews."""

# Standard Libraries
import weakref

# Third Party Libraries
from qtpy.QtGui import QColor, QPalette, QTextCharFormat, QTextCursor
from qtpy.QtWidgets import QTextEdit

# Project Libraries
from spyder_okvim.executor.executor_base import ExecutorSubBase
from spyder_okvim.utils.motion import MotionInfo, MotionType
from spyder_okvim.utils.qtcompat import live_widget, widget_is_deleted

SURROUNDINGS = "'\"{[()]}"
NEW_DELIMITER_HELP = (
    "new delimiter · ) → (text), ( → ( text ), "
    "] → [text], [ → [ text ], } → {text}, { → { text }, "
    "quotes → quoted text · Esc cancel"
)


def normalize_delimiter(character):
    """Expand the supported b/B aliases without accepting multi-key input."""
    return {"b": ")", "B": "}"}.get(character, character)


class SurroundExecutor(ExecutorSubBase):
    """Own temporary selections only for the document that started this input."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self.has_zero_cmd = False
        self._editor_ref = None
        self._document = None
        self._revision = None
        self._connections = []

    def begin(self):
        """Capture the document before showing candidate delimiter pairs."""
        self._clear_preview()
        editor = self.get_editor()
        self._editor_ref = weakref.ref(editor)
        self._document = editor.document()
        self._revision = self._document.revision()
        for signal, callback in (
            (self.vim_status.input_cancelled, self._input_cancelled),
            (self._document.contentsChanged, self._document_changed),
        ):
            signal.connect(callback)
            self._connections.append((signal, callback))

    def valid(self):
        editor = live_widget(self._editor_ref)
        return (
            editor is not None
            and not widget_is_deleted(self._document)
            and self.get_editor() is editor
            and editor.document() is self._document
            and self._document.revision() == self._revision
            and not editor.isReadOnly()
        )

    def _show_ranges(self, ranges):
        """Underline preview spans without changing the real selection or text."""
        editor = live_widget(self._editor_ref)
        if editor is None:
            return
        color = QColor(editor.palette().color(QPalette.Highlight))
        color.setAlpha(90)
        selections = []
        for start, end in ranges:
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(self._document)
            selection.cursor.setPosition(start)
            selection.cursor.setPosition(end, QTextCursor.KeepAnchor)
            selection.format.setBackground(color)
            selection.format.setUnderlineStyle(QTextCharFormat.DashUnderline)
            selections.append(selection)
        editor.set_extra_selections("vim_surround_preview", selections)

    def _pair_ranges(self, motion):
        """Return the two delimiter spans of the exact execution range."""
        if motion.sel_start is None or motion.sel_end is None:
            return []
        return [
            (motion.sel_start, motion.sel_start + 1),
            (motion.sel_end - 1, motion.sel_end),
        ]

    def _show_available_pairs(self, operation):
        ranges = set()
        for delimiter in ")]}'\"":
            ranges.update(self._pair_ranges(self.edits.surrounding_range(delimiter)))
        self._show_ranges(sorted(ranges))
        target = (
            "choose existing delimiter"
            if ranges
            else "no target at cursor; choose existing delimiter"
        )
        self.vim_status.set_message(
            f"Surround: {operation} · {target} · ) ] }} quotes · b/B aliases · Esc cancel"
        )

    def _clear_preview(self):
        editor = live_widget(self._editor_ref)
        if editor is not None:
            editor.clear_extra_selections("vim_surround_preview")
        for signal, callback in self._connections:
            try:
                signal.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        self._connections = []
        self._editor_ref = None
        self._document = None
        self._revision = None

    def _finish(self, message=""):
        self._clear_preview()
        self.vim_status.sub_mode = None
        self.vim_status.set_message(message)

    def on_escape(self):
        """Remove temporary display while preserving the document and mode."""
        self._finish()

    def _input_cancelled(self):
        """Release display before the input owner handles its mode transition."""
        self._clear_preview()
        self.vim_status.set_message("")

    def _document_changed(self):
        self._finish("Surround cancelled: document changed")
        self.vim_status.input_cmd.clear()
        self.vim_status.cmd_line.clear()

    def _accept_context(self):
        if self.valid():
            return True
        self._finish("Surround cancelled: target document is no longer active")
        return False


class ExecutorAddSurround(SurroundExecutor):
    """Wait for a delimiter with the exact motion/Visual range highlighted."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.pos_start = 0
        self.pos_end = 0

    def begin_range(self, start, end):
        self.begin()
        self.pos_start, self.pos_end = start, end
        self._show_ranges([(start, end)])
        self.vim_status.set_message("Surround: add · " + NEW_DELIMITER_HELP)

    def set_motion_info(self, motion_info: MotionInfo):
        """Capture a UTF-16 range; linewise motions include complete blocks."""
        if motion_info.motion_type == MotionType.BlockWise:
            sel_start = motion_info.sel_start
            sel_end = motion_info.sel_end
        else:
            cursor = self.get_cursor()
            cursor_pos_cur = cursor.position()
            cursor_pos_new = motion_info.cursor_pos
            sel_start, sel_end = sorted([cursor_pos_cur, cursor_pos_new])

            if motion_info.motion_type == MotionType.CharWiseIncludingEnd:
                sel_end += 1
            elif motion_info.motion_type == MotionType.LineWise:
                block_start, _ = self.vim_status.cursor.get_block(sel_start)
                block_end, _ = self.vim_status.cursor.get_block(sel_end)
                sel_start = block_start.position()
                sel_end = block_end.position() + block_end.length() - 1

        self.begin_range(sel_start, sel_end)

    def __call__(self, ch: str):
        if ch == "\x1b":
            self.on_escape()
            return True
        if not self._accept_context():
            return True
        ch = normalize_delimiter(ch)
        if ch not in SURROUNDINGS or len(ch) != 1:
            self._finish(f"Surround: unsupported delimiter {ch!r}")
        else:
            self._finish()
            self.update_input_cmd_info(None, None, ch)
            self.edits.add_surrounding(self.pos_start, self.pos_end, ch)
        self.vim_status.to_normal()
        self.vim_status.cursor.set_cursor_pos(self.pos_start)
        return True


class ExecutorDeleteSurround(SurroundExecutor):
    """Show available pairs while waiting for the delimiter to remove."""

    def begin(self):
        super().begin()
        self._show_available_pairs("delete")

    def __call__(self, ch: str):
        if ch == "\x1b":
            self.on_escape()
            return True
        if not self._accept_context():
            return True
        ch = normalize_delimiter(ch)
        if ch not in SURROUNDINGS or len(ch) != 1:
            self._finish(f"Surround: unsupported delimiter {ch!r}")
            return True
        motion = self.edits.surrounding_range(ch)
        if motion.sel_start is None:
            self._finish(f"Surround: no target for {ch!r}")
            return True
        self._finish()
        self.update_input_cmd_info(None, None, ch)
        motion = self.edits.delete_surrounding(ch)
        self.vim_status.to_normal()
        self.vim_status.cursor.set_cursor_pos(motion.sel_start)
        return True


class ExecutorChangeSurround(SurroundExecutor):
    """Highlight the chosen old pair before accepting its replacement."""

    def begin(self):
        super().begin()
        self._show_available_pairs("change")

    def __call__(self, txt: str):
        if txt == "\x1b":
            self.on_escape()
            return True
        if not txt:
            return False
        if not self._accept_context():
            return True
        source = normalize_delimiter(txt[0])
        if source not in SURROUNDINGS:
            self._finish(f"Surround: unsupported delimiter {source!r}")
            return True
        motion = self.edits.surrounding_range(source)
        if motion.sel_start is None:
            self._finish(f"Surround: no target for {source!r}")
            return True
        if len(txt) == 1:
            self._show_ranges(self._pair_ranges(motion))
            self.vim_status.set_message(
                f"Surround: change {source!r} · " + NEW_DELIMITER_HELP
            )
            return False
        replacement = normalize_delimiter(txt[1])
        if replacement not in SURROUNDINGS or len(txt) != 2:
            self._finish(f"Surround: unsupported delimiter {txt[1:]!r}")
            return True
        self._finish()
        self.update_input_cmd_info(None, None, source + replacement)
        motion = self.edits.change_surrounding(source, replacement)
        self.vim_status.to_normal()
        self.vim_status.cursor.set_cursor_pos(motion.sel_start)
        return True
