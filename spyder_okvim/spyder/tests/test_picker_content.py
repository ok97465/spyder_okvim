"""Shared content keeps metadata, UTF-16 coordinates and previews consistent."""

from unittest.mock import patch

import pytest

from spyder_okvim.spyder.picker_preview import (
    ContentService,
    MAX_PREVIEW_CHARS,
    MAX_READ_BYTES,
    from_text,
    locate,
    preview,
)
from spyder_okvim.utils.picker import PickerTarget


def test_utf16_after_emoji_and_normalized_newlines(tmp_path):
    path = tmp_path / "emoji.py"
    path.write_bytes("one\r\na😀b\r\nlast".encode())
    content = ContentService().read(str(path))
    # "one\n" = 4 UTF-16 units; a + emoji = 3 more units.
    location = locate(content, PickerTarget(str(path), offset_utf16=7))
    assert (location.line_number, location.column_number, location.text) == (
        2,
        4,
        "a😀b",
    )
    marked = locate(content, PickerTarget(str(path), block_number=1, column_utf16=3))
    assert marked == location


def test_metadata_and_preview_share_one_disk_read(tmp_path):
    path = tmp_path / "marks.py"
    path.write_text("first\nsecond\nthird")
    service = ContentService()
    with patch("builtins.open", wraps=open) as reader:
        first = service.read(str(path))
        assert locate(first, PickerTarget(str(path), block_number=1)).text == "second"
        second = service.read(str(path))
        assert preview(second, PickerTarget(str(path), block_number=2)).target_line == 3
        assert reader.call_count == 1
    assert first is second


def test_disk_version_and_live_document_override(tmp_path):
    path = tmp_path / "changed.py"
    path.write_text("before")
    service = ContentService()
    before = service.read(str(path))
    path.write_text("after, different size")
    after = service.read(str(path))
    assert before.identity != after.identity
    assert after.text == "after, different size"
    live = from_text("unsaved", ("document", 3))
    assert preview(live, PickerTarget(str(path))).text == "unsaved"
    assert service.read(str(path)).text == after.text


def test_binary_missing_and_legacy_encoding(tmp_path):
    service = ContentService()
    binary = tmp_path / "binary"
    binary.write_bytes(b"data\x00hidden")
    assert "Binary" in service.read(str(binary)).message
    assert service.read(str(tmp_path / "missing")).message
    legacy = tmp_path / "legacy.py"
    legacy.write_bytes(b"# coding: cp1252\ncaf\xe9\n")
    assert service.read(str(legacy)).text.endswith("café\n")


def test_read_limit_never_guesses_unreachable_coordinates(tmp_path):
    path = tmp_path / "large.py"
    path.write_bytes(b"a\n" * (MAX_READ_BYTES // 2 + 20))
    content = ContentService().read(str(path))
    assert not content.complete
    far = PickerTarget(str(path), offset_utf16=MAX_READ_BYTES + 10)
    assert locate(content, far).line_number is None
    result = preview(content, far)
    assert result.text == ""
    assert "limited" in result.message
    assert locate(content, PickerTarget(str(path), block_number=1)).line_number == 2


def test_long_line_has_separate_display_limit_and_exact_target():
    content = from_text("head\n" + "x" * (MAX_PREVIEW_CHARS + 1000) + "\ntail")
    target = PickerTarget("long.py", block_number=1, column_utf16=200_010)
    assert locate(content, target).column_number == 200_011
    result = preview(content, target)
    assert result.target_line == 2
    assert result.first_line == 2
    assert len(result.text) <= MAX_PREVIEW_CHARS
    assert "display limit" in result.message


def test_lru_memory_bound_and_explicit_refresh(tmp_path):
    service = ContentService(max_cache_bytes=1024)
    for i in range(8):
        path = tmp_path / str(i)
        path.write_text("word" * 40)
        service.read(str(path))
        assert service.cache_bytes <= 1024
    assert service.cache_bytes > 0
    service.clear()
    assert service.cache_bytes == 0


def test_unstable_read_is_not_cached(tmp_path):
    path = tmp_path / "unstable"
    path.write_text("hello")
    service = ContentService()
    with patch(
        "spyder_okvim.spyder.picker_preview._disk_identity", side_effect=[(1,), (2,)]
    ):
        assert "changed" in service.read(str(path)).message
    assert service.cache_bytes == 0


def test_partial_open_document_never_claims_last_line_is_complete():
    content = from_text("first\npartial", ("doc", 1), complete=False)
    assert locate(content, PickerTarget("live.py", block_number=1)).line_number is None
    assert locate(content, PickerTarget("live.py", block_number=0)).line_number == 1


@pytest.mark.parametrize("text", ["a😀b\n😀😀x\nend", "😀\n\n😀e", "x\n😀😀\nx😀z"])
def test_utf16_index_matches_reference_at_every_offset(text):
    content = from_text(text)
    units = len(text.encode("utf-16-le")) // 2
    for offset in range(units + 1):
        position = len(
            text.encode("utf-16-le")[: offset * 2].decode("utf-16-le", errors="ignore")
        )
        line_start = text.rfind("\n", 0, position) + 1
        expected_line = text.count("\n", 0, position) + 1
        expected_column = len(text[line_start:position].encode("utf-16-le")) // 2 + 1
        metadata = locate(content, PickerTarget("emoji.py", offset_utf16=offset))
        assert (metadata.line_number, metadata.column_number) == (
            expected_line,
            expected_column,
        )


@pytest.mark.parametrize("block, length", [(0, 4), (1, 2), (2, 0), (3, 5)])
def test_block_column_validates_utf16_length_after_preceding_astral_text(block, length):
    content = from_text("a😀b\n😀\n\n😀😀x")
    at_end = locate(
        content, PickerTarget("emoji.py", block_number=block, column_utf16=length)
    )
    assert (at_end.line_number, at_end.column_number) == (block + 1, length + 1)
    beyond = locate(
        content, PickerTarget("emoji.py", block_number=block, column_utf16=length + 1)
    )
    assert beyond.line_number == block + 1
    assert beyond.column_number is None
    assert beyond.message == "Column no longer exists"
