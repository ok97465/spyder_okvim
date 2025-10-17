"""Conftest."""

# Standard Libraries
import os
import os.path as osp
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Third Party Libraries
import pytest
from pytestqt.plugin import QtBot
from qtpy.QtCore import QCoreApplication
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QVBoxLayout, QWidget
from spyder.api.plugins import Plugins
from spyder.config.manager import CONF
from spyder.plugins.editor.widgets.editorstack import EditorStack

# Project Libraries
from spyder_okvim.spyder.config import CONF_DEFAULTS, CONF_SECTION
from spyder_okvim.spyder.plugin import OkVim

LOCATION = osp.realpath(osp.join(os.getcwd(), osp.dirname(__file__)))


class VimTesting(OkVim):
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


class StatusBarMock(QWidget):
    """Stausbar mock."""

    def __init__(self):
        QWidget.__init__(self, None)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

    def add_status_widget(self, widget):
        self.layout.addWidget(widget)


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


@pytest.fixture(scope="session")
def qtbot_module(qapp, request):
    """Module fixture for qtbot."""
    result = QtBot(request)
    return result


@pytest.fixture(scope="session", autouse=True)
def vim_bot(qtbot_module):
    """Editorstack pytest fixture."""
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
    finfo0 = editor_stack.new(osp.join(LOCATION, "foo.py"), "utf-8", text)
    finfo1 = editor_stack.new(osp.join(LOCATION, "foo1.py"), "utf-8", text)
    finfo2 = editor_stack.new(osp.join(LOCATION, "foo2.py"), "utf-8", text)
    finfo3 = editor_stack.new(osp.join(LOCATION, "foo3.py"), "utf-8", text)
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


@pytest.fixture(autouse=True)
def process_events_after_test():
    """Process pending Qt events after each test."""
    yield
    QCoreApplication.processEvents()
