"""Passive search and substitution help in one scrollable prompt panel."""

# Standard Libraries
from dataclasses import dataclass

# Third Party Libraries
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from spyder.utils.palette import SpyderPalette

# Project Libraries
from spyder_okvim.utils.search_helpers import resolve_ignorecase

SUBSTITUTION_OPTIONS = (
    ("g", "Replace all"),
    ("c", "Confirm"),
    ("i", "Ignore case"),
    ("I", "Match case"),
    ("n", "Count"),
)


@dataclass(frozen=True)
class SearchGuideContext:
    """The effective search policy and the user's help expansion choice."""

    pattern: str
    ignorecase: bool
    smartcase: bool
    expanded: bool = False


class PromptGuidePopup(QFrame):
    """Explain input without selecting rows or changing command-line focus."""

    MAX_WIDTH = 640

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("substituteGuidePopup")
        self.setMinimumSize(0, 0)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._content = None
        self._font = None

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("substituteGuideScroll")
        self.scroll_area.setFocusPolicy(Qt.NoFocus)
        self.scroll_area.viewport().setFocusPolicy(Qt.NoFocus)
        self.scroll_area.verticalScrollBar().setFocusPolicy(Qt.NoFocus)
        self.scroll_area.horizontalScrollBar().setFocusPolicy(Qt.NoFocus)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setMinimumSize(0, 0)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidgetResizable(True)

        self.content_widget = QWidget(self.scroll_area)
        self.content_widget.setObjectName("substituteGuideContent")
        self.content_widget.setFocusPolicy(Qt.NoFocus)
        self.content_widget.setMinimumSize(0, 0)
        self.content_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.header = QLabel(self.content_widget)
        self.description = QLabel(self.content_widget)
        self.range_label = QLabel(self.content_widget)
        self.effective_label = QLabel(self.content_widget)
        self.note = QLabel(self.content_widget)

        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)
        content_layout.setSizeConstraint(QLayout.SetNoConstraint)
        content_layout.addWidget(self.header)
        content_layout.addWidget(self.description)
        content_layout.addWidget(self.range_label)

        self.options_widget = QWidget(self.content_widget)
        self.options_widget.setFocusPolicy(Qt.NoFocus)
        self.options_widget.setMinimumSize(0, 0)
        options_layout = QGridLayout(self.options_widget)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setHorizontalSpacing(10)
        options_layout.setVerticalSpacing(3)
        options_layout.setColumnStretch(1, 1)
        self.option_labels = []
        for row, (flag, explanation) in enumerate(SUBSTITUTION_OPTIONS):
            flag_label = QLabel(flag, self.options_widget)
            description_label = QLabel(explanation, self.options_widget)
            options_layout.addWidget(flag_label, row, 0, Qt.AlignTop)
            options_layout.addWidget(description_label, row, 1)
            self.option_labels.append((flag_label, description_label))
        content_layout.addWidget(self.options_widget)
        content_layout.addWidget(self.effective_label)
        content_layout.addWidget(self.note)
        self.scroll_area.setWidget(self.content_widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 5, 6, 5)
        layout.setSizeConstraint(QLayout.SetNoConstraint)
        layout.addWidget(self.scroll_area)

        for label in self.findChildren(QLabel):
            label.setTextFormat(Qt.PlainText)
            label.setFocusPolicy(Qt.NoFocus)
            label.setMinimumSize(0, 0)
            label.setWordWrap(True)
            # Let wrapped text shrink below its longest word in narrow editors.
            policy = label.sizePolicy()
            policy.setHorizontalPolicy(QSizePolicy.Ignored)
            label.setSizePolicy(policy)
        for flag_label, _description in self.option_labels:
            flag_label.setWordWrap(False)
            flag_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.hide()

    def set_context(self, context):
        """Update changed help text, returning whether its layout needs fitting."""
        if isinstance(context, SearchGuideContext):
            self.setAccessibleName("Search pattern guide")
            self.setAccessibleDescription(
                "Qt regular expressions and the current case policy. "
                "Press F1 in the search input to expand or collapse examples."
            )
            content = self._search_content(context)
        else:
            self.setAccessibleName("Substitution guide")
            self.setAccessibleDescription("Help for the current substitution field.")
            content = self._substitute_content(context)
        if content == self._content:
            return False
        self._content = content
        title, explanation, range_text, show_options, effective_text, note = content
        for label, text in (
            (self.header, title),
            (self.description, explanation),
            (self.range_label, range_text),
            (self.effective_label, effective_text),
            (self.note, note),
        ):
            if label.text() != text:
                label.setText(text)
            label.setVisible(bool(text))
        self.options_widget.setVisible(show_options)
        self.scroll_area.verticalScrollBar().setValue(0)
        return True

    @staticmethod
    def _search_content(context):
        ignorecase = resolve_ignorecase(
            context.pattern,
            ignorecase=context.ignorecase,
            smartcase=context.smartcase,
        )
        case = "Ignore case" if ignorecase else "Match case"
        if context.ignorecase and context.smartcase:
            case += " (smartcase: uppercase patterns match case)"
        title = f"Qt regex · {case}"
        description = ""
        if context.expanded:
            description = (
                r". any character; \d digit; \w word; \s whitespace"
                "\n"
                r"^ line start; $ line end; \b word boundary"
                "\n"
                r"[abc] one of a/b/c; a|b either; (...) capture group"
                "\n"
                r"* zero or more; + one or more; ? optional; {n,m} repetitions"
                "\n"
                r"Examples: \bfoo\b = whole word; foo\d+ = foo followed by digits"
                "\nMatches are evaluated one line at a time."
            )
        note = "F1: hide examples" if context.expanded else "F1: regex examples"
        return title, description, "", False, "", note

    @staticmethod
    def _substitute_content(context):
        delimiter = context.delimiter
        if context.stage == "pattern":
            title = "Search pattern"
            explanation = (
                ". = any character;\n"
                "\\d = digit; \\w = word; \\s = whitespace\n"
                "[abc] = one of a, b, c; [a-z] = character range\n"
                "[^abc] = any character except a, b, c\n"
                "^ = start of line; $ = end of line; "
                r"\b = word boundary"
                "\n"
                "* = zero or more; + = one or more; ? = zero or one\n"
                "{n,m} = n to m repetitions\n"
                "(...) = capture group; a|b = a or b"
            )
        elif context.stage == "replacement":
            title = "Replacement text"
            explanation = (
                r"& or \0 = entire match; \1–\9 = capture groups"
                "\n"
                r"\& = literal &; \\ = literal backslash"
                "\n"
                r"\t = tab; \b = backspace"
                "\n"
                f"\\{delimiter} = literal delimiter {delimiter}\n"
                "Missing capture groups insert empty text. "
                r"Other unrecognized escapes drop the backslash (\z inserts z)."
                "\n"
                r"Line breaks, \r, \n, \u, \U, \l, \L, \e, \E and "
                r"expression replacements (\=) are not supported. ~ is literal."
            )
        elif context.stage == "flags":
            title = "Substitution options"
            explanation = ""
        elif context.stage == "count":
            title = "Line count"
            explanation = (
                "The number after the options is the number of lines to process, "
                f"starting at the end of the range. Example: :s{delimiter}foo"
                f"{delimiter}bar{delimiter}g 3"
            )
        else:
            title = "Unsupported substitution option"
            explanation = (
                f"Unsupported option or trailing input: {context.unsupported}. "
                "The command executor will validate the input."
            )
        if context.stage in ("pattern", "replacement", "flags"):
            range_text = ""
        elif context.addresses == ("%",):
            range_text = "Range: % selects the entire file."
        elif context.addresses:
            range_text = "Range: the specified lines. % selects the entire file."
        else:
            range_text = "Range: current line. % selects the entire file."

        show_options = context.stage == "flags"
        effective_text = ""
        notes = []
        if show_options:
            if context.raw_flags:
                effective_text = "Currently applied: " + (
                    context.effective_flags or "none"
                )
            if context.missing_previous:
                notes.append("&: no previous substitution.")
            if "r" in context.raw_flags:
                notes.append("r has no effect with an explicit pattern.")
        note = "\n".join(notes)
        return title, explanation, range_text, show_options, effective_text, note

    def refresh_appearance(self, font):
        """Follow the command-line font and Spyder palette only when changed."""
        # Qt may resolve additional font properties while polishing widgets.
        # Compare the requested font so that resolution is not a fresh change.
        font_changed = self._font != font
        if font_changed:
            self._font = QFont(font)
            self.setFont(font)
        stylesheet = (
            "QFrame#substituteGuidePopup {"
            f"background-color: {SpyderPalette.COLOR_BACKGROUND_1};"
            f"border: 1px solid {SpyderPalette.COLOR_BACKGROUND_4};"
            "border-radius: 4px; }"
            "QFrame#substituteGuidePopup QLabel {"
            f"color: {SpyderPalette.COLOR_TEXT_1};"
            "background: transparent; border: none; padding: 0; }"
            "QScrollArea#substituteGuideScroll, QWidget#substituteGuideContent {"
            f"background-color: {SpyderPalette.COLOR_BACKGROUND_1};"
            "border: none; }"
        )
        stylesheet_changed = self.styleSheet() != stylesheet
        if stylesheet_changed:
            self.setStyleSheet(stylesheet)
        # Stylesheet children do not reliably inherit their parent's font.
        if font_changed or stylesheet_changed:
            for label in self.findChildren(QLabel):
                label.setFont(font)
        return font_changed or stylesheet_changed

    def _preferred_text_width(self):
        """Fit visible references without relying on ignored size hints."""

        def text_width(label):
            metrics = label.fontMetrics()
            return max(
                (metrics.horizontalAdvance(line) for line in label.text().splitlines()),
                default=0,
            )

        width = max(
            text_width(label)
            for label in (
                self.header,
                self.description,
                self.range_label,
                self.effective_label,
                self.note,
            )
        )
        if not self.options_widget.isHidden():
            flag_width = max(text_width(flag) for flag, _ in self.option_labels)
            description_width = max(
                text_width(description) for _, description in self.option_labels
            )
            width = max(
                width,
                flag_width
                + self.options_widget.layout().horizontalSpacing()
                + description_width,
            )
        return width + 2

    def preferred_size(self, available_width, available_height, *, fixed_width=None):
        """Measure wrapped help within the width allocated by the host."""
        self.ensurePolished()
        margins = self.layout().contentsMargins() + self.contentsMargins()
        horizontal_padding = margins.left() + margins.right()
        vertical_padding = margins.top() + margins.bottom()
        scrollbar_width = self.scroll_area.verticalScrollBar().sizeHint().width()
        popup_width = min(
            available_width,
            self.MAX_WIDTH,
            self._preferred_text_width() + horizontal_padding + scrollbar_width,
        )
        if fixed_width is not None:
            popup_width = max(1, min(available_width, fixed_width))
        text_width = max(1, popup_width - horizontal_padding - scrollbar_width)
        content_layout = self.content_widget.layout()
        content_layout.invalidate()
        content_height = max(
            1,
            content_layout.heightForWidth(text_width),
            content_layout.minimumSize().height(),
        )
        self.content_widget.setMinimumHeight(content_height)
        popup_height = min(available_height, content_height + vertical_padding)
        return QSize(popup_width, popup_height)
