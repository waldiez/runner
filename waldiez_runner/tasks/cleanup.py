# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught
"""Cleanup stale tasks."""

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqDepends

from waldiez_runner.dependencies import Storage
from waldiez_runner.services import TaskService

from .__base__ import broker
from .dependencies import get_db_session, get_storage

LOG = logging.getLogger(__name__)


@broker.task
async def delete_task(
    task_id: str,
    client_id: str,
    db_session: AsyncSession = TaskiqDepends(get_db_session),
    storage: Storage = TaskiqDepends(get_storage),
) -> None:
    """Delete a single task.

    Parameters
    ----------
    task_id : str
        The task ID
    client_id : str
        The Client id that triggered the task.
    db_session : AsyncSession
        The database session dependency.
    storage : Storage
        The storage implementation dependency.
    """
    try:
        await TaskService.delete_task(db_session, task_id=task_id)
        LOG.debug("Deleted task %s", task_id)
    except BaseException as exc:
        LOG.error("Error deleting task: %s", exc)
    try:
        await storage.delete_folder(os.path.join(client_id, str(task_id)))
        LOG.debug("Deleted task storage for task %s", task_id)
    except BaseException as exc:
        LOG.error("Error deleting task storage: %s", exc)
