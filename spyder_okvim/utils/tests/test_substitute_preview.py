"""Incremental parsing and finite calculation share final execution semantics."""

from dataclasses import replace

import pytest
from qtpy.QtGui import QTextCursor, QTextDocument

from spyder_okvim.utils.ex_parser import (
    ExError,
    SubstituteSpec,
    resolve_substitute,
    scan_substitute_preview,
)
from spyder_okvim.utils.substitute import (
    build_substitution_plan,
    prepare_substitution,
)
from spyder_okvim.utils.substitute_preview import (
    PreviewLimits,
    SubstitutePreview,
)


def preview(
    text,
    command,
    *,
    previous=None,
    current=0,
    limits=None,
    preview_lines=None,
    include_replacement=False,
):
    document = QTextDocument(text)
    context = scan_substitute_preview(command, previous)
    prepared = prepare_substitution(
        context.header,
        context.spec,
        current,
        document.blockCount(),
        prepare_replacement=include_replacement and context.pattern_closed,
    )
    calculation = SubstitutePreview(
        document, prepared, limits=limits, preview_lines=preview_lines
    )
    while not calculation.step(0):
        pass
    return document, prepared, calculation.result


@pytest.mark.parametrize(
    "command,pattern,replacement,closed,flags,count",
    [
        (":%s/fo", "fo", "", False, "", None),
        (":%s/foo/", "foo", "", True, "", None),
        (":su#foo#ba", "foo", "ba", True, "", None),
        (":substitute!foo!bar!g 3", "foo", "bar", True, "g", 3),
        (r":s/a\/b/x\/y/g", "a/b", r"x\/y", True, "g", None),
        (':s#[a#]#&#ggcIin " comment', "[a#]", "&", True, "cIin", None),
        (r":s#\Qa\#b\E#c#r", r"\Qa#b\E", "c", True, "r", None),
    ],
)
def test_scan_reads_entire_command(command, pattern, replacement, closed, flags, count):
    context = scan_substitute_preview(command)
    assert context.spec.pattern == pattern
    assert context.spec.replacement == replacement
    assert context.pattern_closed is closed
    assert (context.spec.flags, context.spec.count) == (flags, count)
    if closed:
        assert context.spec == resolve_substitute(context.header, None, "")


@pytest.mark.parametrize("command", [":s", ":s g", ":&", ":&&", ":~", ":1,", ":w/x"])
def test_repeat_and_unfinished_header_have_no_preview(command):
    assert scan_substitute_preview(command) is None


def test_completed_substitute_rejects_unsupported_flags():
    with pytest.raises(ExError):
        scan_substitute_preview(":s/foo/bar/unsupported")


def test_count_starts_from_range_end_and_previous_count_is_not_reused():
    previous = SubstituteSpec("x", "z", "/", "g", 8)
    document, prepared, result = preview(
        "x\nx x\nx x\nx", ":0,2s/x/y/& 2", previous=previous
    )
    assert (prepared.first_line, prepared.last_line) == (1, 2)
    assert (result.match_count, result.matched_lines) == (4, 2)
    assert (result.first_line, result.last_line) == (2, 3)
    assert result.spans == ((2, 3), (4, 5), (6, 7), (8, 9))
    without_count = scan_substitute_preview(":s/x/y/&", previous)
    assert without_count.spec.count is None
    assert document.toPlainText() == "x\nx x\nx x\nx"


