"""Integration checks for OkVim keys in Spyder's own switcher popup."""

# Standard Libraries
from types import SimpleNamespace
from unittest.mock import Mock

# Third Party Libraries
import pytest
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QKeyEvent, QKeySequence
from qtpy.QtWidgets import QApplication, QLineEdit, QMainWindow, QShortcut
from spyder.api.plugins import Plugins
from spyder.config.manager import CONF
from spyder.plugins.switcher.container import SwitcherContainer
from spyder.plugins.switcher.widgets.switcher import Switcher

# Project Libraries
from spyder_okvim.spyder import plugin as plugin_module
from spyder_okvim.spyder.config import CONF_SECTION


@pytest.fixture
def switcher_navigation(vim_bot, monkeypatch):
    """Connect OkVim to a real switcher with a small file/symbol provider."""
    main, _, _, vim, qtbot = vim_bot
    host = QMainWindow()
    switcher = Switcher(host)
    switcher.add_mode("@", "Symbols")

    def populate(mode):
        switcher.clear()
        switcher.add_item(title="alpha", data=(mode, "alpha"), last_item=False)
        switcher.add_separator()
        switcher.add_item(title="beta", data=(mode, "beta"), last_item=False)
        switcher.add_item(title="gamma", data=(mode, "gamma"))

    switcher.sig_mode_selected.connect(populate)
    container = SimpleNamespace(
        switcher=switcher,
        _plugin=SimpleNamespace(get_main=lambda: host),
        get_conf=lambda *args, **kwargs: False,
    )
    service = SimpleNamespace(
        get_container=lambda: container,
        open_switcher=lambda symbol=False: SwitcherContainer.open_switcher(
            container, symbol
        ),
    )
    previous_main_get_plugin = main.get_plugin
    previous_vim_get_plugin = vim.get_plugin
    monkeypatch.setattr(
        main,
        "get_plugin",
        lambda name, **kwargs: service
        if name == Plugins.Switcher
        else previous_main_get_plugin(name, **kwargs),
    )
    monkeypatch.setattr(
        vim,
        "get_plugin",
        lambda name, **kwargs: service
        if name == Plugins.Switcher
        else previous_vim_get_plugin(name, **kwargs),
    )
    previous_leader = CONF.get(CONF_SECTION, "leader_key")
    CONF.set(CONF_SECTION, "leader_key", "Space")
    vim.vim_cmd.set_leader_key()
    vim.on_switcher_available()

    def open_switcher(key="p"):
        commandline = vim.vim_cmd.commandline
        main.show()
        main.activateWindow()
        commandline.esc_pressed()
        commandline.setFocus()
        QApplication.processEvents()
        qtbot.keyPress(commandline, Qt.Key_Space)
        qtbot.keyClicks(commandline, key)
        QApplication.processEvents()
        assert switcher.isVisible()
        assert QApplication.focusWidget() is switcher.edit
        return switcher

    state = SimpleNamespace(
        vim=vim,
        qtbot=qtbot,
        host=host,
        switcher=switcher,
        container=container,
        open=open_switcher,
    )
    try:
        yield state
    finally:
        vim.on_switcher_teardown()
        switcher.reject()
        host.close()
        host.deleteLater()
        CONF.set(CONF_SECTION, "leader_key", previous_leader)
        vim.vim_cmd.set_leader_key()
        main.activateWindow()
        vim.vim_cmd.commandline.setFocus()
        QApplication.processEvents()


@pytest.mark.parametrize("leader,mode", [("p", ""), ("s", "@")])
def test_leader_switchers_navigate_like_arrow_keys(switcher_navigation, leader, mode):
    """Both leader actions retain focus, skip separators and wrap once per key."""
    state = switcher_navigation
    switcher = state.open(leader)
    assert switcher.get_mode() == mode
    assert switcher.edit.text() == mode
    assert switcher.current_row() == 0

    for key, row in [(Qt.Key_N, 2), (Qt.Key_P, 0), (Qt.Key_P, 3), (Qt.Key_N, 0)]:
        state.qtbot.keyClick(switcher.edit, key, Qt.ControlModifier)
        assert switcher.current_row() == row
        assert switcher.edit.text() == mode
        assert QApplication.focusWidget() is switcher.edit


