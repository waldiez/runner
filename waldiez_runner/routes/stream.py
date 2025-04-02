# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Faststream (+ FastAPI) router."""

import json
import logging
from typing import Any, Dict

from fastapi import (
    Depends,
    HTTPException,
)
from faststream import Path
from faststream.redis.fastapi import RedisBroker, RedisMessage, RedisRouter
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
from waldiez_runner.services import TaskService
from waldiez_runner.tasks import broker as taskiq_broker

from .ws import ws_task_registry

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


def get_broker() -> RedisBroker:
    """Get the Redis broker.

    Returns
    -------
    RedisBroker
        The Redis broker
    """
    return stream_router.broker


# pylint: disable=unused-argument
@stream_router.subscriber(stream="task-output")
async def tasks_output(message: RedisMessage, msg: str | None = None) -> None:
    """Task output.

    Parameters
    ----------
    msg : str | None
        The FastStream parsed message.
    message : str
        The full message with all details.
    """
    data = parse_message(message)
    if data is None:
        LOG.warning("Received invalid task output message: %s", message)
        return
    try:
        task_id = data.get("task_id", None)
        if task_id:
            await ws_task_registry.broadcast_to(task_id, data)
        else:
            LOG.warning("Received output message with no task_id: %s", data)
    except BaseException as e:  # pylint: disable=broad-exception-caught
        LOG.warning("Failed to process task output message: %s", e)


# in addition to/instead of ws input,
# one can make a simple POST request to
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
            message=message, channel=f"task:{task_id}:input_response"
        )
    except BaseException as e:  # pylint: disable=broad-exception-caught
        LOG.warning("Failed to publish task input response message: %s", e)


if (
    SettingsManager.is_testing() is False
    or getattr(taskiq_broker, "_is_smoke_testing", False) is True
):  # pragma: no cover
    LOG.error("Including task status subscription")

    @stream_router.subscriber(channel="task:{task_id}:status")
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
        if message.upper() in (
            "PENDING",
            "COMPLETED",
            "FAILED",
            "WAITING_FOR_INPUT",
            "CANCELLED",
        ):
            await redis_client.set(f"task:{task_id}:status", message, ex=60)

    @stream_router.subscriber(channel="task:{task_id}:results")
    async def task_specific_results(
        message: str,
        task_id: str = Path(),
    ) -> None:
        """Task results.

        Parameters
        ----------
        message : str
            The message
        task_id : str
            The task ID.
        """
        LOG.debug(
            "Received task results message: %s for task: %s", message, task_id
        )
        # TODO: Handle task results (e.g., store in database)
        # This is just a placeholder for now.

else:
    LOG.warning("Not including task status subscription")


# pylint: disable=too-many-return-statements
def parse_message(message: RedisMessage) -> Dict[str, Any] | None:
    """Parse a Redis message into a task dictionary, or return None on failure.

    Parameters
    ----------
    message : RedisMessage
        The Redis message to parse.
    Returns
    -------
    Dict[str, Any] | None
        The parsed task dictionary or None if parsing fails.
    """
    raw = getattr(message, "raw_message", None)

    if raw is None:
        LOG.warning("No raw message in RedisMessage: %s", message)
        return None

    # Decode bytes to str or dict
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")

    if isinstance(raw, str):
        raw = _safe_json_loads(raw)
        if raw is None:
            return None

    if not isinstance(raw, dict):
        LOG.warning("Expected dict in message, got: %s", type(raw))
        return None

    decoded = _decode_dict_bytes(raw)

    message_ids = decoded.get("message_ids")
    if not isinstance(message_ids, list) or not message_ids:
        LOG.warning("Invalid or missing message_ids: %s", message_ids)
        return None

    if len(message_ids) != 1:
        LOG.warning("Multiple message_ids received: %s", message_ids)
        return None

    message_id = (
        message_ids[0]
        if isinstance(message_ids[0], str)
        else str(message_ids[0])
    )

    message_data = decoded.get("data")
    if not isinstance(message_data, dict):
        LOG.warning("Missing or invalid 'data' field: %s", message_data)
        return None

    decoded_data = _decode_dict_bytes(message_data)

    task_id = decoded_data.get("task_id")
    if not task_id:
        LOG.warning("Missing task_id in data: %s", decoded_data)
        return None

    decoded_data["id"] = message_id
    return decoded_data


def _decode_dict_bytes(obj: Any) -> Any:
    """Recursively decode a dict with byte keys/values."""
    if not isinstance(obj, dict):
        return obj
    return {
        k.decode() if isinstance(k, bytes) else k: _decode_dict_bytes(
            v.decode() if isinstance(v, bytes) else v
        )
        for k, v in obj.items()
    }


def _safe_json_loads(raw: str) -> Dict[str, Any] | None:
    """Safely decode JSON string.
    Parameters
    ----------
    raw : str
        The JSON string to decode.
    Returns
    -------
    Dict[str, Any] | None
        The decoded JSON object or None if decoding fails.
    """
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        LOG.warning("Failed to decode JSON: %s", e)
        return None


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
