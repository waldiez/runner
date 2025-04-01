# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Task status."""

import enum

PossibleStatus = [
    "PENDING",
    "RUNNING",
    "COMPLETED",
    "CANCELLED",
    "FAILED",
    "WAITING_FOR_INPUT",
]


class TaskStatus(enum.Enum):
    """Task status."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"

    @property
    def is_inactive(self) -> bool:
        """Check if the task is inactive.

        Returns
        -------
        bool
            True if the task is inactive.
        """
        return self.value in {
            "COMPLETED",
            "CANCELLED",
            "FAILED",
        }
