"""Substitution computation preserves text and follows Vim's match progression."""

import pytest
from qtpy.QtGui import QTextCursor, QTextDocument

from spyder_okvim.utils import substitute
from spyder_okvim.utils.search_helpers import compile_pattern


def _plan(
    text, expression, replacement, *, delimiter="/", first=0, last=None, **kwargs
):
    document = QTextDocument(text)
    pattern = compile_pattern(expression, ignorecase=False)
    tokens = (
        ()
        if kwargs.get("count_only")
        else substitute.tokenize_replacement(replacement, delimiter)
    )
    plan = substitute.build_substitution_plan(
        document,
        first,
        document.blockCount() - 1 if last is None else last,
        pattern,
        tokens,
        **kwargs,
    )
    return document, plan


def _apply(document, plan):
    for start, end, text in reversed(plan.edits):
        cursor = QTextCursor(document)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.insertText(text)
    return document.toPlainText()


@pytest.mark.parametrize(
    "text, pattern, replacement, expected, count",
    [
        ("foo foo\nfoo", "foo", "longer", "longer foo\nlonger", 2),
        ("foo bar", "(foo) (bar)", r"\2-\1-&-\0", "bar-foo-foo bar-foo bar", 1),
        ("b ab", "(a)?b", r"<\1>", "<> ab", 1),
        ("a", "a", r"\&\\\t~\/", "&\\\t~/", 1),
        ("a", "a", r"\q\z\~\b", "qz~\b", 1),
        ("a", "a", r"x\=y", "x=y", 1),
        ("a", "a", "tail\\", "tail\\", 1),
        ("a", "a", r"<\1\9>", "<>", 1),
        ("a\u00a0b", "(a b)", r"\1&", "a ba b", 1),
        ("😀a😀", "(😀)", r"\1!", "😀!a😀", 1),
        ("a\u0301b", "(a\u0301)", r"[\1]", "[a\u0301]b", 1),
        ("", "^", "x", "x", 1),
        ("a\n", "$", "!", "a!\n!", 2),
    ],
)
def test_compute_and_apply(text, pattern, replacement, expected, count):
    document, plan = _plan(text, pattern, replacement)
    assert plan.match_count == count
    assert _apply(document, plan) == expected


def test_nbsp_capture_and_whole_match_preserve_original_paragraph():
    document, plan = _plan("a\u00a0b", "(a b)", r"[\1]-&")
    assert plan.edits == ((0, 3, "[a\u00a0b]-a\u00a0b"),)
    _apply(document, plan)
    assert document.begin().text() == "[a\u00a0b]-a\u00a0b"


@pytest.mark.parametrize(
    "text, pattern, replacement, expected, count",
    [
        ("foo foo\nfoo", "foo", "x", "x x\nx", 3),
        ("😀aa", "(?=a)|a", "x", "😀xaxa", 2),
        ("aaa", "(?=a)|a+", "x", "xaxaxa", 3),
        ("aaa", "a*", "x", "x", 1),
        ("baab", "a*", "x", "xbxb", 2),
        ("bbb", "a*", "x", "xbxbxb", 3),
        ("aa", "a|$", "x", "xx", 2),
        ("ab", "a|$", "x", "xbx", 2),
        ("😀a", "(?=.)", "!", "!😀!a", 2),
        ("a\u0301b", "x*", "X", "Xa\u0301Xb", 2),
        ("😀\ufe0fb", "x*", "X", "X😀\ufe0fXb", 2),
        ("a\n\nb", "^", "!", "!a\n!\n!b", 3),
        ("aaa", r"a\K", "!", "a!a!a!", 3),
        ("ab", r"a\K|b", "X", "aXX", 2),
        ("aba", r"a\K|[ab]?", "X", "aXXaX", 3),
        ("abab", r"a*|b\K", "X", "XbXb", 2),
        ("aba", r"(?=b)|b\K", "X", "aXba", 1),
    ],
)
def test_global_empty_and_same_start_matches(
    text, pattern, replacement, expected, count
):
    document, plan = _plan(text, pattern, replacement, global_matches=True)
    assert plan.match_count == count
    assert _apply(document, plan) == expected


def test_range_starts_at_requested_block_and_counts_target_lines():
    document, plan = _plan(
        "x\nx x\nx x\nx", "x", "z", first=1, last=2, global_matches=True
    )
    assert plan.edits == ((2, 3, "z"), (4, 5, "z"), (6, 7, "z"), (8, 9, "z"))
    assert (plan.match_count, plan.line_count, plan.last_line) == (4, 2, 2)
    assert _apply(document, plan) == "x\nz z\nz z\nx"


