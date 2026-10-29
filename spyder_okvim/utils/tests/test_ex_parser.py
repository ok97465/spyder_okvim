"""The supported Ex grammar is independent of editor and search state."""

import pytest

from spyder_okvim.utils.ex_parser import (
    ExError,
    SubstituteSpec,
    is_substitute,
    parse_substitute,
    resolve_range,
    resolve_substitute,
    scan_header,
)


@pytest.mark.parametrize(
    "text, addresses, command, argument",
    [
        ("s/foo/bar/g", (), "s", "/foo/bar/g"),
        ("su/foo/bar/g", (), "su", "/foo/bar/g"),
        ("substit/foo/bar/g", (), "substit", "/foo/bar/g"),
        (
            "%substitute#old/path#new/path#g",
            ("%",),
            "substitute",
            "#old/path#new/path#g",
        ),
        ("3,8s/a/b/", ("3", "8"), "s", "/a/b/"),
        (" . , $ s/a/b/", (".", "$"), "s", "/a/b/"),
        ("q!", (), "q!", ""),
        ("s!a!b!", (), "s", "!a!b!"),
        ("s /foo/bar/g", (), "s", "/foo/bar/g"),
        ('e "a folder/한글.py"', (), "e", '"a folder/한글.py"'),
        ("e a folder/name.py  ", (), "e", "a folder/name.py  "),
        ("YankyRingHistory", (), "YankyRingHistory", ""),
        ("3", ("3",), "", ""),
    ],
)
def test_header_leaves_command_arguments_intact(text, addresses, command, argument):
    header = scan_header(text)
    assert header.addresses == addresses
    assert header.command == command
    assert header.argument == argument
    assert text[header.command_start : header.command_end] == command
    assert text[header.argument_start :] == argument


@pytest.mark.parametrize("text", ["s", "%su", "3,8su", ".,$substitute/a"])
def test_incomplete_header_never_parses_substitute_body(text):
    header = scan_header(text, incomplete=True)
    assert header.command in ("s", "su", "substitute")


@pytest.mark.parametrize(
    "text, current, count, expected",
    [
        ("s/a/b", 2, 9, (2, 2)),
        ("%s/a/b", 2, 9, (0, 8)),
        ("3,8s/a/b", 2, 9, (2, 7)),
        (".,$s/a/b", 2, 9, (2, 8)),
        ("$s/a/b", 0, 9, (8, 8)),
        ("1s/^/x", 0, 1, (0, 0)),
        ("%s/^/x", 0, 0, (0, 0)),
        ("0s/a/b/", 2, 9, (0, 0)),
        ("0,2s/a/b/", 2, 9, (0, 1)),
        ("0,0s/a/b/", 2, 9, (0, 0)),
    ],
)
def test_resolve_inclusive_block_range(text, current, count, expected):
    assert resolve_range(scan_header(text), current, count) == expected


@pytest.mark.parametrize("text", ["10s/a/b/", "8,3s/a/b/"])
def test_invalid_resolved_ranges(text):
    with pytest.raises(ExError):
        resolve_range(scan_header(text), 0, 9)


@pytest.mark.parametrize(
    "text",
    ["3,s/a/b/", "3,,8s/a/b/", "%,3s/a/b/", "3 8s/a/b/", "'<,'>s/a/b/", "__class__"],
)
def test_invalid_header_addresses(text):
    with pytest.raises(ExError):
        scan_header(text)


@pytest.mark.parametrize("text", ["q!!", "wq!extra", "wq/path", "e'path'", "n|q"])
def test_non_substitute_commands_require_whitespace_before_arguments(text):
    with pytest.raises(ExError):
        scan_header(text)


def test_whitespace_separated_legacy_arguments_remain_available():
    assert scan_header("w 한글.py").argument == "한글.py"
    assert scan_header("wq !extra").argument == "!extra"


def test_lone_decimal_address_remains_a_line_motion():
    assert scan_header("  03 ").line_number == 3
    assert scan_header("3s/a/b/").line_number is None
    assert scan_header("3,8").line_number is None
    assert scan_header("$").line_number is None


