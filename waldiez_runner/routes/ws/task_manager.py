# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Manage WebSocket clients for a single task."""

# pylint: disable=broad-exception-caught,too-few-public-methods
# pylint: disable=too-many-try-statements

import asyncio
import logging
import time
from typing import Any, Dict, List

from fastapi import WebSocket

LOG = logging.getLogger(__name__)


class TooManyClientsException(Exception):
    """Exception raised when too many clients are connected."""


class WsTaskManager:
    """Manage WebSocket clients for a single task."""

    def __init__(
        self, task_id: str, max_clients: int = 5, queue_size: int = 100
    ) -> None:
        """Initialize the task manager.

        Parameters
        ----------
        task_id : str
            The task ID.
        max_clients : int, optional
            Maximum allowed clients for this task, by default 5.
        queue_size : int, optional
            Maximum messages per client queue, by default 100.
        """
        self.task_id = task_id
        self.max_clients = max_clients
        self.queue_size = queue_size
        self.last_used = time.monotonic()
        self.clients: List[WebSocket] = []
        self.client_queues: Dict[WebSocket, asyncio.Queue[Dict[str, Any]]] = {}
        self.client_tasks: Dict[WebSocket, asyncio.Task[Any]] = {}

    def add_client(self, websocket: WebSocket) -> None:
        """Add a WebSocket client if within limits.

        Parameters
        ----------
        websocket : WebSocket
            The WebSocket connection.

        Raises
        ------
        TooManyClientsException
            Raised when the maximum number of clients is exceeded.
        """
        if len(self.clients) >= self.max_clients:
            raise TooManyClientsException(
                f"Too many clients for task {self.task_id}"
            )

        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(
            maxsize=self.queue_size
        )
        self.clients.append(websocket)
        self.client_queues[websocket] = queue

        # Start a background task to send messages from the queue
        task = asyncio.create_task(self.websocket_writer(websocket, queue))
        self.client_tasks[websocket] = task

        LOG.debug(
            "Added client to task %s, total: %d",
            self.task_id,
            len(self.clients),
        )

    async def websocket_writer(
        self,
        websocket: WebSocket,
        queue: asyncio.Queue[Dict[str, Any]],
    ) -> None:
        """Sends messages from queue to the WebSocket client.

        Parameters
        ----------
        websocket : WebSocket
            The WebSocket connection.
        queue : asyncio.Queue
            The message queue.
        """
        try:
            while True:
                message = await queue.get()  # Wait for message
                await websocket.send_json(message)  # Send message to WebSocket
        except asyncio.CancelledError:  # pragma: no cover
            LOG.debug(
                "WebSocket writer task cancelled for client %s", websocket
            )
        except BaseException as e:  # pragma: no cover
            LOG.error("WebSocket send error: %s", e)
        finally:
            self.remove_client(websocket)  # Cleanup

    def remove_client(self, websocket: WebSocket) -> None:
        """Remove a WebSocket client and cleanup.

        Parameters
        ----------
        websocket : WebSocket
            The WebSocket connection
        """
        try:
            self.clients.remove(websocket)
            queue = self.client_queues.pop(websocket, None)
            task = self.client_tasks.pop(websocket, None)

            if task:
                task.cancel()  # Stop sending messages
            if queue:
                while not queue.empty():
                    try:
                        queue.get_nowait()  # Drain queue to free memory
                    except BaseException:  # pragma: no cover
                        pass

            LOG.debug(
                "Removed client from task %s, total: %d",
                self.task_id,
                len(self.clients),
            )
        except ValueError:  # pragma: no cover
            pass  # Client already removed?

    async def broadcast(
        self, message: Dict[str, Any], skip_queue: bool = False
    ) -> None:
        """Broadcast a message by adding it to each client's queue.

        Parameters
        ----------
        message : dict
            The message to broadcast.
        skip_queue : bool, optional
            Send message directly without adding to queue, by default False.
        """
        for client in self.clients[:]:
            try:
                if skip_queue:
                    await client.send_json(message)
                else:
                    queue = self.client_queues.get(client)
                    if queue:
                        await queue.put(message)
            except asyncio.QueueFull:
                LOG.warning(
                    "Queue full for client %s, dropping message.", client
                )

    def is_empty(self) -> bool:
        """Check if the task has no connected clients.

        Returns
        -------
        bool
            True if no clients are connected, False otherwise.
        """
        return len(self.clients) == 0

    def update_usage(self) -> None:
        """Update the last used timestamp"""
        self.last_used = time.monotonic()
