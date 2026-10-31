"""Compatibility imports for the former motion helper module.

New commands use CursorMotions.text_objects explicitly. Legacy methods remain
here for callers of the historical MotionHelper import path.
"""

# Project Libraries
from spyder_okvim.utils.motions import CursorMotions


class MotionHelper(CursorMotions):
    """Preserve the former text-object method names without owning their rules."""

    def i_quote(self, quote):
        """Compatibility alias for ``text_objects.inner_quote``."""
        return self.text_objects.inner_quote(quote)

    def a_quote(self, quote):
        """Compatibility alias for ``text_objects.around_quote``."""
        return self.text_objects.around_quote(quote)

    def i_p(self, num=1):
        """Compatibility alias for ``text_objects.inner_paragraph``."""
        return self.text_objects.inner_paragraph(num)

    def a_p(self, num=1):
        """Compatibility alias for ``text_objects.around_paragraph``."""
        return self.text_objects.around_paragraph(num)

    def i_w(self, num):
        """Compatibility alias for ``text_objects.inner_word``."""
        return self.text_objects.inner_word(num)

    def i_W(self, num):
        """Compatibility alias for ``text_objects.inner_WORD``."""
        return self.text_objects.inner_WORD(num)

    def a_w(self, num):
        """Compatibility alias for ``text_objects.around_word``."""
        return self.text_objects.around_word(num)

    def a_W(self, num=1):
        """Compatibility alias for ``text_objects.around_WORD``."""
        return self.text_objects.around_WORD(num)

    def get_pos_bracket(self, num, bracket, cursor_pos):
        """Compatibility alias for ``text_objects.bracket_range``."""
        return self.text_objects.bracket_range(num, bracket, cursor_pos)

    def a_bracket(self, num, bracket):
        """Compatibility alias for ``text_objects.around_bracket``."""
        return self.text_objects.around_bracket(num, bracket)

    def i_bracket(self, num, bracket):
        """Compatibility alias for ``text_objects.inner_bracket``."""
        return self.text_objects.inner_bracket(num, bracket)

    def s(self, num):
        """Preserve the old word-object alias."""
        return self.text_objects.inner_word(num)
