"""Exercise external plugin registration against Spyder's current API."""

# Standard Libraries
from types import SimpleNamespace

# Third Party Libraries
import pytest
from spyder.config.manager import ConfigurationManager

# Project Libraries
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION, CONF_VERSION
from spyder_okvim.spyder.plugin import OkVim


@pytest.mark.parametrize("legacy", [False, True])
def test_external_configuration_registers_and_preserves_user_options(tmp_path, legacy):
    """Use real temporary config files for fresh and existing installations."""
    manager = SimpleNamespace(
        _plugin_configs={},
        get_plugin_config_path=lambda section: str(tmp_path),
        old_spyder_version="100.0.0",
    )
    plugin_class = OkVim
    if legacy:
        defaults = [(section, dict(values)) for section, values in CONF_DEFAULTS]
        dict(defaults)[CONF_SECTION].update(
            cursor_fg_color="#000000",
            cursor_bg_color="#BBBBBB",
            select_fg_color="#A9B7C6",
            select_bg_color="#214283",
            search_fg_color="#A9B7C6",
            search_bg_color="#30652F",
            yank_fg_color="#17172d",
            yank_bg_color="#5cacee",
        )
        plugin_class = type(
            "LegacyOkVim", (OkVim,), {"CONF_VERSION": None, "CONF_DEFAULTS": defaults}
        )
    ConfigurationManager.register_plugin(manager, plugin_class)
    _, config = manager._plugin_configs[CONF_SECTION]
    assert config.get("main", "version") == CONF_VERSION
    defaults = dict(CONF_DEFAULTS)[CONF_SECTION]
    assert config.get(CONF_SECTION, "leader_key") == defaults["leader_key"]

    config.set(CONF_SECTION, "leader_key", ",")
    config.set(CONF_SECTION, "yank_history_length", 25)
    config.set(CONF_SECTION, "which_key_delay", 150)
    manager._plugin_configs.clear()
    ConfigurationManager.register_plugin(manager, OkVim)
    _, reopened = manager._plugin_configs[CONF_SECTION]
    assert reopened.get(CONF_SECTION, "leader_key") == ","
    assert reopened.get(CONF_SECTION, "yank_history_length") == 25
    assert reopened.get(CONF_SECTION, "which_key_delay") == 150


def test_plugin_icon_is_available(qapp):
    """Create the plugin icon through Spyder's current icon manager."""
    assert not OkVim.get_icon().isNull()
