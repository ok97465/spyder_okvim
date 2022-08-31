"""Conftest."""
# Standard library imports
import os
import os.path as osp
from unittest.mock import Mock

# Third party imports
import pytest
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QVBoxLayout, QWidget
from spyder.config.manager import CONF
from spyder.plugins.editor.widgets.editor import EditorStack

# Local imports
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
        self.save_action = Mock()
        self.close_action = Mock()

        layout = QVBoxLayout()
        layout.addWidget(self.editor_stack)
        self.setLayout(layout)

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

    def __init__(self, editor_stack, qtbot):
        """Main Window Mock constructor."""
        QWidget.__init__(self, None)
        self.main = QWidget()
        self.plugin_focus_changed = Mock()
        self.editor = EditorMock(editor_stack)
        self.status_bar = StatusBarMock()
        self.projects = Mock()
        self.open_file = Mock()
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

        self.add_dockwidget = Mock()
        # qtbot.add_widget(self.main)
        # qtbot.add_widget(self.editor)
        # qtbot.add_widget(self.status_bar)

    def get_plugin(self, dummy, error=True):
        return self.status_bar


@pytest.fixture
def editor_bot(qtbot):
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
    editor_stack.set_io_actions(Mock(), Mock(), Mock(), Mock())
    finfo = editor_stack.new(osp.join(LOCATION, "foo.py"), "utf-8", text)
    editor_stack.new(osp.join(LOCATION, "foo1.py"), "utf-8", text)
    editor_stack.new(osp.join(LOCATION, "foo2.py"), "utf-8", text)
    editor_stack.new(osp.join(LOCATION, "foo3.py"), "utf-8", text)
    main = MainMock(editor_stack, qtbot)

    # qtbot.add_widget(editor_stack)
    # qtbot.add_widget(main)

    # Hide GUI
    # qtbot.addWidget(main)
    # return main, editor_stack, finfo.editor, qtbot

    # Show GUI
    main.show()
    yield main, editor_stack, finfo.editor, qtbot
    # editor_stack.destroy()
    main.destroy()


@pytest.fixture
def vim_bot(editor_bot):
    """Create an spyder-vim plugin instance."""
    main, editor_stack, editor, qtbot = editor_bot
    vim = VimTesting(main, None)
    vim.on_initialize()
    return main, editor_stack, editor, vim, qtbot
