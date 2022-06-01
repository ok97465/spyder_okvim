
"""Tests for the executor_surround."""
# Third party imports
import pytest
from spyder_okvim.utils.vim_status import VimState


@pytest.mark.parametrize(
    "text, cmd_list, text_expected, cursor_pos",
    [
        ("", ["v", "S", "'"], "''", 0),
        ("", ["v", "S", "i"], "", 0),
        ("abde", ["l", "v", "S", "'"], "a'b'de", 1),
        ("abde", ["l", "v", "l" "S", '"'], 'a"bd"e', 1),
        ("abde", ["l", "v", "l" "S", '['], 'a[ bd ]e', 1),
        ("abde", ["l", "v", "l" "S", '{'], 'a{ bd }e', 1),
        ("abde", ["l", "v", "l" "S", '('], 'a( bd )e', 1),
        ("abde", ["l", "v", "l" "S", ']'], 'a[bd]e', 1),
        ("abde", ["l", "v", "l" "S", '}'], 'a{bd}e', 1),
        ("abde", ["l", "v", "l" "S", ')'], 'a(bd)e', 1),
        ("abde\ndd", ["l", "v", "j" "S", ')'], 'a(bde\ndd)', 1),
    ],
)
def test_surround_in_v(vim_bot, text, cmd_list, text_expected, cursor_pos):
    """Test surround command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        qtbot.keyClicks(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")

    assert sel == []
    assert cmd_line.text() == ""
    assert vim.vim_cmd.vim_status.vim_state == VimState.NORMAL
    assert editor.textCursor().position() == cursor_pos
    assert editor.toPlainText() == text_expected
