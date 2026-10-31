"""Theme and viewport regressions for temporary jump labels."""

from types import SimpleNamespace

from qtpy.QtCore import QCoreApplication, QEvent, QPoint, QRect
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QPlainTextEdit, QWidget

from spyder_okvim.vim.label import InlineLabel, annotation_style


def test_annotation_palette_and_custom_colors(qtbot):
    source = QPlainTextEdit()
    parent = QWidget()
    qtbot.addWidget(source)
    qtbot.addWidget(parent)
    label = InlineLabel(parent)
    settings = SimpleNamespace(
        annotation_bg_color="#abcdef", annotation_fg_color="invalid"
    )
    label.set_style("Monospace", 10, source, settings)
    assert "#abcdef" in label.styleSheet()
    palette = QPalette(source.palette())
    palette.setColor(QPalette.HighlightedText, QColor("#112233"))
    source.setPalette(palette)
    assert "color: #112233" in label.styleSheet()
    assert annotation_style(source, settings)["background"] == "#abcdef"


def test_annotation_survives_style_source_deletion(qtbot):
    source = QPlainTextEdit()
    parent = QWidget()
    qtbot.addWidget(parent)
    label = InlineLabel(parent)
    label.set_style("Monospace", 10, source)
    source.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    palette = QPalette(label.palette())
    palette.setColor(QPalette.Window, QColor("#ffffff"))
    label.setPalette(palette)
    assert label.parent() is parent


def test_jump_annotation_fits_right_edge_and_replaces_previous_labels(vim_bot):
    from tests.qt_support import reset_vim_state

    _, stack, editor, vim, qtbot = vim_bot
    stack.set_stack_index(0)
    status = vim.vim_cmd.vim_status
    reset_vim_state(status)
    editor.set_text("a" * 200)
    status.cursor.set_cursor_pos(0)
    viewport = editor.viewport()
    edge = editor.cursorForPosition(
        QPoint(viewport.width() - 1, editor.cursorRect().center().y())
    ).position()
    status.annotate_on_txt({0: "s", 2: "f", edge: "SS"})
    edge_label = status.labels_for_annotate[2]
    assert not edge_label.isHidden()
    local = viewport.mapFromGlobal(edge_label.mapToGlobal(QPoint(0, 0)))
    assert viewport.rect().contains(QRect(local, edge_label.size()))
    status.annotate_on_txt({0: "s"})
    assert all(label.isHidden() for label in status.labels_for_annotate[1:])


def test_crowded_leap_targets_are_visible_selectable_and_nonoverlapping(vim_bot):
    """A dense viewport never retains an invisible selectable Leap target."""
    from tests.qt_support import reset_vim_state

    _, stack, editor, vim, qtbot = vim_bot
    stack.set_stack_index(0)
    status = vim.vim_cmd.vim_status
    reset_vim_state(status)
    editor.set_text(("ab" * 18 + "\n") * 8)
    status.cursor.set_cursor_pos(0)
    commandline = vim.vim_cmd.commandline
    qtbot.keyClicks(commandline, "s")
    assert "first character" in status.msg_label.text()
    qtbot.keyClicks(commandline, "a")
    assert "second character" in status.msg_label.text()
    qtbot.keyClicks(commandline, "b")
    selector = status.sub_mode
    visible = [label for label in status.labels_for_annotate if not label.isHidden()]
    assert 0 < len(visible) <= 50
    assert len(selector._label_to_motion) == len(visible)
    assert set(selector._label_to_motion) == {label.text() for label in visible}
    assert "showing" in status.msg_label.text()
    assert all(
        not first.geometry().intersects(second.geometry())
        for index, first in enumerate(visible)
        for second in visible[index + 1 :]
    )
    commandline.esc_pressed()
