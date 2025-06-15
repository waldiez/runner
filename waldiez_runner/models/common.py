# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Common models and functions."""

import enum
import typing
from datetime import datetime, timezone
from typing import Annotated, Any

import sqlalchemy
from sqlalchemy import DateTime, String, types
from sqlalchemy.dialects import sqlite
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry
from ulid import ULID

PrimaryKey = Annotated[str, mapped_column(primary_key=True)]
Registry = registry()


# pylint: disable=too-many-ancestors
# credits:
# https://github.com/sqlalchemy/sqlalchemy/issues/1985#issuecomment-1854269776
class UTCDateTime(types.TypeDecorator[datetime]):  # pragma: no cover
    """
    In unit tests we use sqlite to represent the database.
    There is a bug in sqlalchemy that does not set the timezone on read
    sa.Datetime(timezone=True) columns
    Works around https://github.com/sqlalchemy/sqlalchemy/issues/1985
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    @property
    def python_type(self) -> type[datetime]:
        """Return the python type of the column.

        Returns
        -------
        type[datetime]
            The python type of the column.
        """
        return datetime

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """Convert the value to UTC if the dialect is SQLite.

        Parameters
        ----------
        value : datetime | None
            The value to convert.
        dialect : Dialect
            The dialect to use.
        Returns
        -------
        datetime | None
            The converted value.
        """
        if value is None:
            return None
        if isinstance(dialect, sqlite.base.SQLiteDialect):
            return value.replace(tzinfo=timezone.utc)

        return value

    def compare_values(self, x: Any, y: Any) -> bool:
        """Compare two values.

        Parameters
        ----------
        x : Any
            The first value to compare.
        y : Any
            The second value to compare.

        Returns
        -------
        bool
            True if the values are equal, False otherwise.
        """
        if isinstance(x, datetime) and isinstance(y, datetime):
            return x.replace(tzinfo=timezone.utc) == y.replace(
                tzinfo=timezone.utc
            )
        return super().compare_values(x, y)

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """Convert the value to UTC if the dialect is SQLite.

        Parameters
        ----------
        value : datetime | None
            The value to convert.
        dialect : Dialect
            The dialect to use.
        Returns
        -------
        datetime | None
            The converted value.
        """
        if value is None:
            return None
        if isinstance(dialect, sqlite.base.SQLiteDialect):
            return value.astimezone(timezone.utc)

        return value

    def process_literal_param(self, value: Any, dialect: Dialect) -> Any:
        """Convert the value to UTC if the dialect is SQLite.
        Parameters
        ----------
        value : Any
            The value to convert.
        dialect : Dialect
            The dialect to use.
        Returns
        -------
        Any
            The converted value.
        """
        if isinstance(dialect, sqlite.base.SQLiteDialect):
            return self.value_to_tz_utc(value)
        return value

    @staticmethod
    def value_to_tz_utc(value: Any) -> Any:
        """Convert the value to UTC if it is a datetime.

        Parameters
        ----------
        value : Any
            The value to convert.

        Returns
        -------
        Any
            The converted value.
        """
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).astimezone(timezone.utc)
            except ValueError:
                pass
        if isinstance(value, bytes):
            try:
                return datetime.fromisoformat(value.decode()).astimezone(
                    timezone.utc
                )
            except ValueError:
                pass
        if isinstance(value, int):
            return datetime.fromtimestamp(value).astimezone(timezone.utc)
        if isinstance(value, float):
            return datetime.fromtimestamp(value).astimezone(timezone.utc)
        return value


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
        UTCDateTime, default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=now, onupdate=now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True
    )

    def mark_deleted(self) -> None:
        """Mark the record as soft-deleted."""
        self.deleted_at = now()

    type_annotation_map = {  # pyright: ignore
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
