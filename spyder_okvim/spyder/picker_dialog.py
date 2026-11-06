"""The common picker view: rendering and input, without host actions or I/O."""

from __future__ import annotations

import os.path as osp
import weakref

from qtpy.QtCore import (
    QAbstractListModel,
    QEvent,
    QModelIndex,
    QPoint,
    QPointF,
    QRect,
    QSize,
    QSignalBlocker,
    Qt,
    Signal,
)
from qtpy.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPalette,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QTextLayout,
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QLayout,
    QListView,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyledItemDelegate,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from spyder.widgets.simplecodeeditor import SimpleCodeEditor

from spyder_okvim.spyder.picker_git_actions import can_revert_status
from spyder_okvim.utils.picker import MAX_QUERY_LENGTH, SearchResult
from spyder_okvim.utils.qtcompat import live_widget
from spyder_okvim.utils.theme import readable_color, selection_colors

SOURCES = (
    ("files", "Files"),
    ("marks", "Marks"),
    ("jumps", "Jumps"),
    ("git_status", "Git status"),
    ("git_branches", "Git branches"),
    ("git_stash", "Git stashes"),
    ("git_log", "Git commits / log"),
    ("git_file_log", "Git commits: current file"),
)


_COMMIT_ACTIONS = (
    ("checkout", "Checkout selected commit (detached HEAD)\tEnter"),
    ("commit_files", "Changed files\tCtrl+L"),
    ("reset_mixed", "Reset mixed\tCtrl+R, m"),
    ("reset_soft", "Reset soft\tCtrl+R, s"),
    ("reset_hard", "Reset hard\tCtrl+R, h"),
)
_GIT_ACTIONS = {
    "git_status": (
        ("stage_toggle", "Stage / unstage selected file\tTab"),
        ("revert", "Revert unstaged changes in selected file…\tCtrl+R"),
        ("commit", "Commit staged changes…\tCtrl+Enter"),
    ),
    "git_log": _COMMIT_ACTIONS,
    "git_file_log": _COMMIT_ACTIONS,
    "git_branches": (
        ("checkout", "Checkout selected branch\tEnter"),
        ("branch_track", "Track selected remote branch\tCtrl+T"),
        ("branch_create", "Create branch\tCtrl+A"),
        ("branch_delete", "Delete selected branch\tCtrl+D"),
        ("branch_rebase", "Rebase current branch onto selected\tCtrl+R"),
        ("branch_merge", "Merge selected into current branch\tCtrl+Y"),
    ),
    "git_stash": (("stash_apply", "Apply selected stash\tEnter"),),
}
_COMMIT_SHORTCUTS = {Qt.Key_R: "reset", Qt.Key_L: "commit_files"}
_GIT_CONTROL_SHORTCUTS = {
    "git_status": {
        Qt.Key_Return: "commit",
        Qt.Key_Enter: "commit",
        Qt.Key_R: "revert",
    },
    "git_log": _COMMIT_SHORTCUTS,
    "git_file_log": _COMMIT_SHORTCUTS,
    "git_branches": {
        Qt.Key_T: "branch_track",
        Qt.Key_A: "branch_create",
        Qt.Key_D: "branch_delete",
        Qt.Key_R: "branch_rebase",
        Qt.Key_Y: "branch_merge",
    },
}


class PickerModel(QAbstractListModel):
    """Hold only references to the bounded, current display result."""

    MatchRole = Qt.UserRole + 1
    CurrentRole = Qt.UserRole + 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.matches = ()
        self.current_id = None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.matches)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.matches):
            return None
        match = self.matches[index.row()]
        if role in (Qt.DisplayRole, Qt.AccessibleTextRole):
            return f"{match.entry.label}   {match.entry.detail}"
        if role == Qt.ToolTipRole:
            return match.entry.search_text
        if role == self.MatchRole:
            return match
        if role == self.CurrentRole:
            return match.entry.id == self.current_id
        return None

    def set_result(self, result):
        self.beginResetModel()
        self.matches = result.matches
        self.endResetModel()

    def set_current_id(self, entry_id):
        if entry_id == self.current_id:
            return
        old = self.current_id
        self.current_id = entry_id
        for row, match in enumerate(self.matches):
            if match.entry.id in (old, entry_id):
                index = self.index(row)
                self.dataChanged.emit(index, index, [self.CurrentRole])


