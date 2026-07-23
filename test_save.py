"""Tests for the save module -- UTF-8 multibyte handling at the 64KB boundary."""

import os
import tempfile

import save


def test_save_large_file_with_multibyte_chars():
    """Files >64KB with multibyte UTF-8 characters save without error."""
    # Each emoji is 4 bytes in UTF-8; 18000 emojis = 72KB
    content = "\U0001f600" * 18000
    assert len(content) == 18000
    assert len(content.encode("utf-8")) == 72000  # >64KB

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        path = f.name
    try:
        save.save_file(content, path)
        with open(path, "r", encoding="utf-8") as f:
            result = f.read()
        assert result == content
    finally:
        os.unlink(path)


def test_save_file_just_under_64kb_with_multibyte():
    """File just under 64KB with multibyte chars saves correctly."""
    # 16000 emojis * 4 bytes = 64000 bytes, just under 64KB
    content = "\U0001f600" * 16000
    assert len(content.encode("utf-8")) < save.BUFFER_SIZE

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        path = f.name
    try:
        save.save_file(content, path)
        with open(path, "r", encoding="utf-8") as f:
            result = f.read()
        assert result == content
    finally:
        os.unlink(path)


def test_save_multibyte_spanning_buffer_boundary():
    """A multibyte character at the 64KB buffer boundary is handled correctly."""
    # Fill to just under 64KB with ASCII, then add multibyte chars
    ascii_part = "A" * (save.BUFFER_SIZE - 1)  # 65535 bytes
    multibyte_part = "\U0001f600" * 100  # 400 bytes of 4-byte emoji
    content = ascii_part + multibyte_part

    byte_len = len(content.encode("utf-8"))
    assert byte_len > save.BUFFER_SIZE

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        path = f.name
    try:
        save.save_file(content, path)
        with open(path, "r", encoding="utf-8") as f:
            result = f.read()
        assert result == content
    finally:
        os.unlink(path)


def test_save_mixed_ascii_and_multibyte_over_64kb():
    """Mixed ASCII and multibyte content totaling >64KB saves correctly."""
    # Alternating ASCII and CJK characters
    unit = "hello世界"  # "hello世界" -- 5 + 6 = 11 bytes
    repeat_count = (save.BUFFER_SIZE // len(unit.encode("utf-8"))) + 1000
    content = unit * repeat_count

    assert len(content.encode("utf-8")) > save.BUFFER_SIZE

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        path = f.name
    try:
        save.save_file(content, path)
        with open(path, "r", encoding="utf-8") as f:
            result = f.read()
        assert result == content
    finally:
        os.unlink(path)


def test_save_ascii_only_over_64kb():
    """Large ASCII-only file over 64KB saves correctly (regression guard)."""
    content = "A" * (save.BUFFER_SIZE + 1000)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        path = f.name
    try:
        save.save_file(content, path)
        with open(path, "r", encoding="utf-8") as f:
            result = f.read()
        assert result == content
    finally:
        os.unlink(path)


def test_save_small_file():
    """Files under 64KB save normally."""
    content = "Hello, world! \U0001f30d"

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        path = f.name
    try:
        save.save_file(content, path)
        with open(path, "r", encoding="utf-8") as f:
            result = f.read()
        assert result == content
    finally:
        os.unlink(path)


def test_save_empty_file():
    """Empty content saves correctly."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        path = f.name
    try:
        save.save_file("", path)
        with open(path, "r", encoding="utf-8") as f:
            result = f.read()
        assert result == ""
    finally:
        os.unlink(path)
