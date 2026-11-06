"""Record README GIFs from the real Spyder editor and Okvim input widgets.

Run with the repository's development dependencies and Pillow installed:
    python scripts/record_demos.py
    python scripts/record_demos.py --only picker substitute
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = """# %% Analyse a small dataset
from statistics import mean

prices = [12, 18, 24, 30]
weights = [2, 1, 3, 2]

def summarize(values):
    total = sum(values)
    average = mean(values)
    return total, average

# %% Show the results
print(summarize(prices))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        nargs="+",
        choices=(
            "movement",
            "combination",
            "spyder",
            "easymotion",
            "leap",
            "picker",
            "substitute",
        ),
    )
    parser.add_argument("--output", type=Path, default=ROOT / "doc")
    parser.add_argument(
        "--frames", type=Path, help="Also save representative PNGs here"
    )
    args = parser.parse_args()

    # Set before importing Spyder: never read or write the user's preferences,
    # bookmarks, command histories, autosave data or project files.
    with tempfile.TemporaryDirectory(
        prefix="okvim-demos-", dir="/tmp" if Path("/tmp").is_dir() else None
    ) as temporary:
        directory = Path(temporary)
        os.environ["SPYDER_CONFDIR"] = str(directory / "config")
        # Spyder's pytest mode overrides SPYDER_CONFDIR with another temp root.
        os.environ.pop("SPYDER_PYTEST", None)
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        sys.path.insert(0, str(ROOT))
        record(args, directory)


