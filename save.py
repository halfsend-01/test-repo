"""File save module with proper UTF-8 multibyte character handling.

Handles saving files of any size, including those larger than 64KB
containing UTF-8 multibyte characters (emoji, CJK, etc.).
"""

import os
import tempfile

# Default buffer size in bytes (64KB)
BUFFER_SIZE = 65536


def save_file(content: str, path: str) -> None:
    """Save content to a file, correctly handling UTF-8 multibyte characters.

    Uses byte length (not character count) for buffer sizing to prevent
    buffer overruns when content contains multibyte UTF-8 characters.

    Args:
        content: The text content to save.
        path: The file path to write to.

    Raises:
        OSError: If the file cannot be written.
    """
    encoded = content.encode("utf-8")
    dir_name = os.path.dirname(os.path.abspath(path))

    # Write to a temporary file first, then rename for atomicity
    fd, tmp_path = tempfile.mkstemp(dir=dir_name)
    try:
        offset = 0
        while offset < len(encoded):
            chunk = encoded[offset : offset + BUFFER_SIZE]
            os.write(fd, chunk)
            offset += BUFFER_SIZE
        os.close(fd)
        os.replace(tmp_path, path)
    except Exception:
        os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
