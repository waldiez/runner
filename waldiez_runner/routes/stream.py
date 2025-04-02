# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pylint: disable=unused-argument, disable=broad-exception-caught
# pylint: disable=too-many-try-statements
"""Faststream (+ FastAPI) router."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Tuple

from fastapi import (
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
)
from faststream import Path
from faststream.redis.fastapi import RedisBroker, RedisRouter
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from typing_extensions import Annotated

from waldiez_runner.config import SettingsManager
from waldiez_runner.dependencies import (
    REDIS_MANAGER,
    TASK_API_AUDIENCE,
    AsyncRedis,
    RedisManager,
    get_client_id,
    get_db,
    get_redis,
    skip_redis,
)
from waldiez_runner.models import Task
from waldiez_runner.services import TaskService
from waldiez_runner.tasks import broker as taskiq_broker

from .ws import WsTaskManager, validate_websocket_connection, ws_task_registry

LOG = logging.getLogger(__name__)
REQUIRED_AUDIENCES = [TASK_API_AUDIENCE]
validate_tasks_audience = get_client_id(*REQUIRED_AUDIENCES)


def get_stream_router() -> RedisRouter:
    """Get the Faststream router instance.

    Returns
    -------
    RedisRouter
        The Faststream router instance.
    """
    if skip_redis():
        is_running = REDIS_MANAGER.is_using_fake_redis()
        if is_running:
            redis_url = REDIS_MANAGER.redis_url
        else:
            redis_url = REDIS_MANAGER.start_fake_redis_server(new_port=True)
    else:
        settings = SettingsManager.load_settings()
        redis_manager = RedisManager(settings)
        redis_url = redis_manager.redis_url
    router = RedisRouter(
        url=redis_url,
        include_in_schema=False,
    )
    return router


stream_router = get_stream_router()
if getattr(taskiq_broker, "_is_smoke_testing", False):
    setattr(stream_router, "_is_smoke_testing", True)


def get_broker() -> RedisBroker:
    """Get the Redis broker.

    Returns
    -------
    RedisBroker
        The Redis broker
    """
    return stream_router.broker


@stream_router.subscriber(stream="tasks-output")
async def tasks_output(
    message: str,
) -> None:
    """Task output.

    Parameters
    ----------
    message : str
        The message
    """
    try:
        data: Dict[str, Any] = json.loads(message)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        LOG.warning("Failed to decode task output message: %s", e)
        return
    if not isinstance(data, dict):
        LOG.warning("Received invalid output message: %s", data)
        return
    try:
        task_id = data.get("task_id", None)
        if task_id:
            await ws_task_registry.broadcast_to(task_id, data)
        else:
            LOG.warning("Received output message with no task_id: %s", data)
    except BaseException as e:
        LOG.warning("Failed to process task output message: %s", e)


# if testing, the tests seem to hang forever :( (they need a keyboard interrupt)
# we might need to find another way to handle/test this
if (
    SettingsManager.is_testing() is False
    or getattr(stream_router, "_is_smoke_testing", False) is True
):  # pragma: no cover
    LOG.error("Including task status subscription")

    @stream_router.subscriber(channel="tasks:{task_id}:status")
    async def task_specific_status(
        message: str,
        task_id: str = Path(),
        redis_client: AsyncRedis = Depends(get_redis),
    ) -> None:
        """Task status.

        Parameters
        ----------
        message : str
            The message
        task_id : str
            The task ID.
        redis_client : AsyncRedis
            The Redis client.
        """
        LOG.debug("Received task status message: %s", message)
        if message in ("COMPLETED", "FAILED", "WAITING_FOR_INPUT"):
            await redis_client.set(f"tasks:{task_id}:status", message)

else:
    LOG.warning("Not including task status subscription")


# in addition to ws input, one can make a simple POST request to
# /api/v1/tasks/{task_id}/input
# to send input to the task
@stream_router.post("/api/v1/tasks/{task_id}/input")
async def on_ws_input_request(
    message: str,
    task_id: Annotated[str, Path()],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    client_id: Annotated[str, Depends(validate_tasks_audience)],
) -> None:
    """Task input

    Parameters
    ----------
    message : str
        The message
    task_id : str
        The task ID.
    db_session : AsyncSession
        The database session.
    client_id : str
        The client ID.

    Raises
    ------
    HTTPException
        If the message or the task_id is invalid.

    """
    try:
        task = await TaskService.get_task(db_session, task_id=task_id)
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        ) from e
    if task is None or task.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    try:
        payload = json.loads(message)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        LOG.warning("Failed to decode task input message: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input message format",
        ) from e
    if not isinstance(payload, dict):
        LOG.warning("Received invalid input message: %s", payload)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input message format",
        )
    if not valid_user_input(payload):
        LOG.warning("Invalid input payload: %s", payload)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input payload",
        )

    try:
        await stream_router.broker.publish(
            message=message, channel=f"tasks:{task_id}:input_response"
        )
    except BaseException as e:
        LOG.warning("Failed to publish task input response message: %s", e)


@stream_router.websocket("/ws/{task_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    broker: Annotated[RedisBroker, Depends(get_broker)],
    redis_client: Annotated[AsyncRedis, Depends(get_redis)],
    validated_data: Annotated[
        Tuple[Task, WsTaskManager, str | None],
        Depends(validate_websocket_connection),
    ],
    task_id: Annotated[str, Path()],
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
    broker : RedisBroker
        The Faststream Redis broker dependency.
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
            listen_for_ws_input(websocket, task_id, broker),
            name=f"input_task for {task_id}",
        )
        await input_task
    except asyncio.CancelledError:
        LOG.debug("WebSocket task cancelled for %s", task_id)
        raise
    except Exception as err:
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

    except Exception as e:
        LOG.warning("Error replaying Redis stream for task %s: %s", task_id, e)


async def listen_for_ws_input(
    websocket: WebSocket,
    task_id: str,
    broker: RedisBroker,
) -> None:
    """Listen for user input from WebSocket and publish to FastStream Redis.

    Parameters
    ----------
    websocket : WebSocket
        The WebSocket connection.
    task_id : str
        The task ID.
    broker : RedisBroker
        The FastStream Redis broker.

    Raises
    ------
    asyncio.CancelledError
        If the task is cancelled.
    WebSocketDisconnect
        If the WebSocket is disconnected
    """
    output_channel = f"tasks:{task_id}:input_response"
    # pylint: disable=too-many-try-statements
    try:
        while True:
            data = await websocket.receive_text()
            LOG.debug("Received input from WebSocket: %s", data)

            try:
                payload = json.loads(data)
                if valid_user_input(payload):
                    await broker.publish(
                        message=data,
                        channel=output_channel,
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
    except BaseException as err:
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
    except Exception as e:
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
        payload.get("input_response"), str
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