def test_switcher_preserves_typing_arrows_enter_and_escape(switcher_navigation):
    """The added keys leave the popup's existing editing and selection intact."""
    state = switcher_navigation
    switcher = state.open()
    selected = Mock()
    rejected = Mock()
    switcher.sig_item_selected.connect(selected)
    switcher.sig_rejected.connect(rejected)

    state.qtbot.keyClicks(switcher.edit, "a")
    assert switcher.edit.text() == "a"
    state.qtbot.keyClick(switcher.edit, Qt.Key_Backspace)
    state.qtbot.keyClick(switcher.edit, Qt.Key_Down)
    assert switcher.current_row() == 2
    state.qtbot.keyClick(switcher.edit, Qt.Key_Up)
    assert switcher.current_row() == 0
    state.qtbot.keyClick(switcher.edit, Qt.Key_Return)
    selected.assert_called_once()
    assert selected.call_args.args[0].get_title() == "alpha"
    state.qtbot.keyClick(switcher.edit, Qt.Key_Escape)
    assert not switcher.isVisible()
    rejected.assert_called_once()


def test_switcher_overrides_global_shortcuts_without_moving_twice(switcher_navigation):
    """Reserve the shortcut first, then move only on the actual key press."""
    state = switcher_navigation
    outside = QLineEdit(state.host)
    state.host.setCentralWidget(outside)
    state.host.show()
    activated = Mock()
    shortcut = QShortcut(QKeySequence("Ctrl+N"), outside)
    shortcut.setContext(Qt.ApplicationShortcut)
    shortcut.activated.connect(activated)
    switcher = state.open()

    override = QKeyEvent(QEvent.ShortcutOverride, Qt.Key_N, Qt.ControlModifier)
    override.ignore()
    QCoreApplication.sendEvent(switcher.edit, override)
    assert override.isAccepted()
    assert switcher.current_row() == 0

    state.qtbot.keyClick(switcher.edit, Qt.Key_N, Qt.ControlModifier)
    assert switcher.current_row() == 2
    activated.assert_not_called()

    state.vim.on_switcher_teardown()
    state.qtbot.keyClick(switcher.edit, Qt.Key_N, Qt.ControlModifier)
    assert switcher.current_row() == 2
    activated.assert_called_once()

    switcher.hide()
    state.host.activateWindow()
    outside.setFocus()
    QApplication.processEvents()
    state.qtbot.keyClick(outside, Qt.Key_N, Qt.ControlModifier)
    assert activated.call_count == 2


def test_switcher_attach_and_teardown_restore_existing_key_handling(switcher_navigation):
    """Repeated registration installs one handler, which teardown removes."""
    state = switcher_navigation
    switcher = state.open()
    state.vim.on_switcher_available()
    state.vim.on_switcher_available()
    state.qtbot.keyClick(switcher.edit, Qt.Key_N, Qt.ControlModifier)
    assert switcher.current_row() == 2

    state.vim.on_switcher_teardown()
    state.vim.on_switcher_teardown()
    state.qtbot.keyClick(switcher.edit, Qt.Key_P, Qt.ControlModifier)
    assert switcher.current_row() == 2
    state.qtbot.keyClick(switcher.edit, Qt.Key_Up)
    assert switcher.current_row() == 0


def test_switcher_consumes_navigation_with_no_results(switcher_navigation):
    """An empty filtered list safely keeps focus and search text."""
    state = switcher_navigation
    switcher = state.open()
    switcher.clear()
    for key in (Qt.Key_N, Qt.Key_P):
        state.qtbot.keyClick(switcher.edit, key, Qt.ControlModifier)
    assert switcher.count() == 0
    assert switcher.current_row() == -1
    assert switcher.edit.text() == ""
    assert QApplication.focusWidget() is switcher.edit


@pytest.mark.parametrize("dont_swap", [True, False])
def test_mac_physical_control_respects_qt_modifier_mapping(
    switcher_navigation, monkeypatch, dont_swap
):
    """Spyder's macOS mapping keeps Command free; default Qt also accepts Control."""
    state = switcher_navigation
    switcher = state.open()
    monkeypatch.setattr(plugin_module, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(
        plugin_module.QCoreApplication, "testAttribute", lambda attribute: dont_swap
    )
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_N, Qt.MetaModifier)
    state.vim.eventFilter(switcher.edit, event)
    assert switcher.current_row() == (0 if dont_swap else 2)
    switcher.set_current_row(0)
    state.qtbot.keyClick(switcher.edit, Qt.Key_N, Qt.ControlModifier)
    assert switcher.current_row() == 2
