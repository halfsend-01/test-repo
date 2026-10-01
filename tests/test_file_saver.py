"""Tests for file_saver module.

Covers the 64KB boundary with various encodings to verify the buffer
allocation fix for UTF-8 multibyte characters.
"""

import os
import tempfile

import pytest

from src.file_saver import BUFFER_SIZE, _byte_length, save_file


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestByteLength:
    """Tests for the _byte_length helper."""

    def test_ascii_string(self):
        assert _byte_length("hello") == 5

    def test_multibyte_string(self):
        # Each emoji is 4 bytes in UTF-8
        assert _byte_length("\U0001f600") == 4

    def test_bytes_input(self):
        assert _byte_length(b"hello") == 5

    def test_mixed_ascii_and_multibyte(self):
        # 'a' = 1 byte, emoji = 4 bytes
        text = "a\U0001f600"
        assert _byte_length(text) == 5

    def test_cjk_characters(self):
        # CJK characters are 3 bytes in UTF-8
        assert _byte_length("世界") == 6


class TestSaveFile:
    """Tests for the save_file function."""

    def test_save_small_ascii_file(self, tmp_dir):
        """Small ASCII file saves correctly."""
        path = os.path.join(tmp_dir, "small.txt")
        content = "Hello, world!"
        save_file(path, content)
        with open(path, "rb") as f:
            assert f.read() == content.encode("utf-8")

    def test_save_small_file_with_emoji(self, tmp_dir):
        """Small file with emoji saves correctly."""
        path = os.path.join(tmp_dir, "emoji.txt")
        content = "Hello \U0001f600\U0001f601\U0001f602!"
        save_file(path, content)
        with open(path, "rb") as f:
            assert f.read() == content.encode("utf-8")

    def test_save_under_64kb_with_emoji(self, tmp_dir):
        """File just under 64KB with emoji saves correctly."""
        path = os.path.join(tmp_dir, "under64k.txt")
        # ~63KB of emoji (each emoji is 4 bytes in UTF-8)
        emoji_count = (63 * 1024) // 4
        content = "\U0001f600" * emoji_count
        byte_len = len(content.encode("utf-8"))
        assert byte_len < BUFFER_SIZE
        save_file(path, content)
        with open(path, "rb") as f:
            assert f.read() == content.encode("utf-8")

    def test_save_over_64kb_with_emoji(self, tmp_dir):
        """File over 64KB with emoji saves correctly (the crash scenario)."""
        path = os.path.join(tmp_dir, "over64k_emoji.txt")
        # ~70KB of emoji characters
        emoji_count = (70 * 1024) // 4
        content = "\U0001f600" * emoji_count
        byte_len = len(content.encode("utf-8"))
        assert byte_len > BUFFER_SIZE
        save_file(path, content)
        with open(path, "rb") as f:
            assert f.read() == content.encode("utf-8")

    def test_save_over_64kb_mixed_ascii_and_multibyte(self, tmp_dir):
        """File over 64KB with mixed ASCII and multibyte saves correctly."""
        path = os.path.join(tmp_dir, "mixed.txt")
        # Mix ASCII and emoji to exceed 64KB
        chunk = "abcdef\U0001f600"  # 6 + 4 = 10 bytes
        repeat_count = (70 * 1024) // 10 + 1
        content = chunk * repeat_count
        byte_len = len(content.encode("utf-8"))
        assert byte_len > BUFFER_SIZE
        save_file(path, content)
        with open(path, "rb") as f:
            assert f.read() == content.encode("utf-8")

    def test_save_over_64kb_ascii_only(self, tmp_dir):
        """File over 64KB with ASCII-only content saves correctly."""
        path = os.path.join(tmp_dir, "ascii_large.txt")
        content = "A" * (70 * 1024)
        byte_len = len(content.encode("utf-8"))
        assert byte_len > BUFFER_SIZE
        save_file(path, content)
        with open(path, "rb") as f:
            assert f.read() == content.encode("utf-8")

    def test_save_over_64kb_cjk(self, tmp_dir):
        """File over 64KB with CJK characters saves correctly."""
        path = os.path.join(tmp_dir, "cjk.txt")
        # CJK chars are 3 bytes each in UTF-8
        char_count = (70 * 1024) // 3 + 1
        content = "世" * char_count
        byte_len = len(content.encode("utf-8"))
        assert byte_len > BUFFER_SIZE
        save_file(path, content)
        with open(path, "rb") as f:
            assert f.read() == content.encode("utf-8")

    def test_save_bytes_content(self, tmp_dir):
        """Bytes content saves correctly."""
        path = os.path.join(tmp_dir, "bytes.txt")
        content = b"raw bytes content"
        save_file(path, content)
        with open(path, "rb") as f:
            assert f.read() == content

    def test_save_empty_content(self, tmp_dir):
        """Empty content saves correctly."""
        path = os.path.join(tmp_dir, "empty.txt")
        save_file(path, "")
        with open(path, "rb") as f:
            assert f.read() == b""

    def test_save_invalid_type_raises(self, tmp_dir):
        """Non-string/bytes content raises TypeError."""
        path = os.path.join(tmp_dir, "invalid.txt")
        with pytest.raises(TypeError, match="content must be str or bytes"):
            save_file(path, 12345)

    def test_atomic_write_no_partial_file_on_error(self, tmp_dir):
        """Failed writes do not leave partial files at the target path."""
        path = os.path.join(tmp_dir, "noexist", "sub", "file.txt")
        with pytest.raises(OSError):
            save_file(path, "content")
        assert not os.path.exists(path)
