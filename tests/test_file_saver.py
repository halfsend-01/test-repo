"""Tests for file_saver module.

Covers the 64KB boundary with mixed encodings to verify the buffer
allocation fix for UTF-8 multibyte characters.
"""

import os
import tempfile

import pytest

from src.file_saver import BUFFER_SIZE, _byte_length, save_file


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory, cleaned up after each test."""
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

    def test_mixed_characters(self):
        # 'a' = 1 byte, 'é' = 2 bytes, '世' = 3 bytes, emoji = 4 bytes
        text = "aé世\U0001f600"
        assert _byte_length(text) == 1 + 2 + 3 + 4


class TestSaveFile:
    """Tests for save_file covering the 64KB boundary with mixed encodings."""

    def test_save_ascii_under_64kb(self, tmp_dir):
        """Small ASCII file saves correctly."""
        filepath = os.path.join(tmp_dir, "small.txt")
        content = "Hello, world!"
        save_file(filepath, content)
        with open(filepath, "rb") as f:
            assert f.read() == content.encode("utf-8")

    def test_save_ascii_over_64kb(self, tmp_dir):
        """ASCII-only text exceeding 64KB saves correctly."""
        filepath = os.path.join(tmp_dir, "large_ascii.txt")
        content = "A" * (BUFFER_SIZE + 1024)  # ~65KB + 1KB
        save_file(filepath, content)
        with open(filepath, "rb") as f:
            result = f.read()
        assert result == content.encode("utf-8")
        assert len(result) > BUFFER_SIZE

    def test_save_multibyte_over_64kb(self, tmp_dir):
        """Text with multibyte chars whose byte representation exceeds 64KB.

        This is the core regression test: character count < 64K but byte
        length > 64K due to multibyte UTF-8 encoding.
        """
        filepath = os.path.join(tmp_dir, "large_multibyte.txt")
        # Each emoji is 4 bytes; 20000 emoji = 80KB in bytes but only 20K chars
        content = "\U0001f600" * 20000
        assert len(content) == 20000  # character count
        assert len(content.encode("utf-8")) == 80000  # byte count > 64KB
        save_file(filepath, content)
        with open(filepath, "rb") as f:
            result = f.read()
        assert result == content.encode("utf-8")
        assert len(result) == 80000

    def test_save_emoji_at_64kb_boundary(self, tmp_dir):
        """Exactly 64KB of 4-byte emoji characters (~16K characters).

        Boundary case where byte length equals BUFFER_SIZE exactly.
        """
        filepath = os.path.join(tmp_dir, "boundary_emoji.txt")
        num_chars = BUFFER_SIZE // 4  # 16384 emoji = exactly 65536 bytes
        content = "\U0001f600" * num_chars
        assert len(content.encode("utf-8")) == BUFFER_SIZE
        save_file(filepath, content)
        with open(filepath, "rb") as f:
            result = f.read()
        assert result == content.encode("utf-8")

    def test_save_mixed_encoding_over_64kb(self, tmp_dir):
        """Mixed ASCII and multibyte content exceeding 64KB."""
        filepath = os.path.join(tmp_dir, "mixed.txt")
        # Mix of ASCII (1 byte), accented chars (2 bytes), CJK (3 bytes),
        # and emoji (4 bytes) totaling over 64KB in byte length
        segment = "Hello éè 世界 \U0001f600\U0001f389 "
        segment_bytes = len(segment.encode("utf-8"))
        repeats = (BUFFER_SIZE // segment_bytes) + 100
        content = segment * repeats
        assert len(content.encode("utf-8")) > BUFFER_SIZE
        save_file(filepath, content)
        with open(filepath, "rb") as f:
            result = f.read()
        assert result == content.encode("utf-8")

    def test_save_cjk_over_64kb(self, tmp_dir):
        """CJK characters (3 bytes each) exceeding 64KB."""
        filepath = os.path.join(tmp_dir, "cjk.txt")
        # 25000 CJK chars = 75KB in bytes
        content = "世" * 25000
        assert len(content.encode("utf-8")) == 75000
        save_file(filepath, content)
        with open(filepath, "rb") as f:
            result = f.read()
        assert result == content.encode("utf-8")

    def test_save_bytes_input(self, tmp_dir):
        """Bytes input is written directly."""
        filepath = os.path.join(tmp_dir, "raw.bin")
        content = b"\xff\xfe" * 40000  # 80KB of raw bytes
        save_file(filepath, content)
        with open(filepath, "rb") as f:
            assert f.read() == content

    def test_save_invalid_type_raises(self, tmp_dir):
        """Non-string, non-bytes content raises TypeError."""
        filepath = os.path.join(tmp_dir, "bad.txt")
        with pytest.raises(TypeError):
            save_file(filepath, 12345)

    def test_save_empty_content(self, tmp_dir):
        """Empty string saves as an empty file."""
        filepath = os.path.join(tmp_dir, "empty.txt")
        save_file(filepath, "")
        with open(filepath, "rb") as f:
            assert f.read() == b""

    def test_content_roundtrip_integrity(self, tmp_dir):
        """Content read back matches what was written (no corruption)."""
        filepath = os.path.join(tmp_dir, "roundtrip.txt")
        # Build content with every UTF-8 byte width at >64KB total
        parts = []
        parts.append("ASCII " * 5000)  # 1-byte chars
        parts.append("éèê" * 3000)  # 2-byte chars
        parts.append("世界人" * 2000)  # 3-byte chars
        parts.append("\U0001f600\U0001f389\U0001f680" * 1500)  # 4-byte chars
        content = "".join(parts)
        assert len(content.encode("utf-8")) > BUFFER_SIZE
        save_file(filepath, content)
        with open(filepath, "r", encoding="utf-8") as f:
            assert f.read() == content
