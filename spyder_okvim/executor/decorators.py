from functools import wraps
from typing import Callable, List

from .executor_base import FUNC_INFO, RETURN_EXECUTOR_METHOD_INFO


def submode(func_list_getter: Callable[[object], List[FUNC_INFO]] | None = None, clear_command_line: bool = True):
    """Decorator to handle common submode boilerplate."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, num=1, num_str=""):
            executor_sub = func(self, num, num_str)
            self.set_parent_info_to_submode(executor_sub, num, num_str)
            func_list = func_list_getter(self) if func_list_getter else []
            executor_sub.set_func_list_deferred(func_list)
            return RETURN_EXECUTOR_METHOD_INFO(executor_sub, clear_command_line)

        return wrapper

    return decorator
