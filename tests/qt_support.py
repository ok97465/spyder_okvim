"""Qt/Spyder fixtures and session reset helpers for integration tests only.

Import this module from integration tests or lazy fixture bodies. Pure value and
parser tests must not import it merely to collect tests.
"""

# Standard Libraries
import os.path as osp
from collections import defaultdict
from unittest.mock import Mock

# Third Party Libraries
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QStatusBar, QVBoxLayout, QWidget
from spyder.api.plugins import Plugins
from spyder.config.manager import CONF
from spyder.plugins.editor.widgets.editorstack import EditorStack

# Project Libraries
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION
from spyder_okvim.spyder.plugin import OkVim
from spyder_okvim.utils.jump_list import JumpList
from spyder_okvim.vim.macro import MacroManager
from spyder_okvim.vim.search import SearchInfo
from spyder_okvim.vim.state import FindInfo, InputCmdInfo, RegisterInfo


class VimTesting(OkVim):
    """Use the real plugin lifecycle without persistent plugin configuration."""

    CONF_FILE = False
    CONF_SECTION = CONF_SECTION


class EditorMock(QWidget):
    """Editor plugin mock."""

    def __init__(self, editor_stack):
        """Editor Mock constructor."""
        QWidget.__init__(self, None)
        self.editor_stack = editor_stack
        self.editorsplitter = self.editor_stack
        self.open_action = Mock()
        self.new_action = Mock()
        self.new = Mock()
        self.save_action = Mock()
        self.save = Mock()
        self.close_action = Mock()
        self.close_file = Mock()

        layout = QVBoxLayout()
        layout.addWidget(self.editor_stack)
        self.setLayout(layout)

    def get_widget(self):
        """Return self, mimicking Spyder 6 API."""
        return self

    def get_current_editorstack(self):
        """Return EditorStack instance."""
        return self.editor_stack


class StatusBarMock(QStatusBar):
    """Expose the status-widget attachment used by the real plugin."""

    def __init__(self):
        super().__init__(None)

    def add_status_widget(self, widget):
        self.insertPermanentWidget(0, widget)


class MainMock(QWidget):
    """Spyder MainWindow mock."""

    def __init__(self, editor_stack, qtbot_module):
        """Main Window Mock constructor."""
        QWidget.__init__(self, None)
        self.main = QWidget()
        self.plugin_focus_changed = Mock()
        self.editor = EditorMock(editor_stack)
        self.status_bar = StatusBarMock()
        self.application = Mock()
        self.application.open_file_in_plugin = Mock()
        self.projects = Mock()
        self.load_edit = Mock()
        self.projects.get_active_project_path = lambda: None
        layout = QVBoxLayout()
        layout.addWidget(self.editor)
        layout.addWidget(self.status_bar)
        self.setLayout(layout)

        for name, dict_info in CONF_DEFAULTS:
            if name != CONF_SECTION:
                continue
            for key, val in dict_info.items():
                CONF.set(name, key, val)

        # Disable highlight yank delay to avoid timer side effects
        CONF.set(CONF_SECTION, "highlight_yank_duration", 0)
        CONF.set(CONF_SECTION, "which_key_enabled", False)

        self.add_dockwidget = Mock()

        qtbot_module.add_widget(self.main)
        qtbot_module.add_widget(self.editor)
        qtbot_module.add_widget(self.status_bar)

    def get_plugin(self, plugin, error=True):
        if plugin == Plugins.StatusBar:
            return self.status_bar
        if plugin == Plugins.Application:
            return self.application
        return self.status_bar


