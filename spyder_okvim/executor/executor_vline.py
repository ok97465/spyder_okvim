# -*- coding: utf-8 -*-
"""Vertical line selection helper."""

# Standard Libraries
import re

# Third Party Libraries
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.executor.executor_base import (
    FUNC_INFO,
    RETURN_EXECUTOR_METHOD_INFO,
    ExecutorBase,
)
from spyder_okvim.executor.decorators import submode
from spyder_okvim.executor.executor_colon import ExecutorColon
from spyder_okvim.executor.executor_easymotion import ExecutorEasymotion
from spyder_okvim.executor.executor_sub import (
    ExecutorSearch,
    ExecutorSubCmd_alnum,
    ExecutorSubCmd_closesquarebracket,
    ExecutorSubCmd_closebrace,
    ExecutorSubCmd_f_t,
    ExecutorSubCmd_g,
    ExecutorSubCmd_opensquarebracket,
    ExecutorSubCmd_openbrace,
    ExecutorSubCmd_r,
    ExecutorSubCmd_register,
    ExecutorSubCmdSneak,
)
from spyder_okvim.executor.mixins import MovementMixin, SelectionMixin
from spyder_okvim.spyder.config import CONF_SECTION


class ExecutorVlineCmd(SelectionMixin, MovementMixin, ExecutorBase):
    """Executor for vline."""

    def __init__(self, vim_status):
        super().__init__(vim_status)

        # MovementMixin hooks
        self.move_cursor = vim_status.cursor.set_cursor_pos_in_vline
        self.move_cursor_no_end = vim_status.cursor.set_cursor_pos_in_vline

        cmds = "uUovhydcsSxHjJklLMwWbBepP^$gG~:%fFtTnN/;,\"`'mr<>{} \b\r[]*#"
        cmds = "".join(re.escape(c) for c in cmds)
        self.pattern_cmd = re.compile(r"(\d*)([{}])".format(cmds))
        self.set_cursor_pos = vim_status.cursor.set_cursor_pos
        self.set_cursor_pos_in_vline = vim_status.cursor.set_cursor_pos_in_vline
        self.apply_motion_info_in_vline = (
            self.vim_status.cursor.apply_motion_info_in_vline
        )
        self.executor_sub_g = ExecutorSubCmd_g(vim_status)
        self.executor_sub_f_t = ExecutorSubCmd_f_t(vim_status)
        self.executor_sub_r = ExecutorSubCmd_r(vim_status)
        self.executor_sub_register = ExecutorSubCmd_register(vim_status)
        self.executor_sub_alnum = ExecutorSubCmd_alnum(vim_status)
        self.executor_sub_search = ExecutorSearch(vim_status)
        self.executor_sub_easymotion = ExecutorEasymotion(vim_status)
        self.executor_sub_sneak = ExecutorSubCmdSneak(vim_status)
        self.executor_colon = ExecutorColon(vim_status)
        self.executor_sub_opensquarebracekt = ExecutorSubCmd_opensquarebracket(
            vim_status
        )
        self.executor_sub_closesquarebracekt = (
            ExecutorSubCmd_closesquarebracket(vim_status)
        )
        self.executor_sub_openbrace = ExecutorSubCmd_openbrace(vim_status)
        self.executor_sub_closebrace = ExecutorSubCmd_closebrace(vim_status)

        # SelectionMixin hooks
        self.apply_motion_info_in_sel = self.apply_motion_info_in_vline
        self.set_cursor_pos_in_sel = self.set_cursor_pos_in_vline
        self.paste_in_sel = self.helper_action.paste_in_vline

    def v(self, num=1, num_str=""):
        """Start Visual mode per character."""
        self.vim_status.to_visual_char()

    def J(self, num=1, num_str=""):
        """Join lines, with a minimum of two lines."""
        block_no_start = self.get_block_no_start_in_selection()
        block_no_end = self.get_block_no_end_in_selection()

        if block_no_start is None:
            self.vim_status.to_normal()
            return

        if block_no_start == block_no_end:
            block_no_end += 1

        cursor_pos_start = self.get_pos_start_in_selection()
        self.helper_action.join_lines(cursor_pos_start, block_no_start, block_no_end)
        self.vim_status.to_normal()

    def g(self, num=1, num_str=""):
        """Start g submode."""
        executor_sub = self.executor_sub_g

        self.set_parent_info_to_submode(executor_sub, num, num_str)
        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def G(self, num=1, num_str=""):
        """Move to the line."""
        motion_info = self.helper_motion.G(num=num, num_str=num_str)

        self.set_cursor_pos_in_vline(motion_info.cursor_pos)

    def tilde(self, num=1, num_str=""):
        """Switch case of the character under the cursor.

        Move the cursor to the start of selection.
        """
        self.helper_action.handle_case(None, "swap")

    def f(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def F(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def t(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    def T(self, num=1, num_str=""):
        """Go to the next occurrence of a character."""
        executor_sub = self.executor_sub_f_t

        self.set_parent_info_to_submode(executor_sub, num, num_str)

        executor_sub.set_func_list_deferred(
            [FUNC_INFO(self.apply_motion_info_in_vline, True)]
        )

        return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_vline, True)])
    def opensquarebracket(self, num=1, num_str=""):
        """Start [ submode."""
        return self.executor_sub_opensquarebracekt

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_vline, True)])
    def closesquarebracket(self, num=1, num_str=""):
        """Start ] submode."""
        return self.executor_sub_closesquarebracekt

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_vline, True)])
    def openbrace(self, num=1, num_str=""):
        """Start { submode."""
        return self.executor_sub_openbrace

    @submode(lambda self: [FUNC_INFO(self.apply_motion_info_in_vline, True)])
    def closebrace(self, num=1, num_str=""):
        """Start } submode."""
        return self.executor_sub_closebrace

    def d(self, num=1, num_str=""):
        """Delete text."""
        editor = self.get_editor()
        block_no_start = self.get_block_no_start_in_selection()

        self.helper_action.yank(None)
        self.helper_action.delete(None, is_insert=False)
        self.vim_status.to_normal()

        # calc cursor position
        n_block = editor.blockCount()
        block_no = min([block_no_start, n_block - 1])
        block = editor.document().findBlockByNumber(block_no)
        cursor_pos = block.position()
        txt = block.text()
        cursor_pos += len(txt) - len(txt.lstrip())

        self.set_cursor_pos(cursor_pos)

    def S(self, num=1, num_str=""):
        """Delete text and start insert."""
        use_sneak = CONF.get(CONF_SECTION, "use_sneak")
        if use_sneak:
            executor_sub = self.executor_sub_sneak

            self.set_parent_info_to_submode(executor_sub, num, num_str)

            executor_sub.set_func_list_deferred(
                [
                    FUNC_INFO(self.apply_motion_info_in_vline, True),
                    FUNC_INFO(
                        self.helper_motion.display_another_group_after_rsneak, False
                    ),
                ]
            )

            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, True)
