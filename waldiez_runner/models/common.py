# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Common models and functions."""

import enum
import typing
from datetime import datetime, timezone
from typing import Annotated

import sqlalchemy
from sqlalchemy import DateTime, String
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry
from ulid import ULID

PrimaryKey = Annotated[str, mapped_column(primary_key=True)]
Registry = registry()


def get_next_id() -> str:
    """Get next id.

    Returns
    -------
    str
        The Next id.
    """
    return ULID().hex


def now() -> datetime:
    """Get the current time in UTC.

    Returns
    -------
    datetime
        The current time in UTC.
    """
    return datetime.now(timezone.utc)


class Base(DeclarativeBase, AsyncAttrs):
    """Base table to be inherited by all tables."""

    __mapper_args__ = {"confirm_deleted_rows": False}

    id: Mapped[PrimaryKey] = mapped_column(
        String, primary_key=True, default=get_next_id
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now, onupdate=now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def mark_deleted(self) -> None:
        """Mark the record as soft-deleted."""
        self.deleted_at = now()

    type_annotation_map = {
        enum.Enum: sqlalchemy.Enum(enum.Enum),
        typing.Literal: sqlalchemy.Enum(enum.Enum),
    }

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft-deleted.

        Returns
        -------
        bool
            True if the record is soft-deleted
            otherwise False.
        """
        return self.deleted_at is not None
