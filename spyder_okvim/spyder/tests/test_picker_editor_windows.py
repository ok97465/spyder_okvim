"""Picker ownership in the paired fork's real editor-window hosts."""

import os

import pytest
from qtpy.QtCore import Qt

from spyder_okvim.spyder.tests.test_editor_windows import (
    _focus_stack,
    _settle,
    editor_windows,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("SPYDER_OKVIM_WINDOW_INTEGRATION") != "1",
    reason="Set SPYDER_OKVIM_WINDOW_INTEGRATION=1 with the paired Spyder fork",
)


@pytest.mark.parametrize("new_window", [False, True])
def test_picker_preview_in_real_host_preserves_document(editor_windows, new_window):
    state = editor_windows
    if new_window:
        window = state.widget.create_new_window()
        _settle()
        stack = window.editorwidget.editorstacks[0]
    else:
        state.widget.create_window()
        _settle()
        stack = state.widget.editorstacks[0]
    code = _focus_stack(state, stack)
    status = state.vim.vim_cmd.vim_status
    status.bookmark_manager.set_bookmark("a")
    before = (
        code.toPlainText(),
        code.textCursor().position(),
        tuple(status.jump_list.jumps),
    )
    state.vim.vim_cmd.open_picker("marks")
    picker = state.vim.vim_cmd.picker
    state.qtbot.waitUntil(lambda: picker.result_token is not None)
    state.qtbot.waitUntil(lambda: "alpha beta" in picker.dialog.preview.toPlainText())
    assert picker.dialog.window() is picker.dialog
    assert picker.dialog.parentWidget().window() is stack.window()
    state.qtbot.keyClick(picker.dialog.prompt, Qt.Key_Escape)
    state.qtbot.waitUntil(lambda: picker.phase == "closed")
    assert before == (
        code.toPlainText(),
        code.textCursor().position(),
        tuple(status.jump_list.jumps),
    )
    assert state.commandline.hasFocus()


def test_picker_cancels_when_real_host_is_undocked(editor_windows):
    state = editor_windows
    stack = state.widget.editorstacks[0]
    _focus_stack(state, stack)
    state.vim.vim_cmd.open_picker("marks")
    picker = state.vim.vim_cmd.picker
    state.qtbot.waitUntil(lambda: picker.result_token is not None)
    state.widget.create_window()
    _settle()
    state.qtbot.waitUntil(lambda: picker.phase == "closed")
    assert not picker.owns_focus
