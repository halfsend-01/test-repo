"""File saving module with correct UTF-8 buffer handling.

Provides file saving functionality that sizes I/O buffers based on byte
length rather than character count, preventing buffer overflows when
content contains multibyte UTF-8 characters.
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
    """Save content to a file, correctly handling UTF-8 multibyte characters.

    The buffer is sized by byte length (not character count) to prevent
    overflows when multibyte UTF-8 characters cause the encoded size to
    exceed BUFFER_SIZE.

    Args:
        filepath: Path to the destination file.
        content: String or bytes content to write.

    Raises:
        OSError: If the file cannot be written.
        TypeError: If content is not a string or bytes.
    """
    if not isinstance(content, (str, bytes)):
        raise TypeError(
            f"content must be str or bytes, not {type(content).__name__}"
        )

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
            # Size each chunk by byte length, not character count.
            # The v2.3.1 regression used len(content) (character count)
            # as the buffer size, which under-allocated when multibyte
            # characters made the encoded byte length exceed BUFFER_SIZE.
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
