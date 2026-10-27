# -*- coding: utf-8 -*-
"""Collection of executor classes for various submodes."""

# Standard Libraries
import math
import os.path as osp
import re

# Third Party Libraries
from qtpy.QtCore import QTimer
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QTextEdit
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.executor.executor_base import (
    FUNC_INFO,
    RETURN_EXECUTOR_METHOD_INFO,
    CommandSpec,
    ExecutorSubBase,
)
from spyder_okvim.executor.executor_easymotion import ExecutorEasymotion
from spyder_okvim.executor.executor_surround import (
    ExecutorAddSurround,
    ExecutorChangeSurround,
    ExecutorDeleteSurround,
)
from spyder_okvim.spyder.config import CONF_SECTION
from spyder_okvim.utils.motion import MotionInfo, MotionType
from spyder_okvim.vim.state import VimState


class ExecutorSubMotion_i(ExecutorSubBase):
    """Submode of iw, i( ..."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

    def __call__(self, txt):
        """Parse command and execute."""
        self.update_input_cmd_info(None, None, txt)
        self.vim_status.sub_mode = None

        if txt in "wWp{}[]()'\"`bBc":
            if txt == "w":
                motion_info = self.helper_motion.i_w(self.parent_num[-1])
            elif txt == "W":
                motion_info = self.helper_motion.i_W(self.parent_num[-1])
            elif txt == "p":
                motion_info = self.helper_motion.i_p(math.prod(self.parent_num))
            elif txt in "'\"`":
                motion_info = self.helper_motion.i_quote(txt)
            elif txt == "c":
                motion_info = self.helper_motion.i_cell(self.parent_num[-1])
            else:
                txt = txt.replace("b", "(")
                txt = txt.replace("B", "{")
                motion_info = self.helper_motion.i_bracket(self.parent_num[-1], txt)

            if motion_info.sel_start is None or motion_info.sel_end is None:
                return True

            return self.process_return(self.execute_func_deferred(motion_info))

        return True


class ExecutorSubMotion_a(ExecutorSubBase):
    """Submode of aw, a( ..."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

    def __call__(self, txt):
        """Parse command and execute."""
        self.update_input_cmd_info(None, None, txt)
        self.vim_status.sub_mode = None

        if txt in "wWp{}[]()'\"`bB":
            if txt in "w":
                motion_info = self.helper_motion.a_w(self.parent_num[-1])
            elif txt == "W":
                motion_info = self.helper_motion.a_W(math.prod(self.parent_num))
            elif txt == "p":
                motion_info = self.helper_motion.a_p(math.prod(self.parent_num))
            elif txt in "'\"`":
                motion_info = self.helper_motion.a_quote(txt)
            else:
                txt = txt.replace("b", "(")
                txt = txt.replace("B", "{")
                motion_info = self.helper_motion.a_bracket(self.parent_num[-1], txt)

            if motion_info.sel_start is None or motion_info.sel_end is None:
                return True

            return self.process_return(self.execute_func_deferred(motion_info))

        return True


class ExecutorSubMotion(ExecutorSubBase):
    """Submode of motion."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.has_zero_cmd = True

        self.cmds = "/?nNailhkjHML$^wWbBegG%fFtT;,`' \b\r*#z[]"
        cmds = "".join(re.escape(c) for c in self.cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.executor_sub_sub_g = ExecutorSubSubCmd_g(vim_status)
        self.executor_sub_f_t = ExecutorSubCmd_f_t(vim_status)
        self.executor_sub_motion_i = ExecutorSubMotion_i(vim_status)
        self.executor_sub_motion_a = ExecutorSubMotion_a(vim_status)
        self.executor_sub_alnum = ExecutorSubCmd_alnum(vim_status)
        self.executor_sub_search = ExecutorSearch(vim_status)
        self.executor_sub_easymotion = ExecutorEasymotion(vim_status)
        self.executor_sub_leap = ExecutorSubCmdLeap(vim_status)
        self.executor_sub_opensquarebracekt = ExecutorSubCmd_opensquarebracket(
            vim_status
        )
        self.executor_sub_closesquarebracekt = ExecutorSubCmd_closesquarebracket(
            vim_status
        )

    def __call__(self, txt):
        """Parse command and execute."""
        if txt and self.vim_status.input_cmd.cmd and txt[-1] == self.vim_status.input_cmd.cmd[-1]:
            # Handle the case if the input is the same with previous input.
            cmd = txt[-1]
            if len(txt) == 1:
                num_str = ""
                num = 1
            else:
                num_str = txt[:-1]
                num = int(num_str)
            self.update_input_cmd_info(num_str, cmd, txt)

            self.vim_status.sub_mode = None

            return self.process_return(self.same_ch_input(num, num_str))
        else:
            return super().__call__(txt)

    def same_ch_input(self, num=1, num_str=""):
        """Handle the case if the input is the same with previous input."""
        num = num * self.parent_num[0] - 1
        motion_info = self.helper_motion.j(num)
        return self.execute_func_deferred(motion_info)

    def zero(self, num=1, num_str=""):
        """Go to the 1st character of the line and execute."""
        motion_info = self.helper_motion.zero()
        return self.execute_func_deferred(motion_info)

    def l(self, num=1, num_str=""):
        """Go to [num] characters to the right and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.l(num)
        return self.execute_func_deferred(motion_info)

    def h(self, num=1, num_str=""):
        """Go to [num] characters to the left and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.h(num)
        return self.execute_func_deferred(motion_info)

    def k(self, num=1, num_str=""):
        """Go to [num] lines upward linewise and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.k(num)
        return self.execute_func_deferred(motion_info)

    def j(self, num=1, num_str=""):
        """Go to [num] lines downward linewise and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.j(num)
        return self.execute_func_deferred(motion_info)

    def H(self, num=1, num_str=""):
        """Go to top of window(linewise) and execute."""
        motion_info = self.helper_motion.H()
        return self.execute_func_deferred(motion_info)

    def M(self, num=1, num_str=""):
        """Go to middle line of window(linewise) and execute."""
        motion_info = self.helper_motion.M()
        return self.execute_func_deferred(motion_info)

    def L(self, num=1, num_str=""):
        """Go to bottom line of window(linewise) and execute."""
        motion_info = self.helper_motion.L()
        return self.execute_func_deferred(motion_info)

    def dollar(self, num=1, num_str=""):
        """Go to the end of the line and execute."""
        motion_info = self.helper_motion.dollar()
        return self.execute_func_deferred(motion_info)

    def caret(self, num=1, num_str=""):
        """Go to the non-blank character of the line and execute."""
        motion_info = self.helper_motion.caret()
        return self.execute_func_deferred(motion_info)

    def w(self, num=1, num_str=""):
        """Move forward [num] words and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.w(num)
        return self.execute_func_deferred(motion_info)

    def W(self, num=1, num_str=""):
        """Move forward [num] WORDs and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.W(num)
        return self.execute_func_deferred(motion_info)

    def b(self, num=1, num_str=""):
        """Move backward [num] words and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.b(num)
        return self.execute_func_deferred(motion_info)

    def B(self, num=1, num_str=""):
        """Move backward [num] WORDS and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.B(num)
        return self.execute_func_deferred(motion_info)

    def e(self, num=1, num_str=""):
        """Move to the end of [num] words and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.e(num)
        return self.execute_func_deferred(motion_info)

    def G(self, num=1, num_str=""):
        """Go to [num] line and execute."""
        num = num * self.parent_num[0]
        num_str = num_str or self.parent_num_str[0]
        motion_info = self.helper_motion.G(num, num_str)
        return self.execute_func_deferred(motion_info)

    def g(self, num=1, num_str=""):
        """Execute submode of g."""
        executor_sub = self.executor_sub_sub_g
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def opensquarebracket(self, num=1, num_str=""):
        """Enter [ submode."""
        executor_sub = self.executor_sub_opensquarebracekt
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def closesquarebracket(self, num=1, num_str=""):
        """Enter ] submode."""
        executor_sub = self.executor_sub_closesquarebracekt
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def percent(self, num=1, num_str=""):
        """Find the next item in this line and execute."""
        motion_info = self.helper_motion.percent()
        return self.execute_func_deferred(motion_info)

    def f(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def F(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def t(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def T(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def semicolon(self, num=1, num_str=""):
        """Repeat latest f, t, F, T and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.semicolon(num)
        return self.execute_func_deferred(motion_info)

    def comma(self, num=1, num_str=""):
        """Repeat latest f, t, F, T in opposite direction and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.comma(num)
        return self.execute_func_deferred(motion_info)

    def apostrophe(self, num=1, num_str=""):
        """Motion to line of mark."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)

        def run(ch):
            motion_info = self.helper_motion.apostrophe(ch)
            return self.execute_func_deferred(motion_info)

        executor_sub.set_func_list_deferred([FUNC_INFO(run, True)])
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def backtick(self, num=1, num_str=""):
        """Motion to position of mark."""
        executor_sub = self.executor_sub_alnum
        self.set_parent_info_to_submode(executor_sub, num, num_str)

        def run(ch):
            motion_info = self.helper_motion.backtick(ch)
            return self.execute_func_deferred(motion_info)

        executor_sub.set_func_list_deferred([FUNC_INFO(run, True)])
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def i(self, num=1, num_str=""):
        """Select block exclusively."""
        executor_sub = self.executor_sub_motion_i

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def a(self, num=1, num_str=""):
        """Select block inclusively."""
        executor_sub = self.executor_sub_motion_a

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def slash(self, num=1, num_str="", forward=True):
        """Find text position."""
        executor_sub = self.executor_sub_search
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )
        if not executor_sub.begin(forward):
            return

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, False)

    def question(self, num=1, num_str=""):
        """Find text backward before executing the pending operator."""
        return self.slash(num, num_str, forward=False)

    def n(self, num=1, num_str=""):
        """Goto the next selected text."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.n(num)
        return self.execute_func_deferred(motion_info)

    def N(self, num=1, num_str=""):
        """Goto the next selected text."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.N(num)
        return self.execute_func_deferred(motion_info)

    def space(self, num=1, num_str=""):
        """Go to [num] characters to the right and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.space(num)
        return self.execute_func_deferred(motion_info)

    def backspace(self, num=1, num_str=""):
        """Go to [num] characters to the left and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.backspace(num)
        return self.execute_func_deferred(motion_info)

    def enter(self, num=1, num_str=""):
        """Go to [num] lines downward linewise and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.enter(num)
        return self.execute_func_deferred(motion_info)

    def asterisk(self, num=1, num_str=""):
        """Search word under cursor forward and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.asterisk(num)
        return self.execute_func_deferred(motion_info)

    def sharp(self, num=1, num_str=""):
        """Search word under cursor backward and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.sharp(num)
        return self.execute_func_deferred(motion_info)

    def run_easymotion(self, num=1, num_str=""):
        """Run easymotion."""
        executor_sub = self.executor_sub_easymotion

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def z(self, num=1, num_str=""):
        """Execute leap."""
        use_leap = CONF.get(CONF_SECTION, "use_leap")
        if use_leap:
            executor_sub = self.executor_sub_leap

            self.set_parent_info_to_submode(executor_sub, num, num_str)
            executor_sub.set_func_list_deferred(
                self.func_list_deferred, self.return_deferred
            )

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)


class ExecutorSubMotion_d(ExecutorSubMotion):
    """Replace w, W for d command in normal."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.cmds += "s"
        cmds = "".join(re.escape(c) for c in self.cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.executor_sub_delete_surround = ExecutorDeleteSurround(vim_status)

    def w(self, num=1, num_str=""):
        """Move forward [num] words and delete."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.w_for_d(num)
        return self.execute_func_deferred(motion_info)

    def W(self, num=1, num_str=""):
        """Move forward [num] WORDs and delete."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.W_for_d(num)
        return self.execute_func_deferred(motion_info)

    def s(self, num=1, num_str=""):
        """Delete surroundings."""
        executor_sub = self.executor_sub_delete_surround
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)


class ExecutorSubMotion_c(ExecutorSubMotion):
    """Replace w, W for c command in normal."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.cmds += "s"
        cmds = "".join(re.escape(c) for c in self.cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.executor_sub_change_surround = ExecutorChangeSurround(vim_status)

    def w(self, num=1, num_str=""):
        """Move forward [num] words and delete and start insert mode."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.w_for_c(num)
        return self.execute_func_deferred(motion_info)

    def W(self, num=1, num_str=""):
        """Move forward [num] WORDs and delete and start insert mode."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.W_for_c(num)
        return self.execute_func_deferred(motion_info)

    def s(self, num=1, num_str=""):
        """Change surroundings."""
        executor_sub = self.executor_sub_change_surround
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)


class ExecutorSubMotion_y(ExecutorSubMotion_d):
    """Add s for surround to normal y command."""

    def __init__(self, vim_status):
        """Extend yank motions with surround support."""
        super().__init__(vim_status)
        self.cmds += "s"
        cmds = "".join(re.escape(c) for c in self.cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))

        self.executor_sub_motion_c = ExecutorSubMotion_c(vim_status)
        self.executor_sub_surround = ExecutorAddSurround(vim_status)

    def s(self, num=1, num_str=""):
        """Add surroundings."""
        executor_sub = self.executor_sub_motion_c
        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [
                FUNC_INFO(self.executor_sub_surround.set_motion_info, True),
            ]
        )
        executor_sub.return_deferred = RETURN_EXECUTOR_METHOD_INFO(
            self.executor_sub_surround, True
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)


class ExecutorSubSubCmd_g(ExecutorSubBase):
    """Submode of Submode of g."""

    hint_prefix = "g"
    command_specs = (CommandSpec("g", "g", "Go to line"),)

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

    def g(self, num=1, num_str=""):
        """Goto line (gg)."""
        num = self.parent_num[-1] * self.parent_num[0]
        if self.parent_num_str[-1] == "" and self.parent_num_str[0] == "":
            num = 1
        motion_info = self.helper_motion.G(num, True)
        return self.execute_func_deferred(motion_info)


class ExecutorSubCmd_g(ExecutorSubBase):
    """Submode of g."""

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

        self.executor_sub_motion = ExecutorSubMotion(vim_status)

    def g(self, num=1, num_str=""):
        """Goto line(gg)."""
        num = self.parent_num[-1]
        if self.parent_num_str[-1] == "":
            num = 1
        motion_info = self.helper_motion.G(num, True)
        return self.execute_func_deferred(motion_info)

    def d(self, num=1, num_str=""):
        """Go to definition and update the jumplist."""
        vs = self.vim_status
        previous = vs.get_current_location()
        vs.push_jump()

        editor = self.get_editor()
        if editor:
            vs.start_definition_tracking(previous)
            editor.go_to_definition_from_cursor()

    def t(self, num=1, num_str=""):
        """Cycle to next file."""
        editor_stack = self.get_editorstack()
        if self.parent_num_str[-1] == "":
            editor_stack.tabs.tab_navigate(1)
        else:
            idx = self.parent_num[-1] - 1
            if editor_stack.get_stack_count() > idx:
                editor_stack.set_stack_index(idx)
        self.vim_status.set_focus_to_vim()

    def T(self, num=1, num_str=""):
        """Cycle to previous file."""
        editor_stack = self.get_editorstack()
        for _ in range(self.parent_num[-1]):
            editor_stack.tabs.tab_navigate(-1)
        self.vim_status.set_focus_to_vim()

    def u(self, num=1, num_str=""):
        """Make txt lowercase and move cursor to the start of selection."""
        if self.vim_status.is_normal():
            executor_sub = self.executor_sub_motion
            self.set_parent_info_to_submode(executor_sub, num, num_str)
            executor_sub.set_func_list_deferred(
                [FUNC_INFO(lambda x: self.helper_action.handle_case(x, "lower"), True)]
            )

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            self.helper_action.handle_case(None, "lower")

    def U(self, num=1, num_str=""):
        """Make txt uppercase and move the cursor to the start of selection."""
        if self.vim_status.is_normal():
            executor_sub = self.executor_sub_motion
            self.set_parent_info_to_submode(executor_sub, num, num_str)
            executor_sub.set_func_list_deferred(
                [FUNC_INFO(lambda x: self.helper_action.handle_case(x, "upper"), True)]
            )

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            self.helper_action.handle_case(None, "upper")

    def tilde(self, num=1, num_str=""):
        """Switch case of the character under the cursor.

        Move the cursor to the start of selection.
        """
        if self.vim_status.is_normal():
            executor_sub = self.executor_sub_motion
            self.set_parent_info_to_submode(executor_sub, num, num_str)
            executor_sub.set_func_list_deferred(
                [FUNC_INFO(lambda x: self.helper_action.handle_case(x, "swap"), True)]
            )

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            self.helper_action.handle_case(None, "swap")

    def c(self, num=1, num_str=""):
        """Toggle comment."""
        if self.vim_status.is_normal():
            executor_sub = self.executor_sub_motion
            self.set_parent_info_to_submode(executor_sub, num, num_str)
            executor_sub.set_func_list_deferred(
                [FUNC_INFO(lambda x: self.helper_action.toggle_comment(x), True)]
            )

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            self.helper_action.toggle_comment(None)


class ExecutorSubCmd_register(ExecutorSubBase):
    """Set register name."""

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


class ExecutorSubCmd_f_t(ExecutorSubBase):
    """Submode of f, t."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

    def __call__(self, ch: str):
        """Go to the occurrence of character and execute."""
        ch_previous = self.vim_status.input_cmd.cmd[-1]
        method = self.helper_motion.find_cmd_map.get(ch_previous, None)

        self.update_input_cmd_info(None, None, ch)

        self.vim_status.sub_mode = None

        if method:
            if len(self.parent_num) == 1:
                num = self.parent_num[0]
            else:
                num = self.parent_num[0] * self.parent_num[-1]
            motion_info = method(ch, num)
            return self.process_return(self.execute_func_deferred(motion_info))

        return True


class ExecutorSubCmdLeap(ExecutorSubBase):
    """Submode for Leap-style two-character motions."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self.selector = ExecutorSubCmdLeapSelect(vim_status, self)
        self._base_cmd: str | None = None

    def __call__(self, ch2: str):
        """Jump to the matching two-character sequence and execute."""
        if not ch2:
            return False
        if ch2 == "\x1b":
            self.on_escape()
            return True
        if not self.vim_status.input_cmd.cmd:
            self._clear_state(clear_input=True, clear_cmd_line=True)
            return True

        ch_previous = self.vim_status.input_cmd.cmd[-1]
        if len(ch2) == 1:
            base_cmd = ch_previous
            self._base_cmd = base_cmd
        else:
            base_cmd = self._base_cmd or ch_previous

        full_view = base_cmd in "sS"
        method = self.helper_motion.find_cmd_map.get(base_cmd, None)

        self.update_input_cmd_info(None, None, ch2)

        if len(ch2) == 1:
            reverse = base_cmd in "LSZ"
            self.helper_motion.leap_helper.preview_first_char(
                ch2, reverse, full_view=full_view
            )
            return False

        self.helper_motion.leap_helper.clear_overlays(preserve_preview=True)

        if not method:
            self.reset_base_cmd()
            return True

        if len(self.parent_num) == 1:
            num = self.parent_num[0]
        else:
            num = self.parent_num[0] * self.parent_num[-1]

        reverse = base_cmd in "LSZ"
        positions = self.helper_motion.search_in_view(
            ch2, reverse=reverse, full_view=full_view
        )
        if base_cmd in "sS":
            self.vim_status.find_info.set(base_cmd, ch2)
        elif reverse:
            self.vim_status.find_info.set("L", ch2)
        else:
            self.vim_status.find_info.set("l", ch2)

        def _dispatch_motion():
            if base_cmd in "sS":
                leap_method = (
                    self.helper_motion.leap_helper.reverse_leap
                    if reverse
                    else self.helper_motion.leap_helper.leap
                )
                return leap_method(
                    ch2, num, full_view=full_view, cmd_name=base_cmd
                )
            return method(ch2, num)

        if not positions:
            motion_info = _dispatch_motion()
            result = self.process_return(self.execute_func_deferred(motion_info))
            self._clear_state()
            return result

        if len(positions) == 1:
            motion_info = _dispatch_motion()
            result = self.process_return(self.execute_func_deferred(motion_info))
            self._clear_state()
            return result

        label_map = self.helper_motion.leap_helper.build_label_map(positions)
        self.helper_motion.leap_helper.show_label_map(label_map)

        motion_map = {
            label: self.helper_motion.leap_helper._set_motion_info(
                pos, motion_type=MotionType.CharWise
            )
            for label, pos in label_map.items()
        }

        self.selector.prepare_targets(motion_map)
        self.selector.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )
        self.set_parent_info_to_submode(
            self.selector, num, self.parent_num_str[-1] if self.parent_num_str else ""
        )
        return self.process_return(
            RETURN_EXECUTOR_METHOD_INFO(self.selector, True)
        )

    def reset_base_cmd(self) -> None:
        """Forget the command that initiated the current Leap sequence."""
        self._base_cmd = None

    def on_escape(self) -> None:
        """Handle escape by clearing Leap overlays."""
        self._clear_state(clear_input=True, clear_cmd_line=True)

    def _clear_state(self, *, clear_input: bool = False, clear_cmd_line: bool = False):
        """Reset Leap overlays and optionally clear command state."""
        self.helper_motion.leap_helper.clear_overlays()
        self.reset_base_cmd()
        if clear_input:
            self.vim_status.input_cmd.clear()
        self.vim_status.sub_mode = None
        if clear_cmd_line and hasattr(self.vim_status, "cmd_line"):
            self.vim_status.cmd_line.clear()


class ExecutorSubCmdLeapSelect(ExecutorSubBase):
    """Handle label selection after ambiguous Leap matches."""

    def __init__(self, vim_status, parent_executor: ExecutorSubCmdLeap):
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self._label_to_motion: dict[str, MotionInfo] = {}
        self._partial = ""
        self._parent_executor = parent_executor

    def on_escape(self) -> None:
        """Handle escape by cleaning up label targets."""
        self.cleanup()

    def prepare_targets(self, label_map: dict[str, MotionInfo]) -> None:
        """Store label mapping for subsequent keypresses."""
        self._label_to_motion = label_map
        self._partial = ""

    def cleanup(self) -> None:
        """Reset internal state and hide annotations."""
        self._label_to_motion = {}
        self._partial = ""
        self._parent_executor._clear_state(
            clear_input=True, clear_cmd_line=True
        )

    def __call__(self, ch: str):
        """Accept label characters and execute the matching motion."""
        if not ch:
            return False

        if ch == "\x1b":  # Escape
            self.cleanup()
            return True

        if ch == "\b":  # Backspace
            self._partial = self._partial[:-1]
            return False

        self._partial += ch

        matching_labels = [
            label
            for label in self._label_to_motion
            if label.startswith(self._partial)
        ]

        if not matching_labels:
            self.cleanup()
            return True

        if self._partial not in self._label_to_motion:
            return False

        motion_info = self._label_to_motion[self._partial]
        self.cleanup()
        return self.process_return(self.execute_func_deferred(motion_info))

class ExecutorSubCmd_r(ExecutorSubBase):
    """Submode of r."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.pos_start = 0
        self.pos_end = 0

    def __call__(self, ch: str):
        """Replace the character under the cursor with ch."""
        self.update_input_cmd_info(None, None, ch)

        self.helper_action.replace_txt_with_ch(self.pos_start, self.pos_end, ch)

        self.vim_status.sub_mode = None

        self.execute_func_deferred(None)

        return True


class ExecutorSubCmd_Z(ExecutorSubBase):
    """Submode of Z."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        cmds = "ZQ"
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.editor_widget = vim_status.editor_widget

    def Q(self, num=1, num_str=""):
        """Close current file without saving."""
        self.close_current_file(force=True)
        self.vim_status.set_focus_to_vim()

    def Z(self, num=1, num_str=""):
        """Save and close current file."""
        self.save_and_close_current_file()
        self.vim_status.set_focus_to_vim()


class ExecutorSearch(ExecutorSubBase):
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
        self.helper_motion.search(self._text, forward=self._forward)
        motion_info = self.helper_motion.n(math.prod(self.parent_num))
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
        self.helper_motion.search(pattern, forward=self._forward)
        motion_info = self.helper_motion.n(math.prod(self.parent_num))
        self.vim_status.sub_mode = None
        self._finish()
        if motion_info.cursor_pos is None:
            return True

        self.vim_status.push_jump()
        ret = self.process_return(self.execute_func_deferred(motion_info))
        self.vim_status.push_jump()
        return ret


class ExecutorSubCmd_alnum(ExecutorSubBase):
    """Allow the alphabetics and numbers as input."""

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
        can_change_file = len(self.parent_num) == 1
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


class ExecutorSubCmd_opensquarebracket(ExecutorSubBase):
    """submode of ["""

    def __init__(self, vim_status):
        """Initialize submode for ``[`` commands."""
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

        cmds = "".join(re.escape(c) for c in "dc[")
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))

    def d(self, num=1, num_str=""):
        """Go to previous warning/error."""
        num = num * self.parent_num[0]
        editor = self.get_editor()
        for _ in range(num):
            editor.go_to_previous_warning()
        self.vim_status.cursor.draw_vim_cursor()

    def opensquarebracket(self, num=1, num_str=""):
        """Jump to previous Python definition."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.prev_pydef(num)
        return self.execute_func_deferred(motion_info)

    def c(self, num=1, num_str=""):
        """Move to the previous cell header."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.prev_cell(num)
        return self.execute_func_deferred(motion_info)


