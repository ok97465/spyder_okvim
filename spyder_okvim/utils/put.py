"""Reversible, register-independent puts and their short-lived history session."""

# Standard Libraries
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, replace

# Third Party Libraries
from qtpy.QtGui import QTextCursor

# Project Libraries
from spyder_okvim.utils.qtcompat import live_widget
from spyder_okvim.vim.state import VimState
from spyder_okvim.vim.yank_history import YankEntry


SESSION_BYTE_LIMIT = 10 * 1024 * 1024
CYCLE_BYTE_LIMIT = 10 * 1024 * 1024


def _text(cursor, start, end):
    cursor = QTextCursor(cursor)
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.KeepAnchor)
    return cursor.selectedText().replace("\u2029", "\n")


def _bytes(text):
    return len(text.encode("utf-8"))


@dataclass(frozen=True)
class PutContext:
    mode: int
    position: int
    selection_start: int
    selection_end: int
    block_start: int
    block_end: int
    block_number: int
    at_end: bool
    char_after: int


@dataclass(frozen=True)
class PutPlan:
    start: int
    end: int
    text: str
    cursor_policy: str
    block_number: int = 0


@dataclass(frozen=True)
class PutResult:
    plan: PutPlan
    original: str
    end: int
    cursor_position: int

    @property
    def start(self):
        return self.plan.start

    @property
    def text(self):
        return self.plan.text


@dataclass(frozen=True)
class PutPayload:
    entry: YankEntry
    is_lower: bool
    count: int


@dataclass
class PutSession:
    editor_ref: object
    document: object
    context: PutContext
    candidates: tuple
    index: int
    result: PutResult
    count: int
    is_lower: bool
    generation: int
    edit_bytes: int = 0


def plan_put(context, entry, count, is_lower):
    """Plan against the original context, without changing the document."""
    linewise = entry.kind == "linewise"
    content = entry.text
    if context.mode == VimState.VLINE:
        if linewise:
            content = (content * count)[:-1]
        elif content and count > 1:
            content = ((content + "\n") * count)[:-1]
        return PutPlan(context.selection_start, context.selection_end, content, "start")
    content *= count
    if context.mode == VimState.VISUAL:
        if linewise and content:
            content = "\n" + content
        policy = "visual_line" if linewise else ("start" if "\n" in content else "last")
        return PutPlan(
            context.selection_start,
            context.selection_end,
            content,
            policy,
            context.block_number + 1,
        )
    if not linewise:
        position = context.char_after if is_lower else context.position
        return PutPlan(position, position, content, "last")
    if not is_lower:
        return PutPlan(
            context.block_start,
            context.block_start,
            content,
            "line",
            context.block_number,
        )
    position = context.block_end
    if context.at_end:
        content = "\n" + content[:-1]
    else:
        position += 1
    return PutPlan(position, position, content, "line", context.block_number + 1)


