"""Host navigation must confirm its destination after GUI event handoffs."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from spyder_okvim.spyder.editor import EditorCommands


@pytest.fixture
def navigation_host():
    stack = Mock()
    stack.get_current_filename.return_value = "origin.py"
    stack.is_file_opened.return_value = None
    cursor = SimpleNamespace(
        get_editor=lambda: None,
        get_editorstack=Mock(return_value=stack),
    )
    return EditorCommands(None, cursor, None, None), stack


def test_active_unsaved_buffer_does_not_require_a_disk_file(navigation_host):
    host, stack = navigation_host
    stack.get_current_filename.return_value = "unsaved.py"

    assert host.activate_file("unsaved.py")
    stack.set_current_filename.assert_not_called()


def test_opening_a_file_may_already_select_the_destination(
    navigation_host, monkeypatch, tmp_path
):
    host, stack = navigation_host
    path = str(tmp_path / "target.py")
    tmp_path.joinpath("target.py").write_text("destination\n")

    def open_file(target):
        assert target == path
        stack.is_file_opened.return_value = 0
        stack.get_current_filename.return_value = path

    monkeypatch.setattr(host, "open_file", open_file)

    assert host.activate_file(path)
    stack.set_current_filename.assert_not_called()


def test_focus_change_during_open_does_not_select_another_view(
    navigation_host, monkeypatch, tmp_path
):
    host, stack = navigation_host
    path = str(tmp_path / "target.py")
    tmp_path.joinpath("target.py").write_text("destination\n")

    def open_file(_):
        stack.is_file_opened.return_value = 0
        host.cursor.get_editorstack.return_value = Mock()

    monkeypatch.setattr(host, "open_file", open_file)

    assert not host.activate_file(path)
    stack.set_current_filename.assert_not_called()


def test_tab_activation_rechecks_the_captured_view(navigation_host):
    host, stack = navigation_host
    stack.is_file_opened.return_value = 0

    def select_file(_):
        host.cursor.get_editorstack.return_value = Mock()
        stack.get_current_filename.return_value = "target.py"

    stack.set_current_filename.side_effect = select_file

    assert not host.activate_file("target.py")