class PickerDelegate(QStyledItemDelegate):
    """Paint label and detail matches directly, without creating row widgets."""

    def sizeHint(self, option, index):
        return QSize(0, option.fontMetrics.height() + 10)

    @staticmethod
    def _text(painter, rectangle, text, positions, font, foreground, accent):
        layout = QTextLayout(text, font)
        formats = []
        for position in positions:
            span = QTextLayout.FormatRange()
            # Search positions use Python indices; QTextLayout uses UTF-16.
            span.start = (
                len(text[:position].encode("utf-16-le", errors="surrogatepass")) // 2
            )
            span.length = (
                len(
                    text[position : position + 1].encode(
                        "utf-16-le", errors="surrogatepass"
                    )
                )
                // 2
            )
            span.format.setForeground(accent)
            span.format.setFontWeight(QFont.Bold)
            span.format.setFontUnderline(True)
            formats.append(span)
        layout.setFormats(formats)
        layout.beginLayout()
        line = layout.createLine()
        line.setLineWidth(max(1, rectangle.width()))
        layout.endLayout()
        painter.save()
        painter.setClipRect(rectangle)
        painter.setPen(foreground)
        layout.draw(painter, QPointF(rectangle.x(), rectangle.y()))
        painter.restore()

    def paint(self, painter, option, index):
        match = index.data(PickerModel.MatchRole)
        if match is None:
            return
        selected = bool(option.state & QStyle.State_Selected)
        palette = option.palette
        background = palette.color(QPalette.Base)
        foreground = readable_color(palette.color(QPalette.Text), background)
        if selected:
            foreground, background = selection_colors(option.widget)
        muted = readable_color(palette.color(QPalette.PlaceholderText), background)
        accent = readable_color(palette.color(QPalette.Link), background, foreground)
        painter.save()
        painter.fillRect(option.rect, background)
        rect = option.rect.adjusted(8, 4, -8, -4)
        marker_width = option.fontMetrics.horizontalAdvance("› ")
        if index.data(PickerModel.CurrentRole):
            painter.setPen(accent)
            painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, "›")
        rect.adjust(marker_width, 0, 0, 0)
        label_width = min(
            round(rect.width() * 0.56),
            option.fontMetrics.horizontalAdvance(match.entry.label) + 16,
        )
        label_rect = QRect(rect.x(), rect.y(), max(1, label_width), rect.height())
        detail_rect = QRect(
            rect.x() + label_width,
            rect.y(),
            max(1, rect.width() - label_width),
            rect.height(),
        )
        self._text(
            painter,
            label_rect,
            match.entry.label,
            match.label_matches,
            option.font,
            foreground,
            accent,
        )
        self._text(
            painter,
            detail_rect,
            match.entry.detail,
            match.detail_matches,
            option.font,
            foreground if selected else muted,
            accent,
        )
        painter.restore()


class CodePreview(SimpleCodeEditor):
    """A separate document with source line numbers for a bounded excerpt."""

    first_line = 1

    def set_language(self, language):
        """Keep one reusable Spyder highlighter for the current language."""
        language = str(language).lower()
        highlighter = getattr(self, "_highlighter", None)
        if highlighter is not None:
            if getattr(self, "_preview_language", None) == language:
                if highlighter.document() is not self.document():
                    highlighter.setDocument(self.document())
                return
            # SimpleCodeEditor creates a new document-owned highlighter on
            # every call, leaving the old one processing subsequent edits.
            highlighter.setDocument(None)
            highlighter.deleteLater()
        super().set_language(language)
        self._preview_language = language

    def linenumberarea_width(self):
        if not self._linenumber_enabled:
            return 0
        last_line = self.first_line + self.blockCount() - 1
        return 12 + self.fontMetrics().horizontalAdvance(str(max(1, last_line)))

    def linenumberarea_paint_event(self, event):
        painter = QPainter(self.linenumberarea)
        palette = self.palette()
        background = palette.color(QPalette.Base)
        painter.fillRect(event.rect(), background)
        painter.setFont(self.font())
        painter.setPen(
            readable_color(palette.color(QPalette.PlaceholderText), background)
        )
        block = self.firstVisibleBlock()
        top = round(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        while block.isValid() and top <= event.rect().bottom():
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    self.linenumberarea.width() - 5,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    str(self.first_line + block.blockNumber()),
                )
            top += height
            block = block.next()


