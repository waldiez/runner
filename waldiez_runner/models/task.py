# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Task model."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from typing_extensions import Literal

from .common import Base, UTCDateTime
from .task_status import TaskStatus


class Task(Base):
    """Task in database model."""

    __tablename__ = "tasks"

    client_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    flow_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    input_timeout: Mapped[int] = mapped_column(
        Integer, nullable=False, default=180
    )
    input_request_id: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[TaskStatus] = mapped_column(
        SqlEnum(
            TaskStatus,
            name="task_status",
            create_type=False,
        ),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
    )
    results: Mapped[dict[str, Any] | list[dict[str, Any]] | None] = (
        mapped_column(JSON, nullable=True)
    )

    schedule_type: Mapped[Literal["once", "cron"] | None] = mapped_column(
        String, nullable=True, index=True, default=None
    )
    scheduled_time: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True, index=True, default=None
    )
    cron_expression: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )
    triggered_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True, default=None
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True, default=None
    )

    def get_status(self) -> str:
        """Get the status.

        Returns
        -------
        str
            The status.
        """
        if isinstance(self.status, str):  # pragma: no cover
            return self.status
        return self.status.value

    def is_inactive(self) -> bool:
        """Check if the task is inactive.

        Returns
        -------
        bool
            True if the task is inactive.
        """
        if self.is_deleted:
            return True
        if isinstance(self.status, str):
            return self.status in {
                "COMPLETED",
                "CANCELLED",
                "FAILED",
            }
        return self.status.is_inactive

    def is_active(self) -> bool:
        """Check if the task is active.

        Returns
        -------
        bool
            True if the task is active.
        """
        return not self.is_inactive()

    def is_stuck(self) -> bool:
        """Check if the task is stuck.

        Returns
        -------
        bool
            True if the task is stuck.
        """
        return self.is_active() and self.results is not None