class PutController:
    """Own one view's observed document and the last reversible put."""

    def __init__(self, vim_status):
        self.status = vim_status
        self.session = None
        self.text_generation = 0
        self._editor_ref = None
        self._document = None
        self._connections = []
        self._internal = 0
        self._expected_extent = None
        self._foreign_edit = False
        self._pending_result = None

    @property
    def editor(self):
        return live_widget(self._editor_ref)

    @contextmanager
    def _edit_block(self, start, end, *, join_previous=False):
        """Group an owned patch and always release its temporary edit state."""
        cursor = self.editor.textCursor()
        self._expected_extent = (start, end)
        self._foreign_edit = False
        self._pending_result = None
        self._internal += 1
        try:
            if join_previous:
                cursor.joinPreviousEditBlock()
            else:
                cursor.beginEditBlock()
            try:
                yield cursor
            finally:
                # contentsChange can arrive here, so keep the edit guard active.
                cursor.endEditBlock()
        finally:
            self._expected_extent = None
            self._pending_result = None
            self._internal -= 1

    def bind_editor(self, editor):
        """Observe a view once; switching views always expires its session."""
        document = editor.document() if editor is not None else None
        if editor is self.editor and document is self._document:
            return
        self.cancel()
        for signal, callback in self._connections:
            try:
                signal.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        self._connections.clear()
        self._editor_ref = weakref.ref(editor) if editor is not None else None
        self._document = document
        self.text_generation += 1
        if editor is None:
            return
        connections = [
            (document.contentsChange, self._contents_change),
            (document.undoCommandAdded, self._external_change),
            (document.undoAvailable, self._undo_available),
            (editor.cursorPositionChanged, self._external_change),
            (editor.destroyed, self._destroyed),
        ]
        for signal, callback in connections:
            signal.connect(callback)
            self._connections.append((signal, callback))

    def _contents_change(self, position, removed, added):
        if removed or added:
            self.text_generation += 1
            if not self._internal:
                self.cancel()
            elif self._expected_extent is not None:
                start, end = self._expected_extent
                if position < start or position + removed > end:
                    self._foreign_edit = True
                    self.cancel()

    def _external_change(self):
        if not self._internal:
            self.cancel()

    def _undo_available(self, available):
        if not available and not self._internal:
            self.cancel()

    def _destroyed(self, *args):
        self.cancel()
        self._editor_ref = None
        self._document = None

    def cancel(self):
        self.session = None

    def cleanup(self):
        self.bind_editor(None)
        self.status.cursor.clear_highlights()

    def capture_context(self):
        editor = self.status.get_editor()
        self.bind_editor(editor)
        cursor = editor.textCursor()
        mode = self.status.vim_state
        position = cursor.position()
        start = end = position
        if mode != VimState.NORMAL:
            start = self.status.get_pos_start_in_selection()
            end = self.status.get_pos_end_in_selection()
            if start is None or end is None:
                start = end = position
        initial = QTextCursor(cursor)
        initial.setPosition(start)
        block = initial.block()
        after = QTextCursor(cursor)
        if not after.atBlockEnd():
            after.movePosition(QTextCursor.NextCharacter)
        initial.movePosition(QTextCursor.EndOfBlock)
        return PutContext(
            mode=mode,
            position=position,
            selection_start=start,
            selection_end=end,
            block_start=block.position(),
            block_end=initial.position(),
            block_number=block.blockNumber(),
            at_end=initial.atEnd(),
            char_after=after.position(),
        )

    def _cursor_position(self, plan, end):
        cursor = self.editor.textCursor()
        cursor.setPosition(end)
        if plan.cursor_policy == "last":
            cursor.movePosition(QTextCursor.PreviousCharacter)
        elif plan.cursor_policy in ("line", "visual_line"):
            block = self.editor.document().findBlockByNumber(plan.block_number)
            cursor.setPosition(block.position() if block.isValid() else plan.start)
            if plan.cursor_policy == "line":
                while (
                    not cursor.atBlockEnd()
                    and cursor.document().characterAt(cursor.position()).isspace()
                ):
                    cursor.movePosition(QTextCursor.NextCharacter)
        else:
            cursor.setPosition(plan.start)
        return cursor.position()

    def _apply(self, plan, original=None):
        cursor = self.editor.textCursor()
        if original is None:
            original = _text(cursor, plan.start, plan.end)
        cursor.setPosition(plan.start)
        cursor.setPosition(plan.end, QTextCursor.KeepAnchor)
        cursor.insertText(plan.text)
        end = cursor.position()
        # Keep a reversible patch even if cursor or highlight completion fails.
        self._pending_result = PutResult(plan, original, end, end)
        position = self._cursor_position(plan, end)
        return replace(self._pending_result, cursor_position=position)

    def _finish(self, result):
        self.status.to_normal()
        self.status.cursor.set_cursor_pos(result.cursor_position)
        if self.status.yanky_enabled:
            self.status.cursor.highlight_put(result.start, result.end)

    def put(self, num=1, is_lower=True, entry=None):
        """Put a register or explicit immutable entry; return the resulting patch."""
        editor = self.status.get_editor()
        if editor is None or editor.isReadOnly():
            self.cancel()
            return None
        context = self.capture_context()
        self.cancel()
        num = max(1, int(num))
        explicit = entry is not None
        if entry is None:
            register = self.status.get_register()
            entry = YankEntry.from_register(register.content, register.type)
        self.status.update_dot_cmd(
            connect_editor=False, register_name=self.status.get_register_name()
        )
        if explicit and not self.status.running_dot_cmd:
            self.status.dot_cmd.cmd = "p" if is_lower else "P"
            self.status.dot_cmd.num_str = str(num) if num > 1 else ""
            self.status.dot_cmd.register_name = None
        plan = plan_put(context, entry, num, is_lower)
        old_blocks = editor.blockCount()
        # At most three UTF-8 bytes per UTF-16 unit (non-BMP characters use two
        # units). Bound the original before copying a potentially huge selection.
        retain_original = (
            self.status.yanky_enabled
            and bool(entry.text)
            and 3 * (plan.end - plan.start) + _bytes(plan.text) <= SESSION_BYTE_LIMIT
        )
        previous_length = editor.document().characterCount()
        with self._edit_block(plan.start, plan.end):
            result = self._apply(plan, original=None if retain_original else "")
            self._finish(result)
        if explicit and not self.status.running_dot_cmd:
            self.status.dot_cmd.put_payload = PutPayload(entry, is_lower, num)
        enabled = self.status.yanky_enabled
        expected_length = (
            previous_length - (plan.end - plan.start) + result.end - result.start
        )
        valid_patch = (
            not self._foreign_edit
            and editor.document().characterCount() == expected_length
            and (
                not retain_original
                or _text(editor.textCursor(), result.start, result.end) == result.text
            )
        )
        if enabled and retain_original and valid_patch:
            snapshot = self.status.yank_history.snapshot()
            if snapshot and (snapshot[0].text, snapshot[0].kind) == (
                entry.text,
                entry.kind,
            ):
                snapshot = snapshot[1:]
            self.session = PutSession(
                weakref.ref(editor),
                editor.document(),
                context,
                (entry,) + snapshot,
                0,
                result,
                num,
                is_lower,
                self.text_generation,
            )
        elif entry.text and enabled and valid_patch:
            self.status.set_message("Put is too large to cycle")
        if old_blocks != editor.blockCount():
            self.status.set_message(f"{editor.blockCount() - old_blocks} more lines")
        editor.document_did_change()
        return result

    def can_cycle(self):
        """Read-only validation, also used by Qt ShortcutOverride."""
        session = self.session
        if session is None or not self.status.yanky_enabled:
            return False
        editor = live_widget(session.editor_ref)
        if (
            editor is None
            or editor is not self.editor
            or editor is not self.status.get_editor()
        ):
            return False
        document = editor.document()
        if document is not session.document or document is not self._document:
            return False
        if (
            editor.isReadOnly()
            or not document.isUndoRedoEnabled()
            or not document.isUndoAvailable()
            or session.generation != self.text_generation
        ):
            return False
        result = session.result
        # Qt can defer contentsChange until an enclosing edit block ends.
        return _text(editor.textCursor(), result.start, result.end) == result.text

    def cycle(self, direction, count=1):
        """Replace once with the final bounded candidate; boundary keys are handled."""
        if not self.can_cycle():
            self.cancel()
            return False
        session = self.session
        index = max(
            0,
            min(
                len(session.candidates) - 1,
                session.index + direction * max(1, int(count)),
            ),
        )
        if index == session.index:
            self.status.set_message("End of yank history")
            return True
        entry = session.candidates[index]
        # Check expansion before multiplying: a small original with a large
        # count can otherwise expand a much larger candidate far past budget.
        estimated_bytes = entry.byte_size * session.count
        if session.context.mode == VimState.VLINE and entry.kind == "charwise":
            estimated_bytes += max(0, session.count - 1)
        if estimated_bytes > SESSION_BYTE_LIMIT:
            self.cancel()
            self.status.set_message("Yank cycling memory limit reached")
            return True
        plan = plan_put(session.context, entry, session.count, session.is_lower)
        old = session.result
        payload = PutPayload(entry, session.is_lower, session.count)
        # Type and repeat meaning can change even when the produced patch and
        # final cursor are identical. Commit the candidate without editing Qt.
        same_range = (plan.start, plan.end) == (old.plan.start, old.plan.end)
        same_result = (
            same_range
            and plan.text == old.text
            and self._cursor_position(plan, old.end) == old.cursor_position
        )
        if same_result:
            session.result = replace(old, plan=plan)
            session.index = index
            if not self.status.running_dot_cmd:
                self.status.dot_cmd.put_payload = payload
            return True
        original_bytes = _bytes(old.original)
        planned_bytes = _bytes(plan.text)
        cost = _bytes(old.text) + planned_bytes
        if not same_range:
            cost += 2 * original_bytes
        if (
            original_bytes + planned_bytes > SESSION_BYTE_LIMIT
            or session.edit_bytes + cost > CYCLE_BYTE_LIMIT
        ):
            self.cancel()
            self.status.set_message("Yank cycling memory limit reached")
            return True
        editor = self.editor
        # The combined notification spans the old patch and the new original
        # range. Changes elsewhere during a reentrant Qt callback expire it.
        shift = (old.end - old.start) - (old.plan.end - old.plan.start)
        mapped_start = plan.start + (shift if plan.start > old.plan.end else 0)
        mapped_end = plan.end + (shift if plan.end > old.plan.end else 0)
        previous_length = editor.document().characterCount()
        failed = False
        recovered = False
        with self._edit_block(
            min(old.start, mapped_start), max(old.end, mapped_end), join_previous=True
        ) as cursor:
            try:
                if same_range:
                    replacement = replace(plan, start=old.start, end=old.end)
                    applied = self._apply(replacement, original=old.original)
                    result = replace(applied, plan=plan)
                else:
                    cursor.setPosition(old.start)
                    cursor.setPosition(old.end, QTextCursor.KeepAnchor)
                    cursor.insertText(old.original)
                    result = self._apply(plan)
                self._finish(result)
            except Exception:
                failed = True
                patch = self._pending_result
                # Recover only a patch whose exact text is still ours. A
                # reentrant editor change must never be overwritten by recovery.
                if (
                    not self._foreign_edit
                    and live_widget(session.editor_ref) is editor
                    and editor.document() is session.document
                    and patch is not None
                    and _text(editor.textCursor(), patch.start, patch.end) == patch.text
                ):
                    cursor.setPosition(patch.start)
                    cursor.setPosition(patch.end, QTextCursor.KeepAnchor)
                    cursor.insertText(old.text if same_range else patch.original)
                    if not same_range:
                        cursor.setPosition(old.plan.start)
                        cursor.setPosition(old.plan.end, QTextCursor.KeepAnchor)
                        cursor.insertText(old.text)
                    self.status.cursor.set_cursor_pos(old.cursor_position)
                    self.status.cursor.highlight_put(old.start, old.end)
                    recovered = True
        if failed:
            if recovered and not self._foreign_edit:
                session.generation = self.text_generation
                session.edit_bytes += cost
            else:
                self.cancel()
            self.status.set_message("Could not cycle this yank entry")
            return True
        expected_length = (
            previous_length
            - (old.end - old.start)
            + (old.plan.end - old.plan.start)
            - (plan.end - plan.start)
            + result.end
            - result.start
        )
        valid_patch = (
            not self._foreign_edit
            and editor.document().characterCount() == expected_length
            and _text(editor.textCursor(), result.start, result.end) == result.text
        )
        if not valid_patch:
            self.cancel()
            self.status.set_message("Put changed during cycling")
            return True
        session.result = result
        session.index = index
        session.edit_bytes += cost
        session.generation = self.text_generation
        if not self.status.running_dot_cmd:
            self.status.dot_cmd.put_payload = payload
        editor.document_did_change()
        return True

    def repeat(self, num=1, num_str=""):
        """Replay only snapshot puts here; ordinary puts retain register lookup."""
        dot = self.status.dot_cmd
        payload = dot.put_payload
        if payload is None:
            return
        self.cancel()
        self.status.running_dot_cmd = True
        try:
            if dot.vim_state != VimState.NORMAL:
                line = self.status.cmd_line
                line.clear()
                for ch in dot.selection_to_cmd_string():
                    line.setText(line.text() + ch)
            count = (
                max(1, int(num))
                if num_str and dot.vim_state == VimState.NORMAL
                else payload.count
            )
            self.put(count, payload.is_lower, payload.entry)
        finally:
            self.status.running_dot_cmd = False
