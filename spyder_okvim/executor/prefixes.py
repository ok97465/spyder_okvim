"""Handle short command prefixes and assemble mode-specific continuations.

Small g/register/character/structure/window handlers share their input-dispatch
contract here. Search and Leap have independent session lifetimes and live in
their own modules. ModeSubmodes creates fresh continuations for every mode; it
does not share mutable prompt or callback state between modes.
"""

# Standard Libraries
import os.path as osp
import re

# Project Libraries
from spyder_okvim.executor.executor_base import (
    CommandSpec,
    DeferredAction,
    ExecutorSubBase,
    ExecutorTransition,
)
from spyder_okvim.utils.editor_windows import focus_neighbor


class OperatorGExecutor(ExecutorSubBase):
    """Resolve the gg motion after an operator without losing explicit line counts."""

    hint_prefix = "g"
    command_specs = (CommandSpec("g", "g", "Go to line"),)

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

    def g(self, count=1, count_text=""):
        """Goto line (gg)."""
        count = self.parent_counts[-1] * self.parent_counts[0]
        if self.parent_count_texts[-1] == "" and self.parent_count_texts[0] == "":
            count = 1
        motion_info = self.motions.G(count, True)
        return self.execute_func_deferred(motion_info)


class GPrefixExecutor(ExecutorSubBase):
    """Dispatch g continuations for navigation, case changes and commenting."""

    hint_prefix = "g"
    command_specs = (
        CommandSpec("g", "g", "Go to line"),
        CommandSpec("d", "d", "Go to definition"),
        CommandSpec("t", "t", "Next file"),
        CommandSpec("T", "T", "Previous file"),
        CommandSpec("u", "u", "Lowercase"),
        CommandSpec("U", "U", "Uppercase"),
        CommandSpec("c", "c", "Toggle comment"),
        CommandSpec("~", "tilde", "Swap case"),
    )

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        # Operator parsing also uses these small prefix handlers. Import only
        # when assembling an instance, after both modules are initialized.
        # Project Libraries
        from spyder_okvim.executor.operators import OperatorMotionExecutor

        self.operator_motion = OperatorMotionExecutor(vim_status)

    def g(self, count=1, count_text=""):
        """Goto line(gg)."""
        count = self.parent_counts[-1]
        if self.parent_count_texts[-1] == "":
            count = 1
        motion_info = self.motions.G(count, True)
        return self.execute_func_deferred(motion_info)

    def d(self, count=1, count_text=""):
        """Go to definition and update the jumplist."""
        vs = self.vim_status
        previous = vs.get_current_location()
        vs.push_jump()

        editor = self.get_editor()
        if editor:
            vs.start_definition_tracking(previous)
            editor.go_to_definition_from_cursor()

    def t(self, count=1, count_text=""):
        """Cycle to next file."""
        editor_stack = self.get_editorstack()
        if self.parent_count_texts[-1] == "":
            editor_stack.tabs.tab_navigate(1)
        else:
            idx = self.parent_counts[-1] - 1
            if editor_stack.get_stack_count() > idx:
                editor_stack.set_stack_index(idx)
        self.vim_status.set_focus_to_vim()

    def T(self, count=1, count_text=""):
        """Cycle to previous file."""
        editor_stack = self.get_editorstack()
        for _ in range(self.parent_counts[-1]):
            editor_stack.tabs.tab_navigate(-1)
        self.vim_status.set_focus_to_vim()

    def u(self, count=1, count_text=""):
        """Make txt lowercase and move cursor to the start of selection."""
        if self.vim_status.is_normal():
            executor_sub = self.operator_motion
            self.set_parent_info_to_submode(executor_sub, count, count_text)
            executor_sub.set_func_list_deferred(
                [DeferredAction(lambda x: self.edits.change_case(x, "lower"), True)]
            )

            return ExecutorTransition(executor_sub, True)
        else:
            self.edits.change_case(None, "lower")

    def U(self, count=1, count_text=""):
        """Make txt uppercase and move the cursor to the start of selection."""
        if self.vim_status.is_normal():
            executor_sub = self.operator_motion
            self.set_parent_info_to_submode(executor_sub, count, count_text)
            executor_sub.set_func_list_deferred(
                [DeferredAction(lambda x: self.edits.change_case(x, "upper"), True)]
            )

            return ExecutorTransition(executor_sub, True)
        else:
            self.edits.change_case(None, "upper")

    def tilde(self, count=1, count_text=""):
        """Switch case of the character under the cursor.

        Move the cursor to the start of selection.
        """
        if self.vim_status.is_normal():
            executor_sub = self.operator_motion
            self.set_parent_info_to_submode(executor_sub, count, count_text)
            executor_sub.set_func_list_deferred(
                [DeferredAction(lambda x: self.edits.change_case(x, "swap"), True)]
            )

            return ExecutorTransition(executor_sub, True)
        else:
            self.edits.change_case(None, "swap")

    def c(self, count=1, count_text=""):
        """Toggle comment."""
        if self.vim_status.is_normal():
            executor_sub = self.operator_motion
            self.set_parent_info_to_submode(executor_sub, count, count_text)
            executor_sub.set_func_list_deferred(
                [DeferredAction(lambda x: self.edits.toggle_comment(x), True)]
            )

            return ExecutorTransition(executor_sub, True)
        else:
            self.edits.toggle_comment(None)


