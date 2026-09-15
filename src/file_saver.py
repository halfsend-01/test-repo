"""File saving module with UTF-8-aware chunked writing.

Provides a chunked file writer that respects UTF-8 character boundaries
when splitting data into fixed-size chunks, preventing corruption of
multibyte characters that straddle chunk boundaries.
"""

# Default chunk size: 64KB
DEFAULT_CHUNK_SIZE = 65536


def _find_utf8_safe_split(data: bytes, max_size: int) -> int:
    """Find the largest split point <= max_size that does not break a
    UTF-8 multibyte character.

    UTF-8 encoding rules:
      - Single-byte chars: 0xxxxxxx (0x00-0x7F)
      - Continuation bytes: 10xxxxxx (0x80-0xBF)
      - 2-byte lead:       110xxxxx (0xC0-0xDF)
      - 3-byte lead:       1110xxxx (0xE0-0xEF)
      - 4-byte lead:       11110xxx (0xF0-0xF7)

    A safe split point is one where the byte at that index is NOT a
    continuation byte (i.e., it starts a new character or is a
    single-byte character).

    Args:
        data: The raw UTF-8 encoded bytes.
        max_size: Maximum number of bytes for the first chunk.

    Returns:
        The largest index <= max_size that does not split a multibyte
        character.
    """
    if max_size >= len(data):
        return len(data)

    # Walk backward from max_size to find a byte that is not a
    # continuation byte (0x80-0xBF). That byte is the start of a
    # character, so splitting before it is safe.
    pos = max_size
    while pos > 0 and (data[pos] & 0xC0) == 0x80:
        pos -= 1

    return pos


def save_file(content: str, path: str) -> None:
    """Save string content to a file using chunked writes that respect
    UTF-8 character boundaries.

    Args:
        content: The text content to save.
        path: Destination file path.

    Raises:
        OSError: If the file cannot be written.
    """
    data = content.encode("utf-8")

    with open(path, "wb") as f:
        offset = 0
        while offset < len(data):
            remaining = len(data) - offset
            if remaining <= DEFAULT_CHUNK_SIZE:
                f.write(data[offset:])
                break

            split = _find_utf8_safe_split(
                data, offset + DEFAULT_CHUNK_SIZE
            ) - offset
            # Defensive: if split is zero (extremely unlikely with
            # valid UTF-8), advance by one full character width
            # based on the lead byte to avoid an infinite loop.
            if split <= 0:
                lead = data[offset]
                if lead < 0x80:
                    split = 1
                elif lead < 0xE0:
                    split = 2
                elif lead < 0xF0:
                    split = 3
                else:
                    split = 4
                split = min(split, remaining)

            f.write(data[offset:offset + split])
            offset += split
