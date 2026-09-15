"""Tests for the UTF-8-aware chunked file saver."""

import os
import tempfile

import pytest

from src.file_saver import (
    DEFAULT_CHUNK_SIZE,
    _find_utf8_safe_split,
    load_file,
    save_file,
)


@pytest.fixture
def tmp_path_file(tmp_path):
    """Return a path for a temporary file inside tmp_path."""
    return str(tmp_path / "output.txt")


class TestFindUtf8SafeSplit:
    """Tests for _find_utf8_safe_split."""

    def test_ascii_only(self):
        data = b"Hello, world!"
        assert _find_utf8_safe_split(data, 5) == 5

    def test_split_before_two_byte_char(self):
        # 'é' is 0xC3 0xA9 (2 bytes)
        data = b"abc\xc3\xa9def"
        # Splitting at 4 lands on the continuation byte 0xA9;
        # should back up to 3 (before the lead byte).
        assert _find_utf8_safe_split(data, 4) == 3

    def test_split_at_two_byte_char_start(self):
        data = b"abc\xc3\xa9def"
        # Splitting at 3 lands on the lead byte 0xC3 — that's safe.
        assert _find_utf8_safe_split(data, 3) == 3

    def test_split_after_two_byte_char(self):
        data = b"abc\xc3\xa9def"
        # Splitting at 5 lands on 'd' — safe.
        assert _find_utf8_safe_split(data, 5) == 5

    def test_split_inside_three_byte_char(self):
        # '€' is 0xE2 0x82 0xAC (3 bytes)
        data = b"ab\xe2\x82\xaccd"
        # Splitting at 3 lands on continuation 0x82 → back up to 2.
        assert _find_utf8_safe_split(data, 3) == 2
        # Splitting at 4 lands on continuation 0xAC → back up to 2.
        assert _find_utf8_safe_split(data, 4) == 2

    def test_split_inside_four_byte_char(self):
        # '😀' (U+1F600) is 0xF0 0x9F 0x98 0x80 (4 bytes)
        data = b"a\xf0\x9f\x98\x80b"
        # Splitting at 2 lands on 0x9F → back up to 1.
        assert _find_utf8_safe_split(data, 2) == 1
        # Splitting at 3 lands on 0x98 → back up to 1.
        assert _find_utf8_safe_split(data, 3) == 1
        # Splitting at 4 lands on 0x80 → back up to 1.
        assert _find_utf8_safe_split(data, 4) == 1

    def test_max_size_exceeds_data_length(self):
        data = b"short"
        assert _find_utf8_safe_split(data, 100) == 5

    def test_max_size_equals_data_length(self):
        data = b"exact"
        assert _find_utf8_safe_split(data, 5) == 5


class TestSaveFile:
    """Tests for save_file."""

    def test_save_ascii_small_file(self, tmp_path_file):
        content = "Hello, world!"
        save_file(content, tmp_path_file)
        assert load_file(tmp_path_file) == content

    def test_save_ascii_file_larger_than_chunk(self, tmp_path_file):
        # Use a small chunk size to exercise chunked writing.
        content = "A" * 200
        save_file(content, tmp_path_file, chunk_size=64)
        assert load_file(tmp_path_file) == content

    def test_save_utf8_file_under_64kb(self, tmp_path_file):
        content = "Hello 🌍🌎🌏 World!"
        save_file(content, tmp_path_file)
        assert load_file(tmp_path_file) == content

    def test_save_utf8_file_over_64kb_with_emoji(self, tmp_path_file):
        """Core regression test: >64KB file with emoji should save
        without corruption."""
        # Build a ~70KB string with emoji characters
        # '😀' is 4 bytes in UTF-8; mix with ASCII to cross the 64KB
        # boundary at various offsets.
        base = "Hello 😀 World! "  # 18 chars, variable bytes
        repetitions = (70 * 1024) // len(base.encode("utf-8")) + 1
        content = base * repetitions
        assert len(content.encode("utf-8")) > DEFAULT_CHUNK_SIZE

        save_file(content, tmp_path_file)
        result = load_file(tmp_path_file)
        assert result == content

    def test_save_utf8_file_over_64kb_with_cjk(self, tmp_path_file):
        """CJK characters (3-byte UTF-8) crossing the 64KB boundary."""
        # '中' is 3 bytes in UTF-8.
        base = "中文测试数据 "
        repetitions = (70 * 1024) // len(base.encode("utf-8")) + 1
        content = base * repetitions
        assert len(content.encode("utf-8")) > DEFAULT_CHUNK_SIZE

        save_file(content, tmp_path_file)
        result = load_file(tmp_path_file)
        assert result == content

    def test_save_entirely_multibyte_over_64kb(self, tmp_path_file):
        """File consisting entirely of 4-byte emoji over 64KB."""
        emoji = "😀"
        repetitions = (70 * 1024) // len(emoji.encode("utf-8")) + 1
        content = emoji * repetitions
        assert len(content.encode("utf-8")) > DEFAULT_CHUNK_SIZE

        save_file(content, tmp_path_file)
        result = load_file(tmp_path_file)
        assert result == content

    def test_multibyte_char_at_exact_boundary(self, tmp_path_file):
        """4-byte emoji placed so it straddles bytes 65534-65538."""
        # Fill up to byte 65534 with ASCII, then place a 4-byte char.
        padding = "A" * 65534
        boundary_char = "😀"  # 4 bytes: straddles 65534-65537
        trailing = "B" * 100
        content = padding + boundary_char + trailing

        encoded = content.encode("utf-8")
        # Verify the emoji straddles the 64KB boundary.
        assert encoded[65534:65538] == boundary_char.encode("utf-8")

        save_file(content, tmp_path_file)
        result = load_file(tmp_path_file)
        assert result == content

    def test_small_chunk_size_with_multibyte(self, tmp_path_file):
        """Exercise boundary handling with a very small chunk size."""
        content = "Hello 😀🎉🌍 World 中文 Test"
        save_file(content, tmp_path_file, chunk_size=8)
        result = load_file(tmp_path_file)
        assert result == content

    def test_empty_file(self, tmp_path_file):
        save_file("", tmp_path_file)
        assert load_file(tmp_path_file) == ""

    def test_no_temp_file_on_success(self, tmp_path_file):
        save_file("test", tmp_path_file)
        assert not os.path.exists(tmp_path_file + ".tmp")

    def test_no_temp_file_on_failure(self, tmp_path):
        bad_path = str(tmp_path / "nonexistent_dir" / "file.txt")
        with pytest.raises(OSError):
            save_file("test", bad_path)
        assert not os.path.exists(bad_path + ".tmp")


class TestLoadFile:
    """Tests for load_file."""

    def test_load_utf8_file(self, tmp_path_file):
        content = "Hello 🌍 World!"
        save_file(content, tmp_path_file)
        assert load_file(tmp_path_file) == content

    def test_load_nonexistent_file(self):
        with pytest.raises(OSError):
            load_file("/nonexistent/path/file.txt")
