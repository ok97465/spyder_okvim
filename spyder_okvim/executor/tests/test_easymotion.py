# -*- coding: utf-8 -*-
"""Tests for the executor_easymotion."""

# Third Party Libraries
import pytest
from qtpy.QtCore import Qt

# Project Libraries
from tests.qt_support import reset_vim_state


@pytest.mark.parametrize(
    "method_name, cursor_position",
    [
        ("forwards_find_char", 2),
        ("backwards_find_char", 4),
        ("forwards_find_char", 0),
        ("backwards_find_char", 6),
    ],
)
def test_easymotion_character_targets_stay_in_view(
    vim_bot, monkeypatch, method_name, cursor_position
):
    """A document search may find a match beyond the visible search bounds."""
    from spyder_okvim.executor import executor_easymotion

    _, _, editor, vim, _ = vim_bot
    status = vim.vim_cmd.vim_status
    reset_vim_state(status)
    editor.set_text("x--x--x")
    status.cursor.set_cursor_pos(cursor_position)
    search = vim.vim_cmd.executor_normal_cmd.submodes.easymotion.executor_search_char
    monkeypatch.setattr(
        executor_easymotion, "_viewport_positions", lambda editor: (2, 4)
    )
    monkeypatch.setattr(
        search, "set_position_result_to_vim_status", lambda positions, _: positions
    )

    assert getattr(search, method_name)("x") == [3]


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "w"], 0),
        ("a b.c d;e\n", [Qt.Key_Space, Qt.Key_Space, "w", "h"], 2),
        ("a b.c d;e\n", ["w", Qt.Key_Space, Qt.Key_Space, "w", "h"], 4),
        ("a b.c d;e\n", [Qt.Key_Space, Qt.Key_Space, "w", "e", "l"], 1),
        ("a b.c d;e\n", [Qt.Key_Space, Qt.Key_Space, "1", "w", "e"], 0),
        ('a b.c d"e\n\nf', [Qt.Key_Space, Qt.Key_Space, "w", "u"], 11),
        (
            "a\nb\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nf",
            [Qt.Key_Space, Qt.Key_Space, "w", "h"],
            2,
        ),
        (
            "1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1",
            [Qt.Key_Space, Qt.Key_Space, "w", "rh"],
            30,
        ),
    ],
)
def test_easymotion_w_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion w command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["l", "v", Qt.Key_Space, Qt.Key_Space, "w", "u"],
            26,
            [1, 27],
        )
    ],
)
def test_easymotion_w_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test easymotion w command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        (
            """import numpy as np
import matplotlib.pyplot as plt
import scipy.scipy as sc""",
            ["V", Qt.Key_Space, Qt.Key_Space, "w", "u"],
            26,
            [0, 50],
        )
    ],
)
def test_easymotion_w_cmd_in_vline(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test easymotion w command in vline."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a b.c de",
            ["y", Qt.Key_Space, Qt.Key_Space, "w", "l"],
            0,
            "a b.c de",
            '"',
            "a b.c ",
        ),
        (
            "a b.c de\nf k",
            ["d", Qt.Key_Space, Qt.Key_Space, "w", "u"],
            0,
            "k",
            '"',
            "a b.c de\nf ",
        ),
        (
            "a b.c de\nf k",
            ["c", Qt.Key_Space, Qt.Key_Space, "w", "u"],
            0,
            "k",
            '"',
            "a b.c de\nf ",
        ),
    ],
)
def test_easymotion_w_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion w command in submotion."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "b"], 0),
        ("a b.c d;e\n", ["$", Qt.Key_Space, Qt.Key_Space, "b", "h"], 6),
        ("a b.c d;e\n", ["$", Qt.Key_Space, Qt.Key_Space, "b", "e", "h"], 7),
        ('a b.c d"e\n\nf', ["2j", Qt.Key_Space, Qt.Key_Space, "b", "y"], 2),
    ],
)
def test_easymotion_b_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion b command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a b.c de",
            ["$", "y", Qt.Key_Space, Qt.Key_Space, "b", "l"],
            2,
            "a b.c de",
            '"',
            "b.c d",
        ),
        (
            "a b.c de\nf k",
            ["j", "$", "d", Qt.Key_Space, Qt.Key_Space, "b", "y"],
            2,
            "a k",
            '"',
            "b.c de\nf ",
        ),
        (
            "a b.c de\nf k",
            ["j", "$", "c", Qt.Key_Space, Qt.Key_Space, "b", "y"],
            2,
            "a k",
            '"',
            "b.c de\nf ",
        ),
    ],
)
def test_easymotion_b_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion b command in submotion."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "j"], 0),
        ("a b.c d;", [Qt.Key_Space, Qt.Key_Space, "j", "l"], 1),
        ("a b.c d;\ne", [Qt.Key_Space, Qt.Key_Space, "j", "h"], 9),
        ("a b.c d;\n e", [Qt.Key_Space, Qt.Key_Space, "j", "h"], 10),
        ("a b.c d;\n e\n\nf", [Qt.Key_Space, Qt.Key_Space, "j", "l"], 13),
        (
            "a\nb\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nf",
            [Qt.Key_Space, Qt.Key_Space, "j", "h"],
            2,
        ),
    ],
)
def test_easymotion_j_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion j command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a b\nkk dd\nd",
            ["y", Qt.Key_Space, Qt.Key_Space, "j", "h"],
            0,
            "a b\nkk dd\nd",
            '"',
            "a b\nkk dd\n",
        ),
        (
            "a b\nkk dd\nd",
            ["d", Qt.Key_Space, Qt.Key_Space, "j", "h"],
            0,
            "d",
            '"',
            "a b\nkk dd\n",
        ),
        (
            "a b\nkk dd\nd",
            ["c", Qt.Key_Space, Qt.Key_Space, "j", "h"],
            0,
            "\nd",
            '"',
            "a b\nkk dd\n",
        ),
    ],
)
def test_easymotion_j_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion j command in submotion."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "k"], 0),
        ("a b.c d;", [Qt.Key_Space, Qt.Key_Space, "k", "l"], 1),
        (" a b.c d;\ne", ["j", Qt.Key_Space, Qt.Key_Space, "k", "h"], 1),
        ("a b.c d;\n e", ["j", Qt.Key_Space, Qt.Key_Space, "k", "h"], 0),
        ("a b.c d;\n e\n\nf", ["3j", Qt.Key_Space, Qt.Key_Space, "k", "l"], 0),
        (
            "a\nb\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nf",
            ["G", Qt.Key_Space, Qt.Key_Space, "k", "j"],
            31,
        ),
    ],
)
def test_easymotion_k_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion k command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a b\nkk dd\nd",
            ["j", "y", Qt.Key_Space, Qt.Key_Space, "k", "h"],
            0,
            "a b\nkk dd\nd",
            '"',
            "a b\nkk dd\n",
        ),
        (
            "a b\nkk dd\nd",
            ["j", "d", Qt.Key_Space, Qt.Key_Space, "k", "h"],
            0,
            "d",
            '"',
            "a b\nkk dd\n",
        ),
        (
            "a b\nkk dd\nd",
            ["j", "c", Qt.Key_Space, Qt.Key_Space, "k", "h"],
            0,
            "\nd",
            '"',
            "a b\nkk dd\n",
        ),
    ],
)
def test_easymotion_k_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion k command in submotion."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "f", "a"], 0),
        ("b a a\na", [Qt.Key_Space, Qt.Key_Space, "f", "a", "h"], 2),
        ("b a a\na", [Qt.Key_Space, Qt.Key_Space, "f", "a", "k"], 4),
    ],
)
def test_easymotion_f_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion f command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        (
            "import numpy as np",
            ["v", Qt.Key_Space, Qt.Key_Space, "f", "p", "h"],
            2,
            [0, 3],
        )
    ],
)
def test_easymotion_f_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test easymotion w command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a a.a aa",
            ["y", Qt.Key_Space, Qt.Key_Space, "f", "a", "l"],
            0,
            "a a.a aa",
            '"',
            "a a.a a",
        ),
        (
            "a a.a aa",
            ["d", Qt.Key_Space, Qt.Key_Space, "f", "a", "l"],
            0,
            "a",
            '"',
            "a a.a a",
        ),
        (
            "a a.a aa",
            ["c", Qt.Key_Space, Qt.Key_Space, "f", "a", "l"],
            0,
            "a",
            '"',
            "a a.a a",
        ),
    ],
)
def test_easymotion_f_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion f command in submotion."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos",
    [
        ("", [Qt.Key_Space, Qt.Key_Space, "F", "a"], 0),
        ("b a a\na", ["$", Qt.Key_Space, Qt.Key_Space, "F", "a", "h"], 2),
        ("b a a\na", ["j", Qt.Key_Space, Qt.Key_Space, "F", "b", "h"], 0),
    ],
)
def test_easymotion_F_cmd_in_normal(vim_bot, text, cmd_list, cursor_pos):
    """Test easymotion F command in normal."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    assert editor.textCursor().position() == cursor_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, sel_pos",
    [
        (
            "import numpy as np",
            ["$", "v", Qt.Key_Space, Qt.Key_Space, "F", "p", "h"],
            10,
            [10, 18],
        )
    ],
)
def test_easymotion_F_cmd_in_visual(vim_bot, text, cmd_list, cursor_pos, sel_pos):
    """Test easymotion F command in visual."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    sel = editor.get_extra_selections("vim_selection")[0]
    sel_pos_ = [sel.cursor.selectionStart(), sel.cursor.selectionEnd()]

    assert cmd_line.text() == ""
    assert editor.textCursor().position() == cursor_pos
    assert sel_pos_ == sel_pos


