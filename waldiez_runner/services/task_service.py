# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Task service."""

from ._task_service import (
    count_active_tasks,
    count_pending_tasks,
    create_task,
    delete_client_flow_task,
    delete_client_tasks,
    delete_task,
    delete_tasks,
    get_active_client_tasks,
    get_active_tasks,
    get_all_tasks,
    get_client_tasks,
    get_old_tasks,
    get_pending_tasks,
    get_stuck_tasks,
    get_task,
    mark_active_tasks_as_failed,
    soft_delete_client_tasks,
    soft_delete_tasks_by_ids,
    task_transformer,
    trigger,
    update_task,
    update_task_status,
    update_waiting_for_input_tasks,
)


# pylint: disable=too-few-public-methods
class TaskService:
    """Task service."""

    count_active_tasks = staticmethod(count_active_tasks)
    count_pending_tasks = staticmethod(count_pending_tasks)
    create_task = staticmethod(create_task)
    delete_client_flow_task = staticmethod(delete_client_flow_task)
    delete_client_tasks = staticmethod(delete_client_tasks)
    delete_task = staticmethod(delete_task)
    delete_tasks = staticmethod(delete_tasks)
    get_active_client_tasks = staticmethod(get_active_client_tasks)
    get_active_tasks = staticmethod(get_active_tasks)
    get_all_tasks = staticmethod(get_all_tasks)
    get_client_tasks = staticmethod(get_client_tasks)
    get_old_tasks = staticmethod(get_old_tasks)
    get_pending_tasks = staticmethod(get_pending_tasks)
    get_stuck_tasks = staticmethod(get_stuck_tasks)
    get_task = staticmethod(get_task)
    mark_active_tasks_as_failed = staticmethod(mark_active_tasks_as_failed)
    soft_delete_client_tasks = staticmethod(soft_delete_client_tasks)
    soft_delete_tasks_by_ids = staticmethod(soft_delete_tasks_by_ids)
    task_transformer = staticmethod(task_transformer)
    trigger = staticmethod(trigger)
    update_task = staticmethod(update_task)
    update_task_status = staticmethod(update_task_status)
    update_waiting_for_input_tasks = staticmethod(
        update_waiting_for_input_tasks
    )


__all__ = ["TaskService"]
