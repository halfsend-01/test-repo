"""File saving module with chunked I/O that handles UTF-8 correctly.

Writes files in 64KB chunks. Prior to v2.3.1, a bug caused segmentation
faults when multibyte UTF-8 characters straddled chunk boundaries because
the code split on byte offsets without checking whether a multibyte
sequence was in progress. This module fixes that by ensuring chunk
boundaries always fall on valid UTF-8 character boundaries.
"""

CHUNK_SIZE = 65536  # 64KB


def _find_safe_split(data: bytes, offset: int) -> int:
    """Find the largest split point <= offset that does not cut a multibyte
    UTF-8 sequence.

    UTF-8 continuation bytes have the bit pattern 10xxxxxx (0x80..0xBF).
    Walking backwards from *offset* until we land on a non-continuation
    byte gives us the start of the character that straddles the boundary.
    We split just before that character so neither chunk contains a
    partial sequence.
    """
    if offset >= len(data):
        return len(data)
    # Walk backwards past any continuation bytes (10xxxxxx).
    pos = offset
    while pos > 0 and (data[pos] & 0xC0) == 0x80:
        pos -= 1
    return pos


def save_file(path: str, content: str) -> None:
    """Save *content* to *path* in 64KB chunks, respecting UTF-8 boundaries.

    Encodes *content* to UTF-8 bytes, then writes in chunks of up to
    ``CHUNK_SIZE`` bytes, adjusting each boundary so that no multibyte
    character is split across chunks.
    """
    encoded = content.encode("utf-8")
    with open(path, "wb") as fh:
        offset = 0
        while offset < len(encoded):
            end = min(offset + CHUNK_SIZE, len(encoded))
            if end < len(encoded):
                end = _find_safe_split(encoded, end)
            fh.write(encoded[offset:end])
            offset = end


def load_file(path: str) -> str:
    """Read a file written by :func:`save_file` and return its text."""
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()