class RegisterPrefixExecutor(ExecutorSubBase):
    """Accept a register name and expose read-only register hints."""

    hint_prefix = '"'
    register_hints = (
        ('"', "Unnamed register"),
        ("0", "Last yank"),
        ("-", "Small delete"),
        ("+", "Clipboard"),
        ("_", "Black hole"),
        ("1-9", "Delete history"),
        ("a-z", "Named registers"),
        ("A-Z", "Append to named register"),
    )

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

    def get_hint_candidates(self):
        """Describe register names without creating or reading clipboard values."""
        registers = self.vim_status.register_dict

        def with_preview(description, info):
            content = info.content if info is not None else ""
            preview = " ".join(content[:160].split())
            if len(preview) > 40 or len(content) > 160:
                preview = preview[:39] + "…"
            return f"{description}: {preview}" if preview else description

        candidates = [
            (key, with_preview(description, registers.get(key)))
            for key, description in self.register_hints
        ]
        for key, info in sorted(registers.items()):
            is_numbered = len(key) == 1 and "1" <= key <= "9"
            is_named = len(key) == 1 and "a" <= key <= "z"
            if not (is_numbered or is_named) or not info.content:
                continue
            description = "Delete history" if is_numbered else "Named register"
            candidates.append((key, with_preview(description, info)))
        return candidates

    def __call__(self, ch: str):
        """Update command to vim status."""
        self.update_input_cmd_info(None, None, ch)

        self.vim_status.sub_mode = None

        return True


class FindCharacterExecutor(ExecutorSubBase):
    """Accept the target character for f/F/t/T and finish the pending motion."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

    def __call__(self, ch: str):
        """Go to the occurrence of character and execute."""
        ch_previous = self.vim_status.input_cmd.cmd[-1]
        method = self.motions.find_cmd_map.get(ch_previous, None)

        self.update_input_cmd_info(None, None, ch)

        self.vim_status.sub_mode = None

        if method:
            if len(self.parent_counts) == 1:
                count = self.parent_counts[0]
            else:
                count = self.parent_counts[0] * self.parent_counts[-1]
            motion_info = method(ch, count)
            return self.process_return(self.execute_func_deferred(motion_info))

        return True


class ReplaceCharacterExecutor(ExecutorSubBase):
    """Accept one replacement character for r and apply the captured selection."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.pos_start = 0
        self.pos_end = 0

    def __call__(self, ch: str):
        """Replace the character under the cursor with ch."""
        self.update_input_cmd_info(None, None, ch)

        self.edits.replace_with_character(self.pos_start, self.pos_end, ch)

        self.vim_status.sub_mode = None

        self.execute_func_deferred(None)

        return True


