"""Regression coverage for Ex completion without changing the filesystem."""

# Standard Libraries
import os

# Third Party Libraries
import pytest

# Project Libraries
from spyder_okvim.utils.commandline import (
    CompletionCandidate,
    command_candidates,
    completion_items,
    merge_candidates,
    substitute_field_candidates,
)


COMMANDS = ("e", "w", "q", "q!", "wq", "n", "marks", "jumps")


def complete(text, directory, cursor=None, commands=COMMANDS):
    """Complete at the end by default."""
    return [
        (candidate.text, candidate.cursor_position)
        for candidate in completion_items(
            text, len(text) if cursor is None else cursor, commands, str(directory)
        )
    ]


def test_command_completion_preserves_argument(tmp_path):
    """Only supported names are proposed, including punctuation."""
    assert complete(":", tmp_path) == [
        (":" + cmd, len(cmd) + 1) for cmd in sorted(COMMANDS)
    ]
    assert complete(":q", tmp_path) == [(":q", 2), (":q!", 3)]
    assert complete(":wrong path.py", tmp_path, 2) == [
        (":w path.py", 2),
        (":wq path.py", 3),
    ]
    assert complete(":unknown", tmp_path) == []
    assert complete("/w", tmp_path) == []


def test_named_extension_commands_keep_builtin_completion_order(tmp_path):
    commands = COMMANDS + ("YankyRingHistory", "YankyClearHistory")
    candidates = complete(":", tmp_path, commands=commands)
    assert candidates[0] == (":e", 2)
    assert complete(":Yanky", tmp_path, commands=commands) == [
        (":YankyClearHistory", len(":YankyClearHistory")),
        (":YankyRingHistory", len(":YankyRingHistory")),
    ]


def test_path_completion_with_korean_and_spaces(tmp_path):
    """An entire raw argument is one path, regardless of spaces or Unicode."""
    directory = tmp_path / "한글 폴더"
    directory.mkdir()
    (directory / "보고서 초안.py").touch()
    assert complete(":w 한", tmp_path) == [
        (":w 한글 폴더" + os.sep, len(":w 한글 폴더" + os.sep))
    ]
    text = ":w 한글 폴더" + os.sep + "보고"
    expected = ":w 한글 폴더" + os.sep + "보고서 초안.py"
    assert complete(text, tmp_path) == [(expected, len(expected))]
    assert complete(":unknown 한", tmp_path) == []


@pytest.mark.parametrize("quote", ["'", '"'])
@pytest.mark.parametrize("closed", [False, True])
def test_quoted_paths_preserve_quotes(tmp_path, quote, closed):
    """Quoted paths stay quoted, and the cursor stays inside a closing quote."""
    (tmp_path / "한글 파일.py").touch()
    text = ":w " + quote + "한" + (quote if closed else "")
    cursor = len(text) - int(closed)
    expected = ":w " + quote + "한글 파일.py" + (quote if closed else "")
    assert complete(text, tmp_path, cursor) == [(expected, len(expected) - int(closed))]


@pytest.mark.parametrize("quote", ["'", '"'])
def test_completion_after_closing_quote(tmp_path, quote):
    """A caret just after the quote completes inside the quoted argument."""
    (tmp_path / "file name.py").touch()
    text = ":w " + quote + "fi" + quote
    expected = ":w " + quote + "file name.py" + quote
    assert complete(text, tmp_path) == [(expected, len(expected) - 1)]


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize(
    "path_prefix, target_directory",
    [
        ("", "."),
        ("." + os.sep, "."),
        (".." + os.sep, ".."),
        ("nested" + os.sep, "nested"),
    ],
)
def test_all_commands_complete_relative_paths_from_working_directory(
    tmp_path, monkeypatch, command, path_prefix, target_directory
):
    """Every path completer uses the supplied working directory consistently."""
    working_directory = tmp_path / "working"
    working_directory.mkdir()
    (working_directory / "nested").mkdir()
    target = working_directory / target_directory / "report_work.py"
    target.touch()
    unrelated_directory = tmp_path / "unrelated"
    unrelated_directory.mkdir()
    (unrelated_directory / "report_other.py").touch()
    monkeypatch.chdir(unrelated_directory)

    text = ":" + command + " " + path_prefix + "report"
    expected = ":" + command + " " + path_prefix + target.name
    assert complete(text, working_directory) == [(expected, len(expected))]


@pytest.mark.parametrize("command", COMMANDS)
def test_absolute_and_home_paths(tmp_path, monkeypatch, command):
    """Lookup expands the home directory without rewriting the typed spelling."""
    (tmp_path / "home file.py").touch()
    expanduser = os.path.expanduser

    def expand(path):
        if path == "~" + os.sep:
            return str(tmp_path) + os.sep
        return expanduser(path)

    monkeypatch.setattr(os.path, "expanduser", expand)
    unrelated_directory = tmp_path / "unrelated"
    unrelated_directory.mkdir()
    prompt = ":" + command + " "
    expected = prompt + str(tmp_path / "home file.py")
    assert complete(prompt + str(tmp_path / "ho"), unrelated_directory) == [
        (expected, len(expected))
    ]
    expected = prompt + "~" + os.sep + "home file.py"
    assert complete(prompt + "~" + os.sep + "ho", unrelated_directory) == [
        (expected, len(expected))
    ]


