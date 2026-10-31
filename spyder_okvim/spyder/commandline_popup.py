"""One passive viewport host for command-line candidates and field guidance."""

# Third Party Libraries
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QFrame

# Project Libraries
from spyder_okvim.spyder.commandline_history import HistoryPopup
from spyder_okvim.spyder.substitute_guide import SubstituteGuidePopup


class CommandlinePopupHost(QFrame):
    """Fit the candidate list above the guide without taking input focus."""

    SPACING = 4

    def __init__(self, viewport):
        super().__init__(viewport)
        self.setObjectName("commandlinePopupHost")
        self.setMinimumSize(0, 0)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.popup = HistoryPopup(self)
        self.guide_popup = SubstituteGuidePopup(self)
        self._sections = (False, False)
        self._geometry_dirty = True
        self._viewport_size = None
        self.hide()

    def invalidate_geometry(self):
        """Defer changed content measurements until both sections are ready."""
        self._geometry_dirty = True

    def show_sections(self, *, candidates, guide):
        """Show requested sections, reusing unchanged content and geometry."""
        sections = bool(candidates), bool(guide)
        if sections != self._sections:
            self._sections = sections
            self.invalidate_geometry()
        self.popup.setVisible(sections[0])
        self.guide_popup.setVisible(sections[1])
        if not any(sections):
            self.hide()
            return
        self.update_geometry()
        self.raise_()
        self.show()

    def update_geometry(self):
        """Allocate bounded heights to two independently scrollable sections."""
        viewport = self.parentWidget()
        viewport_size = viewport.size()
        if not self._geometry_dirty and viewport_size == self._viewport_size:
            return
        self._viewport_size = viewport_size
        self._geometry_dirty = False
        candidates, guide = self._sections
        if not (candidates or guide):
            return
        width, height = viewport.width(), viewport.height()
        margin = min(8, max(0, (min(width, height) - 1) // 2))
        available_width = max(1, width - 2 * margin)
        available_height = max(1, height - 2 * margin)
        spacing = (
            min(self.SPACING, max(0, available_height - 2))
            if candidates and guide
            else 0
        )
        panel_size = (
            self.popup.preferred_size(available_width, available_height)
            if candidates
            else None
        )
        guide_size = (
            self.guide_popup.preferred_size(available_width, available_height)
            if guide
            else None
        )
        popup_width = max(
            panel_size.width() if panel_size is not None else 0,
            guide_size.width() if guide_size is not None else 0,
        )
        if guide and guide_size.width() != popup_width:
            guide_size = self.guide_popup.preferred_size(
                available_width, available_height, fixed_width=popup_width
            )
        panel_height = panel_size.height() if candidates else 0
        guide_height = guide_size.height() if guide else 0
        content_height = available_height - spacing
        if candidates and guide and panel_height + guide_height > content_height:
            # Keep both sections reachable; each retains its own scrollbar.
            panel_height = min(panel_height, max(1, content_height // 2))
            guide_height = max(1, content_height - panel_height)
        popup_height = min(available_height, panel_height + spacing + guide_height)
        self.setGeometry(
            margin, height - margin - popup_height, popup_width, popup_height
        )
        if candidates:
            self.popup.setGeometry(0, 0, popup_width, panel_height)
            self.popup.layout().activate()
            self.popup.ensure_selection_visible()
        if guide:
            guide_top = panel_height + spacing if candidates else 0
            self.guide_popup.setGeometry(0, guide_top, popup_width, guide_height)
            self.guide_popup.layout().activate()

    def forward_wheel(self, event):
        """Scroll the section under a viewport wheel without moving focus."""
        point = self.mapFromParent(event.position().toPoint())
        for popup, scrollbar in (
            (self.popup, self.popup.list_widget.verticalScrollBar()),
            (self.guide_popup, self.guide_popup.scroll_area.verticalScrollBar()),
        ):
            if (
                popup.isVisible()
                and popup.geometry().contains(point)
                and scrollbar.maximum() > scrollbar.minimum()
            ):
                scrollbar.event(event)
                event.accept()
                return True
        return False
