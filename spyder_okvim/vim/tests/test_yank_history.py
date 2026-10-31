"""History limits and collection through real Vim operator paths."""

# Standard Libraries
from dataclasses import FrozenInstanceError

# Third Party Libraries
import pytest

# Project Libraries
from spyder_okvim.vim.state import VimState
from spyder_okvim.vim.yank_history import YankEntry, YankHistory


def test_history_deduplicates_only_consecutive_text_and_kind():
    history = YankHistory()
    first = history.record("A", "charwise")
    assert history.record("A", "charwise", "delete") is None
    history.record("B", "charwise")
    newest = history.record("A", "charwise")
    assert [entry.text for entry in history.snapshot()] == ["A", "B", "A"]
    assert newest is not first
    history.record("A", "linewise")
    assert [entry.kind for entry in history.snapshot()[:2]] == ["linewise", "charwise"]


def test_history_snapshot_survives_eviction_resize_and_clear():
    history = YankHistory(length=2)
    first = history.record("one", "charwise")
    second = history.record("two", "charwise")
    snapshot = history.snapshot()
    third = history.record("three", "charwise")
    assert history.snapshot() == (third, second)
    history.resize(1)
    assert history.snapshot() == (third,)
    history.clear()
    assert history.snapshot() == ()
    assert history.byte_size == 0
    assert snapshot == (second, first)
    with pytest.raises(FrozenInstanceError):
        first.text = "changed"


def test_history_utf8_limits_skip_whole_value_and_evict_oldest():
    history = YankHistory(max_entry_bytes=6, max_bytes=8)
    history.record("abc", "charwise")
    history.record("def", "charwise")
    newest = history.record("한글", "charwise")
    assert history.snapshot() == (newest,)
    assert history.byte_size == 6
    assert history.record("한글!", "charwise") is None
    assert history.last_skip_reason == "oversize"
    assert history.snapshot() == (newest,)
    assert newest.text == "한글"


def test_history_empty_values_and_line_metadata():
    history = YankHistory()
    assert history.record("", "charwise") is None
    history.record(" ", "charwise")
    empty_line = history.record("\n", "linewise")
    assert empty_line.line_count == 1
    entry = history.record("one\u2029two\u2029", "linewise")
    assert entry.text == "one\ntwo\n"
    assert entry.line_count == 2
    assert len(history) == 3
    register = YankEntry.from_register("🙂", VimState.NORMAL)
    assert register.byte_size == 4
    assert register.kind == "charwise"
    assert YankEntry.from_register("line\n", VimState.VLINE).kind == "linewise"


@pytest.mark.parametrize("length", [0, -1, False, 1.5, "100"])
def test_history_rejects_invalid_length(length):
    with pytest.raises(ValueError):
        YankHistory(length)
    history = YankHistory()
    with pytest.raises(ValueError):
        history.resize(length)


@pytest.fixture
def history_bot(vim_bot):
    """Load Qt support only for the operator integration tests in this module."""
    # Third Party Libraries
    from qtpy.QtCore import QCoreApplication
    from qtpy.QtWidgets import QApplication

    # Project Libraries
    from tests.qt_support import reset_vim_state

    _, stack, _, vim, qtbot = vim_bot
    status = vim.vim_cmd.vim_status
    commandline = vim.vim_cmd.commandline
    old_index = stack.get_stack_index()
    old_clipboard = QApplication.clipboard().text()
    old_enabled = status.yanky_enabled
    commandline.setFocus()
    QCoreApplication.processEvents()
    commandline.esc_pressed()
    stack.set_stack_index(0)
    reset_vim_state(status)
    status.yanky_enabled = True
    commandline.clear()
    editor = stack.get_current_editor()
    editor.set_text("alpha\nbeta\ntail")
    status.cursor.set_cursor_pos(0)
    try:
        yield editor, status, commandline, qtbot
    finally:
        commandline.setFocus()
        commandline.esc_pressed()
        reset_vim_state(status)
        status.yanky_enabled = old_enabled
        QApplication.clipboard().setText(old_clipboard)
        stack.set_stack_index(old_index)


