"""Surround."""
# Local imports
from spyder_okvim.executor.executor_base import ExecutorSubBase

SURROUNDINGS = "'\"{[()]}"


class ExecutorVisualSurround(ExecutorSubBase):
    """Vim-surround in Visual mode."""

    def __init__(self, vim_status):
        """."""
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self.has_zero_cmd = False

        self.pos_start = 0
        self.pos_end = 0

    def __call__(self, ch: str):
        """."""
        self.vim_status.sub_mode = None

        if ch not in SURROUNDINGS:
            self.vim_status.to_normal()
            self.vim_status.cursor.set_cursor_pos(self.pos_start)
        else:
            self.update_input_cmd_info(None, None, ch)
            self.helper_action.add_surrounding(self.pos_start, self.pos_end, ch)
            self.execute_func_deferred(None)

        return True
