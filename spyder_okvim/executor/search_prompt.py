"""Preview and confirm search input while preserving its original editor state.

The prompt owns its debounce timer, search snapshot, selection and scroll
origin. Pending operator actions run only on confirmation, never on preview;
cancellation restores the saved state and releases the signal connection.
"""

# Standard Libraries
import math
import re

# Third Party Libraries
from qtpy.QtCore import QTimer
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QTextEdit

# Project Libraries
from spyder_okvim.executor.executor_base import ExecutorSubBase
from spyder_okvim.vim.state import VimState


class SearchPromptExecutor(ExecutorSubBase):
    """Preview searches without executing pending operators until Enter."""

    accepts_input_method = True
    history_kind = "search"

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self._editor = None
        self._search = None
        self._preview_timer = QTimer(vim_status)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._preview)

    @staticmethod
    def _copy_selections(selections):
        """Copy cursors because Visual motions mutate the displayed selections."""
        copies = []
        for selection in selections:
            copy = QTextEdit.ExtraSelection()
            copy.cursor = QTextCursor(selection.cursor)
            copy.format = selection.format
            copies.append(copy)
        return copies

    def begin(self, forward=True):
        """Save the original position, selection, view, and confirmed search."""
        self._finish()
        self._editor = self.get_editor()
        if self._editor is None or self.vim_status.search.is_closed:
            self._editor = None
            return False
        self._start_cursor = QTextCursor(self._editor.textCursor())
        self._selections = self._copy_selections(
            self._editor.get_extra_selections("vim_selection")
        )
        self._scroll = (
            self._editor.horizontalScrollBar().value(),
            self._editor.verticalScrollBar().value(),
        )
        self._search = self.vim_status.search
        self._snapshot = self._search.snapshot()
        self._message = self.vim_status.msg_label.text()
        self._search.closed.connect(self._search_closed)
        self._forward = forward
        self._text = ""
        return True

    def _is_current(self):
        """Ignore delayed callbacks belonging to another editor or status reset."""
        return (
            self._editor is not None
            and self._search is not None
            and not self._search.is_closed
            and self.vim_status.search is self._search
            and self.get_editor() is self._editor
            and self._editor.document() is self._start_cursor.document()
        )

    @property
    def previous_pattern(self):
        """The confirmed pattern reused when an empty search is submitted."""
        return self._snapshot.text if self._search is not None else ""

    def _finish(self):
        """Stop pending previews and release the current search session."""
        self._preview_timer.stop()
        if self._search is not None:
            try:
                self._search.closed.disconnect(self._search_closed)
            except (TypeError, RuntimeError):
                pass
        self._editor = None
        self._search = None
        self._start_cursor = None
        self._selections = []

    def _search_closed(self):
        """Discard previews immediately when search state is reset or closed."""
        self._finish()
        if self.vim_status.sub_mode is self:
            self.vim_status.sub_mode = None

    def _restore_position(self):
        """Restore fresh selection copies before every preview and final motion."""
        self._editor.setTextCursor(QTextCursor(self._start_cursor))
        self._editor.set_extra_selections(
            "vim_selection", self._copy_selections(self._selections)
        )
        self.vim_status.cursor.draw_vim_cursor()
        self._editor.horizontalScrollBar().setValue(self._scroll[0])
        self._editor.verticalScrollBar().setValue(self._scroll[1])

    def _preview(self):
        """Move only the cursor/selection, always relative to the search origin."""
        if self.vim_status.sub_mode is not self or not self._is_current():
            return
        self._restore_position()
        if not self._text:
            self._search.restore(self._snapshot)
            self.vim_status.msg_label.setText(self._message)
            return
        self.motions.search(self._text, forward=self._forward)
        motion_info = self.motions.n(math.prod(self.parent_counts))
        cursor = self.vim_status.cursor
        if self.vim_status.vim_state == VimState.VISUAL:
            cursor.apply_motion_info_in_visual(motion_info)
        elif self.vim_status.vim_state == VimState.VLINE:
            cursor.apply_motion_info_in_vline(motion_info)
        else:
            cursor.apply_motion_info_in_normal(motion_info)

    def on_escape(self):
        """Cancel pending previews and restore the state before search entry."""
        self._preview_timer.stop()
        if self._is_current():
            self._restore_position()
        if self._editor is not None and self.vim_status.search is self._search:
            self._search.restore(self._snapshot)
            self.vim_status.msg_label.setText(self._message)
        self._finish()

    def __call__(self, txt: str) -> bool:
        """Debounce input previews, or execute the confirmed search once."""
        self._preview_timer.stop()
        match = re.fullmatch(r"\d*([/?])(.*)", txt, re.DOTALL)
        if not match or not self._is_current():
            self.on_escape()
            self.vim_status.sub_mode = None
            return True

        prompt, text = match.groups()
        self._forward = prompt == "/"
        if not text.endswith("\r"):
            self._text = text
            self._preview_timer.start()
            return False

        self._restore_position()
        pattern = text[:-1] or self._snapshot.text
        if not pattern:
            self.on_escape()
            self.vim_status.sub_mode = None
            return True

        # The prompt and count were recorded when entering this submode.
        self.update_input_cmd_info(None, None, text)
        self.motions.search(pattern, forward=self._forward)
        motion_info = self.motions.n(math.prod(self.parent_counts))
        self.vim_status.sub_mode = None
        self._finish()
        if motion_info.cursor_pos is None:
            return True

        self.vim_status.push_jump()
        ret = self.process_return(self.execute_func_deferred(motion_info))
        self.vim_status.push_jump()
        return ret