class FileExitExecutor(ExecutorSubBase):
    """Handle ZZ and ZQ through the host file actions supplied by the session."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        cmds = "ZQ"
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.editor_widget = vim_status.editor_widget

    def Q(self, count=1, count_text=""):
        """Close current file without saving."""
        self.close_current_file(force=True)
        self.vim_status.set_focus_to_vim()

    def Z(self, count=1, count_text=""):
        """Save and close current file."""
        self.save_and_close_current_file()
        self.vim_status.set_focus_to_vim()


class MarkNameExecutor(ExecutorSubBase):
    """Accept an alphanumeric mark/register continuation without interpreting a motion."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

    @property
    def hint_prefix(self):
        """Offer mark hints only while waiting for an apostrophe motion."""
        return "'" if self.vim_status.input_cmd.cmd.endswith("'") else None

    def get_hint_candidates(self):
        """List marks reachable by the pending direct jump or operator motion."""
        if self.hint_prefix is None:
            return []
        current = self.get_editorstack().get_current_filename()
        can_change_file = len(self.parent_counts) == 1
        return [
            (name, f"{osp.basename(info['file'])}:{info['line'] + 1}")
            for name, info in self.vim_status.bookmark_manager.list_bookmarks()
            if len(name) == 1
            and name.isalnum()
            and (can_change_file or info["file"] == current)
        ]

    def __call__(self, ch: str):
        """Return deferred result when ``ch`` is alphanumeric."""
        self.update_input_cmd_info(None, None, ch)

        self.vim_status.sub_mode = None

        if ch.isalnum():
            return self.process_return(self.execute_func_deferred(ch))

        return True


class PreviousStructureExecutor(ExecutorSubBase):
    """Resolve [ prefixes for previous definitions, cells and structural navigation."""

    def __init__(self, vim_status):
        """Initialize submode for ``[`` commands."""
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

        cmds = "".join(re.escape(c) for c in "dc[")
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))

    def d(self, count=1, count_text=""):
        """Go to previous warning/error."""
        count = count * self.parent_counts[0]
        editor = self.get_editor()
        for _ in range(count):
            editor.go_to_previous_warning()
        self.vim_status.cursor.draw_vim_cursor()

    def opensquarebracket(self, count=1, count_text=""):
        """Jump to previous Python definition."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.prev_pydef(count)
        return self.execute_func_deferred(motion_info)

    def c(self, count=1, count_text=""):
        """Move to the previous cell header."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.prev_cell(count)
        return self.execute_func_deferred(motion_info)


class NextStructureExecutor(ExecutorSubBase):
    """Resolve ] prefixes for next definitions, cells and structural navigation."""

    def __init__(self, vim_status):
        """Initialize submode for ``]`` commands."""
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

        cmds = "".join(re.escape(c) for c in "dc]")
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))

    def d(self, count=1, count_text=""):
        """Go to next warning/error."""
        count = count * self.parent_counts[0]
        editor = self.get_editor()
        for _ in range(count):
            editor.go_to_next_warning()
        self.vim_status.cursor.draw_vim_cursor()

    def closesquarebracket(self, count=1, count_text=""):
        """Jump to next Python definition."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.next_pydef(count)
        return self.execute_func_deferred(motion_info)

    def c(self, count=1, count_text=""):
        """Move to the next cell header."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.next_cell(count)
        return self.execute_func_deferred(motion_info)


class PreviousBlockExecutor(ExecutorSubBase):
    """Resolve { prefixes for previous Python block boundaries."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

        cmds = "{"
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))

    def openbrace(self, count=1, count_text=""):
        """Jump to previous Python block."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.prev_pyblock(count)
        return self.execute_func_deferred(motion_info)


class NextBlockExecutor(ExecutorSubBase):
    """Resolve } prefixes for next Python block boundaries."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

        cmds = "}"
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))

    def closebrace(self, count=1, count_text=""):
        """Jump to next Python block."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.next_pyblock(count)
        return self.execute_func_deferred(motion_info)


