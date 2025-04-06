# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""WebSocket connection validation."""

import logging
from typing import Tuple

from fastapi import Depends, HTTPException, WebSocket, WebSocketException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from typing_extensions import Annotated

from waldiez_runner.config import (
    MAX_ACTIVE_TASKS,
    MAX_CLIENTS_PER_TASK,
    Settings,
)
from waldiez_runner.dependencies import get_db, get_settings
from waldiez_runner.models import Task
from waldiez_runner.services import TaskService

from .auth import get_ws_client_id
from .manager import TooManyClientsException, WsTaskManager
from .registry import TooManyTasksException, WsTaskRegistry

ws_task_registry = WsTaskRegistry(
    max_active_tasks=MAX_ACTIVE_TASKS, max_clients_per_task=MAX_CLIENTS_PER_TASK
)

LOG = logging.getLogger(__name__)


async def validate_websocket_connection(
    task_id: str,
    websocket: WebSocket,
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Tuple[Task, WsTaskManager, str | None]:
    """Dependency to validate WebSocket before accepting the connection.

    Parameters
    ----------
    task_id : str
        The task ID.
    websocket : WebSocket
        The WebSocket connection.
    session : AsyncSession, optional
        The database session, by default Depends(get_db_session).
    settings : Settings, optional
        The application settings, by default Depends(get_app_settings).

    Returns
    -------
    Tuple[Task, WsTaskManager, str | None]
        The task, the task manager, and the subprotocol if any.

    Raises
    ------
    WebSocketException
        Raised when the WebSocket connection is invalid.
    """

    client_id, subprotocol = await get_ws_client_id(
        websocket, settings=settings
    )

    if client_id is None:
        LOG.debug("Client ID is None")
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Invalid client ID"
        )

    try:
        task, task_manager = await _validate_ws_connection(
            websocket, session, task_id
        )
    except HTTPException as err:
        LOG.debug("Task not found: %s", err)
        # pylint: disable=raise-missing-from
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason=str(err)
        )

    if not task.is_active() and task.status.value.lower() != "pending":
        LOG.debug("Task is not active: %s", task.status.value)
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Task is not active"
        )

    return task, task_manager, subprotocol


async def _validate_ws_connection(
    websocket: WebSocket,
    session: AsyncSession,
    task_id: str,
) -> Tuple[Task, WsTaskManager]:
    """Validate the WebSocket connection.

    Parameters
    ----------
    websocket : WebSocket
        The WebSocket connection.
    session : AsyncSession
        The database session.
    task_id : str
        The task ID.

    Returns
    -------
    Tuple[Task, WsTaskManager]
        The task and the task manager.

    Raises
    ------
    WebSocketException
        Raised when the task is not found or
        there are too many tasks or clients.
    """
    task = await TaskService.get_task(session, task_id)
    if not task:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Task not found"
        )
    try:
        task_manager = ws_task_registry.get_or_create_task_manager(task_id)
    except TooManyTasksException as err:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Too many tasks"
        ) from err

    try:
        task_manager.add_client(websocket)
    except TooManyClientsException as err:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Too many clients"
        ) from err
    return task, task_manager
