# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Task sqlmodel."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, field_serializer
from sqlalchemy import JSON
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .common import Base
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


class TaskCreate(BaseModel):
    """Task create model."""


class TaskUpdate(BaseModel):
    """Task update model."""

    status: TaskStatus | None = None
    results: Dict[str, Any] | List[Dict[str, Any]] | None


class TaskResponse(BaseModel):
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

    model_config = ConfigDict(
        from_attributes=True,
    )

    @classmethod
    @field_serializer("created_at", "updated_at")
    def serialize_datetime(cls, v: datetime) -> str:
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
        return v.isoformat(timespec="milliseconds").replace("+00:00", "Z")