@pytest.mark.parametrize(
    "body, pattern, replacement, flags",
    [
        ("/foo/bar/", "foo", "bar", ""),
        ("/foo//g", "foo", "", "g"),
        ("//bar/g", "", "bar", "g"),
        ("/foo/", "foo", "", ""),
        ("/foo", "foo", "", ""),
        ("/foo/barg", "foo", "barg", ""),
        ("/ foo / bar /giIg", " foo ", " bar ", "iI"),
        (r"#old/path#new/path#g", "old/path", "new/path", "g"),
        (r"/a\/b/c\/d/g", "a/b", r"c\/d", "g"),
        (r"+a\+b+c+", r"a\+b", "c", ""),
        (r".a\.b.c.", r"a\.b", "c", ""),
        (r"-[a\-z]-x-", r"[a\-z]", "x", ""),
        (r"#(?x)a\#b#x#", r"(?x)a\#b", "x", ""),
        (r"/(foo)\d+/\1\t&/", r"(foo)\d+", r"\1\t&", ""),
    ],
)
def test_substitution_grammar_preserves_spaces_and_escape_domains(
    body, pattern, replacement, flags
):
    spec = parse_substitute(body)
    assert spec.pattern == pattern
    assert spec.replacement == replacement
    assert spec.delimiter == body[0]
    assert spec.flags == flags


def test_odd_and_even_backslashes_before_delimiter():
    # Two backslashes quote one regex backslash; the next slash is a boundary.
    spec = parse_substitute("/" + "a" + "\\" * 2 + "/b/")
    assert spec.pattern == "a" + "\\" * 2
    assert spec.replacement == "b"
    # With three, the last backslash quotes the slash inside the pattern.
    spec = parse_substitute("/" + "a" + "\\" * 3 + "/b/c/")
    assert spec.pattern == "a" + "\\" * 2 + "/b"
    assert spec.replacement == "c"


@pytest.mark.parametrize(
    "body, expected_pattern, target",
    [
        (r".\Qa\.b\E.x.", r"\Qa.b\E", "a.b"),
        (r"+\Qa\+b\E+x+", r"\Qa+b\E", "a+b"),
        (r"#\Qfoo\#bar\E#x#", r"\Qfoo#bar\E", "foo#bar"),
        (r"-\Qa\-b\E-x-", r"\Qa-b\E", "a-b"),
        (r".\Qa\\E\.b.x.", r"\Qa\\E\.b", r"a\.b"),
        (r".\\Qa\.b.x.", r"\\Qa\.b", r"\Qa.b"),
        (r".\Qa\\\.b\E.x.", r"\Qa\\.b\E", r"a\\.b"),
        (r".\Qa\.b.x.", r"\Qa.b", "a.b"),
    ],
)
def test_delimiter_quoting_respects_qt_literal_spans(body, expected_pattern, target):
    from qtpy.QtCore import QRegularExpression

    spec = parse_substitute(body)
    assert spec.pattern == expected_pattern
    pattern = QRegularExpression(spec.pattern)
    assert pattern.isValid()
    match = pattern.match(target)
    assert match.hasMatch()
    assert match.captured() == target


@pytest.mark.parametrize(
    "delimiter", ["a", "0", " ", "\\", '"', "|", "한", "\x7f", "\n"]
)
def test_invalid_substitution_delimiters(delimiter):
    with pytest.raises(ExError):
        parse_substitute(delimiter + "foo" + delimiter + "bar")


@pytest.mark.parametrize(
    "body",
    [
        "",
        "/foo/bar/g count",
        "/foo/bar/ggx",
        "/foo/bar/g|q",
        "/foo/bar/ g",
        "/foo/bar/g i",
        "/foo/bar/0",
        "/foo/bar/2147483648",
        "/foo/bar/2g",
        "/foo/bar/g2i",
    ],
)
def test_invalid_substitution_flags_counts_and_trailing_input(body):
    with pytest.raises(ExError):
        parse_substitute(body)


@pytest.mark.parametrize("command", ["s", "su", "sub", "substitute"])
def test_substitute_abbreviations(command):
    assert is_substitute(command)
    assert scan_header(command + "/a/b/").argument == "/a/b/"


@pytest.mark.parametrize("command", ["", "S", "substitutex", "sort", "smagic"])
def test_other_commands_are_not_substitute(command):
    assert not is_substitute(command)


@pytest.mark.parametrize(
    "body, flags, count",
    [
        ("/foo/bar/gg", "", None),
        ("/foo/bar/ggg", "g", None),
        ("/foo/bar/ee", "", None),
        ("/foo/bar/eee", "e", None),
        ("/foo/bar/giIgg", "iIg", None),
        ("/foo/bar/nniI", "nniI", None),
        ("/foo/bar/cn", "cn", None),
        ("/foo/bar/c", "c", None),
        ("/foo/bar/ccc", "c", None),
        ("/foo/bar/nc", "nc", None),
        ("/foo/bar/cc", "", None),
        ("/foo/bar/2", "", 2),
        ("/foo/bar/g2", "g", 2),
        ("/foo/bar/g 002  ", "g", 2),
        ("/foo/bar/ 99", "", 99),
        ('/foo/bar/g "comment', "g", None),
        ('/foo/bar/g 2 "comment', "g", 2),
    ],
)
def test_substitute_flags_toggle_and_optional_count(body, flags, count):
    spec = parse_substitute(body)
    assert spec.flags == flags
    assert spec.count == count


