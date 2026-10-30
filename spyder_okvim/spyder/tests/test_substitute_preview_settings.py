"""Preview preferences survive upgrades without changing other prompt options."""

# Third Party Libraries
import pytest
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION
from spyder_okvim.spyder.confpage import OkvimConfigPage


def test_missing_substitute_preview_preference_defaults_enabled(vim_bot, monkeypatch):
    """An older configuration file uses the enabled default in Preferences."""
    main, _, _, vim, _ = vim_bot
    assert dict(CONF_DEFAULTS)[CONF_SECTION]["substitute_preview_enabled"] is True
    monkeypatch.setattr(vim, "_conf", CONF)
    page = OkvimConfigPage(vim, main)
    get_option = page.get_option

    def without_preview_option(option, default, **kwargs):
        if option == "substitute_preview_enabled":
            return default
        return get_option(option, default, **kwargs)

    monkeypatch.setattr(page, "get_option", without_preview_option)
    try:
        page.initialize()
        assert page.substitute_preview_enabled.checkbox.isChecked()
        assert page.substitute_preview_enabled.checkbox.text() == (
            "Enable incremental substitute preview (:s)"
        )
    finally:
        page.deleteLater()


@pytest.mark.parametrize("enabled", [False, True])
def test_substitute_preview_preference_roundtrip(vim_bot, monkeypatch, enabled):
    """Save and reopen preview while history and guide retain their values."""
    main, _, _, vim, _ = vim_bot
    monkeypatch.setattr(vim, "_conf", CONF)
    options = (
        "substitute_preview_enabled",
        "substitute_guide_enabled",
        "commandline_history_enabled",
    )
    previous = {option: CONF.get(CONF_SECTION, option, True) for option in options}
    pages = []
    try:
        CONF.set(CONF_SECTION, "substitute_preview_enabled", enabled)
        CONF.set(CONF_SECTION, "substitute_guide_enabled", False)
        CONF.set(CONF_SECTION, "commandline_history_enabled", True)
        page = OkvimConfigPage(vim, main)
        pages.append(page)
        page.initialize()
        assert page.substitute_preview_enabled.checkbox.isChecked() is enabled
        page.substitute_preview_enabled.checkbox.click()
        page.save_to_conf()

        assert CONF.get(CONF_SECTION, "substitute_preview_enabled") is not enabled
        assert CONF.get(CONF_SECTION, "substitute_guide_enabled") is False
        assert CONF.get(CONF_SECTION, "commandline_history_enabled") is True

        reopened = OkvimConfigPage(vim, main)
        pages.append(reopened)
        reopened.initialize()
        assert reopened.substitute_preview_enabled.checkbox.isChecked() is not enabled
        assert not reopened.substitute_guide_enabled.checkbox.isChecked()
        assert reopened.commandline_history_enabled.checkbox.isChecked()
    finally:
        for page in pages:
            page.deleteLater()
        for option, value in previous.items():
            CONF.set(CONF_SECTION, option, value)
