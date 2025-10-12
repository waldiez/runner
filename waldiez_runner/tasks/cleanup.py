# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught
# pyright: reportCallInDefaultInitializer=false
"""Cleanup stale tasks."""

import logging
import os

from taskiq import TaskiqDepends

from waldiez_runner.dependencies import DatabaseManager, Storage
from waldiez_runner.services import TaskService

from .__base__ import broker
from .dependencies import get_db_manager, get_storage

LOG = logging.getLogger(__name__)


@broker.task
async def delete_task(
    task_id: str,
    client_id: str,
    db_manager: DatabaseManager = TaskiqDepends(get_db_manager),
    storage: Storage = TaskiqDepends(get_storage),
) -> None:
    """Delete a single task.

    Parameters
    ----------
    task_id : str
        The task ID
    client_id : str
        The Client id that triggered the task.
    db_manager : DatabaseManager
        The database session manager dependency.
    storage : Storage
        The storage implementation dependency.
    """
    try:
        async with db_manager.session() as db_session:
            await TaskService.delete_task(db_session, task_id=task_id)
        LOG.debug("Deleted task %s", task_id)
    except BaseException as exc:
        LOG.error("Error deleting task: %s", exc)
    try:
        await storage.delete_folder(os.path.join(client_id, str(task_id)))
        LOG.debug("Deleted task storage for task %s", task_id)
    except BaseException as exc:
        LOG.error("Error deleting task storage: %s", exc)