@pytest.mark.parametrize(
    "body, pattern, target",
    [
        ("/[a/b]/x/g", "[a/b]", "/"),
        ("#[#]#x#", "[#]", "#"),
        ("#[^#]#x#", "[^#]", "a"),
        ("/[]/]/x/g", "[]/]", "]"),
        ("/[^]/]/x/g", "[^]/]", "a"),
        ("/[[:digit:]/]/x/g", "[[:digit:]/]", "/"),
        (r"/[a\]/]/x/g", r"[a\]/]", "]"),
        (r"/\Q[\/\E/x/", r"\Q[/\E", "[/"),
        (r"/\Qa\\E[/]/X/g", r"\Qa\\E[/]", r"a\/"),
    ],
)
def test_pattern_delimiters_inside_character_classes(body, pattern, target):
    from qtpy.QtCore import QRegularExpression

    spec = parse_substitute(body)
    assert spec.pattern == pattern
    expression = QRegularExpression(spec.pattern)
    assert expression.isValid()
    assert expression.match(target).hasMatch()


@pytest.mark.parametrize(
    "text, command, argument",
    [
        ("&", "&", ""),
        ("&&", "&&", ""),
        ("&g2", "&", "g2"),
        ("&&g 2", "&&", "g 2"),
        ("~", "~", ""),
        ("~&g", "~", "&g"),
        ("1,2&&", "&&", ""),
    ],
)
def test_repeat_header_preserves_flags(text, command, argument):
    header = scan_header(text)
    assert header.command == command
    assert header.argument == argument
    assert is_substitute(command)


@pytest.mark.parametrize(
    "command, pattern, flags, count",
    [
        ("s", "old", "", None),
        ("su", "old", "", None),
        ("s g 2", "old", "g", 2),
        ('s "comment', "old", "", None),
        ("&", "old", "", None),
        ("&g", "old", "g", None),
        ("&&", "old", "gI", None),
        ("&&g", "old", "I", None),
        ("&&i 3", "old", "gIi", 3),
        ("~", "latest", "", None),
        ("~&", "latest", "gI", None),
        ("&r", "latest", "r", None),
        ("s r", "latest", "r", None),
        ("s/new/next/&", "new", "gI", None),
        ("s//next/&g", "latest", "I", None),
    ],
)
def test_resolve_new_and_repeat_substitutions(command, pattern, flags, count):
    previous = SubstituteSpec("old", r"\1/path", "#", "gI")
    spec = resolve_substitute(scan_header(command), previous, "latest")
    assert (spec.pattern, spec.flags, spec.count) == (pattern, flags, count)
    if not command.startswith("s/"):
        assert (spec.replacement, spec.delimiter) == (r"\1/path", "#")
    assert previous == SubstituteSpec("old", r"\1/path", "#", "gI")


@pytest.mark.parametrize("command", ["s", "&", "&&", "~", "&g 2"])
def test_repeat_requires_previous_substitute(command):
    with pytest.raises(ExError, match="No previous substitute"):
        resolve_substitute(scan_header(command), None, "search")


@pytest.mark.parametrize("command", ["&&&", "&x", "~x", "s g extra", "&0"])
def test_repeat_rejects_invalid_flags_and_counts(command):
    previous = SubstituteSpec("old", "new", "/", "g")
    with pytest.raises(ExError):
        resolve_substitute(scan_header(command), previous, "search")


def test_repeat_uses_saved_pattern_without_search_but_tilde_needs_search():
    previous = SubstituteSpec("old", "new", "/", "")
    assert resolve_substitute(scan_header("s"), previous, "").pattern == "old"
    with pytest.raises(ExError, match="No previous search"):
        resolve_substitute(scan_header("~"), previous, "")


@pytest.mark.parametrize("command", ["s", "&", "&&"])
def test_repeats_do_not_reuse_the_previous_count(command):
    previous = SubstituteSpec("old", "new", "/", "g", count=3)
    spec = resolve_substitute(scan_header(command), previous, "search")
    assert spec.count is None
    assert previous.count == 3


@pytest.mark.parametrize(
    "command, pattern, flags",
    [
        ("&&", "old", "g"),
        ("&&r", "search", "gr"),
        ("s/new/next/&", "new", "g"),
        ("s//next/&", "search", "g"),
    ],
)
def test_keep_flags_does_not_reuse_the_pattern_selector(command, pattern, flags):
    previous = SubstituteSpec("old", "new", "/", "gr")
    spec = resolve_substitute(scan_header(command), previous, "search")
    assert (spec.pattern, spec.flags) == (pattern, flags)