def test_directory_lookup_is_not_recursive(tmp_path):
    """Nested paths are read only when their parent is explicitly entered."""
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "nested.py").touch()
    assert complete(":w nested", tmp_path) == []
    expected = ":w folder" + os.sep
    assert complete(":w fol", tmp_path) == [(expected, len(expected))]


def test_component_remainder_is_replaced_and_suffix_preserved(tmp_path):
    """Completing mid-path retains the following path and quoted suffix."""
    (tmp_path / "folder").mkdir()
    text = ":w folWRONG" + os.sep + "child.py"
    expected = ":w folder" + os.sep + "child.py"
    assert complete(text, tmp_path, len(":w fol")) == [(expected, len(":w folder"))]
    (tmp_path / "file.py").touch()
    assert complete(":w fiWRONG", tmp_path, len(":w fi")) == [
        (":w file.py", len(":w file.py"))
    ]


def test_hidden_files_require_dot_prefix(tmp_path):
    """Normal directory completion hides dotfiles until explicitly requested."""
    (tmp_path / ".hidden").touch()
    (tmp_path / "visible").touch()
    assert complete(":w ", tmp_path) == [(":w visible", len(":w visible"))]
    assert complete(":w .", tmp_path) == [(":w .hidden", len(":w .hidden"))]


@pytest.mark.parametrize("command", [":e ", ":w "])
def test_path_completion_keeps_text_files_and_normal_directories(tmp_path, command):
    """Content filtering retains text regardless of extension or encoding."""
    (tmp_path / "source").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "README").write_text("Project notes\n", encoding="utf-8")
    (tmp_path / "한글.py").write_text("print('안녕')\n", encoding="utf-8")
    (tmp_path / "utf16.txt").write_text("안녕하세요\n", encoding="utf-16")
    (tmp_path / "empty.txt").touch()
    (tmp_path / "module.pyc").write_bytes(b"\x00\x01\x02\x03")
    (tmp_path / "binary.py").write_bytes(b"\x00\x01\x02\x03")
    (tmp_path / "binary").write_bytes(b"\x00\x01\x02\x03")

    expected = [
        command + name
        for name in ("README", "empty.txt", "source" + os.sep, "utf16.txt", "한글.py")
    ]
    assert complete(command, tmp_path) == [(text, len(text)) for text in expected]


@pytest.mark.parametrize("prefix", ["", "__", "__pycache__"])
def test_cache_directories_are_not_completed(tmp_path, prefix):
    """Cache folders stay excluded even when their name is explicitly started."""
    (tmp_path / "__pycache__").mkdir()
    assert complete(":e " + prefix, tmp_path) == []


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Requires named pipes")
def test_special_files_are_not_opened_for_text_detection(tmp_path, monkeypatch):
    """Completing a FIFO must not block waiting for a writer."""
    os.mkfifo(tmp_path / "pipe")

    def unexpected_read(path):
        pytest.fail("Special files must not be opened to detect text")

    monkeypatch.setattr("spyder_okvim.utils.commandline.is_text_file", unexpected_read)
    assert complete(":e ", tmp_path) == []


def test_missing_or_unreadable_directory(tmp_path, monkeypatch):
    """Lookup failures leave the command line unchanged."""
    assert complete(":w missing" + os.sep, tmp_path) == []

    def denied(_):
        raise PermissionError("test")

    monkeypatch.setattr(os, "scandir", denied)
    assert complete(":w ", tmp_path) == []


@pytest.mark.parametrize("prefix", [":", ":%", ":3,8", ":.,$"])
def test_substitute_name_completion_preserves_range_and_body(tmp_path, prefix):
    commands = COMMANDS + ("s", "substitute")
    text = prefix + "su/foo/bar/g"
    position = len(prefix + "su")
    expected = prefix + "substitute/foo/bar/g"
    assert complete(text, tmp_path, position, commands) == [
        (expected, len(prefix + "substitute"))
    ]


@pytest.mark.parametrize(
    "body", ["/foo/bar/g", "/foo name/bar", " foo", "#old/path#new/path#g"]
)
@pytest.mark.parametrize("command", ["s", "su", "substit", "substitute"])
def test_substitute_body_never_scans_files(tmp_path, monkeypatch, body, command):
    def unexpected_scan(_):
        pytest.fail("Substitution bodies must not request filesystem completion")

    monkeypatch.setattr(os, "scandir", unexpected_scan)
    text = ":%" + command + body
    assert complete(text, tmp_path, commands=COMMANDS + ("s", "substitute")) == []


@pytest.mark.parametrize("prefix", [":s", ":%s", ":3,8s"])
def test_bare_substitute_name_is_still_completable(tmp_path, prefix):
    commands = COMMANDS + ("s", "substitute")
    assert complete(prefix, tmp_path, commands=commands) == [
        (prefix, len(prefix)),
        (prefix[:-1] + "substitute", len(prefix) + len("ubstitute")),
    ]


