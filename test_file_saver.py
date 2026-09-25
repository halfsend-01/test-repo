"""Tests for the UTF-8-aware chunked file saver.

Covers the boundary conditions identified in the triage:
1. File of exactly 64KB ending with a 4-byte emoji
2. File of ~70KB with mixed ASCII and emoji
3. A 4-byte UTF-8 char starting at byte offset 65534 (straddles 64KB)
4. Round-trip: reload each saved file and assert content matches
"""

import os
import tempfile

from file_saver import (
    CHUNK_SIZE,
    _expected_sequence_length,
    _utf8_safe_boundary,
    save_file,
)


class TestExpectedSequenceLength:
    def test_ascii(self):
        assert _expected_sequence_length(ord("A")) == 1

    def test_two_byte(self):
        # Leading byte 110xxxxx  (e.g. 0xC3 for 'ã')
        assert _expected_sequence_length(0xC3) == 2

    def test_three_byte(self):
        # Leading byte 1110xxxx  (e.g. 0xE4 for CJK chars)
        assert _expected_sequence_length(0xE4) == 3

    def test_four_byte(self):
        # Leading byte 11110xxx  (e.g. 0xF0 for emoji)
        assert _expected_sequence_length(0xF0) == 4


class TestUtf8SafeBoundary:
    def test_ascii_boundary(self):
        data = b"Hello, world!"
        assert _utf8_safe_boundary(data, 5) == 5

    def test_boundary_at_continuation_byte(self):
        # 'é' is 0xC3 0xA9  (2-byte sequence).
        # Place boundary at the continuation byte.
        data = b"A" * 10 + b"\xc3\xa9" + b"B" * 10
        # Boundary at index 11 (the continuation byte 0xA9):
        assert _utf8_safe_boundary(data, 11) == 10

    def test_boundary_at_leading_byte(self):
        # Boundary right on a leading byte whose sequence fits.
        data = b"A" * 10 + b"\xc3\xa9" + b"B" * 10
        # Boundary at index 10 (the leading byte 0xC3): the 2-byte seq
        # fits within boundary+1, so 10 should be adjusted to 10 (start
        # of the sequence) because the full sequence (10,11) extends
        # past boundary=10.
        assert _utf8_safe_boundary(data, 10) == 10

    def test_four_byte_emoji_straddling(self):
        # '😀' is F0 9F 98 80 (4 bytes).
        emoji = "😀".encode("utf-8")
        assert len(emoji) == 4
        data = b"A" * 100 + emoji + b"B" * 100
        # Boundary inside the emoji (at the 2nd byte, index 101):
        assert _utf8_safe_boundary(data, 101) == 100
        # Boundary at the 3rd byte (index 102):
        assert _utf8_safe_boundary(data, 102) == 100
        # Boundary at the 4th byte (index 103):
        assert _utf8_safe_boundary(data, 103) == 100

    def test_boundary_past_data(self):
        data = b"Hello"
        assert _utf8_safe_boundary(data, 100) == 5


class TestSaveFile:
    def _round_trip(self, content: str) -> None:
        """Save *content* via save_file, reload, and assert equality."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            path = tmp.name
        try:
            save_file(path, content)
            with open(path, "r", encoding="utf-8") as fh:
                result = fh.read()
            assert result == content
        finally:
            os.unlink(path)

    def test_small_ascii_file(self):
        self._round_trip("Hello, world!\n")

    def test_exact_64kb_ending_with_emoji(self):
        """File of exactly 64KB (in UTF-8 bytes) ending with a 4-byte
        emoji."""
        emoji = "😀"  # 4 bytes in UTF-8
        padding_size = CHUNK_SIZE - len(emoji.encode("utf-8"))
        content = "A" * padding_size + emoji
        assert len(content.encode("utf-8")) == CHUNK_SIZE
        self._round_trip(content)

    def test_70kb_mixed_ascii_emoji(self):
        """File of ~70KB with mixed ASCII and emoji throughout."""
        # Build ~70KB of mixed content: 10 ASCII chars then 1 emoji,
        # repeated.
        unit = "ABCDEFGHIJ😀"
        repeats = (70 * 1024) // len(unit.encode("utf-8")) + 1
        content = unit * repeats
        assert len(content.encode("utf-8")) > 70 * 1024
        self._round_trip(content)

    def test_emoji_straddling_64kb_boundary(self):
        """A 4-byte UTF-8 char starting at byte offset 65534 straddles
        the 64KB boundary."""
        emoji = "😀"  # 4 bytes in UTF-8
        # Place the emoji so its first byte is at offset 65534.
        padding_size = CHUNK_SIZE - 2  # 65534
        content = "A" * padding_size + emoji + "B" * 1024
        encoded = content.encode("utf-8")
        # Verify the emoji starts at byte 65534.
        assert encoded[padding_size : padding_size + 4] == emoji.encode(
            "utf-8"
        )
        self._round_trip(content)

    def test_three_byte_cjk_straddling(self):
        """CJK character (3 bytes) straddling the chunk boundary."""
        cjk = "中"  # 3 bytes in UTF-8
        padding_size = CHUNK_SIZE - 1  # char starts 1 byte before edge
        content = "A" * padding_size + cjk + "B" * 512
        self._round_trip(content)

    def test_two_byte_char_straddling(self):
        """2-byte character straddling the chunk boundary."""
        char = "é"  # 2 bytes in UTF-8
        padding_size = CHUNK_SIZE - 1  # char starts 1 byte before edge
        content = "A" * padding_size + char + "B" * 512
        self._round_trip(content)

    def test_empty_file(self):
        self._round_trip("")

    def test_exactly_one_chunk(self):
        content = "X" * CHUNK_SIZE
        self._round_trip(content)

    def test_multiple_chunks_no_multibyte(self):
        content = "Y" * (CHUNK_SIZE * 3 + 100)
        self._round_trip(content)