def create_vim_session(qtbot_module, document_directory):
    """Create a shared integration session only when a test requests it."""
    text = (
        "   123\n" "line 1\n" "line 2\n" "line 3\n" "line 4"
    )  # a newline is added at end
    editor_stack = EditorStack(None, [])

    # Fix the area of the selection
    font = QFont("Courier New")
    font.setPointSize(10)
    editor_stack.set_default_font(font)
    editor_stack.setMinimumWidth(400)
    editor_stack.setMinimumHeight(400)

    editor_stack.set_find_widget(Mock())
    if hasattr(editor_stack, "set_io_actions"):
        editor_stack.set_io_actions(Mock(), Mock(), Mock(), Mock())
    finfo0 = editor_stack.new(
        osp.join(str(document_directory), "foo.py"), "utf-8", text
    )
    finfo1 = editor_stack.new(
        osp.join(str(document_directory), "foo1.py"), "utf-8", text
    )
    finfo2 = editor_stack.new(
        osp.join(str(document_directory), "foo2.py"), "utf-8", text
    )
    finfo3 = editor_stack.new(
        osp.join(str(document_directory), "foo3.py"), "utf-8", text
    )
    main = MainMock(editor_stack, qtbot_module)

    vim = VimTesting(main, None)
    vim.on_initialize()

    qtbot_module.addWidget(editor_stack)
    qtbot_module.addWidget(finfo0.editor)
    qtbot_module.addWidget(finfo1.editor)
    qtbot_module.addWidget(finfo2.editor)
    qtbot_module.addWidget(finfo3.editor)
    qtbot_module.addWidget(main)

    # Show GUI
    main.show()
    yield main, editor_stack, finfo0.editor, vim, qtbot_module

    finfo0.editor.close()
    finfo1.editor.close()
    finfo2.editor.close()
    finfo3.editor.close()
    finfo0.deleteLater()
    finfo1.deleteLater()
    finfo2.deleteLater()
    finfo3.deleteLater()
    editor_stack.deleteLater()
    # Close plugin widgets to avoid segmentation faults under Qt
    vim.on_close()
    main.close()
    main.deleteLater()
    # Ensure deferred deletions are processed to avoid segmentation faults
    QCoreApplication.processEvents()


def reset_vim_state(status):
    """Reset shared test state using the same cancellation path as view changes.

    Product code owns cleanup; fixture orchestration owns replacing test data,
    clearing persisted test marks and installing a fresh search owner. Settings
    are explicitly refreshed so tests can configure the session before reset.
    """
    status.cancel_pending_work()
    status.manager_macro.disconnect_from_editor(
        status.add_key_from_editor_to_macro_manager
    )
    QCoreApplication.processEvents()
    status.clear_state()
    status.refresh_settings()
    status.cursor.apply_settings(status.settings)
    status.find_info = FindInfo()
    status.input_cmd = InputCmdInfo("", "")
    status.input_cmd_prev = InputCmdInfo("", "")
    status.dot_cmd.clear_key_list()
    status.dot_cmd.put_payload = None
    status.running_dot_cmd = False
    status.get_editor().clear_extra_selections("hl_yank")
    status.get_editor().clear_extra_selections("hl_put")
    status.yank_history.clear()
    status.register_dict = defaultdict(RegisterInfo)
    status.search.close()
    status.search.deleteLater()
    status.search = SearchInfo(status.cursor, status, settings=status.settings)
    status.last_substitute = None
    status.manager_macro = MacroManager()
    status.msg_prefix = ""
    status.msg_label.setText("")
    status.bookmark_manager.clear()
    status.jump_list = JumpList()
    status.to_normal()
    if status.cmd_line is not None:
        status.cmd_line.vim_widget.bind_editor(status.get_editor())


def configuration_snapshot():
    """Capture plugin options that integration tests may temporarily change."""
    return {
        key: CONF.get(section, key, default=default)
        for section, defaults in CONF_DEFAULTS
        for key, default in defaults.items()
        if section == CONF_SECTION
    }


def restore_configuration(options):
    """Restore changed options without implicitly applying settings to a widget."""
    for key, value in options.items():
        if CONF.get(CONF_SECTION, key, default=value) != value:
            CONF.set(CONF_SECTION, key, value)


def create_substitute_session(vim_bot):
    """Keep the active document, search settings, and input state isolated."""
    _, stack, _, vim, qtbot = vim_bot
    previous_index = stack.get_stack_index()
    commandline = vim.vim_cmd.commandline
    status = vim.vim_cmd.vim_status
    commandline.setFocus()
    QCoreApplication.processEvents()
    commandline.esc_pressed()
    status.disconnect_from_editor()
    stack.set_stack_index(0)
    reset_vim_state(status)
    editor = stack.get_current_editor()
    original = editor.toPlainText()
    options = {
        name: CONF.get(CONF_SECTION, name) for name in ("ignorecase", "smartcase")
    }
    editor.set_text("foo foo\n  foo foo\nlast")
    status.cursor.set_cursor_pos(0)
    commandline.clear()
    commandline.setFocus()
    try:
        yield editor, status, commandline, qtbot
    finally:
        editor.setReadOnly(False)
        commandline.esc_pressed()
        status.disconnect_from_editor()
        reset_vim_state(status)
        editor.set_text(original)
        for name, value in options.items():
            CONF.set(CONF_SECTION, name, value)
        stack.set_stack_index(previous_index)


def submit_substitution(bot, body):
    """Use setText for Unicode input, then the ordinary Return commit path."""
    _, _, commandline, qtbot = bot
    qtbot.keyClicks(commandline, ":")
    commandline.setText(":" + body)
    qtbot.keyPress(commandline, Qt.Key_Return)