class WindowPrefixExecutor(ExecutorSubBase):
    """Dispatch directional focus and close commands for the active editor pane."""

    hint_prefix = "Ctrl+w"
    command_specs = (
        CommandSpec("h", "move", "Focus left split"),
        CommandSpec("j", "move", "Focus split below"),
        CommandSpec("k", "move", "Focus split above"),
        CommandSpec("l", "move", "Focus right split"),
        CommandSpec("c", "close", "Close current split"),
    )

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

    def move(self, count=1, count_text=""):
        """Focus the neighboring split, stopping at the window edge."""
        direction = self.vim_status.input_cmd.cmd[-1]
        for _ in range(count * self.parent_counts[0]):
            if not focus_neighbor(self.vim_status, direction):
                break

    def close(self, count=1, count_text=""):
        """Close an allowed split; the view owner restores input after rebinding."""
        stack = self.get_editorstack()
        if stack.is_closable:
            stack.close_split()


class ViewportPrefixExecutor(ExecutorSubBase):
    """Resolve z continuations that position the current line within the viewport."""

    hint_prefix = "z"
    command_specs = (
        CommandSpec("z", "z", "Center cursor line"),
        CommandSpec("t", "t", "Cursor line to top"),
        CommandSpec("b", "b", "Cursor line to bottom"),
    )

    def __init__(self, vim_status):
        """Initialize submode for ``z`` commands."""
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

    def scroll_cursor_to_center(self, offset: int):
        """Scroll cursor line to center."""
        pos = self.vim_status.get_cursor().position()

        editor = self.get_editor()
        line, _ = editor.get_cursor_line_column()
        editor.go_to_line(line + offset)

        self.vim_status.cursor.set_cursor_pos(pos)
        self.vim_status.cursor.draw_vim_cursor()

    def t(self, count=1, count_text=""):
        """Cursor line to top of screen."""
        visible_lines = self.vim_status.get_number_of_visible_lines()
        offset = visible_lines // 2 - 1
        self.scroll_cursor_to_center(offset)

        editor = self.get_editor()
        n_block = editor.blockCount()
        idx_block, _ = editor.get_cursor_line_column()
        leftover = offset - (n_block - idx_block)

        # When current line is near the end of the document, vim control scrollbar.
        if leftover > 0:
            scroll = editor.verticalScrollBar()
            v_max = scroll.maximum()
            v_current = scroll.value()
            offset_scroll = min([v_max, v_current + leftover])
            scroll.setValue(offset_scroll)

    def b(self, count=1, count_text=""):
        """Cursor line to bottom of screen."""
        visible_lines = self.vim_status.get_number_of_visible_lines()
        self.scroll_cursor_to_center(-(visible_lines // 2 - 1))

    def z(self, count=1, count_text=""):
        """Cursor line to center of screen."""
        self.scroll_cursor_to_center(1)


class ModeSubmodes:
    """Construct one mode's reusable continuations without sharing request state.

    Normal, character-Visual and line-Visual modes use the same set of prefix
    handlers. Each mode receives fresh instances, so search timers, Leap
    targets and deferred operator callbacks cannot leak between modes. Operator
    parsing keeps its own smaller set of continuations in operators.py.
    """

    def __init__(self, vim_status):
        # These session handlers depend on the prefix classes above. Delay their
        # import until instance assembly rather than create a module import cycle.
        # Project Libraries
        from spyder_okvim.executor.executor_easymotion import ExecutorEasymotion
        from spyder_okvim.executor.leap_input import LeapInputExecutor
        from spyder_okvim.executor.operators import (
            AroundTextObjectExecutor,
            InnerTextObjectExecutor,
        )
        from spyder_okvim.executor.search_prompt import SearchPromptExecutor

        self.g_prefix = GPrefixExecutor(vim_status)
        self.find_character = FindCharacterExecutor(vim_status)
        self.replace_character = ReplaceCharacterExecutor(vim_status)
        self.inner_text_object = InnerTextObjectExecutor(vim_status)
        self.around_text_object = AroundTextObjectExecutor(vim_status)
        self.register_prefix = RegisterPrefixExecutor(vim_status)
        self.mark_name = MarkNameExecutor(vim_status)
        self.search_prompt = SearchPromptExecutor(vim_status)
        self.easymotion = ExecutorEasymotion(vim_status)
        self.leap_input = LeapInputExecutor(vim_status)
        self.previous_structure = PreviousStructureExecutor(vim_status)
        self.next_structure = NextStructureExecutor(vim_status)
        self.previous_block = PreviousBlockExecutor(vim_status)
        self.next_block = NextBlockExecutor(vim_status)
