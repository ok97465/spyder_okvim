"""Interpret pending operators and their inner/around text-object input.

Each executor owns its pending count and deferred actions. Motion results use
Qt UTF-16 document positions; applying edits remains the caller's action.
Related d/c/y variations live together so their Vim count and word rules can
be compared without switching modules.
"""

# Standard Libraries
import math
import re

# Project Libraries
from spyder_okvim.executor.executor_base import (
    DeferredAction,
    ExecutorSubBase,
    ExecutorTransition,
)
from spyder_okvim.executor.executor_easymotion import ExecutorEasymotion
from spyder_okvim.executor.executor_surround import (
    ExecutorAddSurround,
    ExecutorChangeSurround,
    ExecutorDeleteSurround,
)
from spyder_okvim.executor.leap_input import LeapInputExecutor
from spyder_okvim.executor.prefixes import (
    FindCharacterExecutor,
    MarkNameExecutor,
    NextStructureExecutor,
    OperatorGExecutor,
    PreviousStructureExecutor,
)
from spyder_okvim.executor.search_prompt import SearchPromptExecutor


class InnerTextObjectExecutor(ExecutorSubBase):
    """Resolve the object following i and pass its inner range to the pending action."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

    def __call__(self, txt):
        """Resolve the suffix and clear input unless a continuation is still pending."""
        self.update_input_cmd_info(None, None, txt)
        self.vim_status.sub_mode = None

        if txt in "wWp{}[]()'\"`bBc":
            if txt == "w":
                motion_info = self.motions.text_objects.inner_word(
                    self.parent_counts[-1]
                )
            elif txt == "W":
                motion_info = self.motions.text_objects.inner_WORD(
                    self.parent_counts[-1]
                )
            elif txt == "p":
                motion_info = self.motions.text_objects.inner_paragraph(
                    math.prod(self.parent_counts)
                )
            elif txt in "'\"`":
                motion_info = self.motions.text_objects.inner_quote(txt)
            elif txt == "c":
                motion_info = self.motions.i_cell(self.parent_counts[-1])
            else:
                txt = txt.replace("b", "(")
                txt = txt.replace("B", "{")
                motion_info = self.motions.text_objects.inner_bracket(
                    self.parent_counts[-1], txt
                )

            if motion_info.sel_start is None or motion_info.sel_end is None:
                return True

            return self.process_return(self.execute_func_deferred(motion_info))

        return True


class AroundTextObjectExecutor(ExecutorSubBase):
    """Resolve the object following a, including its surrounding delimiters or space."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

    def __call__(self, txt):
        """Resolve the suffix and clear input unless a continuation is still pending."""
        self.update_input_cmd_info(None, None, txt)
        self.vim_status.sub_mode = None

        if txt in "wWp{}[]()'\"`bB":
            if txt in "w":
                motion_info = self.motions.text_objects.around_word(
                    self.parent_counts[-1]
                )
            elif txt == "W":
                motion_info = self.motions.text_objects.around_WORD(
                    math.prod(self.parent_counts)
                )
            elif txt == "p":
                motion_info = self.motions.text_objects.around_paragraph(
                    math.prod(self.parent_counts)
                )
            elif txt in "'\"`":
                motion_info = self.motions.text_objects.around_quote(txt)
            else:
                txt = txt.replace("b", "(")
                txt = txt.replace("B", "{")
                motion_info = self.motions.text_objects.around_bracket(
                    self.parent_counts[-1], txt
                )

            if motion_info.sel_start is None or motion_info.sel_end is None:
                return True

            return self.process_return(self.execute_func_deferred(motion_info))

        return True