def test_automatic_candidates_do_not_query_filesystem(monkeypatch):
    """Typing command names does not require filesystem reads."""

    def unexpected_read(*args, **kwargs):
        pytest.fail("Automatic candidates must use in-memory data")

    monkeypatch.setattr(os, "scandir", unexpected_read)
    monkeypatch.setattr("spyder_okvim.utils.commandline.is_text_file", unexpected_read)
    monkeypatch.setattr("builtins.open", unexpected_read)
    assert command_candidates(":w", 2, COMMANDS) == [(":w", 2), (":wq", 3)]


def test_merge_distinguishes_application_cursor_and_keeps_literal_text():
    """Identical labels or text alone do not imply the same application."""
    first = CompletionCandidate("history", "short", "full command", ":w 한글", 5)
    second = CompletionCandidate("command", "short", "command", ":w 한글", 2)
    duplicate = CompletionCandidate("command", "other", "command", ":w 한글", 5)
    assert merge_candidates([first], [second, duplicate]) == [
        CompletionCandidate("history, command", "short", "full command", ":w 한글", 5),
        second,
    ]


def test_explicit_completion_items_wrap_names_and_paths(tmp_path):
    (tmp_path / "file.py").touch()
    assert completion_items(":w", 2, iter(COMMANDS), str(tmp_path))[0] == (
        CompletionCandidate("command", ":w", "command", ":w", 2)
    )
    rows = completion_items(":w fi", 5, iter(COMMANDS), str(tmp_path))
    assert rows == [CompletionCandidate("path", ":w file.py", "path", ":w file.py", 10)]


def test_substitute_field_history_preserves_other_fields_and_suffix():
    entries = ["s/foo/bar/g", "s/food/barn/i", "s/foo/bar/g"]
    text = ":%s/foo/baWRONG/g 3"
    rows = substitute_field_candidates(entries, text, len(":%s/foo/ba"))
    assert [(row.text, row.cursor_position) for row in rows] == [
        (":%s/foo/bar/g 3", len(":%s/foo/bar")),
        (":%s/foo/barn/g 3", len(":%s/foo/barn")),
    ]
    assert all(row.apply_scope == "replacement" for row in rows)
    text = ":3,8substitute/foOLD/current/g"
    rows = substitute_field_candidates(entries, text, len(":3,8substitute/fo"))
    assert [row.text for row in rows] == [
        ":3,8substitute/foo/current/g",
        ":3,8substitute/food/current/g",
    ]


def test_substitute_field_history_uses_same_delimiter_and_raw_escapes():
    entries = [r"s/a\/b/c\/d/g", "s#old#new#g", "s/foo//g"]
    text = r":s/a\/OLD/keep/g"
    rows = substitute_field_candidates(entries, text, len(r":s/a\/"))
    assert [row.text for row in rows] == [r":s/a\/b/keep/g"]
    rows = substitute_field_candidates(entries, ":s/foo/", len(":s/foo/"))
    assert rows[0].label == "(빈 문자열: 삭제)"
    assert rows[0].text == ":s/foo/"
    assert [row.text for row in rows] == [":s/foo/", r":s/foo/c\/d"]


def test_substitute_field_history_skips_implicit_or_ambiguous_records():
    entries = [
        "&",
        "&&",
        "~",
        "s",
        "s g",
        "s//reused/g",
        "s/unfinished",
        "s/foo/bar/x",
        "s#other#different#g",
        "s/foo/explicit",
    ]
    rows = substitute_field_candidates(entries, ":s/foo/", len(":s/foo/"))
    assert [row.text for row in rows] == [":s/foo/explicit"]


def test_field_history_never_escapes_a_preserved_closing_delimiter():
    """An unfinished saved escape must not absorb the target field boundary."""
    entries = ["s/foo/bar\\", "s/foo/baz\\\\"]
    text = ":%s/foo/baOLD/g 2"
    rows = substitute_field_candidates(entries, text, len(":%s/foo/ba"))
    assert [row.text for row in rows] == [":%s/foo/baz\\\\/g 2"]
    assert [
        row.text for row in substitute_field_candidates(entries, ":s/foo/ba", 9)
    ] == [
        ":s/foo/baz\\\\",
        ":s/foo/bar\\",
    ]
    assert [
        row.text for row in substitute_field_candidates(entries, ":s/fo/keep/g", 5)
    ] == [":s/foo/keep/g"]


def test_substitute_field_history_reparses_only_when_history_changes(monkeypatch):
    import spyder_okvim.utils.commandline as commandline

    parse = commandline.parse_substitute
    calls = []

    def counted(body, *args):
        calls.append(body)
        return parse(body, *args)

    monkeypatch.setattr(commandline, "parse_substitute", counted)
    commandline._substitute_history_fields.cache_clear()
    entries = ["s/foo/bar/g"]
    substitute_field_candidates(entries, ":s/f", 4)
    substitute_field_candidates(entries, ":s/fo", 5)
    assert calls == ["/foo/bar/g"]
    entries.append("s/next/last/g")
    substitute_field_candidates(entries, ":s/", 3)
    assert calls == ["/foo/bar/g", "/next/last/g", "/foo/bar/g"]
