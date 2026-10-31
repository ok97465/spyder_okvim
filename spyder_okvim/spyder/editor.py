"""Spyder editor operations used by Vim commands.

This is the host boundary for file lifecycle, IDE actions and language-aware
editing. Callers supply resolved ranges; this module owns Spyder-specific API
calls, save/close guards and cursor restoration on the GUI thread.
"""

# Standard Libraries
import ast

# Third Party Libraries
from qtpy.QtGui import QTextCursor
from spyder.api.plugins import Plugins
from spyder.plugins.editor.utils.editor import TextBlockHelper
from spyder.utils.syntaxhighlighters import PythonSH

# Project Libraries
from spyder_okvim.utils.cell_helpers import CellRegion, get_document_cells


class EditorCommands:
    """Operate on the current Spyder view without interpreting Vim input.

    ``cursor`` resolves the pinned editor stack on each operation. File commands
    recheck identity after operations that can process events or change tabs.
    ``focus_input`` is a callback rather than a reference to an input widget.
    """

    def __init__(self, editor_plugin, cursor, main, focus_input):
        self.editor_plugin = editor_plugin
        self.cursor = cursor
        self.main = main
        self.focus_input = focus_input
        self.get_editor = cursor.get_editor
        self.get_editorstack = cursor.get_editorstack
        self._application_plugin = None

    def close_current_file(self, force=False) -> None:
        """Close the active file, optionally discarding unsaved changes."""
        if not force:
            self.editor_plugin.close_file()
            return

        stack = self.get_editorstack()
        finfo = stack.get_current_finfo()
        if finfo is None:
            return

        filename = finfo.filename
        widget = self.editor_plugin.get_widget()
        # Spyder's forced stack close also bypasses its debugger guard.
        if not widget.can_close_file(filename):
            return

        # Match Spyder's Discard action, including autosave recovery cleanup.
        stack.autosave.remove_autosave_file(filename)
        if self.get_editorstack().get_current_finfo() is finfo:
            stack.close_file(force=True)

    def save_current_file(self) -> bool:
        """Return whether Spyder explicitly reports a successful save."""
        return self.editor_plugin.save() is True

    def save_and_close_current_file(self) -> None:
        """Close only when the original, still-active document was saved."""
        finfo = self.get_editorstack().get_current_finfo()
        if finfo is None or not self.save_current_file():
            return

        # Save As and format-on-save may process events or leave edits unsaved.
        if (
            self.get_editorstack().get_current_finfo() is finfo
            and not finfo.newly_created
            and not finfo.editor.document().isModified()
        ):
            self.close_current_file()

    def create_new_file(self) -> None:
        """Create a new file using Spyder's editor plugin."""
        self.editor_plugin.new()

    def load_file(self, path):
        """Open an Ex-resolved path using the editor plugin's load action."""
        self.editor_plugin.load(path)

    def open_file(self, path):
        """Open a navigation target through the optional application plugin."""
        if not path:
            return
        if self._application_plugin is None:
            try:
                self._application_plugin = self.main.get_plugin(Plugins.Application)
            except Exception:
                return
        open_file = getattr(self._application_plugin, "open_file_in_plugin", None)
        if callable(open_file):
            open_file(path)

    def auto_import(self):
        """Run the optional personal import helper and restore input focus."""
        try:
            self.get_editor().auto_import.auto_import()
            self.focus_input()
        except AttributeError:
            pass

    def search_imports(self):
        """Show the optional modal import picker for a writable Python file."""
        editor = self.get_editor()
        if editor is None or not editor.is_python() or editor.isReadOnly():
            return
        search = getattr(getattr(editor, "auto_import", None), "search_imports", None)
        if callable(search):
            try:
                search(query="")
            finally:
                self.focus_input()

    def toggle_breakpoint(self):
        """Toggle the active editor's breakpoint through its Spyder manager."""
        self.get_editor().breakpoints_manager.toogle_breakpoint()

    def format_document(self):
        """Format the document or current editor selection."""
        self.get_editor().format_document_or_range()

    def open_switcher(self, *, symbol=False):
        """Open Spyder's optional file or symbol switcher."""
        switcher = self.main.get_plugin(Plugins.Switcher)
        if symbol:
            switcher.open_switcher(symbol=True)
        else:
            switcher.open_switcher()

    def trigger_run_action(self, action, *, use_selection=False):
        """Expose a Vim selection to Spyder and restore cursor and focus."""
        editor_stack = self.get_editorstack()
        editor = self.get_editor()
        old_cursor = (
            self.cursor.set_selection_to_editor_using_vim_selection()
            if use_selection
            else None
        )
        try:
            editor_stack.sig_trigger_action.emit(action, Plugins.Run)
        finally:
            if old_cursor is not None:
                editor.setTextCursor(old_cursor)
            self.focus_input()

    def reindent_lines(self, first_block: int, last_block: int) -> None:
        """Reindent an inclusive range of zero-based Spyder text blocks.

        Preserve Python string contents, mixed tabs/spaces and one undo group.
        Place the cursor at the first nonblank character of the first block.
        """
        editor = self.get_editor()
        document = editor.document()
        indent = editor.indent_chars
        tab_width = editor.tab_stop_width_spaces
        is_python = editor.is_python_like()
        edit_cursor = self.cursor.get_cursor()
        previous_skip_rstrip = editor.skip_rstrip
        editor.skip_rstrip = True
        edit_cursor.beginEditBlock()
        try:
            for block_no in range(first_block, last_block + 1):
                block = document.findBlockByNumber(block_no)
                text = block.text()
                if not text.strip():
                    continue

                prefix_length = len(text) - len(text.lstrip(" \t"))
                cursor = QTextCursor(block)
                if is_python:
                    if TextBlockHelper.get_state(block.previous()) in (
                        PythonSH.INSIDE_SQ3STRING,
                        PythonSH.INSIDE_DQ3STRING,
                        PythonSH.INSIDE_SQSTRING,
                        PythonSH.INSIDE_DQSTRING,
                    ):
                        # Leading spaces in a multiline string are its content.
                        continue
                    # Use Spyder's indentation context without its directional
                    # Tab/Backtab behavior or its mixed-whitespace replacement.
                    editor.setTextCursor(cursor)
                    current_width = len(text[:prefix_length].expandtabs(tab_width))
                    if indent == "\t":
                        # Spyder rounds dedents using len(indent_chars), which
                        # is one for tabs rather than the configured tab width.
                        current_width = -(-current_width // tab_width) * tab_width
                    width = editor.find_indentation(cur_indent=current_width)
                    if width < 0:
                        continue
                    if indent == "\t":
                        prefix = "\t" * (width // tab_width) + " " * (width % tab_width)
                    else:
                        prefix = " " * width
                else:
                    # Match Spyder's simple indentation for other languages.
                    previous_text = block.previous().text()
                    prefix = previous_text[
                        : len(previous_text) - len(previous_text.lstrip(" \t"))
                    ]

                if prefix != text[:prefix_length]:
                    cursor.setPosition(
                        block.position() + prefix_length, QTextCursor.KeepAnchor
                    )
                    cursor.insertText(prefix)

            block = document.findBlockByNumber(first_block)
            text = block.text()
            self.cursor.set_cursor_pos(
                block.position() + len(text) - len(text.lstrip(" \t"))
            )
        finally:
            edit_cursor.endEditBlock()
            editor.skip_rstrip = previous_skip_rstrip

        editor.document_did_change()

    def toggle_comments(self, start: int, end: int) -> int:
        """Toggle comments over Qt UTF-16 endpoints and return the first block.

        The caller restores Vim mode and emits the document-change notification
        after applying the returned cursor position, preserving command order.
        """
        editor = self.get_editor()
        cursor = editor.textCursor()
        cursor.setPosition(start, QTextCursor.MoveAnchor)
        first_block = cursor.blockNumber()
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        editor.setTextCursor(cursor)
        editor.toggle_comment()
        cursor = editor.textCursor()
        position = editor.document().findBlockByNumber(first_block).position()
        cursor.setPosition(position, QTextCursor.MoveAnchor)
        editor.setTextCursor(cursor)
        return position

    def python_definition_positions(self) -> list[int]:
        """Return UTF-16 starts of Python definitions; invalid syntax yields none."""
        editor = self.get_editor()
        text = editor.toPlainText()

        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []

        lines: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                lines.add(node.lineno)

        positions: list[int] = []
        for line in sorted(lines):
            block = editor.document().findBlockByNumber(line - 1)
            if not block.isValid():
                continue
            text = block.text()
            start_of_line = len(text) - len(text.lstrip())
            positions.append(block.position() + start_of_line)

        return positions

    def python_block_positions(self) -> list[int]:
        """Return UTF-16 starts of language block headers in the active view."""
        editor = self.get_editor()
        doc = editor.document()
        positions: list[int] = []

        block_keywords = (
            "def ",
            "async def ",
            "class ",
            "if ",
            "for ",
            "async for ",
            "while ",
            "try:",
            "with ",
            "async with ",
        )

        for line_no, text in enumerate(editor.toPlainText().splitlines()):
            stripped = text.lstrip()
            if any(stripped.startswith(kw) for kw in block_keywords):
                block = doc.findBlockByNumber(line_no)
                if not block.isValid():
                    continue
                start_of_line = len(text) - len(stripped)
                positions.append(block.position() + start_of_line)

        return positions

    def get_cells(self) -> list[CellRegion]:
        """Return resolved cell metadata without exposing a Spyder editor to motions."""
        return get_document_cells(self.get_editor())
