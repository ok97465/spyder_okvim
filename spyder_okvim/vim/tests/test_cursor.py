"""Cursor cleanup when settings change or a bound view is destroyed."""

# Standard Libraries
from dataclasses import replace
from types import SimpleNamespace

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent
from qtpy.QtWidgets import QWidget

# Project Libraries
from spyder_okvim.vim.cursor import VimCursor


@pytest.mark.parametrize("group", ["hl_yank", "hl_put"])
def test_disabling_highlight_clears_selection_and_timer(vim_bot, group):
    _, _, editor, vim, _ = vim_bot
    cursor = vim.vim_cmd.vim_status.cursor
    option = "highlight_yank" if group == "hl_yank" else "highlight_put"
    settings = vim.vim_cmd.vim_status.settings
    cursor.apply_settings(
        replace(settings, **{option: True}, highlight_yank_duration=1000)
    )
    editor.set_text("text")
    try:
        highlight = (
            cursor.highlight_yank if group == "hl_yank" else cursor.highlight_put
        )
        highlight(0, 1)
        assert editor.get_extra_selections(group)
        cursor.apply_settings(replace(settings, **{option: False}))
        assert not editor.get_extra_selections(group)
        assert group not in cursor._highlight_timers
    finally:
        cursor.apply_settings(settings)
        cursor.clear_highlights()


def test_deleted_bound_editorstack_uses_current_stack(vim_bot):
    _, stack, _, _, _ = vim_bot
    cursor = VimCursor(SimpleNamespace(get_current_editorstack=lambda: stack))
    bound_stack = QWidget()
    cursor.set_editorstack(bound_stack)
    assert cursor.get_editorstack() is bound_stack
    bound_stack.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert cursor.get_editorstack() is stack
