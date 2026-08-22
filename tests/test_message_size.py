"""Tests for message_size helpers."""
import pytest

from mcp_secure_remote.message_size import (
    DEFAULT_MAX_MESSAGE_BYTES,
    is_within_message_limit,
    message_byte_length,
    parse_max_message_bytes,
)


def test_default_limit_is_10_mib():
    assert DEFAULT_MAX_MESSAGE_BYTES == 10 * 1024 * 1024


def test_parse_max_message_bytes_accepts_valid_values():
    assert parse_max_message_bytes("4096", "--max-message-bytes") == 4096


def test_parse_max_message_bytes_rejects_invalid_values():
    with pytest.raises(ValueError, match="positive integer"):
        parse_max_message_bytes("0", "--max-message-bytes")
    with pytest.raises(ValueError, match="positive integer"):
        parse_max_message_bytes("abc", "--max-message-bytes")


def test_message_byte_length_and_limit():
    message = {"jsonrpc": "2.0", "method": "ping", "id": 1}
    size = message_byte_length(message)
    assert size > 0
    assert is_within_message_limit(message, size)
    assert not is_within_message_limit(message, size - 1)