@pytest.mark.parametrize(
    "text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked",
    [
        (
            "a a.a aa",
            ["$", "y", Qt.Key_Space, Qt.Key_Space, "F", "a", "y"],
            0,
            "a a.a aa",
            '"',
            "a a.a a",
        ),
        (
            "a a.a aa",
            ["$", "d", Qt.Key_Space, Qt.Key_Space, "F", "a", "y"],
            0,
            "a",
            '"',
            "a a.a a",
        ),
        (
            "a a.a aa",
            ["$", "c", Qt.Key_Space, Qt.Key_Space, "F", "a", "y"],
            0,
            "a",
            '"',
            "a a.a a",
        ),
    ],
)
def test_easymotion_F_cmd_in_submotion(
    vim_bot, text, cmd_list, cursor_pos, text_expected, reg_name, text_yanked
):
    """Test easymotion F command in submotion."""
    _, _, editor, vim, qtbot = vim_bot
    editor.set_text(text)
    vim.vim_cmd.vim_status.cursor.set_cursor_pos(0)
    reset_vim_state(vim.vim_cmd.vim_status)

    cmd_line = vim.vim_cmd.commandline
    for cmd in cmd_list:
        if isinstance(cmd, str):
            qtbot.keyClicks(cmd_line, cmd)
        else:
            qtbot.keyPress(cmd_line, cmd)

    reg = vim.vim_cmd.vim_status.register_dict[reg_name]
    assert cmd_line.text() == ""
    assert editor.toPlainText() == text_expected
    assert editor.textCursor().position() == cursor_pos
    assert reg.content == text_yanked


