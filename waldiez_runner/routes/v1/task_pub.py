# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pylint: disable=too-many-lines
# pyright: reportPossiblyUnboundVariable=false

"""Task router helpers."""

import json
import logging

from fastapi import HTTPException

from waldiez_runner.dependencies import app_state
from waldiez_runner.models import TaskStatus
from waldiez_runner.schemas.task import InputResponse

LOG = logging.getLogger(__name__)


async def publish_task_input_response(
    task_id: str,
    message: InputResponse,
) -> None:
    """Publish task input response to Redis.

    Parameters
    ----------
    task_id : str
        The task ID.
    message : InputResponse
        The input response message.

    Raises
    ------
    RuntimeError
        If the Redis connection manager is not initialized.
    """
    if not app_state.redis:  # pragma: no cover
        raise RuntimeError("Redis manager not initialized")
    async with app_state.redis.contextual_client(True) as redis:
        try:
            await redis.publish(
                channel=f"task:{task_id}:input_response",
                message=json.dumps(
                    {"request_id": message.request_id, "data": message.data}
                ),
            )
        except BaseException as e:  # pylint: disable=broad-exception-caught
            LOG.warning("Failed to publish task input response message: %s", e)


async def publish_task_cancellation(
    task_id: str,
) -> None:
    """Publish task cancellation message to Redis.

    Parameters
    ----------
    task_id : str
        The task ID.

    Raises
    ------
    HTTPException
        If the Redis publish fails or if the Redis manager is not initialized.
    """
    if not app_state.redis:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail="Redis manager not initialized",
        )
    async with app_state.redis.contextual_client(True) as redis:
        try:
            await redis.publish(
                channel=f"task:{task_id}:status",
                message=json.dumps(
                    {
                        "task_id": task_id,
                        "status": TaskStatus.CANCELLED.value,
                        "data": {"detail": "Task Cancelled"},
                    }
                ),
            )
        except BaseException as e:
            LOG.warning("Failed to publish task cancellation message: %s", e)
            raise HTTPException(
                status_code=500,
                detail="Failed to publish task cancellation message",
            ) from e
