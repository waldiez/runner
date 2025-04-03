# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""WebSocket route utilities."""

import asyncio
import json
import logging
import time
from typing import Any, Tuple

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
    redis_client: Annotated[AsyncRedis, Depends(get_redis)],
    validated_data: Annotated[
        Tuple[Task, WsTaskManager, str | None],
        Depends(validate_websocket_connection),
    ],
    task_id: str,
) -> None:
    """WebSocket endpoint for the Faststream router.

    Parameters
    ----------
    websocket : WebSocket
        The WebSocket connection.
    task_id : str
        The task ID.
    validated_data : Tuple[Task, WsTaskManager, str | None]
        The validated data for the WebSocket connection after
        authentication.
    redis_client : Redis
        The Redis client dependency.
    Raises
    ------
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
    await websocket.accept(subprotocol)
    try:
        await send_task_status(websocket, task)
    except BaseException as err:
        LOG.error("Error sending task status: %s", err)
        raise WebSocketException(
            code=status.WS_1011_INTERNAL_ERROR, reason="Internal error"
        ) from err

    try:
        replay_count = int(websocket.query_params.get("replay", 100))
    except ValueError:
        replay_count = 100

    input_task: asyncio.Task[Any] | None = None
    try:
        await stream_history(redis_client, task_id, task_manager, replay_count)
        input_task = asyncio.create_task(
            listen_for_ws_input(websocket, task_id, redis_client),
            name=f"input_task for {task_id}",
        )
        await input_task
    except asyncio.CancelledError:
        LOG.debug("WebSocket task cancelled for %s", task_id)
        raise
    except BaseException as err:  # pylint: disable=broad-exception-caught
        LOG.exception("WS exception: %s for %s", err, task_id)
    finally:
        cleanup_ws_client(task_id, websocket, task_manager)
        if input_task:
            await cancel_task(input_task, task_name=f"input_task for {task_id}")


async def stream_history(
    redis_client: AsyncRedis,
    task_id: str,
    task_manager: WsTaskManager,
    replay_count: int = 50,
) -> None:
    """Replay recent task output from Redis stream to WebSocket clients.

    Parameters
    ----------
    redis_client : AsyncRedis
        The Redis client.
    task_id : str
        The task ID.
    task_manager : WsTaskManager
        The WebSocket task manager.
    replay_count : int, optional
        Number of messages to replay, by default 50.
    """
    stream_key = f"task:{task_id}:output"

    # pylint: disable=too-many-try-statements
    try:
        entries = await redis_client.xrevrange(
            stream_key, "+", "-", count=replay_count
        )
        entries.reverse()  # From oldest to newest

        for entry_id, raw_msg in entries:
            if not isinstance(raw_msg, dict):
                continue

            decoded = {
                k.decode() if isinstance(k, bytes) else k: (
                    v.decode() if isinstance(v, bytes) else v
                )
                for k, v in raw_msg.items()
            }
            decoded["id"] = entry_id
            await task_manager.broadcast(decoded, skip_queue=True)

    except BaseException as e:  # pylint: disable=broad-exception-caught
        LOG.warning("Error replaying Redis stream for task %s: %s", task_id, e)


async def listen_for_ws_input(
    websocket: WebSocket,
    task_id: str,
    redis_client: AsyncRedis,
) -> None:
    """Listen for user input from WebSocket and publish to FastStream Redis.

    Parameters
    ----------
    websocket : WebSocket
        The WebSocket connection.
    task_id : str
        The task ID.
    redis_client : AsyncRedis
        The Redis client.

    Raises
    ------
    asyncio.CancelledError
        If the task is cancelled.
    WebSocketDisconnect
        If the WebSocket is disconnected
    """
    output_channel = f"task:{task_id}:input_response"
    # pylint: disable=too-many-try-statements
    try:
        while True:
            data = await websocket.receive_text()
            LOG.debug("Received input from WebSocket: %s", data)

            try:
                payload = json.loads(data)
                if valid_user_input(payload):
                    await redis_client.publish(
                        output_channel, json.dumps(payload)
                    )
                else:
                    LOG.warning("Invalid input payload: %s", payload)
                    await websocket.send_json(
                        {"error": "Invalid input payload"}
                    )
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format"})
            except WebSocketDisconnect:
                LOG.debug("WebSocket disconnected for task_id=%s", task_id)
                break

    except asyncio.CancelledError:
        LOG.debug("Input listener task cancelled for task_id=%s", task_id)
        raise
    except WebSocketDisconnect:
        LOG.debug("WebSocket disconnected for task_id=%s", task_id)
    except BaseException as err:  # pylint: disable=broad-exception-caught
        LOG.error("Input listener error for task_id=%s: %s", task_id, err)


async def cancel_task(
    task: asyncio.Task[Any],
    timeout: float = 1.0,
    task_name: str = "background task",
) -> None:
    """Cancel an asyncio task and await it safely, with optional timeout.

    Parameters
    ----------
    task : asyncio.Task[Any]
        The asyncio task to cancel.
    timeout : float, optional
        How long to wait for task cancellation before logging a warning.
    task_name : str, optional
        Friendly name for logging/debugging.
    """
    if task.done():
        return
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=timeout)
    except asyncio.TimeoutError:
        LOG.warning("Timeout while cancelling %s", task_name)
    except asyncio.CancelledError:
        pass
    except BaseException as e:  # pylint: disable=broad-exception-caught
        LOG.exception("Error while cancelling %s: %s", task_name, e)


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
