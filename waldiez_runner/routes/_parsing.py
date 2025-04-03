# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Message parsing utilities for Faststream Redis integration."""

import json
import logging
from typing import Any, Dict, List, Tuple

from faststream.redis.fastapi import RedisMessage

LOG = logging.getLogger(__name__)


def parse_message(
    message: RedisMessage,
    skip_message_id: bool,
) -> Dict[str, Any] | List[Dict[str, Any]] | None:
    """Parse a Redis message into a serializable format.

    Parameters
    ----------
    message : RedisMessage
        The Redis message.
    skip_message_id : bool
        Whether to skip the message ID.
    Returns
    -------
    Dict[str, Any] | List[Dict[str, Any]] | None
        The parsed message, or None if parsing failed.
    """
    decoded = _get_data_from_raw_message(message)
    if not decoded:
        LOG.warning("Failed to decode message: %s", message)
        return None

    message_id = None if skip_message_id else _extract_message_id(decoded)
    if message_id is None and not skip_message_id:
        LOG.warning("Missing message_id in message: %s", decoded)
        return None

    return _extract_message_data(decoded, message_id)


def parse_task_results(
    message: RedisMessage,
) -> Tuple[Dict[str, Any] | List[Dict[str, Any]] | None, bool]:
    """Parse task results from a Redis message.

    Parameters
    ----------
    message : RedisMessage
        The Redis message.
    Returns
    -------
    Tuple[Dict[str, Any] | List[Dict[str, Any]] | None, bool]
        The parsed task results and a flag indicating if the message was
        malformed.
    """
    decoded = _get_data_from_raw_message(message)
    if not decoded:
        LOG.warning("Failed to decode message: %s", message)
        return None, True

    data = decoded.get("data")
    if isinstance(data, bytes):  # pragma: no cover
        data = data.decode("utf-8")
    if isinstance(data, str):
        data = _safe_json_loads(data)  # decoding is applied inside
    if not isinstance(data, list):
        LOG.warning("Expected list in message data, got: %s", type(data))
        return None, True

    return data, False


def is_valid_user_input(payload: Any) -> bool:
    """Validate the structure of user input payload.

    Parameters
    ----------
    payload : Any
        The payload.

    Returns
    -------
    bool
        True if the payload is valid, False otherwise.
    """
    if not isinstance(payload, dict):
        return False
    return isinstance(payload.get("request_id"), str) and isinstance(
        payload.get("data"), str
    )


def _get_data_from_raw_message(message: RedisMessage) -> Dict[str, Any] | None:
    """Get the data from a raw Redis message."""
    raw = getattr(message, "raw_message", None)
    if raw is None:
        LOG.warning("No raw message in RedisMessage: %s", message)
        return None

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        raw = _safe_json_loads(raw)
    if not isinstance(raw, dict):
        LOG.warning("Expected dict in message, got: %s", type(raw))
        return None

    return _decode_thing(raw)


def _extract_message_id(decoded: Dict[str, Any]) -> str | None:
    """Extract message_id from decoded message."""
    message_id = decoded.get("message_id")
    if isinstance(message_id, bytes):
        return message_id.decode("utf-8")
    if isinstance(message_id, str):
        return message_id

    message_ids = decoded.get("message_ids")
    if isinstance(message_ids, list) and message_ids:
        item = message_ids[0]
        if isinstance(item, bytes):
            return item.decode("utf-8")
        if isinstance(item, str):
            return item
    return None


def _extract_message_data(
    decoded: Dict[str, Any],
    message_id: str | None,
) -> Dict[str, Any] | List[Dict[str, Any]] | None:
    """Extract and decode the message data."""
    message_data = decoded.get("data")
    if not isinstance(message_data, (dict, list)):
        LOG.warning("Missing or invalid 'data' field: %s", message_data)
        return None

    decoded_data = _decode_thing(message_data)

    if message_id is None:
        return decoded_data

    if isinstance(decoded_data, list):
        return {"id": message_id, "data": decoded_data}
    if isinstance(decoded_data, dict):
        return {**decoded_data, "id": message_id}

    return None  # pragma: no cover


def _decode_thing(
    thing: Any, encoding: str = "utf-8", errors: str = "replace"
) -> Any:
    """Recursively decode bytes in dicts, lists, tuples, and sets."""
    if isinstance(thing, dict):
        return {
            _decode_thing(k, encoding, errors): _decode_thing(
                v, encoding, errors
            )
            for k, v in thing.items()
        }
    if isinstance(thing, (list, tuple, set)):
        container = type(thing)
        return container(_decode_thing(i, encoding, errors) for i in thing)
    if isinstance(thing, bytes):
        return thing.decode(encoding, errors)
    return thing


def _safe_json_loads(raw: str, decode: bool = True) -> Any:
    """Safely decode a JSON string. Optionally decode byte strings."""
    try:
        parsed = json.loads(raw)
        return _decode_thing(parsed) if decode else parsed
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        LOG.warning("Failed to decode JSON: %s", e)
        return None