@pytest.mark.parametrize(
    "text,command",
    [
        ("foo foo\nfoo", ":%s/foo/longer/"),
        ("foo foo\nfoo", ":%s/foo/bar/gc"),
        ("aaa", ":s/a(?=a)|(a)/\\1\\1/g"),
        ("aaa", ":s/(?=a)|a+/x/g"),
        ("aaa", r":s/a\K/!/g"),
        ("a\u00a0b", r":s/(a b)/[\1]-&/"),
        ("😀a😀", r":s/(😀)/\1!/g"),
        ("한글 a\u0301b", ":s/x*/X/g"),
        ("a\n", ":%s/$/!/g"),
        ("", ":s/^/x/"),
        ("foo", ":s/foo/"),
        ("foo", ":s/missing/"),
        ("foo foo", ":s/foo/foo/g"),
    ],
)
def test_highlights_match_execution_candidates_and_preserve_document(text, command):
    document, prepared, result = preview(text, command)
    assert (
        "\n".join(
            document.findBlockByNumber(index).text()
            for index in range(document.blockCount())
        )
        == text
    )
    context = scan_substitute_preview(command)
    executed = prepare_substitution(
        context.header, context.spec, 0, document.blockCount()
    )
    plan = build_substitution_plan(
        document,
        executed.first_line,
        executed.last_line,
        executed.pattern,
        executed.tokens,
        global_matches=executed.global_matches,
        confirm=True,
    )
    assert (result.match_count, result.matched_lines) == (
        plan.match_count,
        plan.line_count,
    )
    assert not result.partial
    assert result.spans == tuple((start, end) for start, end, _ in plan.edits)
    assert prepared.tokens == ()


@pytest.mark.parametrize(
    "command,expected_count",
    [
        (":%s/foo", 2),
        (":%s/foo/", 2),
        (":%s/foo/<tag>&/g", 3),
        (r":%s/foo/\1\1/gc", 3),
        (r":%s/foo/\=/gn", 3),
    ],
)
def test_highlighting_never_tokenizes_or_expands_replacements(
    monkeypatch, command, expected_count
):
    from spyder_okvim.utils import substitute

    def fail(*args, **kwargs):
        pytest.fail("Highlighting attempted to prepare replacement text")

    monkeypatch.setattr(substitute, "tokenize_replacement", fail)
    monkeypatch.setattr(substitute, "substitution_match", fail)
    _, prepared, result = preview("foo foo\nfoo", command)
    assert result.match_count == expected_count
    assert prepared.tokens == ()


@pytest.mark.parametrize("flags", ["g", "gnc"])
@pytest.mark.parametrize("replacement", [r"\r", r"\U", r"\2", r"\=", "a\u2028b"])
def test_highlighting_skips_replacement_validation_and_widens_surrogates(
    flags, replacement
):
    _, prepared, result = preview("😀", rf":s/\C/{replacement}/{flags}")
    assert prepared.tokens == ()
    assert result.count_only == ("n" in flags)
    assert not result.confirm
    assert result.match_count == 2
    assert result.spans == ((0, 2), (0, 2))


def test_replacement_errors_are_deferred_to_execution():
    context = scan_substitute_preview(r":s/foo/\=/g")
    prepared = prepare_substitution(
        context.header, context.spec, 0, 1, prepare_replacement=False
    )
    assert prepared.tokens == ()
    with pytest.raises(ExError, match="Expression"):
        prepare_substitution(context.header, context.spec, 0, 1)


def test_surrogate_matches_on_later_lines_remain_safe_for_highlighting():
    document = QTextDocument("a\n😀")
    context = scan_substitute_preview(r":%s/\C/x/g")
    prepared = prepare_substitution(
        context.header, context.spec, 0, 2, prepare_replacement=False
    )
    calculation = SubstitutePreview(document, prepared)
    while not calculation.step(0):
        pass
    assert calculation.result.spans == ((0, 1), (2, 4), (2, 4))
    assert not calculation.result.partial
    assert document.toPlainText() == "a\n😀"


@pytest.mark.parametrize(
    "limit,value,expected_count,reason",
    [
        ("max_lines", 1, 2, "line limit"),
        ("max_matches", 1, 1, "match limit"),
        ("max_scan_chars", 3, 2, "scan character limit"),
        ("max_command_chars", 1, 0, "command length limit"),
    ],
)
def test_scan_limits_bound_candidate_highlights(limit, value, expected_count, reason):
    limits = replace(PreviewLimits(), **{limit: value})
    _, _, result = preview("x x\nx x", ":%s/x/y/g", limits=limits)
    assert result.match_count == expected_count
    assert result.partial
    assert len(result.spans) == expected_count
    assert reason in result.reasons