class DiffHighlighter(QSyntaxHighlighter):
    """Keep unified patch meanings explicit in either light or dark themes."""

    def __init__(self, editor):
        super().__init__(editor.document())
        self.editor = editor

    def highlightBlock(self, text):
        background = self.editor.palette().color(QPalette.Base)
        foreground = self.editor.palette().color(QPalette.Text)
        color = None
        bold = False
        if text.startswith(
            ("diff --git", "index ", "--- ", "+++ ", "commit ", "parent ")
        ):
            color, bold = self.editor.palette().color(QPalette.Link), True
        elif text.startswith("@@"):
            color, bold = QColor("#8c63d9"), True
        elif text.startswith("+"):
            color = QColor("#198754")
        elif text.startswith("-"):
            color = QColor("#d6334b")
        if color is not None:
            style = QTextCharFormat()
            style.setForeground(readable_color(color, background, foreground))
            if bold:
                style.setFontWeight(QFont.Bold)
            else:
                tint = QColor(color)
                tint.setAlpha(28)
                style.setBackground(tint)
            self.setFormat(
                0, len(text.encode("utf-16-le", errors="surrogatepass")) // 2, style
            )


class PickerPrompt(QLineEdit):
    """Track native composition before Enter or Escape reaches the picker."""

    is_composing = False

    def inputMethodEvent(self, event):
        self.is_composing = bool(event.preeditString())
        super().inputMethodEvent(event)


