# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=too-many-try-statements

"""WebSocket route utilities."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict

from fastapi import WebSocket, WebSocketDisconnect, WebSocketException
from starlette import status

from waldiez_runner.config import Settings
from waldiez_runner.dependencies import AsyncRedis, app_state
from waldiez_runner.models import Task

from .listeners import listen_for_ws_input, stream_history_and_live
from .manager import WsTaskManager
from .validation import validate_websocket_connection, ws_task_registry

LOG = logging.getLogger(__name__)


class TaskWebSocketHandler:
    """WebSocket handler for task-related operations."""

    def __init__(
        self,
        websocket: WebSocket,
        task_id: str,
        settings: Settings,
        redis: AsyncRedis,
    ) -> None:
        """Initialize the WebSocket handler.

        Parameters
        ----------
        websocket : WebSocket
            The WebSocket connection.
        task_id : str
            The task ID.
        settings : Settings
            The settings dependency.
        redis : AsyncRedis
            The Redis client dependency.
        """
        self.websocket = websocket
        self.task_id = task_id
        self.settings = settings
        self.redis = redis

        self.task: Task | None = None
        self.task_manager: WsTaskManager | None = None
        self.subprotocol: str | None = None

        self.input_task: asyncio.Task[Any] | None = None
        self.output_task: asyncio.Task[Any] | None = None

    async def run(self) -> None:
        """Run the WebSocket handler.

        This method orchestrates the WebSocket connection lifecycle,
        including validation, acceptance, and task management.

        Raises
        ------
        WebSocketException
            If there is an error during the WebSocket connection lifecycle.
        WebSocketDisconnect
            If the WebSocket connection is disconnected.
        """
        try:
            await self.validate()
            await self._accept()
            await self._send_initial_status()
            await self._start_task_listeners()
        except WebSocketException as err:
            LOG.error("WebSocket error: %s", err)
            await self.websocket.close(
                code=status.WS_1011_INTERNAL_ERROR,
                reason="WebSocket error",
            )
        finally:
            self._cleanup()

    async def validate(self) -> None:
        """Validate the WebSocket connection.

        Raises
        ------
        WebSocketException
            If the validation fails.
        """
        if not app_state.db:  # pragma: no cover
            raise WebSocketException(
                code=status.WS_1011_INTERNAL_ERROR,
                reason="Database not available",
            )
        try:
            async with app_state.db.session() as session:  # pragma: no cover
                (
                    self.task,
                    self.task_manager,
                    self.subprotocol,
                ) = await validate_websocket_connection(
                    websocket=self.websocket,
                    session=session,
                    settings=self.settings,
                    task_id=self.task_id,
                )
        except Exception as err:
            LOG.error("WebSocket validation failed: %s", err)
            manager = ws_task_registry.get_or_create_task_manager(self.task_id)
            manager.remove_client(self.websocket)
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION, reason="Validation failed"
            ) from err

    async def _accept(self) -> None:
        try:
            await self.websocket.accept(subprotocol=self.subprotocol)
        except Exception as err:  # pragma: no cover
            LOG.error("WebSocket accept failed: %s", err)
            raise WebSocketException(
                code=status.WS_1006_ABNORMAL_CLOSURE,
                reason="WebSocket accept failed",
            ) from err

    async def _send_initial_status(self) -> None:
        try:
            if not self.task:  # pragma: no cover
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Task not found",
                )
            payload = build_status_payload(self.task)
            await self.websocket.send_json(payload)
        except WebSocketDisconnect as err:  # pragma: no cover
            LOG.warning("Initial status send failed: %s", err)
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Initial status send failed",
            ) from err

    async def _start_task_listeners(self) -> None:
        stream_key = f"task:{self.task_id}:output"
        input_channel = f"task:{self.task_id}:input_response"

        if not self.task_manager:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Task manager not found",
            )
        self.input_task = asyncio.create_task(
            listen_for_ws_input(
                self.websocket,
                input_channel,
                self.task_id,
                self.redis,
            ),
            name=f"input-listener:{self.task_id}",
        )

        self.output_task = asyncio.create_task(
            stream_history_and_live(
                self.redis,
                stream_key,
                self.task_manager,
            ),
            name=f"output-streamer:{self.task_id}",
        )

        _, pending = await asyncio.wait(
            [self.input_task, self.output_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:  # pragma: no cover
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def _cleanup(self) -> None:
        """Cleanup the WebSocket handler."""
        if (
            self.task_manager and self.websocket in self.task_manager.clients
        ):  # pragma: no branch
            self.task_manager.remove_client(self.websocket)
        ws_task_registry.remove_task_if_empty(self.task_id)


def build_status_payload(task: Task) -> Dict[str, Any]:
    """Build the status payload for the WebSocket.

    Parameters
    ----------
    task : Task
        The task object.
    Returns
    -------
    Dict[str, Any]
        The status payload.
    """

    def format_iso(dt: datetime) -> str:
        """Format datetime to ISO 8601 string.

        Parameters
        ----------
        dt : datetime
            The datetime object to format.
        Returns
        -------
        str
            The formatted ISO 8601 string.
        """
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    return {
        "type": "status",
        "timestamp": int(time.time() * 1_000_000),
        "data": {
            "task_id": task.id,
            "status": task.status.value,
            "created_at": format_iso(task.created_at),
            "updated_at": format_iso(task.updated_at),
            "results": task.results,
            "input_request_id": task.input_request_id,
        },
    }
