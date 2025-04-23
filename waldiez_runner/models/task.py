# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Task model."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator
from sqlalchemy import JSON
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from typing_extensions import Literal, Self

from .common import Base, UTCDateTime
from .cron_util import (
    CronValidationError,
    normalize_and_validate_cron_expression,
)
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
    input_request_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )

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
    results: Mapped[
        Optional[
            Union[
                Dict[str, Any],
                List[Dict[str, Any]],
            ]
        ]
    ] = mapped_column(JSON, nullable=True)

    schedule_type: Mapped[Optional[Literal["once", "cron"]]] = mapped_column(
        String, nullable=True, index=True, default=None
    )
    scheduled_time: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime, nullable=True, index=True, default=None
    )
    cron_expression: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, default=None
    )
    triggered_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime, nullable=True, default=None
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
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


class TaskBase(BaseModel):
    """Task base model."""

    schedule_type: Literal["once", "cron"] | None = None
    scheduled_time: datetime | None = None
    cron_expression: str | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> Self:
        """Check schedule type.

        Returns
        -------
        Self
            The TaskCreate instance.

        Raises
        ------
        ValueError
            If the schedule type is invalid.
        """
        if self.schedule_type == "once":
            if not self.scheduled_time:
                raise ValueError(
                    "scheduled_time is required for 'once' schedule"
                )
            if self.expires_at is not None:
                raise ValueError(
                    "expires_at is not allowed for 'once' schedule"
                )

        if self.schedule_type == "cron":
            if not self.cron_expression:
                raise ValueError(
                    "cron_expression is required for 'cron' schedule"
                )
            try:
                self.cron_expression = normalize_and_validate_cron_expression(
                    self.cron_expression
                )
            except CronValidationError as e:
                raise ValueError(str(e)) from e

        if self.schedule_type != "cron" and self.cron_expression:
            raise ValueError(
                "cron_expression is not allowed unless schedule_type is 'cron'"
            )

        if self.schedule_type != "once" and self.scheduled_time:
            raise ValueError(
                "scheduled_time is not allowed unless schedule_type is 'once'"
            )

        return self


class TaskCreate(TaskBase):
    """Task create model."""

    client_id: str
    flow_id: str
    filename: str
    input_timeout: int = 180


class TaskUpdate(TaskBase):
    """Task update model."""

    status: TaskStatus | None = None
    results: Dict[str, Any] | List[Dict[str, Any]] | None = None


class TaskResponse(TaskBase):
    """Task response model."""

    id: str
    created_at: datetime
    updated_at: datetime
    client_id: str
    flow_id: str
    filename: str
    status: TaskStatus
    input_timeout: int
    input_request_id: str | None
    results: Dict[str, Any] | List[Dict[str, Any]] | None
    triggered_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True,
    )

    @classmethod
    @field_serializer(
        "created_at",
        "updated_at",
        "scheduled_time",
        "triggered_at",
        "expires_at",
    )
    def serialize_datetime(cls, v: datetime | None) -> str | None:
        """Serialize datetime.

        Parameters
        ----------
        v : datetime
            The datetime.

        Returns
        -------
        str
            The serialized datetime.
        """
        if v is None:
            return None
        return v.isoformat(timespec="milliseconds").replace("+00:00", "Z")
