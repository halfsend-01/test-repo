"""Tests for src.filesaver — UTF-8-safe chunked file saving."""

import os
import tempfile

import pytest

from src.filesaver import CHUNK_SIZE, _find_safe_split, load_file, save_file


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _roundtrip(content: str) -> str:
    """Save *content* to a temp file and read it back."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        path = tmp.name
    try:
        save_file(path, content)
        return load_file(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Unit tests for _find_safe_split
# ---------------------------------------------------------------------------

class TestFindSafeSplit:
    def test_ascii_split(self):
        data = b"hello world"
        assert _find_safe_split(data, 5) == 5  # mid-ASCII is always safe

    def test_split_before_two_byte_char(self):
        # 'é' is 0xC3 0xA9 (2 bytes). Splitting between them must back up.
        data = "aaaébbb".encode("utf-8")  # b'aaa\xc3\xa9bbb'
        # offset 4 lands on 0xA9 (continuation) → back up to 3
        assert _find_safe_split(data, 4) == 3

    def test_split_before_four_byte_char(self):
        # '😀' (U+1F600) is 4 bytes: F0 9F 98 80
        data = ("a" * 10 + "😀" + "b" * 10).encode("utf-8")
        # The emoji starts at byte 10. Splitting at byte 12 (mid-emoji)
        # must back up to byte 10.
        assert _find_safe_split(data, 12) == 10

    def test_split_at_end(self):
        data = b"abc"
        assert _find_safe_split(data, 10) == 3  # past the end


# ---------------------------------------------------------------------------
# Integration tests — reproduce the reported bug scenarios
# ---------------------------------------------------------------------------

class TestSaveFileUTF8:
    def test_small_file_with_emoji(self):
        """File under 64KB with emoji — should always work."""
        content = "Hello 😀 " * 1000  # well under 64KB
        assert _roundtrip(content) == content

    def test_large_file_with_emoji(self):
        """File over 64KB with emoji — the crash scenario from #2480."""
        # ~70KB of emoji-containing text
        content = "Hello 😀🎉 World! " * 5000
        assert len(content.encode("utf-8")) > CHUNK_SIZE
        assert _roundtrip(content) == content

    def test_large_ascii_file(self):
        """File over 64KB with only ASCII — should work (control case)."""
        content = "x" * (CHUNK_SIZE + 1024)
        assert _roundtrip(content) == content

    def test_emoji_at_exact_boundary(self):
        """Place a 4-byte emoji exactly at the 64KB byte offset."""
        # Fill up to exactly CHUNK_SIZE - 1 bytes with ASCII, then a
        # 4-byte emoji so the emoji straddles the boundary.
        padding = "a" * (CHUNK_SIZE - 1)
        content = padding + "😀" + "b" * 100
        encoded = content.encode("utf-8")
        # Emoji starts at byte 65535, ends at byte 65538 — straddles
        # the naive 65536 boundary.
        assert encoded[CHUNK_SIZE - 1] == 0xF0  # start of emoji
        assert _roundtrip(content) == content

    def test_mixed_ascii_multibyte_large(self):
        """Large file with mixed ASCII and multibyte characters."""
        segments = []
        for i in range(4000):
            segments.append(f"Line {i}: café résumé naïve 日本語 中文 🚀\n")
        content = "".join(segments)
        assert len(content.encode("utf-8")) > CHUNK_SIZE
        assert _roundtrip(content) == content

    def test_roundtrip_preserves_content(self):
        """Verify round-trip: saved content matches original."""
        content = "🎵 Music 🎶 " * 8000
        assert _roundtrip(content) == content
