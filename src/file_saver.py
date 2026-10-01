"""File saving module with correct UTF-8 buffer allocation.

This module provides file saving functionality that correctly handles
UTF-8 multibyte characters by sizing I/O buffers based on byte length
rather than character count.
"""

import os
import tempfile

# Default buffer size: 64KB
BUFFER_SIZE = 65536


def _byte_length(content):
    """Return the byte length of a string when encoded as UTF-8."""
    if isinstance(content, bytes):
        return len(content)
    return len(content.encode("utf-8"))


def save_file(filepath, content):
    """Save content to a file, handling UTF-8 multibyte characters correctly.

    Uses byte length (not character count) to determine buffer sizes for
    I/O operations, preventing buffer overruns when content contains
    multibyte UTF-8 characters (e.g., emoji or CJK characters).

    Args:
        filepath: Path to the destination file.
        content: String content to write.

    Raises:
        OSError: If the file cannot be written.
        TypeError: If content is not a string or bytes.
    """
    if not isinstance(content, (str, bytes)):
        raise TypeError(f"content must be str or bytes, not {type(content).__name__}")

    if isinstance(content, str):
        encoded = content.encode("utf-8")
    else:
        encoded = content

    total_bytes = len(encoded)

    # Write atomically via a temporary file to prevent data loss on crash.
    dir_name = os.path.dirname(os.path.abspath(filepath))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name)
    try:
        offset = 0
        while offset < total_bytes:
            # Size each write chunk by byte length, not character count.
            # This is the fix for the v2.3.1 regression: the old code used
            # len(content) (character count) as the buffer size, which
            # under-allocated when multibyte characters caused the encoded
            # byte length to exceed BUFFER_SIZE.
            chunk_end = min(offset + BUFFER_SIZE, total_bytes)
            os.write(fd, encoded[offset:chunk_end])
            offset = chunk_end
        os.fsync(fd)
    except Exception:
        os.close(fd)
        os.unlink(tmp_path)
        raise
    else:
        os.close(fd)
        os.replace(tmp_path, filepath)