class ExecutorSubCmd_closesquarebracket(ExecutorSubBase):
    """submode of ]"""

    def __init__(self, vim_status):
        """Initialize submode for ``]`` commands."""
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

        cmds = "".join(re.escape(c) for c in "dc]")
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))

    def d(self, num=1, num_str=""):
        """Go to next warning/error."""
        num = num * self.parent_num[0]
        editor = self.get_editor()
        for _ in range(num):
            editor.go_to_next_warning()
        self.vim_status.cursor.draw_vim_cursor()

    def closesquarebracket(self, num=1, num_str=""):
        """Jump to next Python definition."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.next_pydef(num)
        return self.execute_func_deferred(motion_info)

    def c(self, num=1, num_str=""):
        """Move to the next cell header."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.next_cell(num)
        return self.execute_func_deferred(motion_info)


class ExecutorSubCmd_openbrace(ExecutorSubBase):
    """Submode of {"""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

        cmds = "{"
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))

    def openbrace(self, num=1, num_str=""):
        """Jump to previous Python block."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.prev_pyblock(num)
        return self.execute_func_deferred(motion_info)


class ExecutorSubCmd_closebrace(ExecutorSubBase):
    """Submode of }"""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False

        self.has_zero_cmd = False

        cmds = "}"
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))

    def closebrace(self, num=1, num_str=""):
        """Jump to next Python block."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.next_pyblock(num)
        return self.execute_func_deferred(motion_info)


class ExecutorSubCmd_z(ExecutorSubBase):
    """Submode of z."""

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

    def t(self, num=1, num_str=""):
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

    def b(self, num=1, num_str=""):
        """Cursor line to bottom of screen."""
        visible_lines = self.vim_status.get_number_of_visible_lines()
        self.scroll_cursor_to_center(-(visible_lines // 2 - 1))

    def z(self, num=1, num_str=""):
        """Cursor line to center of screen."""
        self.scroll_cursor_to_center(1)
