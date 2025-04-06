# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Manage WebSocket tasks."""

import logging
import time
from typing import Any, Dict

from .manager import WsTaskManager

LOG = logging.getLogger(__name__)


class TooManyTasksException(Exception):
    """Exception raised when too many tasks are active."""


class WsTaskRegistry:
    """Registry to manage task managers for WebSocket tasks."""

    def __init__(
        self, max_active_tasks: int = 50, max_clients_per_task: int = 5
    ) -> None:
        """Initialize the task registry.

        Parameters
        ----------
        max_active_tasks : int, optional
            Maximum number of active tasks, by default 50.
        max_clients_per_task : int, optional
            Maximum clients per task, by default 5.
        """
        self.max_active_tasks = max_active_tasks
        self.max_clients_per_task = max_clients_per_task
        self.tasks: Dict[str, WsTaskManager] = {}

    def get_or_create_task_manager(self, task_id: str) -> WsTaskManager:
        """Get or create a task manager if within active task limits.

        Parameters
        ----------
        task_id : str
            The task ID.

        Returns
        -------
        WsTaskManager
            The task manager.

        Raises
        ------
        TooManyTasksException
            Raised when too many tasks are active.
        """
        if task_id not in self.tasks:
            if len(self.tasks) >= self.max_active_tasks:
                raise TooManyTasksException(
                    f"Too many active tasks ({len(self.tasks)})"
                )
            self.tasks[task_id] = WsTaskManager(
                task_id, self.max_clients_per_task
            )

        return self.tasks[task_id]

    def remove_task_if_empty(self, task_id: str) -> None:
        """Remove a task if it has no clients.

        Parameters
        ----------
        task_id : str
            The task ID.
        """
        if task_id in self.tasks and self.tasks[task_id].is_empty():
            LOG.debug("Removing empty task %s", task_id)
            del self.tasks[task_id]

    async def broadcast_to(
        self, task_id: str, message: Dict[str, Any], skip_queue: bool = False
    ) -> None:
        """Broadcast a message to all clients of a task.

        Parameters
        ----------
        task_id : str
            The task ID.
        message : dict
            The message to broadcast.
        skip_queue : bool, optional
            Whether to skip the queue, by default False.
        """
        manager = self.tasks.get(task_id)
        if manager:
            await manager.broadcast(message, skip_queue)

    def stats(self) -> Dict[str, Any]:
        """Get task registry statistics.

        Returns
        -------
        Dict[str, Any]
            The task registry statistics.
        """
        return {
            "active_tasks": len(self.tasks),
            "connected_clients": sum(
                len(m.clients) for m in self.tasks.values()
            ),
            "per_task": {
                task_id: len(m.clients) for task_id, m in self.tasks.items()
            },
        }

    def expire_idle_tasks(self, max_idle_seconds: float = 300) -> None:
        """Expire idle tasks.

        Parameters
        ----------
        max_idle_seconds : float, optional
            Maximum idle time in seconds, by default 300.
        """
        now = time.monotonic()
        expired_ids = []

        for task_id, manager in self.tasks.items():
            if (
                manager.is_empty()
                and (now - manager.last_used) > max_idle_seconds
            ):
                expired_ids.append(task_id)

        for task_id in expired_ids:
            LOG.debug("Expiring idle task: %s", task_id)
            del self.tasks[task_id]