def test_easymotion_backspace_restores_candidate_set():
    """Erasing a two-key prefix restores the original marker assignments."""
    from spyder_okvim.utils.easymotion import EasyMotionMarkerManager

    manager = EasyMotionMarkerManager()
    manager.set_positions(list(range(40)), 1)
    original = (manager.position_list[:], manager.name_list[:])
    manager.handle_user_input("r")
    assert 1 < len(manager.position_list) < 40
    manager.handle_user_input("\b")
    assert (manager.position_list, manager.name_list) == original


def test_easymotion_caps_positions_to_available_labels():
    """Unlabelled positions must never become selectable hidden targets."""
    from spyder_okvim.utils.easymotion import EasyMotionMarkerManager

    manager = EasyMotionMarkerManager()
    count = len(manager.marker_keys) + 10
    manager.set_positions(list(range(count)), 1)
    assert manager.total_count == count
    assert (
        len(manager.position_list) == len(manager.name_list) == len(manager.marker_keys)
    )


def test_leap_label_filter_and_backspace(vim_bot):
    """Partial labels redraw only their candidates; Backspace restores them."""
    from tests.qt_support import reset_vim_state

    _, _, editor, vim, qtbot = vim_bot
    status = vim.vim_cmd.vim_status
    reset_vim_state(status)
    editor.set_text("x\n" + ("ab " * 7 + "\n") * 5)
    status.cursor.set_cursor_pos(0)
    commandline = vim.vim_cmd.commandline
    qtbot.keyClicks(commandline, "sab")
    selector = status.sub_mode
    labels = dict(selector._label_to_motion)
    chosen = next(label for label in labels if len(label) == 2)
    qtbot.keyClicks(commandline, chosen[0])
    assert "select label" in status.msg_label.text()
    visible = [
        label.text() for label in status.labels_for_annotate if not label.isHidden()
    ]
    assert visible and all(label.startswith(chosen[0]) for label in visible)
    qtbot.keyPress(commandline, Qt.Key_Backspace)
    visible = [
        label.text() for label in status.labels_for_annotate if not label.isHidden()
    ]
    assert set(visible) == set(labels)
    qtbot.keyClicks(commandline, chosen)
    assert editor.textCursor().position() == labels[chosen].cursor_pos
    assert status.sub_mode is None
    assert all(label.isHidden() for label in status.labels_for_annotate)
