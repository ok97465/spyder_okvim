"""Compatibility import for the former editing helper constructor."""

# Project Libraries
from spyder_okvim.utils.editing import EditingActions


class ActionHelper(EditingActions):
    """Adapt legacy ``ActionHelper(motions)`` calls to explicit dependencies."""

    def __init__(self, helper_motion):
        super().__init__(helper_motion.vim_status, helper_motion)

    def handle_case(self, motion_info, method):
        """Compatibility alias for ``change_case``."""
        return self.change_case(motion_info, method)

    def replace_txt_with_ch(self, pos_start, pos_end, ch):
        """Compatibility alias for ``replace_with_character``."""
        return self.replace_with_character(pos_start, pos_end, ch)
