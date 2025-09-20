# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Task specific configuration.

Environment variables (with prefix WALDIEZ_RUNNER_)
---------------------------------------------------
INPUT_TIMEOUT (int) # default: 180
KEEP_TASKS_FOR_DAYS (int) # default: 0

Command line arguments (no prefix)
--------------------------------------------------
--input-timeout (int) # default: 180
--keep-tasks-for-days (int)  # default: 0
"""

from ._common import get_value

DEFAULT_INPUT_TIMEOUT = 180
DEFAULT_DAYS_TO_KEEP_TASKS = 0


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
