"""Completion and guide preferences remain independent of other prompt options."""

# Third Party Libraries
import pytest
from spyder.config.manager import CONF

# Project Libraries
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION
from spyder_okvim.spyder.confpage import OkvimConfigPage


def test_missing_substitute_guide_preference_defaults_enabled(vim_bot, monkeypatch):
    """An older configuration file uses the new guide's enabled default."""
    main, _, _, vim, _ = vim_bot
    assert dict(CONF_DEFAULTS)[CONF_SECTION]["substitute_guide_enabled"] is True
    monkeypatch.setattr(vim, "_conf", CONF)
    page = OkvimConfigPage(vim, main)
    get_option = page.get_option

    def without_guide_option(option, default, **kwargs):
        if option == "substitute_guide_enabled":
            return default
        return get_option(option, default, **kwargs)

    monkeypatch.setattr(page, "get_option", without_guide_option)
    try:
        page.initialize()
        assert page.substitute_guide_enabled.checkbox.isChecked()
    finally:
        page.deleteLater()


@pytest.mark.parametrize("guide_enabled", [False, True])
@pytest.mark.parametrize("history_enabled", [False, True])
def test_substitute_guide_preference_roundtrip(
    vim_bot, monkeypatch, guide_enabled, history_enabled
):
    """Toggle, save, and reopen the guide without changing history settings."""
    main, _, _, vim, _ = vim_bot
    monkeypatch.setattr(vim, "_conf", CONF)
    previous_guide = CONF.get(CONF_SECTION, "substitute_guide_enabled", True)
    previous_history = CONF.get(CONF_SECTION, "commandline_history_enabled", True)
    pages = []
    try:
        CONF.set(CONF_SECTION, "substitute_guide_enabled", guide_enabled)
        CONF.set(CONF_SECTION, "commandline_history_enabled", history_enabled)
        page = OkvimConfigPage(vim, main)
        pages.append(page)
        page.initialize()
        assert page.substitute_guide_enabled.checkbox.isChecked() is guide_enabled
        assert page.commandline_history_enabled.checkbox.isChecked() is history_enabled
        assert page.substitute_guide_enabled.isEnabled()
        page.substitute_guide_enabled.checkbox.click()
        page.save_to_conf()

        assert CONF.get(CONF_SECTION, "substitute_guide_enabled") is not guide_enabled
        assert CONF.get(CONF_SECTION, "commandline_history_enabled") is history_enabled
        reopened = OkvimConfigPage(vim, main)
        pages.append(reopened)
        reopened.initialize()
        assert (
            reopened.substitute_guide_enabled.checkbox.isChecked() is not guide_enabled
        )
        assert (
            reopened.commandline_history_enabled.checkbox.isChecked() is history_enabled
        )
    finally:
        for page in pages:
            page.deleteLater()
        CONF.set(CONF_SECTION, "substitute_guide_enabled", previous_guide)
        CONF.set(CONF_SECTION, "commandline_history_enabled", previous_history)


def test_missing_completion_preference_defaults_enabled(vim_bot, monkeypatch):
    """An older configuration enables completion suggestions by default."""
    main, _, _, vim, _ = vim_bot
    assert dict(CONF_DEFAULTS)[CONF_SECTION]["commandline_completion_enabled"] is True
    monkeypatch.setattr(vim, "_conf", CONF)
    page = OkvimConfigPage(vim, main)
    get_option = page.get_option

    def without_completion_option(option, default, **kwargs):
        if option == "commandline_completion_enabled":
            return default
        return get_option(option, default, **kwargs)

    monkeypatch.setattr(page, "get_option", without_completion_option)
    try:
        page.initialize()
        assert page.commandline_completion_enabled.checkbox.isChecked()
    finally:
        page.deleteLater()


@pytest.mark.parametrize("enabled", [False, True])
def test_completion_preference_roundtrip_is_independent(vim_bot, monkeypatch, enabled):
    """Saving completion visibility preserves the other prompt preferences."""
    main, _, _, vim, _ = vim_bot
    monkeypatch.setattr(vim, "_conf", CONF)
    options = {
        "commandline_completion_enabled": enabled,
        "commandline_history_enabled": not enabled,
        "substitute_guide_enabled": enabled,
        "substitute_preview_enabled": not enabled,
    }
    previous = {option: CONF.get(CONF_SECTION, option, True) for option in options}
    pages = []
    try:
        for option, value in options.items():
            CONF.set(CONF_SECTION, option, value)
        page = OkvimConfigPage(vim, main)
        pages.append(page)
        page.initialize()
        assert page.commandline_completion_enabled.checkbox.isChecked() is enabled
        page.commandline_completion_enabled.checkbox.click()
        page.save_to_conf()

        options["commandline_completion_enabled"] = not enabled
        reopened = OkvimConfigPage(vim, main)
        pages.append(reopened)
        reopened.initialize()
        for option, value in options.items():
            assert CONF.get(CONF_SECTION, option) is value
            assert getattr(reopened, option).checkbox.isChecked() is value
    finally:
        for page in pages:
            page.deleteLater()
        for option, value in previous.items():
            CONF.set(CONF_SECTION, option, value)
