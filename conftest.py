"""Repository test fixtures, loaded without importing Qt or Spyder eagerly."""

# Standard Libraries
import os
from unittest.mock import patch

# Third Party Libraries
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qtbot_module(qapp, request):
    """Provide a session-scoped Qt driver only to integration fixtures."""
    # Third Party Libraries
    from pytestqt.plugin import QtBot

    return QtBot(request)


@pytest.fixture(scope="session")
def vim_bot(qtbot_module, plugin_config_path):
    """Create Spyder editor widgets only for tests explicitly requesting them."""
    # Project Libraries
    from tests.qt_support import create_vim_session

    directory = plugin_config_path / "editors"
    directory.mkdir()
    yield from create_vim_session(qtbot_module, directory)


@pytest.fixture(scope="session")
def plugin_config_path(tmp_path_factory):
    """Keep persistent test data temporary and restore the user's plugin options."""
    # Third Party Libraries
    from spyder.config.manager import CONF

    # Project Libraries
    from spyder_okvim.spyder.config import CONF_SECTION
    from tests.qt_support import configuration_snapshot, restore_configuration

    directory = tmp_path_factory.mktemp("okvim-config")
    get_config_path = CONF.get_plugin_config_path
    original = configuration_snapshot()

    def isolated_path(plugin_name):
        if plugin_name == CONF_SECTION:
            return str(directory)
        return get_config_path(plugin_name)

    try:
        with patch.object(CONF, "get_plugin_config_path", side_effect=isolated_path):
            yield directory
    finally:
        restore_configuration(original)


@pytest.fixture(autouse=True)
def process_events_after_test(request):
    """Restore GUI settings and drain events only for tests using the shared editor."""
    if "vim_bot" not in request.fixturenames:
        yield
        return

    # Third Party Libraries
    from qtpy.QtCore import QCoreApplication
    from qtpy.QtWidgets import QApplication

    # Project Libraries
    from tests.qt_support import configuration_snapshot, restore_configuration

    _, _, _, vim, _ = request.getfixturevalue("vim_bot")
    widget = vim.vim_cmd
    options = configuration_snapshot()
    clipboard = QApplication.clipboard().text()
    try:
        yield
    finally:
        widget.which_key.cancel()
        widget.substitute_preview.cancel()
        restore_configuration(options)
        widget.apply_settings()
        QApplication.clipboard().setText(clipboard)
        QCoreApplication.processEvents()


@pytest.fixture
def substitute_bot(vim_bot):
    """Share the Ex integration fixture without importing another test module."""
    # Project Libraries
    from tests.qt_support import create_substitute_session

    yield from create_substitute_session(vim_bot)