def test_long_lines_are_omitted_before_regex_is_called(monkeypatch):
    from spyder_okvim.utils import substitute

    observed = []
    iterate = substitute._iter_matches

    def record(pattern, text, global_matches):
        observed.append(text)
        yield from iterate(pattern, text, global_matches)

    monkeypatch.setattr(substitute, "_iter_matches", record)
    limits = replace(PreviewLimits(), max_line_chars=3)
    _, _, result = preview("xxxxxxxx\nx", ":%s/x/y/g", limits=limits)
    assert observed == ["x"]
    assert result.partial and result.match_count == 1
    assert "long line omitted" in result.reasons


def test_highlighting_preserves_document_history_and_modified_state():
    document = QTextDocument("foo foo\nfoo")
    document.setModified(False)
    snapshot = (
        document.toPlainText(),
        document.revision(),
        document.isModified(),
        document.availableUndoSteps(),
        document.availableRedoSteps(),
    )
    context = scan_substitute_preview(":%s/foo/<tag>&/g")
    prepared = prepare_substitution(
        context.header, context.spec, 0, 2, prepare_replacement=False
    )
    calculation = SubstitutePreview(document, prepared)
    while not calculation.step(0):
        pass
    assert calculation.result.match_count == 3
    assert (
        document.toPlainText(),
        document.revision(),
        document.isModified(),
        document.availableUndoSteps(),
        document.availableRedoSteps(),
    ) == snapshot


def test_settings_and_flag_case_resolution_match_shared_execution():
    context = scan_substitute_preview(":s/FOO/bar/Iir")
    prepared = prepare_substitution(
        context.header, context.spec, 0, 1, prepare_replacement=False
    )
    executed = prepare_substitution(context.header, context.spec, 0, 1)
    assert prepared.spec == executed.spec
    assert prepared.pattern.patternOptions() == executed.pattern.patternOptions()
    assert prepared.pattern.match("foo").hasMatch()


@pytest.mark.parametrize(
    "text,command",
    [
        ("foo foo\nfoo", ":%s/foo/longer/g"),
        ("foo foo\nfoo", ":%s/foo/bar/gc"),
        ("aaa", ":s/a(?=a)|(a)/\\1\\1/g"),
        ("aaa", ":s/(?=a)|a+/x/g"),
        ("aaa", r":s/a\K/!/g"),
        ("a\u00a0b", r":s/(a b)/[\1]-&/"),
        ("😀a😀", r":s/(😀)/\1!/g"),
        ("한글 a\u0301b", ":s/x*/X/g"),
        ("a\n", ":%s/$/!/g"),
        ("", ":s/^/x/"),
        ("foo", ":s/foo/"),
        ("foo", ":s/missing/"),
        ("foo foo", ":s/foo/foo/g"),
        ("a\tb", ":s/(a)/\\1\\t/"),
        ("a<b&c", ":s/a/<tag>\\&/"),
    ],
)
def test_visible_overlay_lines_match_execution_without_mutating_source(text, command):
    document, prepared, result = preview(
        text,
        command,
        preview_lines=range(text.count("\n") + 1),
        include_replacement=True,
    )
    expected = QTextDocument(text)
    plan = build_substitution_plan(
        expected,
        prepared.first_line,
        prepared.last_line,
        prepared.pattern,
        prepared.tokens,
        global_matches=prepared.global_matches,
    )
    for start, end, replacement in reversed(plan.edits):
        cursor = QTextCursor(expected)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.insertText(replacement)
    assert result.match_count == plan.match_count
    assert not result.partial and not result.output_truncated
    changed_blocks = {
        number
        for number in range(expected.blockCount())
        if expected.findBlockByNumber(number).text()
        != document.findBlockByNumber(number).text()
    }
    assert {row.block_number for row in result.rows} == changed_blocks
    for row in result.rows:
        assert row.before == document.findBlockByNumber(row.block_number).text()
        assert row.after == expected.findBlockByNumber(row.block_number).text()
    assert (
        "\n".join(
            document.findBlockByNumber(number).text()
            for number in range(document.blockCount())
        )
        == text
    )


