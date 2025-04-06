# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=too-many-try-statements

"""WebSocket route utilities."""

from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
)
from typing_extensions import Annotated

from waldiez_runner.config import Settings
from waldiez_runner.dependencies import (
    AsyncRedis,
    get_redis,
    get_settings,
)

from .handler import TaskWebSocketHandler

ws_router = APIRouter()


@ws_router.websocket("/ws/{task_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    task_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    redis_client: Annotated[AsyncRedis, Depends(get_redis)],
) -> None:
    """WebSocket endpoint for the ws router.

    Parameters
    ----------
    websocket : WebSocket
        The WebSocket connection.
    task_id : str
        The task ID.
    settings : Settings
        The settings dependency.
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
    handler = TaskWebSocketHandler(
        websocket=websocket,
        task_id=task_id,
        settings=settings,
        redis=redis_client,
    )
    await handler.run()