class PickerDialog(QDialog):
    """A nonmodal view whose signals are the only route to host navigation."""

    query_changed = Signal(str)
    source_changed = Signal(str)
    selection_changed = Signal(object)
    accepted_entry = Signal(object)
    action_requested = Signal(str, object)
    navigate_history = Signal(int)
    refresh_requested = Signal()
    back_requested = Signal()
    load_more_requested = Signal()

    def __init__(self, parent=None, *, editor=None):
        super().__init__(parent)
        self._editor = None
        self._source = "files"
        self._results_current = False
        self._actions_busy = False
        self._reset_pending = False
        self._initialized_geometry = False
        self._preview_enabled = True
        self._splitter_sizes = [1, 1]
        self._appearance_updating = False
        self._preview_target_line = None
        self._preview_first_line = 1
        self._preview_available = False
        self._diff_highlighter = None
        self.setWindowTitle("Okvim Picker")
        self.setObjectName("okvimPicker")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setModal(False)
        self.setAccessibleName("Okvim common picker")
        self.setMinimumSize(0, 0)
        outer = QVBoxLayout(self)
        outer.setSizeConstraint(QLayout.SetNoConstraint)
        outer.setContentsMargins(10, 10, 10, 10)
        self._header = QGridLayout()
        self._header.setColumnStretch(1, 1)
        self._header_narrow = False
        self.source_selector = QComboBox(self)
        self.source_selector.setMinimumWidth(80)
        self.source_selector.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.source_selector.setAccessibleName("Picker source")
        for source_id, title in SOURCES:
            self.source_selector.addItem(title, source_id)
        self.scope_label = QLabel(self)
        self.scope_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.back_button = self._button("Back", "Return to commit list")
        self.back_button.setVisible(False)
        self.load_more_button = self._button("More", "Load more commits")
        self.load_more_button.setVisible(False)
        self.actions_button = self._button("Actions", "Git actions for selected item")
        self.actions_menu = QMenu(self.actions_button)
        self.actions_button.setMenu(self.actions_menu)
        self.actions_button.setVisible(False)
        self.refresh_button = self._button("Refresh", "Refresh source")
        self.preview_button = self._button("Preview", "Show or hide preview")
        self.preview_button.setCheckable(True)
        self.preview_button.setChecked(True)
        self._toolbar_buttons = (
            self.actions_button,
            self.back_button,
            self.load_more_button,
            self.refresh_button,
            self.preview_button,
        )
        self._toolbar = QWidget(self)
        toolbar_layout = QHBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(4)
        toolbar_layout.addStretch()
        for button in self._toolbar_buttons:
            toolbar_layout.addWidget(button)
        self._header.addWidget(self.source_selector, 0, 0)
        self._header.addWidget(self.scope_label, 0, 1)
        self._header.addWidget(self._toolbar, 0, 2)
        outer.addLayout(self._header)

        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)
        results_panel = QWidget(self.splitter)
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self.list_view = QListView(results_panel)
        self.list_view.setMinimumSize(0, 0)
        self.list_view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.list_view.setFocusPolicy(Qt.NoFocus)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list_view.setAccessibleName("Picker results")
        self.model = PickerModel(self)
        self.list_view.setModel(self.model)
        self.list_view.setItemDelegate(PickerDelegate(self.list_view))
        self.prompt = PickerPrompt(results_panel)
        self.prompt.setPlaceholderText("Search")
        self.prompt.setAccessibleName("Picker search")
        self.prompt.setMinimumWidth(0)
        self.prompt.setMaxLength(MAX_QUERY_LENGTH)
        results_layout.addStretch()
        results_layout.addWidget(self.list_view, 1)
        results_layout.addWidget(self.prompt)

        self.preview_panel = QWidget(self.splitter)
        preview_layout = QVBoxLayout(self.preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_title = QLabel("Preview", self.preview_panel)
        self.preview_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.preview = CodePreview(self.preview_panel)
        self.preview.setup_editor(
            linenumbers=True, language="", highlight_current_line=False
        )
        self.preview.setReadOnly(True)
        self.preview.setUndoRedoEnabled(False)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setFocusPolicy(Qt.NoFocus)
        self.preview.setMinimumSize(0, 0)
        self.preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.preview.setAccessibleName("Read-only code or diff preview")
        self.preview_message = QLabel(self.preview_panel)
        self.preview_message.setWordWrap(True)
        self.preview_message.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview, 1)
        preview_layout.addWidget(self.preview_message)
        outer.addWidget(self.splitter, 1)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.status_label.setAccessibleName("Picker status")
        self.help_label = QLabel(self)
        self.help_label.setWordWrap(True)
        self.help_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        outer.addWidget(self.status_label)
        outer.addWidget(self.help_label)

        self.source_selector.currentIndexChanged.connect(self._source_selected)
        self.prompt.textChanged.connect(self._query_changed)
        self.list_view.selectionModel().currentChanged.connect(self._selection_changed)
        self.list_view.clicked.connect(lambda *_: self.focus_query())
        self.list_view.doubleClicked.connect(lambda *_: self._activate())
        self.preview_button.toggled.connect(self._toggle_preview)
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.back_button.clicked.connect(self.back_requested)
        self.load_more_button.clicked.connect(self.load_more_requested)
        for child in (
            self.prompt,
            self.list_view,
            self.source_selector,
            self.preview,
            self.actions_button,
            self.back_button,
            self.refresh_button,
            self.preview_button,
            self.load_more_button,
        ):
            child.installEventFilter(self)
        self.set_editor(editor)
        self.apply_appearance()
        self._update_help()

    def _button(self, title, accessible_name):
        button = QPushButton(self)
        button.setAutoDefault(False)
        button.setText(title)
        button.setAccessibleName(accessible_name)
        button.setToolTip(accessible_name)
        return button

    def set_editor(self, editor):
        """Follow the current host view after explicit history navigation."""
        previous = live_widget(self._editor)
        if previous is editor:
            return
        if previous is not None:
            previous.removeEventFilter(self)
            signal = getattr(previous, "sig_theme_colors_changed", None)
            if signal is not None:
                signal.disconnect(self.apply_appearance)
        self._editor = weakref.ref(editor) if editor is not None else None
        if editor is not None:
            editor.installEventFilter(self)
            signal = getattr(editor, "sig_theme_colors_changed", None)
            if signal is not None:
                signal.connect(self.apply_appearance)
        self.apply_appearance()

    def set_scope(self, scope):
        self.scope_label.setText(scope)
        self.scope_label.setToolTip(scope)

    def set_back_enabled(self, enabled):
        self.back_button.setVisible(enabled)

    def set_load_more_enabled(self, enabled):
        self.load_more_button.setVisible(enabled)

    def set_source(self, source_id):
        """Select a source silently; user changes emit ``source_changed``."""
        self._source = source_id
        self._reset_pending = False
        self._rebuild_git_menu()
        previous = self.source_selector.blockSignals(True)
        if source_id != "git_files":
            detail_index = self.source_selector.findData("git_files")
            if detail_index >= 0:
                self.source_selector.removeItem(detail_index)
        index = self.source_selector.findData(source_id)
        if index < 0:
            index = self.source_selector.count()
            self.source_selector.addItem("Commit files", source_id)
        self.source_selector.setCurrentIndex(index)
        self.source_selector.blockSignals(previous)
        self._update_help()

    def _source_selected(self, index):
        self._source = self.source_selector.itemData(index)
        self._rebuild_git_menu()
        self.invalidate_results()
        self._update_help()
        self.source_changed.emit(self._source)

    def query(self):
        return self.prompt.text()

    def set_query(self, text):
        """Restore session state without generating a second search request."""
        previous = self.prompt.blockSignals(True)
        self.prompt.setText(text)
        self.prompt.blockSignals(previous)
        self.invalidate_results()

    def _query_changed(self, text):
        self.invalidate_results()
        self.query_changed.emit(text)

    def invalidate_results(self):
        self._reset_pending = False
        self._results_current = False
        self._update_action_availability()
        self.preview.clear()
        self.preview_message.clear()
        self._preview_available = False
        self._update_help()
        self.selection_changed.emit(None)

    def set_busy(self, message):
        self.invalidate_results()
        self.set_status(message)

    def set_status(self, message):
        self.status_label.setText(message)
        self.status_label.setAccessibleDescription(message)

    def set_results(self, result: SearchResult, selected_id=None, scroll=None):
        """Publish current results and select an id, or the best bottom row."""
        selection_blocker = QSignalBlocker(self.list_view.selectionModel())
        self._results_current = False
        self.model.set_result(result)
        row_height = self.fontMetrics().height() + 10
        self.list_view.setMaximumHeight(max(1, self.model.rowCount()) * row_height + 4)
        row = len(result.matches) - 1
        if selected_id is not None:
            row = next(
                (
                    number
                    for number, match in enumerate(result.matches)
                    if match.entry.id == selected_id
                ),
                row,
            )
        self._results_current = not result.cancelled
        self.list_view.setCurrentIndex(
            self.model.index(row) if row >= 0 else QModelIndex()
        )
        if row >= 0:
            self.list_view.scrollTo(self.model.index(row))
        if scroll is not None:
            self.list_view.verticalScrollBar().setValue(scroll)
        suffix = f" · showing {len(result.matches)}" if result.truncated else ""
        self.set_status(f"{result.total_matches} results{suffix}")
        selection_blocker.unblock()
        self._reset_pending = False
        self._update_action_availability()
        self._update_help()
        self.selection_changed.emit(self.selected_entry())

    def select_id(self, entry_id):
        """Select an existing display entry without resetting the model."""
        for row, match in enumerate(self.model.matches):
            if match.entry.id == entry_id:
                index = self.model.index(row)
                self.list_view.setCurrentIndex(index)
                self.list_view.scrollTo(index)
                return

    def set_current_id(self, entry_id):
        """Update the actual jump position without rebuilding display rows."""
        self.model.set_current_id(entry_id)

    def selected_entry(self):
        row = self.list_view.currentIndex().row()
        if self._results_current and 0 <= row < len(self.model.matches):
            return self.model.matches[row].entry
        return None

    def selection_id(self):
        entry = self.selected_entry()
        return entry.id if entry is not None else None

    def scroll_position(self):
        return self.list_view.verticalScrollBar().value()

    def focus_query(self):
        self.prompt.setFocus(Qt.OtherFocusReason)

    def _selection_changed(self, *_):
        self._reset_pending = False
        self._update_action_availability()
        self._update_help()
        self.selection_changed.emit(self.selected_entry())

    def _activate(self):
        entry = self.selected_entry()
        if entry is not None and not self._actions_busy:
            self.accepted_entry.emit(entry)

    def _rebuild_git_menu(self):
        self.actions_menu.clear()
        actions = _GIT_ACTIONS.get(self._source, ())
        self.actions_button.setVisible(bool(actions))
        for identifier, label in actions:
            action = self.actions_menu.addAction(label)
            action.setData(identifier)
            action.triggered.connect(
                lambda checked=False, identifier=identifier: self._request_action(
                    identifier
                )
            )
        self._update_action_availability()

    def _action_available(self, action, entry):
        """Apply the same selection and busy rules to menus and shortcuts."""
        if self._actions_busy or not self._results_current:
            return False
        if action == "revert":
            return entry is not None and can_revert_status(entry.target)
        return (
            entry is not None
            or (self._source == "git_branches" and action == "branch_create")
            or (self._source == "git_status" and action == "commit")
        )

    def _update_action_availability(self):
        entry = self.selected_entry()
        target = entry.target if entry is not None else None
        untracked = target is not None and target.status == "??"
        actions = self.actions_menu.actions()
        for action in actions:
            identifier = action.data()
            if identifier == "revert":
                action.setText(
                    "Delete selected untracked file…\tCtrl+R"
                    if untracked
                    else "Revert unstaged changes in selected file…\tCtrl+R"
                )
            action.setEnabled(self._action_available(identifier, entry))
        self.actions_button.setEnabled(any(action.isEnabled() for action in actions))

    def set_actions_busy(self, busy):
        """Disable Git execution while a mutation finishes outside the popup."""
        self._actions_busy = bool(busy)
        self._reset_pending = False
        self._update_action_availability()
        self._update_help()

    def _request_action(self, action):
        entry = self.selected_entry()
        if self._action_available(action, entry):
            self.action_requested.emit(action, entry)

    def set_preview(self, content):
        """Display a bounded value snapshot in the independent document."""
        self.preview.clear()
        self._preview_available = content is not None and bool(content.text)
        self._update_help()
        if content is None:
            self.preview_message.clear()
            return
        self.preview.first_line = content.first_line
        language = content.language.lstrip(".")
        if osp.sep in language:
            language = osp.splitext(language)[1].lstrip(".")
        is_diff = language in ("diff", "patch")
        self.preview.update_linenumberarea_width()
        if is_diff:
            self.preview._highlighter.setDocument(None)
        else:
            self.preview.set_language(language)
        if self._diff_highlighter is not None and not is_diff:
            self._diff_highlighter.setDocument(None)
            self._diff_highlighter.deleteLater()
            self._diff_highlighter = None
        if is_diff and self._diff_highlighter is None:
            self._diff_highlighter = DiffHighlighter(self.preview)
        self.preview.setPlainText(content.text)
        self._preview_target_line = content.target_line
        self._preview_first_line = content.first_line
        self.preview_title.setText(f"Preview · line {content.first_line}")
        self.preview_message.setText(content.message)
        self._highlight_preview_target(reveal=True)

    def _highlight_preview_target(self, *, reveal=False):
        selections = []
        target = self._preview_target_line
        if target is not None:
            block = self.preview.document().findBlockByNumber(
                target - self._preview_first_line
            )
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.cursor = QTextCursor(block)
                _, background = selection_colors(self.preview)
                background.setAlpha(70)
                selection.format.setBackground(background)
                selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                selections.append(selection)
                if reveal:
                    self.preview.setTextCursor(selection.cursor)
                    self.preview.centerCursor()
        self.preview.setExtraSelections(selections)

    def _toggle_preview(self, enabled):
        if self._preview_enabled and not enabled:
            self._splitter_sizes = self.splitter.sizes()
        self._preview_enabled = enabled
        self.preview_panel.setVisible(enabled)
        if enabled:
            self.splitter.setSizes(self._splitter_sizes)
        self._update_help()

    def _update_help(self):
        preview = (
            "Ctrl+D/U: scroll preview"
            if self._preview_enabled and self._preview_available
            else "Ctrl+D/U: preview unavailable"
        )
        if self._source == "git_branches":
            preview = "Ctrl+U: scroll preview"
        enter = "open"
        source_help = ""
        if self._source == "jumps":
            source_help = "\nCtrl+O/I: move through actual history immediately"
        elif self._source == "git_status":
            entry = self.selected_entry()
            untracked = (
                entry is not None
                and entry.target is not None
                and entry.target.status == "??"
            )
            revert = "delete untracked file" if untracked else "revert unstaged changes"
            source_help = (
                f"\nTab: stage/unstage · Ctrl+R: {revert}"
                " · Ctrl+Enter: commit staged changes"
            )
        elif self._source in ("git_log", "git_file_log"):
            enter = "checkout commit"
            source_help = (
                "\nCtrl+L: changed files · Ctrl+R then m/s/h: reset mixed/soft/hard"
            )
        elif self._source == "git_branches":
            enter = "checkout branch"
            source_help = "\nCtrl+T: track · Ctrl+A: create · Ctrl+D: delete · Ctrl+R: rebase · Ctrl+Y: merge"
        elif self._source == "git_stash":
            enter = "apply stash"
        text = (
            f"↑/↓ · Ctrl+N/P: select · Ctrl+F/B: page · {preview} · Enter: {enter} · Esc: close"
            + source_help
        )
        if self._reset_pending:
            text += "\nReset selected commit: m mixed · s soft · h hard · Esc cancel"
        if self._actions_busy:
            text += "\nGit operation running; actions are unavailable until it finishes"
        self.help_label.setText(text)
        self.list_view.setAccessibleDescription(text)

    def _handles_key(self, event):
        key, modifiers = event.key(), event.modifiers()
        if self._reset_pending:
            return True
        if modifiers == Qt.ControlModifier:
            return key in _GIT_CONTROL_SHORTCUTS.get(self._source, {}) or key in (
                Qt.Key_N,
                Qt.Key_P,
                Qt.Key_F,
                Qt.Key_B,
                Qt.Key_D,
                Qt.Key_U,
                Qt.Key_O,
                Qt.Key_I,
                Qt.Key_C,
            )
        return modifiers == Qt.NoModifier and (
            (self._source == "git_status" and key == Qt.Key_Tab)
            or key
            in (
                Qt.Key_Up,
                Qt.Key_Down,
                Qt.Key_PageUp,
                Qt.Key_PageDown,
                Qt.Key_Return,
                Qt.Key_Enter,
                Qt.Key_Escape,
            )
        )

    def eventFilter(self, watched, event):
        editor = live_widget(self._editor)
        if watched is editor and event.type() in (
            QEvent.PaletteChange,
            QEvent.ApplicationPaletteChange,
            QEvent.StyleChange,
            QEvent.FontChange,
        ):
            self.apply_appearance()
        if (
            watched is not editor
            and event.type() in (QEvent.ShortcutOverride, QEvent.KeyPress)
            and self._handles_key(event)
        ):
            # Keep native combo navigation and button activation available.
            control = event.modifiers() == Qt.ControlModifier
            if (
                watched is self.source_selector
                and not control
                and event.key() != Qt.Key_Escape
            ):
                return super().eventFilter(watched, event)
            event.accept()
            if event.type() == QEvent.KeyPress:
                if (
                    watched in self._toolbar_buttons
                    and not control
                    and event.key()
                    in (
                        Qt.Key_Return,
                        Qt.Key_Enter,
                    )
                ):
                    watched.click()
                else:
                    self.keyPressEvent(event)
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        key, modifiers = event.key(), event.modifiers()
        if not self._handles_key(event):
            return super().keyPressEvent(event)
        event.accept()
        control = modifiers == Qt.ControlModifier
        git_action = (
            _GIT_CONTROL_SHORTCUTS.get(self._source, {}).get(key) if control else None
        )
        if self.prompt.is_composing and (
            (
                modifiers == Qt.NoModifier
                and key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape)
            )
            or git_action in ("commit", "revert")
        ):
            input_method = QApplication.inputMethod()
            if key == Qt.Key_Escape:
                input_method.reset()
            else:
                input_method.commit()
            return
        if self._reset_pending:
            self._reset_pending = False
            self._update_help()
            reset = {
                Qt.Key_M: "reset_mixed",
                Qt.Key_S: "reset_soft",
                Qt.Key_H: "reset_hard",
            }
            if modifiers == Qt.NoModifier and key in reset:
                self._request_action(reset[key])
            return
        if key == Qt.Key_Escape or (control and key == Qt.Key_C):
            self.reject()
        elif git_action == "commit":
            self._request_action(git_action)
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self._activate()
        elif self._source == "git_status" and key == Qt.Key_Tab:
            self._request_action("stage_toggle")
        elif git_action == "reset":
            if not self._actions_busy and self.selected_entry() is not None:
                self._reset_pending = True
                self._update_help()
        elif git_action is not None:
            if not (git_action == "revert" and event.isAutoRepeat()):
                self._request_action(git_action)
        elif control and key in (Qt.Key_O, Qt.Key_I):
            if self._source == "jumps":
                self.navigate_history.emit(-1 if key == Qt.Key_O else 1)
        elif control and key in (Qt.Key_D, Qt.Key_U):
            if self._preview_enabled and self._preview_available:
                scrollbar = self.preview.verticalScrollBar()
                stride = max(1, scrollbar.pageStep() // 2)
                scrollbar.setValue(
                    scrollbar.value() + (stride if key == Qt.Key_D else -stride)
                )
        else:
            down = key in (Qt.Key_N, Qt.Key_Down, Qt.Key_F, Qt.Key_PageDown)
            page = key in (Qt.Key_F, Qt.Key_B, Qt.Key_PageDown, Qt.Key_PageUp)
            row_height = max(1, self.list_view.sizeHintForRow(0))
            stride = (
                max(1, self.list_view.viewport().height() // row_height) if page else 1
            )
            row = self.list_view.currentIndex().row() + (stride if down else -stride)
            row = min(max(0, row), self.model.rowCount() - 1)
            if row >= 0:
                index = self.model.index(row)
                self.list_view.setCurrentIndex(index)
                self.list_view.scrollTo(index)

    def apply_appearance(self, *_):
        if getattr(self, "_appearance_updating", False) or not hasattr(self, "preview"):
            return
        self._appearance_updating = True
        try:
            editor = live_widget(self._editor)
            palette = self.palette()
            background = palette.color(QPalette.Base)
            foreground = readable_color(palette.color(QPalette.Text), background)
            border = palette.color(QPalette.Mid)
            self.setStyleSheet(
                "QDialog#okvimPicker {"
                f"background: {background.name()}; color: {foreground.name()};"
                f"border: 1px solid {border.name()}; }}"
            )
            for button in self._toolbar_buttons:
                metrics = button.fontMetrics()
                button.setMinimumSize(
                    metrics.horizontalAdvance(button.text()) + 20,
                    max(32, metrics.height() + 14),
                )
            self.list_view.setPalette(palette)
            self.prompt.setPalette(palette)
            if editor is not None:
                self.preview.setFont(editor.font())
                scheme = getattr(
                    editor, "color_scheme", getattr(editor, "_color_scheme", None)
                )
                if scheme is not None:
                    self.preview.set_color_scheme(scheme)
            if self._diff_highlighter is not None:
                self._diff_highlighter.rehighlight()
            if self._preview_target_line is not None:
                self._highlight_preview_target()
            self.list_view.viewport().update()
        finally:
            self._appearance_updating = False

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (
            QEvent.PaletteChange,
            QEvent.ApplicationPaletteChange,
            QEvent.StyleChange,
            QEvent.FontChange,
        ):
            self.apply_appearance()

    def showEvent(self, event):
        if not self._initialized_geometry:
            self._initialized_geometry = True
            parent = self.parentWidget()
            owner = parent.window() if parent is not None else None
            anchor = owner.frameGeometry().center() if owner is not None else self.pos()
            screen = QApplication.screenAt(anchor) or QApplication.primaryScreen()
            area = screen.availableGeometry().adjusted(8, 8, -8, -8)
            if owner is not None and owner.isVisible():
                owner_area = QRect(owner.mapToGlobal(QPoint(0, 0)), owner.size())
                intersection = area.intersected(owner_area)
                if intersection.isValid():
                    area = intersection
            width, height = max(1, round(area.width() * 0.8)), max(
                1, round(area.height() * 0.7)
            )
            self.resize(width, height)
            self.move(area.center() - self.rect().center())
            self.splitter.setSizes([width // 2, width // 2])
        super().showEvent(event)
        self.activateWindow()
        self.focus_query()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "splitter"):
            narrow = self.width() < max(640, self.fontMetrics().averageCharWidth() * 90)
            if narrow != self._header_narrow:
                self._header_narrow = narrow
                self._header.removeWidget(self._toolbar)
                if narrow:
                    self._header.addWidget(self._toolbar, 1, 0, 1, 3)
                else:
                    self._header.addWidget(self._toolbar, 0, 2)
            orientation = Qt.Vertical if narrow else Qt.Horizontal
            if self.splitter.orientation() != orientation:
                sizes = self.splitter.sizes()
                self.splitter.setOrientation(orientation)
                self.splitter.setSizes(sizes)
            self.help_label.setVisible(self.height() >= (300 if narrow else 230))
