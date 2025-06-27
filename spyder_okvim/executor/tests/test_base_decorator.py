import re
from spyder_okvim.executor.decorators import submode
from spyder_okvim.executor.executor_base import (
    ExecutorBase,
    ExecutorSubBase,
    FUNC_INFO,
    RETURN_EXECUTOR_METHOD_INFO,
)


class DummyInputCmd:
    def __init__(self):
        self.cmd = ""
        self.num_str = ""

    def set(self, other):
        self.cmd = other.cmd
        self.num_str = other.num_str


class DummyCursor:
    def __init__(self):
        self.pos = None

    def set_cursor_pos(self, pos):
        self.pos = pos

    def set_cursor_pos_without_end(self, pos):
        self.pos = pos


def noop(*args, **kwargs):
    return None


class DummyEditorWidget:
    def __init__(self):
        self.closed = False

    def get_widget(self):
        return self

    def close_file(self):
        self.closed = True


class DummyVimStatus:
    def __init__(self):
        self.cursor = DummyCursor()
        self.editor_widget = DummyEditorWidget()
        self.input_cmd = DummyInputCmd()
        self.input_cmd_prev = DummyInputCmd()
        self.sub_mode = None
        self.get_cursor = noop
        self.set_cursor = noop
        self.get_editor = noop
        self.get_editorstack = noop
        self.get_block_no_start_in_selection = noop
        self.get_block_no_end_in_selection = noop
        self.get_pos_start_in_selection = noop
        self.get_pos_end_in_selection = noop


class SimpleExecutor(ExecutorBase):
    def __init__(self, vs):
        super().__init__(vs)
        self.pattern_cmd = re.compile(r"(\d*)([ab])")
        self.calls = []

    def a(self, num=1, num_str=""):
        self.calls.append(("a", num, num_str))

    def b(self, num=1, num_str=""):
        self.calls.append(("b", num, num_str))


class DecoratorExecutor(ExecutorBase):
    def __init__(self, vs):
        super().__init__(vs)
        self.called = False

    @submode(lambda self: [FUNC_INFO(lambda: "ok", False)], clear_command_line=False)
    def sub(self, num=1, num_str=""):
        self.called = True
        return ExecutorSubBase(self.vim_status)


def test_process_return_and_close_file():
    vs = DummyVimStatus()
    exe = ExecutorSubBase(vs)
    info = RETURN_EXECUTOR_METHOD_INFO("sub", False)
    assert exe.process_return(info) is False
    assert vs.sub_mode == "sub"
    assert exe.process_return(None) is True
    assert vs.sub_mode is None

    exe.close_current_file()
    assert vs.editor_widget.closed


def test_call_dispatch_and_update_cmd():
    vs = DummyVimStatus()
    exe = SimpleExecutor(vs)
    assert exe("2a") is True
    assert exe.calls == [("a", 2, "2")]
    assert vs.input_cmd.num_str == "2"
    assert vs.input_cmd.cmd == "a"

    # Unknown command should clear sub_mode but return True
    assert exe("9x") is True
    assert vs.sub_mode is None


def test_submode_decorator():
    vs = DummyVimStatus()
    exe = DecoratorExecutor(vs)
    result = exe.sub(3, "3")
    assert isinstance(result, RETURN_EXECUTOR_METHOD_INFO)
    assert result.clear_command_line is False
    assert isinstance(result.sub_mode, ExecutorSubBase)
    # Parent info should be set by decorator
    assert result.sub_mode.parent_num == [3]
    assert result.sub_mode.parent_num_str == ["3"]
    # Func list should come from getter
    assert result.sub_mode.func_list_deferred[0].func() == "ok"
