# -*- coding: utf-8 -*-
"""."""
# %% Import
# Standard library imports
import re

# Local imports
from spyder_okvim.executor.executor_base import (ExecutorSubBase, FUNC_INFO,
                                                 RETURN_EXECUTOR_METHOD_INFO)


class ExecutorSubMotion_i(ExecutorSubBase):
    """Submode of iw, i( ..."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.has_zero_cmd = False

    def __call__(self, txt):
        """Parse command and execute."""
        self.update_input_cmd_info(None, None, txt)
        self.vim_status.sub_mode = None

        if txt in 'wW{}[]()\'"bB':
            if txt in "w":
                motion_info = self.helper_motion.i_w(self.parent_num[-1])
            elif txt in "W":
                motion_info = self.helper_motion.i_W(self.parent_num[-1])
            elif txt in '\'"':
                motion_info = self.helper_motion.i_quote(txt)
            else:
                txt = txt.replace('b', '(')
                txt = txt.replace('B', '{')
                motion_info = self.helper_motion.i_bracket(self.parent_num[-1],
                                                           txt)

            if motion_info.sel_start is None or motion_info.sel_end is None:
                return True

            self.execute_func_deferred(motion_info)

        return True


class ExecutorSubMotion_a(ExecutorSubBase):
    """Submode of aw, a( ..."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.has_zero_cmd = False

    def __call__(self, txt):
        """Parse command and execute."""
        self.update_input_cmd_info(None, None, txt)
        self.vim_status.sub_mode = None

        if txt in 'w{}[]()\'"bB':
            if txt in "w":
                motion_info = self.helper_motion.a_w(self.parent_num[-1])
            elif txt in '\'"':
                motion_info = self.helper_motion.a_quote(txt)
            else:
                txt = txt.replace('b', '(')
                txt = txt.replace('B', '{')
                motion_info = self.helper_motion.a_bracket(self.parent_num[-1],
                                                           txt)

            if motion_info.sel_start is None or motion_info.sel_end is None:
                return True

            self.execute_func_deferred(motion_info)

        return True


class ExecutorSubMotion(ExecutorSubBase):
    """Submode of motion."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.has_zero_cmd = True

        cmds = '/nNailhkjHML$^wWbegG%fFtT;, \b'
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.executor_sub_sub_g = ExecutorSubSubCmd_g(vim_status)
        self.executor_sub_f_t = ExecutorSubCmd_f_t(vim_status)
        self.executor_sub_motion_i = ExecutorSubMotion_i(vim_status)
        self.executor_sub_motion_a = ExecutorSubMotion_a(vim_status)
        self.executor_sub_search = ExecutorSearch(vim_status)

    def __call__(self, txt):
        """Parse command and execute."""
        if txt[-1] == self.vim_status.input_cmd.cmd[-1]:
            # Handle the case if the input is the same with previous input.
            cmd = txt[-1]
            if len(txt) == 1:
                num_str = ''
                num = 1
            else:
                num_str = txt[:-1]
                num = int(num_str)
            self.update_input_cmd_info(num_str, cmd, txt)
            self.same_ch_input(num, num_str)

            self.vim_status.sub_mode = None

            return True
        else:
            return super().__call__(txt)

    def same_ch_input(self, num=1, num_str=''):
        """Handle the case if the input is the same with previous input."""
        num = num * self.parent_num[0] - 1
        motion_info = self.helper_motion.j(num)
        self.execute_func_deferred(motion_info)

    def zero(self, num=1, num_str=''):
        """Go to the 1st character of the line and execute."""
        motion_info = self.helper_motion.zero()
        self.execute_func_deferred(motion_info)

    def l(self, num=1, num_str=''):
        """Go to [num] characters to the right and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.l(num)
        self.execute_func_deferred(motion_info)

    def h(self, num=1, num_str=''):
        """Go to [num] characters to the left and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.h(num)
        self.execute_func_deferred(motion_info)

    def k(self, num=1, num_str=''):
        """Go to [num] lines upward linewise and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.k(num)
        self.execute_func_deferred(motion_info)

    def j(self, num=1, num_str=''):
        """Go to [num] lines downward linewise and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.j(num)
        self.execute_func_deferred(motion_info)

    def H(self, num=1, num_str=''):
        """Go to top of window(linewise) and execute."""
        motion_info = self.helper_motion.H()
        self.execute_func_deferred(motion_info)

    def M(self, num=1, num_str=''):
        """Go to middle line of window(linewise) and execute."""
        motion_info = self.helper_motion.M()
        self.execute_func_deferred(motion_info)

    def L(self, num=1, num_str=''):
        """Go to bottom line of window(linewise) and execute."""
        motion_info = self.helper_motion.L()
        self.execute_func_deferred(motion_info)

    def dollar(self, num=1, num_str=''):
        """Go to the end of the line and execute."""
        motion_info = self.helper_motion.dollar()
        self.execute_func_deferred(motion_info)

    def caret(self, num=1, num_str=''):
        """Go to the non-blank character of the line and execute."""
        motion_info = self.helper_motion.caret()
        self.execute_func_deferred(motion_info)

    def w(self, num=1, num_str=''):
        """Move forward [num] words and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.w(num)
        self.execute_func_deferred(motion_info)

    def W(self, num=1, num_str=''):
        """Move forward [num] WORDs and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.W(num)
        self.execute_func_deferred(motion_info)

    def b(self, num=1, num_str=''):
        """Move backward [num] words and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.b(num)
        self.execute_func_deferred(motion_info)

    def e(self, num=1, num_str=''):
        """Move to the end of [num] words and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.e(num)
        self.execute_func_deferred(motion_info)

    def G(self, num=1, num_str=''):
        """Go to [num] line and execute."""
        num = num * self.parent_num[0]
        num_str = num_str or self.parent_num_str[0]
        motion_info = self.helper_motion.G(num, num_str)
        self.execute_func_deferred(motion_info)

    def g(self, num=1, num_str=''):
        """Execute submode of g."""
        executor_sub = self.executor_sub_sub_g
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(self.func_list_deferred)

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def percent(self, num=1, num_str=''):
        """Find the next item in this line and execute."""
        motion_info = self.helper_motion.percent()
        self.execute_func_deferred(motion_info)

    def f(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(self.func_list_deferred)

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def F(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(self.func_list_deferred)

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def t(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(self.func_list_deferred)

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def T(self, num=1, num_str=''):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(self.func_list_deferred)

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def semicolon(self, num=1, num_str=''):
        """Repeat latest f, t, F, T and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.semicolon(num)
        self.execute_func_deferred(motion_info)

    def comma(self, num=1, num_str=''):
        """Repeat latest f, t, F, T in opposite direction and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.comma(num)
        self.execute_func_deferred(motion_info)

    def i(self, num=1, num_str=''):
        """Select block exclusively."""
        executor_sub = self.executor_sub_motion_i

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(self.func_list_deferred)

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def a(self, num=1, num_str=''):
        """Select block inclusively."""
        executor_sub = self.executor_sub_motion_a

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(self.func_list_deferred)

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def slash(self, num=1, num_str=''):
        """Find text position."""
        executor_sub = self.executor_sub_search
        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(self.func_list_deferred)

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, False)

    def n(self, num=1, num_str=''):
        """Goto the next selected text."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.n(num)
        self.execute_func_deferred(motion_info)

    def N(self, num=1, num_str=''):
        """Goto the next selected text."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.N(num)
        self.execute_func_deferred(motion_info)

    def space(self, num=1, num_str=''):
        """Go to [num] characters to the right and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.space(num)
        self.execute_func_deferred(motion_info)

    def backspace(self, num=1, num_str=''):
        """Go to [num] characters to the left and execute."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.backspace(num)
        self.execute_func_deferred(motion_info)

class ExecutorSubMotion_d(ExecutorSubMotion):
    """Replace w, W for d command in normal."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

    def w(self, num=1, num_str=''):
        """Move forward [num] words and delete."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.w_for_d(num)
        self.execute_func_deferred(motion_info)

    def W(self, num=1, num_str=''):
        """Move forward [num] WORDs and delete."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.W_for_d(num)
        self.execute_func_deferred(motion_info)


class ExecutorSubMotion_c(ExecutorSubMotion):
    """Replace w, W for c command in normal."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

    def w(self, num=1, num_str=''):
        """Move forward [num] words and delete and start insert mode."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.w_for_c(num)
        self.execute_func_deferred(motion_info)

    def W(self, num=1, num_str=''):
        """Move forward [num] WORDs and delete and start insert mode."""
        num = num * self.parent_num[0]
        motion_info = self.helper_motion.W_for_c(num)
        self.execute_func_deferred(motion_info)


class ExecutorSubSubCmd_g(ExecutorSubBase):
    """Submode of Submode of g."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        cmds = 'g'
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))

    def g(self, num=1, num_str=''):
        """Goto line (gg)."""
        num = self.parent_num[-1] * self.parent_num[0]
        if self.parent_num_str[-1] == '' and self.parent_num_str[0] == '':
            num = 1
        motion_info = self.helper_motion.G(num, True)
        self.execute_func_deferred(motion_info)


class ExecutorSubCmd_g(ExecutorSubBase):
    """Submode of g."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        cmds = 'gdtTuUc~'
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.executor_sub_motion = ExecutorSubMotion(vim_status)

    def g(self, num=1, num_str=''):
        """Goto line(gg)."""
        num = self.parent_num[-1]
        if self.parent_num_str[-1] == '':
            num = 1
        motion_info = self.helper_motion.G(num, True)
        self.execute_func_deferred(motion_info)

    def d(self, num=1, num_str=''):
        """Go to definition."""
        self.get_editor().go_to_definition_from_cursor()
        # TODO: Need the API of spyder
        self.vim_status.set_focus_to_vim_after_delay(300)

    def t(self, num=1, num_str=''):
        """Cycle to next file."""
        editor_stack = self.get_editorstack()
        if self.parent_num_str[-1] == '':
            editor_stack.tabs.tab_navigate(1)
        else:
            idx = self.parent_num[-1] - 1
            if editor_stack.get_stack_count() > idx:
                editor_stack.set_stack_index(idx)
        self.vim_status.set_focus_to_vim()

    def T(self, num=1, num_str=''):
        """Cycle to previous file."""
        editor_stack = self.get_editorstack()
        for _ in range(self.parent_num[-1]):
            editor_stack.tabs.tab_navigate(-1)
        self.vim_status.set_focus_to_vim()

    def u(self, num=1, num_str=''):
        """Make txt lowercase and move cursor to the start of selection."""
        if self.vim_status.is_normal():
            executor_sub = self.executor_sub_motion
            self.set_parent_info_to_submode(executor_sub, num, num_str)
            executor_sub.set_func_list_deferred(
                [FUNC_INFO(
                    lambda x: self.helper_action.handle_case(x, 'lower'),
                    True)])

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            self.helper_action.handle_case(None, 'lower')

    def U(self, num=1, num_str=''):
        """Make txt uppercase and move the cursor to the start of selection."""
        if self.vim_status.is_normal():
            executor_sub = self.executor_sub_motion
            self.set_parent_info_to_submode(executor_sub, num, num_str)
            executor_sub.set_func_list_deferred(
                [FUNC_INFO(
                    lambda x: self.helper_action.handle_case(x, 'upper'),
                    True)])

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            self.helper_action.handle_case(None, 'upper')

    def tilde(self, num=1, num_str=''):
        """Switch case of the character under the cursor.

        Move the cursor to the start of selection.
        """
        if self.vim_status.is_normal():
            executor_sub = self.executor_sub_motion
            self.set_parent_info_to_submode(executor_sub, num, num_str)
            executor_sub.set_func_list_deferred(
                [FUNC_INFO(
                    lambda x: self.helper_action.handle_case(x, 'swap'),
                    True)])

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            self.helper_action.handle_case(None, 'swap')

    def c(self, num=1, num_str=''):
        """Toggle comment."""
        if self.vim_status.is_normal():
            executor_sub = self.executor_sub_motion
            self.set_parent_info_to_submode(executor_sub, num, num_str)
            executor_sub.set_func_list_deferred(
                [FUNC_INFO(lambda x: self.helper_action.toggle_comment(x),
                           True)])

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
        else:
            self.helper_action.toggle_comment(None)


class ExecutorSubCmd_register(ExecutorSubBase):
    """Set register name."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

    def __call__(self, ch: str):
        """Update command to vim status."""
        self.update_input_cmd_info(None, None, ch)

        self.vim_status.sub_mode = None

        return True


class ExecutorSubCmd_f_t(ExecutorSubBase):
    """Submode of f, t."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

    def __call__(self, ch: str):
        """Go to the occurrence of character and execute."""
        ch_previous = self.vim_status.input_cmd.cmd[-1]
        method = self.helper_motion.find_cmd_map.get(ch_previous, None)

        self.update_input_cmd_info(None, None, ch)

        if method:
            if len(self.parent_num) == 1:
                num = self.parent_num[0]
            else:
                num = self.parent_num[0] * self.parent_num[-1]
            motion_info = method(ch, num)
            self.execute_func_deferred(motion_info)

        self.vim_status.sub_mode = None

        return True


class ExecutorSubCmd_r(ExecutorSubBase):
    """Submode of r."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        self.pos_start = 0
        self.pos_end = 0

    def __call__(self, ch: str):
        """Replace the character under the cursor with ch."""
        self.update_input_cmd_info(None, None, ch)

        self.helper_action.replace_txt_with_ch(
            self.pos_start, self.pos_end, ch)

        self.execute_func_deferred(None)

        self.vim_status.sub_mode = None

        return True


class ExecutorSubCmd_Z(ExecutorSubBase):
    """Submode of Z."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        cmds = 'ZQ'
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.editor_widget = vim_status.editor_widget

    def Q(self, num=1, num_str=''):
        """Close current file without saving."""
        # TODO :
        self.editor_widget.close_action.trigger()
        self.vim_status.set_focus_to_vim()

    def Z(self, num=1, num_str=''):
        """Save and close current file."""
        self.editor_widget.save_action.trigger()
        self.editor_widget.close_action.trigger()
        self.vim_status.set_focus_to_vim()


class ExecutorSearch(ExecutorSubBase):
    """Submode of search."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

    def __call__(self, txt):
        """Parse txt and executor command.

        Returns
        -------
        bool
            if return is True, Clear command line

        """
        if txt[-1] != '\r':
            return False

        # '/' is saved to input cmd_info at ExecutorBase.
        # So we need only txt[1:].
        self.update_input_cmd_info(None, None, txt[1:])

        txt = txt[1:-1]  # remove /, \r

        self.helper_motion.search(txt)
        motion_info = self.helper_motion.n(1, '')
        self.execute_func_deferred(motion_info)

        self.vim_status.sub_mode = None

        return True
