"""Stable command observations survive recursive input and dispatch failures."""

# Standard Libraries
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party Libraries
import pytest

# Project Libraries
from spyder_okvim.vim import VimState


@pytest.fixture
def pending_command(vim_bot, monkeypatch):
    widget = vim_bot[3].vim_cmd
    executor = SimpleNamespace(
        hint_prefix="x",
        get_hint_candidates=Mock(side_effect=AssertionError("read before display")),
    )
    monkeypatch.setattr(widget.vim_status, "sub_mode", executor)
    monkeypatch.setattr(widget.vim_status, "vim_state", VimState.NORMAL)
    monkeypatch.setattr(widget.vim_status, "running_dot_cmd", False)
    monkeypatch.setattr(widget, "_macro_generation", -1)
    monkeypatch.setattr(widget.which_key, "enabled", False)
    widget.which_key.cancel()
    return widget, executor


def test_pending_hint_is_an_executor_independent_snapshot(pending_command):
    widget, executor = pending_command
    pending = widget.pending_hint()
    assert pending.executor is executor
    assert pending.editor() is widget.vim_status.get_editor()
    assert pending.mode == VimState.NORMAL
    assert pending.prefix == "x"

    # A configurable executor can change its prefix without changing identity.
    executor.hint_prefix = "y"
    updated = widget.pending_hint()
    assert updated != pending
    assert updated.prefix == "y"
    assert pending.prefix == "x"
    executor.get_hint_candidates.assert_not_called()


def test_nested_input_exception_releases_the_outer_boundary(pending_command):
    widget, _ = pending_command
    observations = []

    def started():
        observations.append(("start", widget.is_processing_input, widget.pending_hint()))

    def finished():
        observations.append(("finish", widget.is_processing_input, widget.pending_hint()))

    widget.sig_input_started.connect(started)
    widget.sig_input_finished.connect(finished)
    try:
        with pytest.raises(ValueError, match="dispatch failed"):
            with widget.input_processing():
                with widget.input_processing():
                    raise ValueError("dispatch failed")
        assert [entry[0] for entry in observations] == ["start", "finish"]
        assert observations[0][1:] == (True, None)
        assert observations[1][1] is False
        assert observations[1][2] == widget.pending_hint()

        # A failed command must not suppress the next input's observations.
        observations.clear()
        with widget.input_processing():
            assert widget.pending_hint() is None
        assert [entry[0] for entry in observations] == ["start", "finish"]
        assert not widget.is_processing_input
    finally:
        widget.sig_input_started.disconnect(started)
        widget.sig_input_finished.disconnect(finished)