def test_only_target_blocks_are_matched(monkeypatch):
    observed = []
    iterate = substitute._iter_matches

    def record(pattern, text, global_matches):
        observed.append(text)
        yield from iterate(pattern, text, global_matches)

    monkeypatch.setattr(substitute, "_iter_matches", record)
    _plan("outside\nfirst\nsecond\noutside", ".", "x", first=1, last=2)
    assert observed == ["first", "second"]


@pytest.mark.parametrize(
    "replacement",
    [r"\n", r"\r", r"\U", r"\L", r"\=", "a\nb", "a\u2028b", "a\u2029b"],
)
def test_invalid_replacements_rejected_even_without_matches(replacement):
    with pytest.raises(ValueError):
        _plan("nothing", "foo", replacement)


@pytest.mark.parametrize("replacement", [r"\r", r"\U", r"\2", "a\u2028b"])
def test_count_only_ignores_replacement(replacement):
    document, plan = _plan("foo foo", "foo", replacement, count_only=True)
    assert plan.match_count == 1
    assert plan.edits == ()
    assert document.toPlainText() == "foo foo"


@pytest.mark.parametrize(
    "pattern,replacement", [(r"\C", "x"), (r"(\C)\C", r"\1"), (r"\C(\C)", r"\1")]
)
def test_reject_surrogate_boundaries_in_edit_and_used_captures(pattern, replacement):
    with pytest.raises(ValueError, match="surrogate"):
        _plan("😀", pattern, replacement)


def test_count_only_can_count_qt_utf16_matches_without_edit_validation():
    _, plan = _plan("😀", r"\C", "x", count_only=True, global_matches=True)
    assert plan.match_count == 2


@pytest.mark.parametrize("text", ["\ud800", "\udfff"])
def test_global_matching_rejects_invalid_unicode_before_unchecked_qt_match(text):
    pattern = compile_pattern(r".\K", ignorecase=False)
    with pytest.raises(UnicodeEncodeError):
        list(substitute._iter_matches(pattern, text, True))


def test_unused_capture_can_split_surrogate_when_edit_boundaries_are_safe():
    document, plan = _plan("😀", r"(\C)\C", "x")
    assert _apply(document, plan) == "x"


@pytest.mark.parametrize("replacement", ["&", r"\0", r"\1"])
def test_capture_cannot_insert_soft_line_separator(replacement):
    with pytest.raises(ValueError, match="Line breaks"):
        _plan("a\u2028b", "(a[^b]*b)", replacement)


def test_matching_and_deleting_soft_line_separator_is_supported():
    document, plan = _plan("a\u2028b", "(a[^b]*b)", "")
    assert _apply(document, plan) == ""


def test_separator_byte_sequence_across_code_units_is_not_a_separator():
    # UTF-16 bytes 00 28 20 00 contain the bytes for U+2028 at odd offset 1.
    text = "\u2800 "
    document, plan = _plan(text, "(.*)", r"[\1]")
    assert _apply(document, plan) == "[" + text + "]"


@pytest.mark.parametrize("replacement", ["&", r"\0", r"\1"])
def test_equal_replacements_keep_counts_without_edits(replacement):
    _, plan = _plan("aa\naa", "(a)", replacement, global_matches=True)
    assert plan.edits == ()
    assert (plan.match_count, plan.line_count, plan.last_line) == (4, 2, 1)


def test_confirmation_retains_unchanged_targets_in_match_order():
    document, plan = _plan("aa", "a", "&", global_matches=True, confirm=True)
    assert plan.edits == ((0, 1, "a"), (1, 2, "a"))
    assert plan.match_count == 2
    assert document.toPlainText() == "aa"


def test_adjacent_replacements_can_cancel_for_whole_block():
    _, plan = _plan("aa", r"a(?=a)|(a)", r"\1\1", global_matches=True)
    assert plan.match_count == 2
    assert plan.edits == ()


def test_count_only_does_not_expand_or_allocate_edits(monkeypatch):
    def fail(*args):
        pytest.fail("Count-only execution expanded a replacement")

    monkeypatch.setattr(substitute, "substitution_match", fail)
    document, plan = _plan("a a\na", "a", "z", global_matches=True, count_only=True)
    assert (plan.match_count, plan.line_count, plan.last_line) == (3, 2, 1)
    assert plan.edits == ()
    assert document.toPlainText() == "a a\na"


@pytest.mark.parametrize("delimiter", ["&", ".", "+", "#"])
def test_delimiter_escape_is_literal_in_replacement(delimiter):
    document, plan = _plan("a", "a", "\\" + delimiter, delimiter=delimiter)
    assert _apply(document, plan) == delimiter


def test_invalid_pattern_rejected_without_edits():
    with pytest.raises(ValueError, match="Invalid pattern"):
        _plan("a", "[", "z")
