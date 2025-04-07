# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=too-many-try-statements

"""The tasks to start when a WebSocket connection is established."""

import asyncio
import json
import logging
from typing import Any, Dict

from fastapi import WebSocket, WebSocketDisconnect

from waldiez_runner.dependencies import AsyncRedis

from .manager import WsTaskManager

LOG = logging.getLogger(__name__)


async def stream_history_and_live(
    redis: AsyncRedis,
    stream_key: str,
    manager: WsTaskManager,
) -> None:
    """Stream history and live updates from Redis to WebSocket clients.

    Parameters
    ----------
    redis : AsyncRedis
        The Redis client.
    stream_key : str
        The Redis stream key.
    manager : WsTaskManager
        The WebSocket task manager.

    Raises
    ------
    asyncio.CancelledError
        If the task is cancelled.
    WebSocketException
        If the WebSocket connection is invalid.
    """
    try:
        history = await redis.xrevrange(stream_key, "+", "-", count=50)
        history.reverse()

        last_id = "0"
        for entry_id, raw in history:
            last_id = entry_id
            msg = decode_stream_msg(raw, entry_id)
            asyncio.create_task(manager.broadcast(msg, skip_queue=True))

        # Live stream
        while True:
            response = await redis.xread(
                {stream_key: last_id}, block=5000, count=10
            )
            if not response:  # pragma: no cover
                await asyncio.sleep(0.5)
                continue

            for _, entries in response:
                for entry_id, raw in entries:
                    if entry_id == last_id:
                        continue
                    msg = decode_stream_msg(raw, entry_id)
                    asyncio.create_task(manager.broadcast(msg))
                    last_id = entry_id

    except asyncio.CancelledError:
        LOG.debug("Output stream cancelled for %s", stream_key)
        raise


async def listen_for_ws_input(
    websocket: WebSocket,
    channel: str,
    task_id: str,
    redis_client: AsyncRedis,
) -> None:
    """Listen for user input from WebSocket and publish to Redis.

    Parameters
    ----------
    websocket : WebSocket
        The WebSocket connection.
    channel : str
        The Redis channel to publish to.
    task_id : str
        The task ID.
    redis_client:
        The Redis client.
    Raises
    ------
    WebSocketDisconnect
        If the WebSocket is disconnected.
    asyncio.CancelledError
        If the task is cancelled.
    """
    try:
        while True:
            msg = await websocket.receive_text()
            payload = json.loads(msg)

            if not valid_user_input(payload):
                await websocket.send_json({"error": "Invalid input payload"})
                continue

            await redis_client.publish(channel, json.dumps(payload))
    except WebSocketDisconnect:
        LOG.info("WS disconnected: %s", task_id)
    except asyncio.CancelledError:
        raise
    except BaseException as err:  # pylint: disable=broad-exception-caught
        LOG.error("Input listener error: %s", err)


def valid_user_input(payload: Any) -> bool:
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


def decode_stream_msg(raw: Dict[Any, Any], msg_id: str) -> Dict[str, Any]:
    """Decode the raw message from Redis stream.

    Parameters
    ----------
    raw : dict
        The raw message from Redis stream.
    msg_id : str
        The message ID.
    Returns
    -------
    Dict[str, Any]
        The decoded message.
    """
    if not isinstance(raw, dict):
        return {}
    decoded = {
        k.decode() if isinstance(k, bytes) else k: (
            v.decode() if isinstance(v, bytes) else v
        )
        for k, v in raw.items()
    }
    decoded["id"] = msg_id
    return decoded
