"""Tests for src.filesaver — UTF-8-safe chunked file saving."""

import os
import tempfile

from src.filesaver import CHUNK_SIZE, _find_safe_split, save_file


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _load_file(path: str) -> str:
    """Read a file written by save_file and return its text."""
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _roundtrip(content: str) -> str:
    """Save content to a temp file and read it back."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        path = tmp.name
    try:
        save_file(path, content)
        return _load_file(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Unit tests for _find_safe_split
# ---------------------------------------------------------------------------

class TestFindSafeSplit:
    def test_ascii_split(self):
        """Split mid-ASCII always returns the requested offset."""
        data = b"hello world"
        assert _find_safe_split(data, 5) == 5  # mid-ASCII is always safe

    def test_split_before_two_byte_char(self):
        """Split inside a 2-byte character backs up to its start."""
        # 'é' is 0xC3 0xA9 (2 bytes). Splitting between them must back up.
        data = "aaaébbb".encode("utf-8")  # b'aaa\xc3\xa9bbb'
        # offset 4 lands on 0xA9 (continuation) → back up to 3
        assert _find_safe_split(data, 4) == 3

    def test_split_before_four_byte_char(self):
        """Split inside a 4-byte emoji backs up to its start."""
        # '😀' (U+1F600) is 4 bytes: F0 9F 98 80
        data = ("a" * 10 + "😀" + "b" * 10).encode("utf-8")
        # The emoji starts at byte 10. Splitting at byte 12 (mid-emoji)
        # must back up to byte 10.
        assert _find_safe_split(data, 12) == 10

    def test_split_before_three_byte_char(self):
        """Split inside a 3-byte CJK character backs up to its start."""
        # '日' (U+65E5) is 3 bytes: E6 97 A5
        data = ("aaa" + "日" + "bbb").encode("utf-8")  # b'aaa\xe6\x97\xa5bbb'
        # offset 4 lands on 0x97 (continuation) → back up to 3
        assert _find_safe_split(data, 4) == 3
        # offset 5 lands on 0xA5 (continuation) → back up to 3
        assert _find_safe_split(data, 5) == 3

    def test_split_at_end(self):
        """Offset past the end returns the data length."""
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

    def test_empty_string(self):
        """Round-trip an empty string through save_file and load."""
        assert _roundtrip("") == ""

    def test_no_progress_raises_value_error(self):
        """ValueError is raised when chunk size prevents forward progress."""
        import src.filesaver as mod
        original = mod.CHUNK_SIZE
        mod.CHUNK_SIZE = 1
        try:
            save_file("/tmp/test_noprog.txt", "é")
            assert False, "Expected ValueError was not raised"
        except ValueError as exc:
            assert "No progress" in str(exc)
        finally:
            mod.CHUNK_SIZE = original
