# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Schemas for Waldiez Runner."""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator
from typing_extensions import Literal, Self

from waldiez_runner.models.task_status import TaskStatus

from .utils import CronValidationError, normalize_and_validate_cron_expression


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
