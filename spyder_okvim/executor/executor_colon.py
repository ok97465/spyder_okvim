# -*- coding: utf-8 -*-
"""Executor for ":" command-line input."""

# Standard Libraries
import os.path as osp

# Third Party Libraries
from qtpy.QtCore import QRegularExpression
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QDialog

# Project Libraries
from spyder_okvim.executor.executor_base import ExecutorSubBase
from spyder_okvim.utils.ex_parser import (
    ExError,
    is_substitute,
    resolve_substitute,
    scan_header,
)
from spyder_okvim.utils.jump_dialog import JumpListDialog
from spyder_okvim.utils.mark_dialog import MarkListDialog
from spyder_okvim.utils.qtcompat import exec_dialog
from spyder_okvim.utils.search_helpers import resolve_ignorecase
from spyder_okvim.utils.substitute import (
    build_substitution_plan,
    prepare_substitution,
)
from spyder_okvim.utils.substitute_confirm import SubstituteConfirm
from spyder_okvim.vim import VimState


class ExecutorColon(ExecutorSubBase):
    """Interpreter for ``:`` commands entered in the command line."""

    accepts_input_method = True
    history_kind = "ex"
    COMMANDS = {
        "e": "e",
        "w": "w",
        "q": "q",
        "q!": "qexclamation",
        "wq": "wq",
        "n": "n",
        "marks": "marks",
        "jumps": "jumps",
        "vs": "vs",
        "vsp": "vs",
        "vsplit": "vs",
        "YankyRingHistory": "YankyRingHistory",
        "YankyClearHistory": "YankyClearHistory",
        "s": "substitute",
        "substitute": "substitute",
        "&": "substitute",
        "&&": "substitute",
        "~": "substitute",
    }
    SUPPORTED_COMMANDS = tuple(COMMANDS)

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.pending_range_text = None
        self.origin_line = None

    def begin_input(self):
        """Anchor default and dot addresses when this Ex input session starts."""
        editor = self.get_editor()
        self.origin_line = (
            editor.textCursor().blockNumber() if editor is not None else None
        )

    def __call__(self, txt: str) -> bool:
        """Parse ``txt`` and execute the corresponding ex command.

        Args:
            txt: Command string typed by the user, including the trailing ``\r``.

        Returns:
            if return is True, Clear command line.

        """
        if not txt:
            return False
        if txt[-1] == "\b":
            cmd_line = self.vim_status.cmd_line
            if len(txt) <= 2:
                self.origin_line = None
                self.vim_status.sub_mode = None
                return True
            cmd_line.setText(txt[:-2])
        if txt[-1] != "\r":
            return False

        if txt[0] != ":" or len(txt) <= 2:
            self.origin_line = None
            self.vim_status.sub_mode = None
            return True

        # ':' is saved to input cmd_info at ExecutorBase.
        # So we need only txt[1:].
        self.update_input_cmd_info(None, None, txt[1:])

        try:
            header = scan_header(txt[1:-1])
            if header.line_number is not None:
                self.goto_line(header.line_number)
            elif is_substitute(header.command):
                self.substitute(header)
            elif header.command:
                method = self.COMMANDS.get(header.command)
                if method is None:
                    raise ExError(f"Unknown command: {header.command}")
                if header.explicit_range:
                    raise ExError(f"Range is not supported for :{header.command}")
                getattr(self, method)(header.argument)
            elif header.explicit_range:
                raise ExError("Specify a command after the range")
        except ValueError as error:
            widget = self.vim_status.cmd_line.vim_widget
            if widget.is_playing_macro:
                widget.cancel_macro()
            self.vim_status.set_message(str(error))
        finally:
            self.origin_line = None
            if self.vim_status.sub_mode is self:
                self.vim_status.sub_mode = None

        return True

    def substitute(self, header):
        """Validate and calculate all replacements before editing the document."""
        vs = self.vim_status
        editor = self.get_editor()
        if editor is None:
            raise ExError("No active editor")
        document = editor.document()
        cursor = self.get_cursor()
        origin_block, origin_column = cursor.block(), cursor.positionInBlock()
        current_line = cursor.blockNumber()
        address_line = current_line if self.origin_line is None else self.origin_line
        address_line = min(address_line, document.blockCount() - 1)
        spec = resolve_substitute(header, vs.last_substitute, vs.search.txt_searched)
        prepared = prepare_substitution(
            header, spec, address_line, document.blockCount()
        )
        text = spec.pattern
        pattern = prepared.pattern
        count_only, confirm = prepared.count_only, prepared.confirm
        if confirm and vs.cmd_line.vim_widget.is_playing_macro:
            raise ExError("Confirmation substitutions are not supported in macros")
        if editor.isReadOnly() and not count_only:
            raise ExError("Document is read-only")
        plan = build_substitution_plan(
            document,
            prepared.first_line,
            prepared.last_line,
            pattern,
            prepared.tokens,
            global_matches=prepared.global_matches,
            count_only=count_only,
            confirm=confirm,
        )
        # Planning and applying run synchronously without processing UI events.
        if plan.edits and not confirm:
            self._apply_substitution(editor, plan.edits)
        if plan.match_count and not confirm:
            target_line = current_line if count_only else plan.last_line
            block = document.findBlockByNumber(target_line)
            line = block.text()
            position = block.position() + len(line) - len(line.lstrip(" \t"))
            vs.cursor.set_cursor_pos_without_end(position)
            self._record_substitute_jump(origin_block, origin_column)

        # i/I affect this substitution only; n/N use the normal search options.
        search_ignorecase = resolve_ignorecase(text)
        ignorecase = bool(
            pattern.patternOptions() & QRegularExpression.CaseInsensitiveOption
        )
        vs.search.search(
            text,
            ignorecase=search_ignorecase,
            forward=vs.search.forward,
            pattern=pattern if search_ignorecase == ignorecase else None,
        )
        vs.last_substitute = spec
        if confirm and plan.match_count:
            session = SubstituteConfirm(
                vs,
                editor,
                plan.edits,
                lambda session: self._finish_confirmation(
                    session, origin_block, origin_column
                ),
            )
            vs.substitute_confirm = vs.sub_mode = session
            session.start()
            return
        if not plan.match_count:
            if "e" not in spec.flags:
                raise ExError(f"Pattern not found: {text}")
            vs.set_message("")
        elif count_only:
            vs.set_message(
                f"{plan.match_count} matches on {plan.line_count} lines (count only)"
            )
        else:
            suffix = "" if plan.edits else " (no changes)"
            vs.set_message(
                f"{plan.match_count} substitutions on {plan.line_count} lines{suffix}"
            )

    def _record_substitute_jump(self, origin_block, origin_column):
        """Keep the origin's line and column as substitutions change offsets."""
        vs = self.vim_status
        location = vs.get_current_location()
        if location is not None:
            column = min(origin_column, max(0, origin_block.length() - 2))
            layout = origin_block.layout()
            if column and not layout.isValidCursorPosition(column):
                column = layout.previousCursorPosition(column)
            vs.jump_list.push(location[0], origin_block.position() + column)
            vs.push_jump()

    def _finish_confirmation(self, session, origin_block, origin_column):
        """Report approved targets after the session releases its input hooks."""
        vs = self.vim_status
        if session.valid():
            self._record_substitute_jump(origin_block, origin_column)
            vs.search.refresh()
        vs.set_message(
            f"{session.replacement_count} substitutions on {session.line_count} lines"
        )

    @staticmethod
    def _apply_substitution(editor, edits):
        """Apply the ordered edits backwards as a single undoable operation."""
        cursor = QTextCursor(editor.document())
        previous_skip_rstrip = editor.skip_rstrip
        editor.skip_rstrip = True
        try:
            cursor.beginEditBlock()
            try:
                for start, end, replacement in reversed(edits):
                    cursor.setPosition(start)
                    cursor.setPosition(end, QTextCursor.KeepAnchor)
                    cursor.insertText(replacement)
            finally:
                cursor.endEditBlock()
        finally:
            editor.skip_rstrip = previous_skip_rstrip
        editor.document_did_change()

    def e(self, arg=""):
        """Open an existing path relative to the current working directory."""
        vs = self.vim_status
        path = arg
        if len(path) >= 2 and path[0] in "\"'" and path[-1] == path[0]:
            path = path[1:-1]
        if not path:
            vs.set_message("Specify a file path")
            return
        path = osp.abspath(osp.expanduser(path))
        if not osp.isfile(path):
            vs.set_message(f"Not a file: {path}")
            return
        vs.to_normal()
        vs.push_jump()
        vs.editor_widget.load(path)
        vs.push_jump()
        vs.set_focus_to_vim()
        vs.cursor.draw_vim_cursor()

    def w(self, arg=""):
        """Save current file."""
        self.save_current_file()
        self.vim_status.cursor.draw_vim_cursor()

    def q(self, arg=""):
        """Close current file."""
        self.close_current_file()
        self.vim_status.set_focus_to_vim()

    def qexclamation(self, arg=""):
        """Close current file without saving."""
        self.close_current_file(force=True)
        self.vim_status.set_focus_to_vim()

    def wq(self, arg=""):
        """Save and close current file."""
        self.save_and_close_current_file()
        self.vim_status.set_focus_to_vim()

    def n(self, args=""):
        """Create new file."""
        self.create_new_file()
        self.vim_status.set_focus_to_vim()

    def vs(self, arg=""):
        """Split the active editor into side-by-side views."""
        stack = self.get_editorstack()
        filename = stack.get_current_filename()
        position = self.vim_status.get_cursor().position()
        stack.sig_split_horizontally.emit()
        self.get_editorstack().set_current_filename(filename)
        self.vim_status.cursor.set_cursor_pos(position)
        self.vim_status.set_focus_to_vim()

    def marks(self, arg=""):
        """Show bookmarks and jump to the selected one."""
        vs = self.vim_status
        marks = vs.bookmark_manager.list_bookmarks()

        dlg = MarkListDialog(marks, vs.get_editor().window())
        result = exec_dialog(dlg)
        # Tests patch ``exec_`` to return ``None``; ``exec_dialog`` keeps that
        # behaviour so only an explicit ``QDialog.Rejected`` (0) cancels.
        mark = (
            dlg.get_selected_mark()
            if result is None or result == QDialog.Accepted
            else None
        )
        if mark:
            vs.push_jump()
            vs.bookmark_manager.jump_to_bookmark(mark)
            vs.push_jump()

        vs.set_focus_to_vim()

    def jumps(self, arg=""):
        """Display the jumplist in a popup dialog."""
        vs = self.vim_status

        dlg = JumpListDialog(vs, vs.get_editor().window())
        exec_dialog(dlg)

        vs.set_focus_to_vim()

    def goto_line(self, num):
        """Move cursor according to :number command."""
        vs = self.vim_status
        vs.push_jump()

        if vs.vim_state == VimState.NORMAL:
            motion_info = self.helper_motion.G(num, True)
            vs.cursor.apply_motion_info_in_normal(motion_info)
        elif vs.vim_state in (VimState.VISUAL, VimState.VLINE):
            motion_info = self.helper_motion.j(num)
            if vs.vim_state == VimState.VISUAL:
                vs.cursor.apply_motion_info_in_visual(motion_info)
            else:
                vs.cursor.apply_motion_info_in_vline(motion_info)
            vs.to_normal()
        vs.push_jump()

    def YankyRingHistory(self, arg=""):
        """Show the yank-history picker."""
        self.vim_status.cmd_line.vim_widget.show_yank_history()

    def YankyClearHistory(self, arg=""):
        """Clear history, including an active put cycle or picker."""
        self.vim_status.cmd_line.vim_widget.clear_yank_history()