@pytest.mark.parametrize(
    "text,command,after,replacements,deletions",
    [
        ("foo foo", ":s/foo/longer/g", "longer longer", ((0, 6), (7, 13)), ()),
        ("a😀z", ":s/😀/", "az", (), (1,)),
        ("😀 x", ":s/x/😀/", "😀 😀", ((3, 5),), ()),
        ("ab ab", r":s/(a)(b)/\2\1/g", "ba ba", ((0, 2), (3, 5)), ()),
        ("foo", ":s/foo/", "", (), (0,)),
    ],
)
def test_overlay_marks_are_in_output_utf16_coordinates(
    text, command, after, replacements, deletions
):
    _, _, result = preview(text, command, preview_lines=(0,), include_replacement=True)
    row = result.rows[0]
    assert (row.after, row.replacements, row.deletions) == (
        after,
        replacements,
        deletions,
    )


def test_only_requested_visible_blocks_expand_replacements(monkeypatch):
    from spyder_okvim.utils import substitute

    observed = []
    expand = substitute.substitution_match

    def record(tokens, source, match, **kwargs):
        observed.append(source.decode("utf-16-le"))
        return expand(tokens, source, match, **kwargs)

    monkeypatch.setattr(substitute, "substitution_match", record)
    _, _, result = preview(
        "foo\nfoo foo\nfoo",
        ":%s/foo/bar/g",
        preview_lines=(1,),
        include_replacement=True,
    )
    assert observed == ["foo foo", "foo foo"]
    assert result.match_count == 4
    assert [row.block_number for row in result.rows] == [1]


def test_viewport_blocks_are_prioritized_beyond_the_scan_limit():
    limits = replace(PreviewLimits(), max_lines=2)
    _, _, result = preview(
        "\n".join(["foo"] * 10000),
        ":%s/foo/bar/",
        preview_lines=(9999,),
        include_replacement=True,
        limits=limits,
    )
    assert result.partial
    assert result.match_count == 2
    assert result.scanned_lines == 2
    assert [row.block_number for row in result.rows] == [9999]
    assert (result.first_line, result.last_line) == (1, 10000)


def test_incomplete_match_limited_line_never_emits_a_partial_after_result():
    limits = replace(PreviewLimits(), max_matches=1)
    _, _, result = preview(
        "foo foo",
        ":s/foo/bar/g",
        preview_lines=(0,),
        include_replacement=True,
        limits=limits,
    )
    assert result.partial and result.match_count == 1
    assert result.rows == ()
    assert result.output_truncated and result.omitted_blocks == (0,)


@pytest.mark.parametrize(
    "limit,value", [("max_output_chars", 5), ("max_expansion_chars", 3)]
)
def test_output_limits_omit_rows_while_candidate_scanning_continues(limit, value):
    limits = replace(PreviewLimits(), **{limit: value})
    _, _, result = preview(
        "foo foo\nfoo",
        ":%s/foo/longer/g",
        preview_lines=(0, 1),
        include_replacement=True,
        limits=limits,
    )
    assert result.match_count == 3 and not result.partial
    assert result.rows == () and result.output_truncated
    assert set(result.omitted_blocks) == {0, 1}