def record(args, directory):
    from PIL import Image
    from qtpy.QtCore import QBuffer, QIODevice, QPoint, Qt
    from qtpy.QtGui import QFont, QPainter
    from qtpy.QtTest import QTest
    from qtpy.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout
    from spyder import __version__ as spyder_version
    from spyder.app.utils import create_application, set_links_color
    from spyder.config.manager import CONF

    # Use Spyder's actual startup path to load the selected theme, resources,
    # application font and palette before creating any editor or plugin widgets.
    app = create_application()
    from spyder.utils.stylesheet import APP_STYLESHEET

    # Isolate test-host behavior only after theme loading: Spyder skips parts of
    # its normal theme initialization when running under pytest.
    os.environ["PYTEST_CURRENT_TEST"] = "documentation-demos"
    from spyder_okvim.spyder.config import CONF_SECTION
    from tests.qt_support import create_vim_session, reset_vim_state

    print(
        f"Recording with Spyder {spyder_version}: {CONF.get('appearance', 'selected')}",
        flush=True,
    )

    class Driver:
        # create_vim_session only needs widget retention from the test driver.
        def __init__(self):
            self.widgets = []

        def add_widget(self, widget):
            self.widgets.append(widget)

        addWidget = add_widget

    project = directory / "demo_project"
    project.mkdir()
    (project / "analysis.py").write_text(SAMPLE)
    (project / "plot.py").write_text(
        "from matplotlib import pyplot as plt\n\n"
        "prices = [12, 18, 24, 30]\n\n"
        "plt.plot(prices, marker='o')\nplt.title('Prices')\nplt.show()\n"
    )
    (project / "helpers.py").write_text(
        "def normalize(values):\n    total = sum(values)\n"
        "    return [value / total for value in values]\n"
    )
    (project / "notes.md").write_text("# Analysis\n\nCompare prices and weights.\n")
    git_env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    git_env.update(
        GIT_AUTHOR_NAME="Okvim Demo",
        GIT_AUTHOR_EMAIL="demo@example.invalid",
        GIT_COMMITTER_NAME="Okvim Demo",
        GIT_COMMITTER_EMAIL="demo@example.invalid",
    )
    for command in (
        ("init", "--quiet", "--initial-branch=main"),
        ("add", "."),
        (
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Add analysis example",
        ),
    ):
        subprocess.run(["git", *command], cwd=project, env=git_env, check=True)
    plot_path = project / "plot.py"
    plot_path.write_text(plot_path.read_text().replace("Prices", "Daily prices"))
    driver = Driver()
    session = create_vim_session(driver, project)
    main, stack, _, vim, _ = next(session)
    # Match MainWindow.setup(): apply Spyder's stylesheet to the host, then set
    # the link palette. Caption rules affect only the recorder's named labels.
    main.setStyleSheet(
        str(APP_STYLESHEET)
        + """
        QLabel#demoTitle { font-size: 22px; font-weight: bold; }
        QLabel#demoSubtitle { font-size: 13px; }
        QLabel#demoKeys { font-family: Menlo; font-size: 18px; }
        QLabel#demoCaption { font-size: 14px; }
    """
    )
    set_links_color(app)
    widget = vim.vim_cmd
    line = widget.commandline
    status = widget.vim_status
    main.projects.get_active_project_path = lambda: str(project)
    main.setFixedSize(1000, 610)
    main.layout().setContentsMargins(12, 8, 12, 8)
    main.layout().setSpacing(8)
    # The test host includes Spyder's hidden plugin pane. Hide its placeholder,
    # just as the real application does when the editor is in use.
    vim.get_widget().hide()
    for label in main.findChildren(QLabel):
        if label.text() == "Please hide this pane.":
            label.hide()

    header = QFrame(main)
    header.setFixedHeight(64)
    header_layout = QVBoxLayout(header)
    header_layout.setContentsMargins(8, 2, 8, 2)
    title = QLabel(header)
    title.setObjectName("demoTitle")
    subtitle = QLabel(f"Spyder {spyder_version}  /  Okvim live editor capture", header)
    subtitle.setObjectName("demoSubtitle")
    header_layout.addWidget(title)
    header_layout.addWidget(subtitle)
    main.layout().insertWidget(0, header)
    footer = QFrame(main)
    footer.setFixedHeight(68)
    footer_layout = QVBoxLayout(footer)
    footer_layout.setContentsMargins(8, 2, 8, 2)
    keys_label = QLabel(footer)
    keys_label.setObjectName("demoKeys")
    caption = QLabel(footer)
    caption.setObjectName("demoCaption")
    footer_layout.addWidget(keys_label)
    footer_layout.addWidget(caption)
    main.layout().insertWidget(2, footer)

    for finfo, filename in zip(
        stack.data, ("analysis.py", "plot.py", "helpers.py", "notes.md")
    ):
        stack.rename_in_data(finfo.filename, str(project / filename))
        finfo.editor.set_font(QFont("Menlo", 13))
        finfo.editor.set_text((project / filename).read_text())
        finfo.editor.document().setModified(False)
        finfo.newly_created = False
    stack.set_stack_index(0)
    vim._use_stack(stack)
    editor = stack.get_current_editor()
    # Minimum size in the shared fixture is for tests, not this fixed viewport.
    stack.setMinimumSize(400, 280)
    CONF.set(CONF_SECTION, "which_key_enabled", True)
    CONF.set(CONF_SECTION, "which_key_delay", 200)
    widget.apply_settings()
    main.show()
    main.activateWindow()
    line.setFocus()
    QTest.qWait(150)
    frames = []
    durations = []
    args.output.mkdir(parents=True, exist_ok=True)
    if args.frames:
        args.frames.mkdir(parents=True, exist_ok=True)

    def capture(milliseconds=500):
        QTest.qWait(85)
        pixmap = main.grab()
        # Picker/hint windows are real top-level Qt popups. Include their actual
        # pixels at their screen coordinates in the host widget capture.
        painter = QPainter(pixmap)
        origin = main.mapToGlobal(QPoint(0, 0))
        for popup in QApplication.topLevelWidgets():
            if (
                popup is main
                or not popup.isVisible()
                or popup.windowType() == Qt.ToolTip
            ):
                continue
            if popup is vim.get_widget():
                continue
            offset = popup.mapToGlobal(QPoint(0, 0)) - origin
            if main.rect().intersects(popup.geometry().translated(-origin)):
                painter.drawPixmap(offset, popup.grab())
        painter.end()
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        frames.append(Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGB"))
        durations.append(milliseconds)

    def snapshot(name):
        if args.frames:
            frames[-1].save(args.frames / f"{name}.png")

    def describe(keys, explanation):
        keys_label.setText(keys)
        caption.setText(explanation)

    def type_keys(text, keys=None, explanation=None, hold=650):
        if explanation:
            describe(keys or text, explanation)
        for char in text:
            QTest.keyClicks(line, char)
            capture(100)
        capture(hold)

    def press(key, keys, explanation, modifiers=Qt.NoModifier, hold=700):
        describe(keys, explanation)
        QTest.keyClick(line, key, modifiers)
        capture(hold)

    def reset(name, summary):
        frames.clear()
        durations.clear()
        widget.picker.cancel()
        widget.which_key.cancel()
        line.esc_pressed()
        reset_vim_state(status)
        editor.set_text(SAMPLE)
        status.cursor.set_cursor_pos(0)
        editor.verticalScrollBar().setValue(0)
        line.setFocus()
        title.setText(name)
        describe("NORMAL", summary)
        capture(900)

    def save(filename):
        durations[-1] = 1400
        path = args.output / filename
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            optimize=True,
            disposal=1,
        )
        if args.frames:
            # The middle frame usually shows the interaction rather than a title.
            frames[len(frames) // 2].save(args.frames / path.with_suffix(".png").name)
        with Image.open(path) as gif:
            total = 0
            for number in range(gif.n_frames):
                gif.seek(number)
                total += gif.info.get("duration", 0)
            print(
                f"{path.name}: {gif.width}x{gif.height}, {gif.n_frames} frames, "
                f"{total / 1000:.1f}s, {path.stat().st_size / 1024:.0f} KiB",
                flush=True,
            )

    def movement():
        reset("Move through code", "Use familiar Vim motions without leaving Spyder.")
        type_keys("3j", explanation="Move three lines down to the dataset.")
        type_keys("f[", explanation="Find the opening bracket on this line.")
        type_keys("%", explanation="Jump to its matching closing bracket.")
        type_keys("gg", explanation="Return to the beginning of the file.")
        type_keys("/average", explanation="Search for a name across the file.")
        press(Qt.Key_Return, "Enter", "Confirm the search.")
        type_keys("n", explanation="Jump to the next match.")
        assert editor.textCursor().blockNumber() == 9
        save("ex_movement.gif")

    def combination():
        reset(
            "Compose edits with motions",
            "Delete a word or a list's contents, then undo each edit.",
        )
        type_keys("3j", explanation="Move to the prices assignment.")
        type_keys("diw", explanation="Delete the complete word under the cursor.")
        assert "prices =" not in editor.toPlainText()
        type_keys("u", explanation="Undo restores the deleted word.")
        type_keys("f[di[", explanation="Delete inside the brackets; keep the brackets.")
        assert "prices = []" in editor.toPlainText()
        type_keys("u", explanation="Undo restores the complete list.")
        assert "prices = [12, 18, 24, 30]" in editor.toPlainText()
        save("ex_combination.gif")

    def spyder():
        reset(
            "Work with Python cells",
            "Vim keys also drive Spyder's code comments and cells.",
        )
        type_keys("3j", explanation="Move to the dataset.")
        type_keys("gcc", explanation="Toggle the current line's comment.")
        assert "# prices =" in editor.toPlainText()
        type_keys("gcc", explanation="Toggle again to restore executable code.")
        type_keys("Vj", explanation="Select both dataset lines in Visual Line mode.")
        type_keys("gc", explanation="Comment the selected lines together.")
        assert "# weights =" in editor.toPlainText()
        type_keys("u", explanation="Undo the comment change.")
        type_keys("]c", explanation="Move to the next Spyder cell.")
        assert editor.textCursor().blockNumber() >= 11
        save("ex_spyder_cmd.gif")

    def easymotion():
        reset(
            "Jump with EasyMotion",
            "Show labels for visible words, then choose a destination.",
        )
        type_keys(
            "  w",
            keys="Space  Space  w",
            explanation="Label word starts ahead of the cursor.",
            hold=1500,
        )
        snapshot("easymotion-labels")
        manager = status.manager_marker_easymotion
        assert manager.name_list
        index = min(8, len(manager.name_list) - 1)
        label = manager.name_list[index]
        destination = manager.position_list[index]
        type_keys(label, explanation="Type a displayed label to jump directly there.")
        assert editor.textCursor().position() == destination
        type_keys("gg", explanation="Return to the top for a line-based jump.")
        type_keys(
            "  j",
            keys="Space  Space  j",
            explanation="Label the following lines.",
            hold=1500,
        )
        manager = status.manager_marker_easymotion
        assert manager.name_list
        label = manager.name_list[min(5, len(manager.name_list) - 1)]
        type_keys(label, explanation="Choose a line by its label.")
        save("easymotion.gif")

    def leap():
        reset(
            "Find a place with two characters",
            "Leap previews targets as you type, then offers labels when needed.",
        )
        type_keys("s", explanation="Start a two-character jump.")
        type_keys(
            "a",
            keys="s  a",
            explanation="Preview locations beginning with a.",
            hold=1200,
        )
        type_keys(
            "v", keys="s  a v", explanation="Narrow the targets to av.", hold=1500
        )
        snapshot("leap-labels")
        selector = status.sub_mode
        labels = selector._label_to_motion
        assert len(labels) >= 2
        label, motion = list(labels.items())[-1]
        destination = motion.cursor_pos
        type_keys(label, explanation="Choose the label beside the desired match.")
        assert editor.textCursor().position() == destination
        type_keys(";", explanation="Repeat the two-character motion.")
        save("leap.gif")

    def picker():
        reset(
            "Find files and review Git changes",
            "Search files, preview code and inspect saved changes in one picker.",
        )
        press(
            Qt.Key_P,
            "Ctrl+P",
            "Open the shared project-file picker.",
            Qt.ControlModifier,
        )
        dialog = widget.picker.dialog
        assert dialog is not None
        # Offscreen platform geometry may be smaller than the README viewport.
        dialog.setGeometry(main.x() + 40, main.y() + 105, 920, 390)
        QTest.qWait(500)
        capture(1000)
        describe("plot", "Narrow the project files while keeping a live code preview.")
        QTest.keyClicks(dialog.prompt, "plot")
        QTest.qWait(400)
        capture(1600)
        assert dialog.model.rowCount() == 1
        assert "plt.plot" in dialog.preview.toPlainText()
        snapshot("picker-files")
        describe("Git status", "Switch sources to review saved changes as a Git diff.")
        dialog.source_selector.setCurrentIndex(
            dialog.source_selector.findData("git_status")
        )
        QTest.qWait(600)
        capture(1800)
        assert dialog.model.rowCount() == 1
        assert "Daily prices" in dialog.preview.toPlainText()
        describe("Ctrl+D", "Scroll the diff preview to review the changed lines.")
        QTest.keyClick(dialog.prompt, Qt.Key_D, Qt.ControlModifier)
        capture(1400)
        snapshot("picker-git")
        describe("Esc", "Close the picker and keep your original editing position.")
        QTest.keyClick(dialog.prompt, Qt.Key_Escape)
        capture(900)
        assert editor.toPlainText() == SAMPLE
        save("picker.gif")

    def substitute():
        # Keep both replacement locations visible instead of covering them with
        # the optional command guide in this compact recording viewport.
        CONF.set(CONF_SECTION, "substitute_guide_enabled", False)
        widget.apply_settings()
        reset(
            "Preview a search and replace",
            "Review replacement text in the editor before committing the change.",
        )
        type_keys(":%s/", explanation="Start a substitution across the file.")
        type_keys(
            "prices/", keys=":%s/prices/", explanation="Highlight every matching name."
        )
        type_keys(
            "costs/g",
            keys=":%s/prices/costs/g",
            explanation="Preview all replacements in place.",
            hold=1800,
        )
        assert editor.toPlainText() == SAMPLE
        assert widget.substitute_preview.result is not None
        snapshot("substitute-preview")
        press(Qt.Key_Return, "Enter", "Apply the reviewed replacements as one edit.")
        assert "costs = [12" in editor.toPlainText()
        assert "summarize(costs)" in editor.toPlainText()
        type_keys("u", explanation="Undo restores every replacement together.")
        assert editor.toPlainText() == SAMPLE
        save("substitute.gif")

    actions = {
        name: action
        for name, action in (
            ("movement", movement),
            ("combination", combination),
            ("spyder", spyder),
            ("easymotion", easymotion),
            ("leap", leap),
            ("picker", picker),
            ("substitute", substitute),
        )
    }
    try:
        for name in args.only or actions:
            actions[name]()
    finally:
        try:
            next(session)
        except StopIteration:
            pass
        app.processEvents()


if __name__ == "__main__":
    main()
