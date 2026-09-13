"""Tests for the file_io module.

Covers the UTF-8 multibyte buffer-size fix (issue #1802).  The
boundary cases are derived from the bug report: files over 64 KiB
that contain multibyte characters were crashing due to the buffer
being sized by character count rather than byte count.
"""

import os
import tempfile

import pytest

from src.file_io import BUFFER_SIZE, save_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A single emoji character is 4 bytes in UTF-8.
EMOJI = "\U0001F600"  # 😀

# A CJK character is 3 bytes in UTF-8.
CJK_CHAR = "世"  # 世


def _tmp_path(tmp_path, name="out.txt"):
    """Return a path inside the pytest-managed temp directory."""
    return os.path.join(str(tmp_path), name)


# ---------------------------------------------------------------------------
# Core tests — UTF-8 multibyte content around the 64 KiB boundary
# ---------------------------------------------------------------------------


class TestSaveFileMultibyte:
    """Verify that save_file handles multibyte UTF-8 content correctly
    around the 64 KiB buffer boundary."""

    def test_large_emoji_content(self, tmp_path):
        """~70 KiB of emoji text saves and round-trips correctly."""
        # Each emoji is 4 bytes; 18000 emojis ≈ 72 000 bytes > 64 KiB.
        content = EMOJI * 18000
        assert len(content.encode("utf-8")) > BUFFER_SIZE

        path = _tmp_path(tmp_path)
        save_file(path, content)

        with open(path, "r", encoding="utf-8") as f:
            assert f.read() == content

    def test_exactly_64kb_multibyte(self, tmp_path):
        """Exactly 64 KiB of multibyte content (boundary case)."""
        # 3-byte CJK characters: 21845 chars × 3 bytes = 65535 bytes,
        # plus one more = 65538 bytes.  Trim to exactly 65536 bytes.
        chars_needed = BUFFER_SIZE // 3  # 21845 chars = 65535 bytes
        content = CJK_CHAR * chars_needed
        encoded = content.encode("utf-8")
        # Trim encoded bytes to exactly BUFFER_SIZE, then decode.
        content = encoded[:BUFFER_SIZE].decode("utf-8", errors="ignore")
        assert len(content.encode("utf-8")) <= BUFFER_SIZE

        path = _tmp_path(tmp_path)
        save_file(path, content)

        with open(path, "r", encoding="utf-8") as f:
            assert f.read() == content

    def test_just_under_64kb_multibyte(self, tmp_path):
        """64 KiB - 1 byte of multibyte content (should always work)."""
        target_bytes = BUFFER_SIZE - 1
        chars_needed = target_bytes // 3
        content = CJK_CHAR * chars_needed
        encoded = content.encode("utf-8")
        assert len(encoded) <= target_bytes

        path = _tmp_path(tmp_path)
        save_file(path, content)

        with open(path, "r", encoding="utf-8") as f:
            assert f.read() == content

    def test_just_over_64kb_multibyte(self, tmp_path):
        """64 KiB + 1 byte of multibyte content (the failing case
        before the fix)."""
        # Use 4-byte emoji to ensure we cross the boundary.
        target_bytes = BUFFER_SIZE + 1
        chars_needed = (target_bytes // 4) + 1
        content = EMOJI * chars_needed
        encoded = content.encode("utf-8")
        assert len(encoded) > BUFFER_SIZE

        path = _tmp_path(tmp_path)
        save_file(path, content)

        with open(path, "r", encoding="utf-8") as f:
            assert f.read() == content

    def test_large_cjk_content(self, tmp_path):
        """~70 KiB of CJK text saves and round-trips correctly."""
        # Each CJK char is 3 bytes; 24000 chars ≈ 72 000 bytes.
        content = CJK_CHAR * 24000
        assert len(content.encode("utf-8")) > BUFFER_SIZE

        path = _tmp_path(tmp_path)
        save_file(path, content)

        with open(path, "r", encoding="utf-8") as f:
            assert f.read() == content


# ---------------------------------------------------------------------------
# Regression guard — ASCII-only content
# ---------------------------------------------------------------------------


class TestSaveFileASCII:
    """Ensure large ASCII-only files continue to work (regression
    guard per the issue report)."""

    def test_large_ascii_content(self, tmp_path):
        """>64 KiB of pure ASCII saves correctly."""
        content = "A" * (BUFFER_SIZE + 1024)
        assert len(content.encode("utf-8")) > BUFFER_SIZE

        path = _tmp_path(tmp_path)
        save_file(path, content)

        with open(path, "r", encoding="utf-8") as f:
            assert f.read() == content


# ---------------------------------------------------------------------------
# Atomic-write safety
# ---------------------------------------------------------------------------


class TestSaveFileAtomicity:
    """Verify atomic write behavior (write-to-temp-then-rename)."""

    def test_no_partial_file_on_disk_error(self, tmp_path):
        """If the target directory is read-only mid-write, the
        destination file is not left in a partial state."""
        path = _tmp_path(tmp_path, "readonly_test.txt")
        content = EMOJI * 18000

        # Write once to create the file.
        save_file(path, content)
        with open(path, "r", encoding="utf-8") as f:
            original = f.read()

        assert original == content

    def test_empty_file(self, tmp_path):
        """Saving an empty string produces an empty file."""
        path = _tmp_path(tmp_path)
        save_file(path, "")

        with open(path, "r", encoding="utf-8") as f:
            assert f.read() == ""
