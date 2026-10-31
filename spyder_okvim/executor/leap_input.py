"""Interpret Leap character input and select ambiguous labeled targets.

The input executor and its label continuation share one short-lived search
request. Escape, failed matches and completed labels release annotations and
reset the request before another key sequence can reuse either executor.
"""

# Project Libraries
from spyder_okvim.executor.executor_base import ExecutorSubBase, ExecutorTransition
from spyder_okvim.utils.motion import MotionInfo, MotionType


class LeapInputExecutor(ExecutorSubBase):
    """Collect a two-character Leap target and delegate ambiguous matches to labels."""

    def __init__(self, vim_status):
        super().__init__(vim_status)
        self.allow_leaderkey = False
        self.selector = LeapLabelExecutor(vim_status, self)
        self._base_cmd: str | None = None

    def begin(self):
        """Start a fresh two-character request with its first input hint."""
        self.motions.leap_helper.clear_overlays()
        self.reset_base_cmd()
        self.vim_status.set_message("Leap: first character · Esc cancel")

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
        method = self.motions.find_cmd_map.get(base_cmd, None)

        self.update_input_cmd_info(None, None, ch2)

        if len(ch2) == 1:
            reverse = base_cmd in "LSZ"
            total, shown = self.motions.leap_helper.preview_first_char(
                ch2, reverse, full_view=full_view
            )
            self.show_stage("second character", total, shown)
            return False

        self.motions.leap_helper.clear_overlays(preserve_preview=True)

        if not method:
            self.reset_base_cmd()
            return True

        if len(self.parent_counts) == 1:
            count = self.parent_counts[0]
        else:
            count = self.parent_counts[0] * self.parent_counts[-1]

        reverse = base_cmd in "LSZ"
        positions = self.motions.leap_helper.search_in_view(
            ch2, reverse=reverse, full_view=full_view
        )
        if base_cmd in "sS":
            self.vim_status.find_info.set(base_cmd, ch2)
        elif reverse:
            self.vim_status.find_info.set("L", ch2)
        else:
            self.vim_status.find_info.set("l", ch2)

        if not positions:
            self._clear_state()
            self.vim_status.set_message("Leap: no matching target in this view")
            return True

        if len(positions) == 1:
            if base_cmd in "sS":
                leap_method = (
                    self.motions.leap_helper.reverse_leap
                    if reverse
                    else self.motions.leap_helper.leap
                )
                motion_info = leap_method(
                    ch2, count, full_view=full_view, cmd_name=base_cmd
                )
            else:
                motion_info = method(ch2, count)
            # Finish Leap before callbacks can start another prompt (such as
            # the delimiter input after ys), preserving its state and feedback.
            self._clear_state()
            return self.process_return(self.execute_func_deferred(motion_info))

        label_map = self.motions.leap_helper.build_label_map(positions)
        label_map = self.motions.leap_helper.show_label_map(label_map)
        if not label_map:
            self._clear_state()
            self.vim_status.set_message("Leap: no room for labels; scroll and retry")
            return True
        self.show_stage("select label", len(positions), len(label_map))

        motion_map = {
            label: MotionInfo(pos, motion_type=MotionType.CharWise)
            for label, pos in label_map.items()
        }

        self.selector.prepare_targets(motion_map)
        self.selector.set_func_list_deferred(
            self.func_list_deferred, self.return_deferred
        )
        self.set_parent_info_to_submode(
            self.selector,
            count,
            self.parent_count_texts[-1] if self.parent_count_texts else "",
        )
        return self.process_return(ExecutorTransition(self.selector, True))

    def reset_base_cmd(self) -> None:
        """Forget the command that initiated the current Leap sequence."""
        self._base_cmd = None

    def show_stage(self, stage, total, shown=None):
        """Describe the next input without moving focus from the command line."""
        message = f"Leap: {stage} · {total} candidates"
        if shown is not None and shown < total:
            message += f" · showing {shown}; refine characters or scroll and retry"
        self.vim_status.set_message(message + " · Esc cancel")

    def on_escape(self) -> None:
        """Handle escape by clearing Leap overlays."""
        self._clear_state(clear_input=True, clear_cmd_line=True)

    def _clear_state(self, *, clear_input: bool = False, clear_cmd_line: bool = False):
        """Reset Leap overlays and optionally clear command state."""
        self.motions.leap_helper.clear_overlays()
        self.reset_base_cmd()
        self.vim_status.set_message("")
        if clear_input:
            self.vim_status.input_cmd.clear()
        self.vim_status.sub_mode = None
        if clear_cmd_line and hasattr(self.vim_status, "cmd_line"):
            self.vim_status.cmd_line.clear()


class LeapLabelExecutor(ExecutorSubBase):
    """Select a labeled Leap target owned by one parent input executor."""

    def __init__(self, vim_status, parent_executor: LeapInputExecutor):
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
        self._parent_executor._clear_state(clear_input=True, clear_cmd_line=True)

    def __call__(self, ch: str):
        """Accept label characters and execute the matching motion."""
        if not ch:
            return False

        if ch == "\x1b":  # Escape
            self.cleanup()
            return True

        if ch == "\b":  # Backspace
            self._partial = self._partial[:-1]
            self._refresh_targets()
            return True

        self._partial += ch

        matching_labels = [
            label for label in self._label_to_motion if label.startswith(self._partial)
        ]

        if not matching_labels:
            self.cleanup()
            self.vim_status.set_message("Leap: no target for that label")
            return True

        if self._partial not in self._label_to_motion:
            self._refresh_targets()
            return True

        motion_info = self._label_to_motion[self._partial]
        self.cleanup()
        return self.process_return(self.execute_func_deferred(motion_info))

    def _refresh_targets(self):
        """Hide filtered targets and restore them when a prefix is erased."""
        matches = {
            label: motion.cursor_pos
            for label, motion in self._label_to_motion.items()
            if label.startswith(self._partial)
        }
        displayed = self.motions.leap_helper.show_label_map(
            matches, preserve_positions=True
        )
        stage = "select label"
        if self._partial:
            stage += f" ({self._partial}…)"
        self._parent_executor.show_stage(stage, len(matches), len(displayed))
