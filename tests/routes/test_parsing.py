# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=missing-return-doc,unused-argument
# pylint: disable=missing-param-doc,unused-argument,missing-yield-doc
# pyright: reportPrivateUsage=false

"""Test waldiez_runner.routes._parsing.*."""

import json
from types import SimpleNamespace
from typing import Any, Callable

import pytest

# noinspection PyProtectedMember
from waldiez_runner.routes._parsing import (
    _decode_thing,
    _extract_message_data,
    _extract_message_id,
    _get_data_from_raw_message,
    _safe_json_loads,
    is_valid_user_input,
    parse_message,
    parse_task_results,
)


@pytest.fixture(name="redis_msg")
def redis_msg_fixture() -> Callable[[bytes | dict[str, Any]], SimpleNamespace]:
    """Fixture to create a RedisMessage mock."""

    def _make(raw: bytes | dict[str, Any]) -> SimpleNamespace:
        """Create a RedisMessage mock."""
        return SimpleNamespace(raw_message=raw)

    return _make


def test_parse_message_with_id(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test parsing a message with a message ID."""
    raw = b'{"message_id": "abc", "data": {"foo": "bar"}}'
    msg = redis_msg(raw)
    result = parse_message(msg, skip_message_id=False)  # type: ignore
    assert result == {"foo": "bar", "id": "abc"}


def test_parse_message_skip_id(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test parsing a message with a message ID, skipping it."""
    raw = b'{"data": {"foo": "bar"}}'
    msg = redis_msg(raw)
    result = parse_message(msg, skip_message_id=True)  # type: ignore
    assert result == {"foo": "bar"}


def test_parse_message_missing_data(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test parsing a message with missing data."""
    raw = b'{"message_id": "abc"}'
    msg = redis_msg(raw)
    parsed = parse_message(msg, skip_message_id=False)  # type: ignore
    assert parsed is None


def test_parse_task_results_valid_list(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test parsing task results with a valid list."""
    raw = b'{"data": "[{\\"key\\": \\"val\\"}]"}'
    msg = redis_msg(raw)
    result, failed = parse_task_results(msg)  # type: ignore
    assert isinstance(result, list)
    assert result[0]["key"] == "val"
    assert failed is False


def test_parse_task_results_invalid_type(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test parsing task results with an invalid type."""
    raw = b'{"data": {"not": "a list"}}'
    msg = redis_msg(raw)
    result, failed = parse_task_results(msg)  # type: ignore
    assert result is None
    assert failed is True


def test_parse_task_results_unparsable(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test parsing task results with an unparsable string."""
    raw = b'{"data": "not json"}'
    msg = redis_msg(raw)
    result, failed = parse_task_results(msg)  # type: ignore
    assert result is None
    assert failed is True


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"request_id": "abc", "data": "hello"}, True),
        ({"request_id": 123, "data": "text"}, False),
        ({"request_id": "xyz"}, False),
        ("not a dict", False),
        (None, False),
    ],
)
def test_is_valid_user_input(payload: Any, expected: bool) -> None:
    """Test the is_valid_user_input function."""
    assert is_valid_user_input(payload) is expected


def test_get_data_from_dict(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test getting data from a RedisMessage with a dict."""
    msg = redis_msg({"key": b"value"})
    result = _get_data_from_raw_message(msg)  # type: ignore
    assert result == {"key": "value"}


def test_get_data_from_bytes(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test getting data from a RedisMessage with bytes."""
    msg = redis_msg(b'{"key": "val"}')
    result = _get_data_from_raw_message(msg)  # type: ignore
    assert result == {"key": "val"}


def test_get_data_from_invalid(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test getting data from a RedisMessage with invalid data."""
    msg = redis_msg(123)  # type: ignore
    result = _get_data_from_raw_message(msg)  # type: ignore
    assert result is None


@pytest.mark.parametrize(
    "input_data,expected",
    [
        ({"message_id": b"123"}, "123"),
        ({"message_id": "abc"}, "abc"),
        ({"message_ids": [b"xyz"]}, "xyz"),
        ({"message_ids": ["uvw"]}, "uvw"),
        ({}, None),
    ],
)
def test_extract_message_id(
    input_data: dict[str, Any], expected: str | None
) -> None:
    """Test the _extract_message_id function."""
    assert _extract_message_id(input_data) == expected


def test_safe_json_loads_valid() -> None:
    """Test the _safe_json_loads function with valid JSON."""
    raw = '{"foo": "bar"}'
    result = _safe_json_loads(raw)
    assert result == {"foo": "bar"}


def test_safe_json_loads_invalid() -> None:
    """Test the _safe_json_loads function with invalid JSON."""
    raw = "{invalid json}"
    result = _safe_json_loads(raw)
    assert result is None


@pytest.mark.parametrize(
    "input_val,expected",
    [
        ({b"name": b"Alice"}, {"name": "Alice"}),
        ([b"one", b"two"], ["one", "two"]),
        ((b"yes", b"no"), ("yes", "no")),
        ({b"set": {b"a", b"b"}}, {"set": {"a", "b"}}),
    ],
)
def test_decode_thing(input_val: Any, expected: Any) -> None:
    """Test the _decode_thing function."""
    assert _decode_thing(input_val) == expected


def test_parse_message_invalid_json(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test parse_message with undecodable raw message."""
    msg = redis_msg(b"{not valid json}")
    result = parse_message(msg, skip_message_id=False)  # type: ignore
    assert result is None


def test_parse_message_missing_message_id(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test parse_message with missing message_id when not skipping it."""
    raw = b'{"data": {"foo": "bar"}}'
    msg = redis_msg(raw)
    result = parse_message(msg, skip_message_id=False)  # type: ignore
    assert result is None


def test_parse_task_results_no_raw(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test parse_task_results with no raw_message field."""
    msg = SimpleNamespace(raw_message=None)
    result, failed = parse_task_results(msg)  # type: ignore
    assert result is None
    assert failed is True


def test_parse_task_results_data_as_bytes(
    redis_msg: Callable[[bytes | dict[str, Any]], SimpleNamespace],
) -> None:
    """Test parse_task_results with data as bytes containing a list."""
    data = json.dumps([{"foo": "bar"}]).encode("utf-8")
    raw = {"data": data}
    msg = redis_msg(raw)
    result, failed = parse_task_results(msg)  # type: ignore
    assert result == [{"foo": "bar"}]
    assert failed is False


def test_get_data_from_raw_message_none() -> None:
    """Test _get_data_from_raw_message with raw_message=None."""
    msg = SimpleNamespace(raw_message=None)
    result = _get_data_from_raw_message(msg)  # type: ignore
    assert result is None


def test_extract_message_data_dict_format() -> None:
    """Test _extract_message_data with decoded data as dict."""
    decoded: dict[str, Any] = {"data": {"key": [b"one", b"two", "three", 4]}}
    result = _extract_message_data(decoded, message_id="xyz")
    assert result == {"key": ["one", "two", "three", 4], "id": "xyz"}


def test_extract_message_data_list_format() -> None:
    """Test _extract_message_data with decoded data as list."""
    decoded: dict[str, Any] = {"data": [b"one", b"two", "three", 4]}
    result = _extract_message_data(decoded, message_id="xyz")
    assert result == {"id": "xyz", "data": ["one", "two", "three", 4]}


def test_extract_message_data_raw_list() -> None:
    """Test _extract_message_data with raw list data."""
    decoded = {"data": [b"one", b"two"]}
    result = _extract_message_data(decoded, message_id="abc")
    assert result == {"id": "abc", "data": ["one", "two"]}
