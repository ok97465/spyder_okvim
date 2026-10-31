"""Attach a pending action and inherited count when entering a continuation.

The decorated handler returns an executor; the wrapper supplies its parent
count and packages the transition for the caller. Preparing a continuation does
not execute its deferred edit or selection callback.
"""

# Standard Libraries
from collections.abc import Callable
from functools import wraps

from .executor_base import DeferredAction, ExecutorTransition


def submode(
    func_list_getter: Callable[[object], list[DeferredAction]] | None = None,
    clear_command_line: bool = True,
):
    """Return a decorator that prepares and enters a submode.

    The wrapped command returns its continuation executor. Parent count values
    retain the typed count text as well as the effective number, since an absent
    count is meaningful for commands such as gg. ``func_list_getter`` supplies
    callbacks only when the handler has not already prepared its own actions.
    ``clear_command_line`` controls input display after entering the submode;
    it does not indicate whether the Vim command has finished.
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, count=1, count_text=""):
            continuation = func(self, count, count_text)
            self.set_parent_info_to_submode(continuation, count, count_text)
            actions = func_list_getter(self) if func_list_getter else []
            if not continuation.func_list_deferred:
                continuation.set_func_list_deferred(actions)
            return ExecutorTransition(continuation, clear_command_line)

        return wrapper

    return decorator
