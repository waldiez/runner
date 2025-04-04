# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=too-many-try-statements

"""WebSocket route utilities."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Tuple

from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
)
from starlette import status
from typing_extensions import Annotated

from waldiez_runner.dependencies import AsyncRedis, get_redis
from waldiez_runner.models import Task

from .dependency import validate_websocket_connection, ws_task_registry
from .task_manager import WsTaskManager

ws_router = APIRouter()

LOG = logging.getLogger(__name__)


@ws_router.websocket("/ws/{task_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    task_id: str,
    validated_data: Annotated[
        Tuple[Task, WsTaskManager, str | None],
        Depends(validate_websocket_connection),
    ],
    redis_client: Annotated[AsyncRedis, Depends(get_redis)],
) -> None:
    """WebSocket endpoint for the ws router.

    Parameters
    ----------
    websocket : WebSocket
        The WebSocket connection.
    task_id : str
        The task ID.
    validated_data : Tuple[Task, WsTaskManager, str | None]
        The validated data for the WebSocket connection after
        authentication.
    redis_client : AsyncRedis
        The Redis client dependency.
    Raises
    ------
    HTTPException
        If the websocket cannot be accepted.
    WebSocketException
        If there is an error with the WebSocket connection.
    asyncio.CancelledError
        If the task is cancelled.
    """
    # regarding `validated_data`:
    # from starlette docs:
    # You can use an HTTPException on a WebSocket endpoint.
    # In case it's raised before websocket.accept()
    # the connection is not upgraded to a WebSocket connection,
    #  and the proper HTTP response is returned.
    # BUT this might not work with all the middlewares
    # we might get:
    # https://github.com/MagicStack/uvloop/issues/506#issuecomment\
    # -2404171195
    # and:
    # https://github.com/python-websockets/websockets/issues/1396
    # so an HTTPException might not work as expected
    # we try to raise a WebSocketException instead
    task, task_manager, subprotocol = validated_data

    try:
        await websocket.accept(subprotocol)
    except Exception as err:
        LOG.error("WebSocket accept failed: %s", err)
        cleanup_ws_client(task_id, websocket, task_manager)
        raise WebSocketException(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Internal server error",
        ) from err
    try:
        await send_task_status(websocket, task)
    except WebSocketDisconnect as err:
        LOG.error("WebSocket send status failed: %s", err)
        cleanup_ws_client(task_id, websocket, task_manager)
    stream_key = f"task:{task_id}:output"
    input_channel = f"task:{task_id}:input_response"

    input_task = asyncio.create_task(
        listen_for_ws_input(websocket, input_channel, task_id, redis_client),
        name=f"input-listener:{task_id}",
    )
    output_task = asyncio.create_task(
        stream_history_and_live(redis_client, stream_key, task_manager),
        name=f"output-streamer:{task_id}",
    )

    try:
        _, pending = await asyncio.wait(
            [input_task, output_task], return_when=asyncio.FIRST_COMPLETED
        )
        for a_task in pending:
            a_task.cancel()
            try:
                await a_task
            except asyncio.CancelledError:
                pass
    finally:
        cleanup_ws_client(task_id, websocket, task_manager)


async def send_task_status(
    websocket: WebSocket,
    task: Task,
) -> None:
    """Send the task status to the WebSocket.

    Parameters
    ----------
    websocket : WebSocket
        The WebSocket connection.
    task : Task
        The task.
    """
    created_at = task.created_at.isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
    updated_at = task.updated_at.isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
    payload = {
        "type": "status",
        "timestamp": int(time.time() * 1_000_000),
        "data": {
            "task_id": task.id,
            "status": task.status.value,
            "created_at": created_at,
            "updated_at": updated_at,
            "results": task.results,
            "input_request_id": task.input_request_id,
        },
    }
    await websocket.send_json(payload)


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
            await manager.broadcast(msg, skip_queue=True)

        # Live stream
        while True:
            response = await redis.xread(
                {stream_key: last_id}, block=5000, count=10
            )
            if not response:
                await asyncio.sleep(0.5)
                continue

            for _, entries in response:
                for entry_id, raw in entries:
                    if entry_id == last_id:
                        continue
                    msg = decode_stream_msg(raw, entry_id)
                    await manager.broadcast(msg)
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


def decode_stream_msg(raw: Dict[str, Any], msg_id: str) -> Dict[str, Any]:
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


def cleanup_ws_client(
    task_id: str,
    websocket: WebSocket,
    task_manager: WsTaskManager,
) -> None:
    """Cleanup WebSocket client.

    Parameters
    ----------
    task_id : str
        The task ID.
    websocket : WebSocket
        The WebSocket connection.
    task_manager : WsTaskManager
        The WebSocket task manager.
    """
    if websocket in task_manager.clients:
        task_manager.remove_client(websocket)
    ws_task_registry.remove_task_if_empty(task_id)