def test_output_limit_is_checked_before_assembling_large_expansions(monkeypatch):
    from spyder_okvim.utils import substitute

    def fail(*args, **kwargs):
        pytest.fail("Oversized replacement was assembled")

    monkeypatch.setattr(substitute, "assemble_substitution_line", fail)
    _, _, result = preview(
        "a" * 100,
        r":s/(a+)/" + r"\1" * 100 + "/",
        preview_lines=(0,),
        include_replacement=True,
        limits=replace(PreviewLimits(), max_output_chars=200),
    )
    assert result.match_count == 1
    assert result.rows == () and result.output_truncated


def test_visible_row_limit_does_not_stop_other_candidate_highlights():
    _, _, result = preview(
        "foo\nfoo\nfoo",
        ":%s/foo/bar/",
        preview_lines=(0, 1, 2),
        include_replacement=True,
        limits=replace(PreviewLimits(), max_preview_lines=1),
    )
    assert result.match_count == 3
    assert [row.block_number for row in result.rows] == [0]
    assert result.output_truncated and result.omitted_blocks == (1, 2)


def test_later_bad_capture_discards_all_prior_overlay_rows():
    document = QTextDocument("a\n😀")
    context = scan_substitute_preview(r":%s/\C/x/g")
    prepared = prepare_substitution(context.header, context.spec, 0, 2)
    calculation = SubstitutePreview(document, prepared, preview_lines=(0, 1))
    with pytest.raises(ValueError, match="surrogate"):
        while not calculation.step(0):
            pass
    assert calculation.result.rows == ()
    assert calculation.result.spans == ()
    assert calculation.result.partial


def test_count_only_and_unfinished_pattern_never_prepare_overlay_replacements(
    monkeypatch,
):
    from spyder_okvim.utils import substitute

    def fail(*args, **kwargs):
        pytest.fail("A search/count-only preview attempted replacement expansion")

    monkeypatch.setattr(substitute, "tokenize_replacement", fail)
    monkeypatch.setattr(substitute, "substitution_match", fail)
    for command in (":%s/foo", r":%s/foo/\u/gnc"):
        _, _, result = preview(
            "foo foo\nfoo",
            command,
            preview_lines=(0, 1),
            include_replacement=True,
        )
        assert result.rows == () and result.match_count >= 2


def test_viewport_priority_order_survives_duplicate_and_buffered_lines():
    _, _, result = preview(
        "foo\nfoo\nfoo",
        ":%s/foo/bar/",
        preview_lines=(2, 2, 0, 1),
        include_replacement=True,
        limits=replace(PreviewLimits(), max_matches=1),
    )
    assert result.partial and result.match_count == 1
    assert [row.block_number for row in result.rows] == [2]
    assert result.spans == ((8, 11),)


def test_unchanged_syntax_spans_map_unicode_deletion_and_noop_replacement():
    _, _, result = preview(
        "a😀foo x",
        r":s/foo|(x)/\1/g",
        preview_lines=(0,),
        include_replacement=True,
    )
    row = result.rows[0]
    assert row.after == "a😀 x"
    assert row.deletions == (3,)
    assert row.replacements == ()
    assert row.source_spans == ((0, 3, 0), (6, 8, 3))


def test_failed_expansion_is_not_retried_for_later_visible_rows(monkeypatch):
    from spyder_okvim.utils import substitute

    observed = []
    expand = substitute.substitution_match

    def record(tokens, source, match, **kwargs):
        observed.append(source.decode("utf-16-le"))
        return expand(tokens, source, match, **kwargs)

    monkeypatch.setattr(substitute, "substitution_match", record)
    _, _, result = preview(
        "foo\nfoo\nfoo",
        ":%s/foo/longer/",
        preview_lines=(0, 1, 2),
        include_replacement=True,
        limits=replace(PreviewLimits(), max_expansion_chars=3),
    )
    assert observed == ["foo"]
    assert result.match_count == 3
    assert result.rows == () and result.output_truncated
    assert result.omitted_blocks == (0, 1, 2)
