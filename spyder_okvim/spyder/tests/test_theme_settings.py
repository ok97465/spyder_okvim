"""Keep preferences independent of obsolete, manually configured colors."""

# Standard Libraries
from types import SimpleNamespace

# Project Libraries
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION, read_settings
from spyder_okvim.spyder.confpage import OkvimConfigPage


def test_applied_settings_ignore_legacy_colors(monkeypatch):
    options = {
        "cursor_fg_color": "#123456",
        "search_bg_color": "#654321",
        "annotation_fg_color": "#abcdef",
        "ignorecase": False,
        "highlight_yank_duration": 150,
    }

    def get_option(section, option, default=None):
        assert not option.endswith("_color")
        return options.get(option, default)

    monkeypatch.setattr(
        "spyder.config.manager.CONF", SimpleNamespace(get=get_option)
    )
    settings = read_settings()
    assert settings.ignorecase is False
    assert settings.highlight_yank_duration == 150
    assert not any(name.endswith("_color") for name in vars(settings))


def test_preferences_have_no_color_controls(vim_bot):
    main, _, _, vim, qtbot = vim_bot
    page = OkvimConfigPage(vim, main)
    qtbot.addWidget(page)
    page.setup_page()
    defaults = dict(CONF_DEFAULTS)[CONF_SECTION]
    assert not page.coloredits
    assert not any(name.endswith("_color") for name in defaults)
    assert "theme_colors_migrated" not in defaults
