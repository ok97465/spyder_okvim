"""Executors for manipulating surrounding characters."""

# Project Libraries
from spyder_okvim.executor.executor_base import ExecutorSubBase
from spyder_okvim.utils.motion import MotionInfo, MotionType

SURROUNDINGS = "'\"{[()]}"


class ExecutorAddSurround(ExecutorSubBase):
    """Executor for adding surrounding."""

    def __init__(self, vim_status):
        """Initialize submode for adding surroundings."""
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self.has_zero_cmd = False

        self.pos_start = 0
        self.pos_end = 0

    def set_motion_info(self, motion_info: MotionInfo):
        """Set motion_info."""
        if motion_info.motion_type == MotionType.BlockWise:
            sel_start = motion_info.sel_start
            sel_end = motion_info.sel_end
        else:
            cursor = self.get_cursor()
            cursor_pos_cur = cursor.position()
            cursor_pos_new = motion_info.cursor_pos
            sel_start, sel_end = sorted([cursor_pos_cur, cursor_pos_new])

            if motion_info.motion_type == MotionType.CharWiseIncludingEnd:
                sel_end += 1
            elif motion_info.motion_type == MotionType.LineWise:
                block_start, _ = self.vim_status.cursor.get_block(sel_start)
                block_end, _ = self.vim_status.cursor.get_block(sel_end)
                sel_start = block_start.position()
                sel_end = block_end.position() + block_end.length() - 1

        self.pos_start = sel_start
        self.pos_end = sel_end

    def __call__(self, ch: str):
        """Add ``ch`` around the motion range."""
        self.vim_status.sub_mode = None

        ch = ch.replace("b", ")")
        ch = ch.replace("B", "}")

        if ch in SURROUNDINGS:
            self.update_input_cmd_info(None, None, ch)
            self.helper_action.add_surrounding(self.pos_start, self.pos_end, ch)

        self.vim_status.to_normal()
        self.vim_status.cursor.set_cursor_pos(self.pos_start)

        return True


class ExecutorDeleteSurround(ExecutorSubBase):
    """Executor for deleting surrounding."""

    def __init__(self, vim_status):
        """Initialize submode for deleting surroundings."""
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self.has_zero_cmd = False

    def __call__(self, ch: str):
        """Delete the surrounding character ``ch``."""
        self.vim_status.sub_mode = None

        ch = ch.replace("b", ")")
        ch = ch.replace("B", "}")

        if ch in SURROUNDINGS:
            self.update_input_cmd_info(None, None, ch)
            motion_info = self.helper_action.delete_surrounding(ch)
            if isinstance(motion_info.sel_start, int):
                self.vim_status.to_normal()
                self.vim_status.cursor.set_cursor_pos(motion_info.sel_start)

        return True


class ExecutorChangeSurround(ExecutorSubBase):
    """Executor for chaging surrounding."""

    def __init__(self, vim_status):
        """Initialize submode for changing surroundings."""
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self.has_zero_cmd = False

    def __call__(self, txt: str):
        """Replace the existing surrounding with ``txt``."""
        if len(txt) < 2:
            return False

        self.vim_status.sub_mode = None

        txt = txt.replace("b", ")")
        txt = txt.replace("B", "}")

        if txt[0] in SURROUNDINGS and txt[1] in SURROUNDINGS:
            self.update_input_cmd_info(None, None, txt)
            motion_info = self.helper_action.change_surrounding(txt[0], txt[1])
            if isinstance(motion_info.sel_start, int):
                self.vim_status.to_normal()
                self.vim_status.cursor.set_cursor_pos(motion_info.sel_start)

        return True
