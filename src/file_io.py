"""File I/O module with proper UTF-8 buffer handling.

Fixes a regression introduced in v2.3.1 where saving files larger than
64KB containing UTF-8 multibyte characters (emoji, CJK, etc.) caused a
segmentation fault.  The root cause was that the write buffer was sized
using the *character* count of the content instead of its *byte* length.
Since multibyte characters occupy 2-4 bytes each, the actual byte payload
could exceed the allocated buffer, triggering an out-of-bounds write.
"""

import os
import tempfile

# Buffer threshold in bytes.  Content larger than this is written in
# chunks to avoid allocating a single monolithic buffer.
BUFFER_SIZE = 65536  # 64 KiB


def save_file(path: str, content: str) -> None:
    """Persist *content* to *path* atomically.

    The function encodes *content* to UTF-8 and uses the **byte length**
    of the encoded payload to determine whether chunked writing is
    necessary.  Previous versions incorrectly used ``len(content)``
    (character count), which under-allocated the buffer for multibyte
    content.

    An atomic write-to-temp-then-rename strategy is used so that a crash
    mid-write cannot corrupt the destination file.
    """
    encoded = content.encode("utf-8")
    dir_name = os.path.dirname(os.path.abspath(path))

    # Write to a temporary file in the same directory, then rename.
    # This ensures the target file is never left in a partially-written
    # state.
    fd, tmp_path = tempfile.mkstemp(dir=dir_name)
    try:
        offset = 0
        total = len(encoded)  # byte length, NOT character length
        while offset < total:
            chunk = encoded[offset : offset + BUFFER_SIZE]
            os.write(fd, chunk)
            offset += len(chunk)
        os.fsync(fd)
        os.close(fd)
        fd = -1  # prevent double-close in the except branch
        os.replace(tmp_path, path)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        # Clean up the temporary file on failure.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
