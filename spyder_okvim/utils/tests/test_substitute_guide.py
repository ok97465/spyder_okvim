"""Incomplete substitution guidance shares executable Ex scanning rules."""

from dataclasses import FrozenInstanceError

import pytest

from spyder_okvim.utils import ex_parser
from spyder_okvim.utils.ex_parser import (
    ExError,
    SubstituteSpec,
    parse_substitute,
    scan_substitute_guide,
)


def guide(text, previous=None):
    return scan_substitute_guide(text, len(text), previous)


@pytest.mark.parametrize(
    "text, stage",
    [
        (":s/", "pattern"),
        (":s/foo", "pattern"),
        (":s/foo/", "replacement"),
        (":s/foo/bar", "replacement"),
        (":s/foo/bar/", "flags"),
        (":s/foo/bar/gc", "flags"),
        (":s//", "replacement"),
        (":s///", "flags"),
        (":s/foo//", "flags"),
        (":s#old/path#new/path#g", "flags"),
    ],
)
def test_fields_follow_typed_or_pasted_input(text, stage):
    assert guide(text).stage == stage


def test_deleting_delimiters_reverses_the_stages():
    text = ":s/foo/bar/"
    stages = [guide(text[:end]).stage for end in range(len(text), 2, -1)]
    assert stages == [
        "flags",
        "replacement",
        "replacement",
        "replacement",
        "replacement",
        "pattern",
        "pattern",
        "pattern",
        "pattern",
    ]


@pytest.mark.parametrize(
    "cursor, expected",
    [
        (0, None),
        (1, None),
        (2, None),
        (3, "pattern"),
        (4, "pattern"),
        (6, "pattern"),
        (7, "replacement"),
        (8, "replacement"),
        (10, "replacement"),
        (11, "flags"),
        (12, "flags"),
        (13, "flags"),
    ],
)
def test_cursor_field_boundaries(cursor, expected):
    context = scan_substitute_guide(":s/foo/bar/gc", cursor)
    assert (context.stage if context else None) == expected


@pytest.mark.parametrize("command", ["substitute"[:end] for end in range(1, 11)])
@pytest.mark.parametrize("prefix", ["", "%", "3,8", ".,$", "1,4", " . , $ "])
def test_abbreviations_and_unresolved_ranges(command, prefix):
    text = ":" + prefix + command + "/"
    context = guide(text)
    assert context.stage == "pattern"
    assert context.addresses == ex_parser.scan_header(text[1:]).addresses


@pytest.mark.parametrize(
    "text",
    [
        "",
        ":",
        ":s",
        ":su",
        ":substitute",
        ":3,",
        ":.,",
        ":3,s/",
        ":3,,8s/",
        ":%,3s/",
        ":&",
        ":&&",
        ":~",
        ":&/a/b/",
        ":s g",
        ':s "comment',
        ":s 3",
        ":s r",
        ":sort/",
        ":S/",
        ":substitutex/",
        ":write /a/b/",
        ":e /a/b/",
        "/s/foo/bar/",
        "?s/foo/",
    ],
)
def test_non_guided_commands_and_incomplete_ranges(text):
    assert guide(text) is None


@pytest.mark.parametrize("delimiter", ["\\", '"', "|", "한", "\x7f", "\n", "0", "a"])
def test_invalid_delimiter_does_not_start_guidance(delimiter):
    assert guide(":s " + delimiter) is None


def test_all_executable_delimiters_start_the_same_guide():
    for codepoint in range(33, 127):
        delimiter = chr(codepoint)
        try:
            parse_substitute(delimiter + "a" + delimiter + "b" + delimiter)
        except ExError:
            continue
        context = guide(":s" + delimiter)
        assert context.stage == "pattern"
        assert context.delimiter == delimiter


@pytest.mark.parametrize(
    "body",
    [
        r"/a\/b/c\/d/g",
        "/" + "a" + "\\" * 2 + "/b/g",
        "/" + "a" + "\\" * 3 + "/b/c/g",
        "/" + "a" + "\\" * 4 + "/b/g",
        "/[a/b]/x/g",
        "#[#]#x#g",
        "/[]/]/x/g",
        "/[^]/]/x/g",
        "/[[:digit:]/]/x/g",
        r"/[a\]/]/x/g",
        r"/\Q[\/\E/x/g",
        r"/\Qa\\E[/]/X/g",
        r".\Qa\.b\E.x.g",
        r".\Qa\\E\.b.x.g",
        r".\\Qa\.b.x.g",
        r".\Qa\\\.b\E.x.g",
        r".\Qa\.b.x.g",
    ],
)
def test_pattern_and_replacement_boundaries_match_execution(body):
    # Execution's decoded values independently identify the final options field.
    spec = parse_substitute(body)
    assert spec.flags == "g"
    text = ":s" + body
    context = guide(text)
    assert context.stage == "flags"
    assert context.delimiter == spec.delimiter
    assert context.effective_flags == spec.flags
    final_delimiter = text.rindex(spec.delimiter)
    assert scan_substitute_guide(text, final_delimiter).stage == "replacement"
    assert scan_substitute_guide(text, final_delimiter + 1).stage == "flags"