@pytest.mark.parametrize(
    "command, text, kind, source",
    [
        ("yy", "alpha\n", "linewise", "yank"),
        ("yiw", "alpha", "charwise", "yank"),
        ("vly", "al", "charwise", "yank"),
        ("dd", "alpha\n", "linewise", "delete"),
        ("ciw", "alpha", "charwise", "delete"),
        ("x", "a", "charwise", "delete"),
        ('"+yy', "alpha\n", "linewise", "yank"),
        ('"+dd', "alpha\n", "linewise", "delete"),
    ],
)
def test_each_operator_records_one_original_value(
    history_bot, command, text, kind, source
):
    _, status, commandline, qtbot = history_bot
    qtbot.keyClicks(commandline, command)
    assert len(status.yank_history) == 1
    entry = status.yank_history.snapshot()[0]
    assert (entry.text, entry.kind, entry.source) == (text, kind, source)


def test_cell_operator_records_one_linewise_value(history_bot):
    editor, status, commandline, qtbot = history_bot
    editor.set_text("# %%\nalpha\n# %%\nbeta")
    status.cursor.set_cursor_pos(0)
    qtbot.keyClicks(commandline, "yic")
    assert len(status.yank_history) == 1
    entry = status.yank_history.snapshot()[0]
    assert entry.kind == "linewise"
    assert entry.text == "# %%\nalpha\n"


def test_append_history_retains_operation_not_accumulated_register(history_bot):
    _, status, commandline, qtbot = history_bot
    qtbot.keyClicks(commandline, '"ayyj"Ayy')
    assert status.register_dict["a"].content == "alpha\nbeta\n"
    assert [entry.text for entry in status.yank_history.snapshot()] == [
        "beta\n",
        "alpha\n",
    ]


def test_black_hole_direct_writes_and_disabled_collection(history_bot):
    _, status, commandline, qtbot = history_bot
    status.set_register("a", "seed", VimState.NORMAL)
    assert len(status.yank_history) == 0
    qtbot.keyClicks(commandline, '"_yy"_x')
    assert len(status.yank_history) == 0
    status.yanky_enabled = False
    qtbot.keyClicks(commandline, "yy")
    assert len(status.yank_history) == 0
    assert status.register_dict['"'].content == "lpha\n"


def test_oversized_history_value_keeps_register_and_reports_skip(history_bot):
    _, status, _, _ = history_bot
    original = status.yank_history
    status.registers.history = YankHistory(max_entry_bytes=2)
    try:
        status.update_registers('"', "abc", VimState.NORMAL, is_yank=True)
        assert status.register_dict['"'].content == "abc"
        assert len(status.yank_history) == 0
        assert "memory limit" in status.msg_label.text()
    finally:
        status.registers.history = original


def test_multiline_yank_preserves_history_limit_warning(history_bot, monkeypatch):
    _, status, commandline, qtbot = history_bot
    monkeypatch.setattr(status.registers, "history", YankHistory(max_entry_bytes=2))

    qtbot.keyClicks(commandline, "y2j")

    assert "memory limit" in status.msg_label.text()
    assert status.register_dict['"'].content == "alpha\nbeta\ntail\n"


def test_black_hole_yank_reports_count_after_history_limit(history_bot, monkeypatch):
    _, status, commandline, qtbot = history_bot
    monkeypatch.setattr(status.registers, "history", YankHistory(max_entry_bytes=2))
    qtbot.keyClicks(commandline, "yy")
    assert "memory limit" in status.msg_label.text()

    qtbot.keyClicks(commandline, '"_y2j')

    assert status.msg_label.text() == "3 lines yanked"
    assert status.register_dict['"'].content == "alpha\n"
    assert len(status.yank_history) == 0