class OperatorMotionExecutor(ExecutorSubBase):
    """Resolve a motion for a pending operator, preserving explicit and inherited counts."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.has_zero_cmd = True

        self.cmds = "/?nNailhkjHML$^wWbBegG%fFtT;,`' \b\r*#z[]"
        cmds = "".join(re.escape(c) for c in self.cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.operator_g = OperatorGExecutor(vim_status)
        self.find_character = FindCharacterExecutor(vim_status)
        self.inner_text_object = InnerTextObjectExecutor(vim_status)
        self.around_text_object = AroundTextObjectExecutor(vim_status)
        self.mark_name = MarkNameExecutor(vim_status)
        self.search_prompt = SearchPromptExecutor(vim_status)
        self.easymotion = ExecutorEasymotion(vim_status)
        self.leap_input = LeapInputExecutor(vim_status)
        self.previous_structure = PreviousStructureExecutor(vim_status)
        self.next_structure = NextStructureExecutor(vim_status)

    def __call__(self, txt):
        """Resolve the suffix and clear input unless a continuation is still pending."""
        if (
            txt
            and self.vim_status.input_cmd.cmd
            and txt[-1] == self.vim_status.input_cmd.cmd[-1]
        ):
            # A repeated operator (dd/cc/yy) consumes its own optional count.
            cmd = txt[-1]
            if len(txt) == 1:
                count_text = ""
                count = 1
            else:
                count_text = txt[:-1]
                count = int(count_text)
            self.update_input_cmd_info(count_text, cmd, txt)

            self.vim_status.sub_mode = None

            return self.process_return(self.same_ch_input(count, count_text))
        else:
            return super().__call__(txt)

    def same_ch_input(self, count=1, count_text=""):
        """Turn a repeated operator such as dd into its counted linewise motion."""
        count = count * self.parent_counts[0] - 1
        motion_info = self.motions.j(count)
        return self.execute_func_deferred(motion_info)

    def zero(self, count=1, count_text=""):
        """Go to the 1st character of the line and execute."""
        motion_info = self.motions.zero()
        return self.execute_func_deferred(motion_info)

    def l(self, count=1, count_text=""):
        """Go to ``count`` characters to the right and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.l(count)
        return self.execute_func_deferred(motion_info)

    def h(self, count=1, count_text=""):
        """Go to ``count`` characters to the left and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.h(count)
        return self.execute_func_deferred(motion_info)

    def k(self, count=1, count_text=""):
        """Go to ``count`` lines upward linewise and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.k(count)
        return self.execute_func_deferred(motion_info)

    def j(self, count=1, count_text=""):
        """Go to ``count`` lines downward linewise and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.j(count)
        return self.execute_func_deferred(motion_info)

    def H(self, count=1, count_text=""):
        """Go to top of window(linewise) and execute."""
        motion_info = self.motions.H()
        return self.execute_func_deferred(motion_info)

    def M(self, count=1, count_text=""):
        """Go to middle line of window(linewise) and execute."""
        motion_info = self.motions.M()
        return self.execute_func_deferred(motion_info)

    def L(self, count=1, count_text=""):
        """Go to bottom line of window(linewise) and execute."""
        motion_info = self.motions.L()
        return self.execute_func_deferred(motion_info)

    def dollar(self, count=1, count_text=""):
        """Go to the end of the line and execute."""
        motion_info = self.motions.dollar()
        return self.execute_func_deferred(motion_info)

    def caret(self, count=1, count_text=""):
        """Go to the non-blank character of the line and execute."""
        motion_info = self.motions.caret()
        return self.execute_func_deferred(motion_info)

    def w(self, count=1, count_text=""):
        """Move forward ``count`` words and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.w(count)
        return self.execute_func_deferred(motion_info)

    def W(self, count=1, count_text=""):
        """Move forward ``count`` WORDs and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.W(count)
        return self.execute_func_deferred(motion_info)

    def b(self, count=1, count_text=""):
        """Move backward ``count`` words and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.b(count)
        return self.execute_func_deferred(motion_info)

    def B(self, count=1, count_text=""):
        """Move backward ``count`` WORDS and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.B(count)
        return self.execute_func_deferred(motion_info)

    def e(self, count=1, count_text=""):
        """Move to the end of ``count`` words and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.e(count)
        return self.execute_func_deferred(motion_info)

    def G(self, count=1, count_text=""):
        """Go to ``count`` line and execute."""
        count = count * self.parent_counts[0]
        count_text = count_text or self.parent_count_texts[0]
        motion_info = self.motions.G(count, count_text)
        return self.execute_func_deferred(motion_info)

    def g(self, count=1, count_text=""):
        """Execute submode of g."""
        executor_sub = self.operator_g
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return ExecutorTransition(executor_sub, True)

    def opensquarebracket(self, count=1, count_text=""):
        """Enter [ submode."""
        executor_sub = self.previous_structure
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return ExecutorTransition(executor_sub, True)

    def closesquarebracket(self, count=1, count_text=""):
        """Enter ] submode."""
        executor_sub = self.next_structure
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return ExecutorTransition(executor_sub, True)

    def percent(self, count=1, count_text=""):
        """Find the next item in this line and execute."""
        motion_info = self.motions.percent()
        return self.execute_func_deferred(motion_info)

    def f(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.find_character

        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return ExecutorTransition(executor_sub, True)

    def F(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.find_character

        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return ExecutorTransition(executor_sub, True)

    def t(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.find_character

        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return ExecutorTransition(executor_sub, True)

    def T(self, count=1, count_text=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.find_character

        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return ExecutorTransition(executor_sub, True)

    def semicolon(self, count=1, count_text=""):
        """Repeat latest f, t, F, T and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.semicolon(count)
        return self.execute_func_deferred(motion_info)

    def comma(self, count=1, count_text=""):
        """Repeat latest f, t, F, T in opposite direction and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.comma(count)
        return self.execute_func_deferred(motion_info)

    def apostrophe(self, count=1, count_text=""):
        """Motion to line of mark."""
        executor_sub = self.mark_name
        self.set_parent_info_to_submode(executor_sub, count, count_text)

        def run(ch):
            motion_info = self.motions.apostrophe(ch)
            return self.execute_func_deferred(motion_info)

        executor_sub.set_func_list_deferred([DeferredAction(run, True)])
        return ExecutorTransition(executor_sub, True)

    def backtick(self, count=1, count_text=""):
        """Motion to position of mark."""
        executor_sub = self.mark_name
        self.set_parent_info_to_submode(executor_sub, count, count_text)

        def run(ch):
            motion_info = self.motions.backtick(ch)
            return self.execute_func_deferred(motion_info)

        executor_sub.set_func_list_deferred([DeferredAction(run, True)])
        return ExecutorTransition(executor_sub, True)

    def i(self, count=1, count_text=""):
        """Select block exclusively."""
        executor_sub = self.inner_text_object

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return ExecutorTransition(executor_sub, True)

    def a(self, count=1, count_text=""):
        """Select block inclusively."""
        executor_sub = self.around_text_object

        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return ExecutorTransition(executor_sub, True)

    def slash(self, count=1, count_text="", forward=True):
        """Find text position."""
        executor_sub = self.search_prompt
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )
        if not executor_sub.begin(forward):
            return

        return ExecutorTransition(executor_sub, False)

    def question(self, count=1, count_text=""):
        """Find text backward before executing the pending operator."""
        return self.slash(count, count_text, forward=False)

    def n(self, count=1, count_text=""):
        """Goto the next selected text."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.n(count)
        return self.execute_func_deferred(motion_info)

    def N(self, count=1, count_text=""):
        """Goto the next selected text."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.N(count)
        return self.execute_func_deferred(motion_info)

    def space(self, count=1, count_text=""):
        """Go to ``count`` characters to the right and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.space(count)
        return self.execute_func_deferred(motion_info)

    def backspace(self, count=1, count_text=""):
        """Go to ``count`` characters to the left and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.backspace(count)
        return self.execute_func_deferred(motion_info)

    def enter(self, count=1, count_text=""):
        """Go to ``count`` lines downward linewise and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.enter(count)
        return self.execute_func_deferred(motion_info)

    def asterisk(self, count=1, count_text=""):
        """Search word under cursor forward and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.asterisk(count)
        return self.execute_func_deferred(motion_info)

    def sharp(self, count=1, count_text=""):
        """Search word under cursor backward and execute."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.sharp(count)
        return self.execute_func_deferred(motion_info)

    def run_easymotion(self, count=1, count_text=""):
        """Run easymotion."""
        executor_sub = self.easymotion

        self.set_parent_info_to_submode(executor_sub, count, count_text)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return ExecutorTransition(executor_sub, True)

    def z(self, count=1, count_text=""):
        """Execute leap."""
        use_leap = self.vim_status.settings.use_leap
        if use_leap:
            executor_sub = self.leap_input
            executor_sub.begin()

            self.set_parent_info_to_submode(executor_sub, count, count_text)
            executor_sub.set_func_list_deferred(
                self.func_list_deferred, self.return_deferred
            )

            return ExecutorTransition(executor_sub, True)


class DeleteOperatorExecutor(OperatorMotionExecutor):
    """Resolve d motions with Vim's delete-word rules and optional surrounding removal."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.cmds += "s"
        cmds = "".join(re.escape(c) for c in self.cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.delete_surround = ExecutorDeleteSurround(vim_status)

    def w(self, count=1, count_text=""):
        """Move forward ``count`` words and delete."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.w_for_d(count)
        return self.execute_func_deferred(motion_info)

    def W(self, count=1, count_text=""):
        """Move forward ``count`` WORDs and delete."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.W_for_d(count)
        return self.execute_func_deferred(motion_info)

    def s(self, count=1, count_text=""):
        """Delete surroundings."""
        executor_sub = self.delete_surround
        executor_sub.begin()
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        return ExecutorTransition(executor_sub, True)


class ChangeOperatorExecutor(OperatorMotionExecutor):
    """Resolve c motions with Vim's change-word rules and optional surrounding change."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.cmds += "s"
        cmds = "".join(re.escape(c) for c in self.cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.change_surround = ExecutorChangeSurround(vim_status)

    def w(self, count=1, count_text=""):
        """Move forward ``count`` words and delete and start insert mode."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.w_for_c(count)
        return self.execute_func_deferred(motion_info)

    def W(self, count=1, count_text=""):
        """Move forward ``count`` WORDs and delete and start insert mode."""
        count = count * self.parent_counts[0]
        motion_info = self.motions.W_for_c(count)
        return self.execute_func_deferred(motion_info)

    def s(self, count=1, count_text=""):
        """Change surroundings."""
        executor_sub = self.change_surround
        executor_sub.begin()
        self.set_parent_info_to_submode(executor_sub, count, count_text)
        return ExecutorTransition(executor_sub, True)


class YankOperatorExecutor(DeleteOperatorExecutor):
    """Resolve y motions and the ys continuation used to add surrounding text."""

    def __init__(self, vim_status):
        """Extend yank motions with surround support."""
        super().__init__(vim_status)
        self.cmds += "s"
        cmds = "".join(re.escape(c) for c in self.cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))

        self.change_operator = ChangeOperatorExecutor(vim_status)
        self.add_surround = ExecutorAddSurround(vim_status)

    def s(self, count=1, count_text=""):
        """Add surroundings."""
        executor_sub = self.change_operator
        self.set_parent_info_to_submode(executor_sub, count, count_text)

        executor_sub.set_func_list_deferred(
            [
                DeferredAction(self.add_surround.set_motion_info, True),
            ]
        )
        executor_sub.return_deferred = ExecutorTransition(self.add_surround, True)

        return ExecutorTransition(executor_sub, True)
