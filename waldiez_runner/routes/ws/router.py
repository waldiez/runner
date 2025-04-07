# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=too-many-try-statements

"""WebSocket route utilities."""

from fastapi import APIRouter, Depends, WebSocket
from typing_extensions import Annotated

from waldiez_runner.config import Settings
from waldiez_runner.dependencies import app_state, get_settings

from .handler import TaskWebSocketHandler

ws_router = APIRouter()


@ws_router.websocket("/ws/{task_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    task_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
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

    Raises
    ------
    RuntimeError
        If the Redis client is not initialized.
    HTTPException
        If the websocket cannot be accepted.
    WebSocketException
        If there is an error with the WebSocket connection.
    asyncio.CancelledError
        If the task is cancelled.
    """
    if not app_state.redis:  # pragma: no cover
        raise RuntimeError("Redis not initialized")
    async with app_state.redis.contextual_client(
        use_single_connection=True
    ) as redis_client:
        handler = TaskWebSocketHandler(
            websocket=websocket,
            task_id=task_id,
            settings=settings,
            redis=redis_client,
        )
        await handler.run()