@pytest.mark.parametrize("body", [r"/[a/b", r"/\Q[\/", r"/a\/b", r"/a\\\/b"])
def test_incomplete_escaped_or_class_patterns_remain_patterns(body):
    assert guide(":s" + body).stage == "pattern"


@pytest.mark.parametrize(
    "flags, effective",
    [
        ("", ""),
        ("g", "g"),
        ("gg", ""),
        ("ggg", "g"),
        ("cc", ""),
        ("ee", ""),
        ("gcegce", ""),
        ("iI", "I"),
        ("Ii", "i"),
        ("iIi", "i"),
        ("nc", "n"),
        ("cn", "n"),
        ("ncc", "n"),
        ("gnc", "gn"),
        ("r", ""),
        ("gr", "g"),
        ("nn", "n"),
    ],
)
def test_effective_flags_follow_execution_precedence(flags, effective):
    context = guide(":s/a/b/" + flags)
    assert context.stage == "flags"
    assert context.raw_flags == flags
    assert context.effective_flags == effective


@pytest.mark.parametrize(
    "flags, effective",
    [("&", "gI"), ("&g", "I"), ("&i", "gi"), ("&nc", "gIn")],
)
def test_previous_options_are_imported_before_applying_new_ones(flags, effective):
    previous = SubstituteSpec("old", "new", "#", "gIr", count=3)
    context = guide(":s/a/b/" + flags, previous)
    assert context.effective_flags == effective
    assert not context.missing_previous
    assert previous == SubstituteSpec("old", "new", "#", "gIr", count=3)


def test_missing_previous_options_are_explained_without_blocking_input():
    context = guide(":s/a/b/&g")
    assert context.stage == "flags"
    assert context.missing_previous
    assert context.effective_flags == "g"


@pytest.mark.parametrize("flags", ["p", "#", "l", "x", "g&", "&g&", "g i"])
def test_unsupported_options_offer_guidance_without_accepting_the_command(flags):
    text = ":s/a/b/" + flags
    context = guide(text)
    assert context.stage == "unsupported"
    assert context.unsupported
    with pytest.raises(ExError):
        parse_substitute(text[2:])


@pytest.mark.parametrize(
    "tail, stage",
    [
        ("g 3", "count"),
        ("3", "count"),
        (" 0", "count"),
        ("2147483648", "count"),
        ("g 3  ", "count"),
        ("g ", "flags"),
        ('g "comment', None),
        ('g 3 "comment', None),
        ('"comment', None),
        ("g 3p", "unsupported"),
    ],
)
def test_counts_comments_and_invalid_count_values(tail, stage):
    context = guide(":s/a/b/" + tail)
    assert (context.stage if context else None) == stage


def test_cursor_moves_from_flags_through_count_and_comment():
    prefix = ":s/a/b/"
    text = prefix + 'g 32 "comment'
    for cursor, stage in [
        (0, "flags"),
        (1, "flags"),
        (2, "count"),
        (3, "count"),
        (4, "count"),
        (5, None),
        (10, None),
    ]:
        context = scan_substitute_guide(text, len(prefix) + cursor)
        assert (context.stage if context else None) == stage


def test_python_cursor_indices_support_korean_and_emoji():
    text = ":s/한😀글/새😀값/g"
    boundary = text.index("/", 3)
    assert scan_substitute_guide(text, boundary).stage == "pattern"
    assert scan_substitute_guide(text, boundary + 1).stage == "replacement"
    assert guide(text).stage == "flags"


def test_guide_neither_resolves_ranges_nor_parses_executable_substitutions(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Guidance must only scan unfinished text")

    monkeypatch.setattr(ex_parser, "resolve_range", unexpected)
    monkeypatch.setattr(ex_parser, "parse_substitute", unexpected)
    monkeypatch.setattr(ex_parser, "resolve_substitute", unexpected)
    monkeypatch.setattr(ex_parser, "_decimal_address", unexpected)
    assert guide(":999,1s/[invalid/b/g").stage == "pattern"
    assert guide(":999,1s/a/b/g").effective_flags == "g"
    assert guide(":999,1s/a/b/g " + "9" * 5000).stage == "count"


def test_context_cannot_mutate_saved_input_state():
    context = guide(":s/a/b/g")
    with pytest.raises(FrozenInstanceError):
        context.stage = "replacement"
