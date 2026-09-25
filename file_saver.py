"""File saver with UTF-8-aware chunked writing.

Fixes a segfault that occurred when saving files larger than 64KB
containing UTF-8 multibyte characters. The bug was caused by splitting
the byte stream at a fixed 64KB boundary without checking whether a
multibyte UTF-8 sequence straddled the split point.

The fix ensures chunk boundaries never fall in the middle of a
multibyte UTF-8 sequence by adjusting the split point backward to the
start of any incomplete character at the buffer edge.
"""

CHUNK_SIZE = 65536  # 64KB


def _utf8_safe_boundary(data: bytes, boundary: int) -> int:
    """Return the largest offset <= *boundary* that does not split a
    multibyte UTF-8 sequence.

    UTF-8 continuation bytes have the bit pattern 10xxxxxx (0x80..0xBF).
    If the byte at *boundary* is a continuation byte we walk backward
    (at most 3 bytes — the maximum number of continuation bytes in a
    valid UTF-8 sequence) to find the leading byte of the sequence,
    then place the split just before it.
    """
    if boundary >= len(data):
        return len(data)

    # Walk back at most 3 bytes to find a non-continuation byte.
    # A 4-byte UTF-8 sequence has up to 3 continuation bytes, so we
    # must check offsets 0 through 3 (4 positions total).
    for offset in range(min(4, boundary + 1)):
        idx = boundary - offset
        byte = data[idx]
        # A byte that is NOT a continuation byte (10xxxxxx) is either
        # ASCII (0xxxxxxx) or a leading byte (11xxxxxx).
        if (byte & 0xC0) != 0x80:
            # If this leading byte starts a sequence that extends past
            # *boundary*, move the split before this byte.
            seq_len = _expected_sequence_length(byte)
            if idx + seq_len > boundary:
                return idx
            return boundary

    # Fallback: should not happen in valid UTF-8.  Return the original
    # boundary to avoid an infinite loop.
    return boundary


def _expected_sequence_length(leading_byte: int) -> int:
    """Return the expected byte length of a UTF-8 character given its
    leading byte."""
    if (leading_byte & 0x80) == 0:
        return 1  # 0xxxxxxx — ASCII
    if (leading_byte & 0xE0) == 0xC0:
        return 2  # 110xxxxx
    if (leading_byte & 0xF0) == 0xE0:
        return 3  # 1110xxxx
    if (leading_byte & 0xF8) == 0xF0:
        return 4  # 11110xxx
    return 1  # Invalid leading byte; treat as single byte.


def save_file(path: str, content: str) -> None:
    """Write *content* to *path* using chunked UTF-8 writes.

    Splits the encoded byte stream into chunks of up to ``CHUNK_SIZE``
    bytes, adjusting each split so that no multibyte UTF-8 sequence is
    broken across chunks.
    """
    data = content.encode("utf-8")

    with open(path, "wb") as fh:
        offset = 0
        while offset < len(data):
            end = min(offset + CHUNK_SIZE, len(data))
            if end < len(data):
                end = _utf8_safe_boundary(data, end)
            fh.write(data[offset:end])
            offset = end
