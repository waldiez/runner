# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Task specific configuration.

Environment variables (with prefix WALDIEZ_RUNNER_)
---------------------------------------------------
MAX_JOBS (int) # default: 5
INPUT_TIMEOUT (int) # default: 180
MAX_TASK_DURATION (int) # default: 60 * 60
KEEP_TASKS_FOR_DAYS (int) # default: 0

Command line arguments (no prefix)
--------------------------------------------------
--max-jobs (int)  # default: 5
--input-timeout (int) # default: 180
--max-task-duration (int)  # default: 3600
--keep-tasks-for-days (int)  # default: 0
"""

from ._common import get_value

DEFAULT_INPUT_TIMEOUT = 180
DEFAULT_DAYS_TO_KEEP_TASKS = 0
DEFAULT_MAX_DURATION_SECS = 3600
DEFAULT_MAX_JOBS = 5


def get_max_jobs() -> int:
    """Get the max jobs per client.

    Returns
    -------
    int
        The max jobs per client.
    """
    return get_value("--max-jobs", "MAX_JOBS", int, DEFAULT_MAX_JOBS)


def get_input_timeout() -> int:
    """Get the input timeout.

    Returns
    -------
    int
        The input timeout
    """
    return get_value(
        "--input-timeout", "INPUT_TIMEOUT", int, DEFAULT_INPUT_TIMEOUT
    )


def get_keep_task_for_days() -> int:
    """Get the days to keep tasks for before deleting them.

    Returns
    -------
    int
        The days to keep tasks for.
    """
    return get_value(
        "--keep-tasks-for-days",
        "KEEP_TASKS_FOR_DAYS",
        int,
        DEFAULT_DAYS_TO_KEEP_TASKS,
    )


def get_max_task_duration() -> int:
    """Get the max allowed task duration in seconds.

    Returns
    -------
    int
        The max task duration.

    """
    return get_value(
        "--max-task-duration",
        "MAX_TASK_DURATION",
        int,
        DEFAULT_MAX_DURATION_SECS,
    )
