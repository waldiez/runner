# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pyright: reportUnusedParameter=false

"""Database connection manager."""

import contextlib
import json
import logging
from asyncio import Lock
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from sqlalchemy.engine import Connection as ConnectionPoolEntry
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.event import listen
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from waldiez_runner.config import Settings

LOG = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection manager with retries and proper session handling."""

    engine: AsyncEngine | None = None
    session_maker: async_sessionmaker[AsyncSession] | None = None
    _db_url: str
    _db_lock = Lock()

    def __init__(self, settings: "Settings") -> None:
        """Initialize the database manager."""
        self.settings = settings
        self._db_url = self.settings.get_database_url()
        self.setup()

    def setup(self) -> None:
        """Setup the database connection."""

        def _serializer(obj: Any) -> str:
            """Serialize JSON objects for the database.

            Parameters
            ----------
            obj : Any
                The object to serialize.

            Returns
            -------
            str
                The serialized JSON string.
            """
            return json.dumps(obj, ensure_ascii=False)

        engine_creation_args: dict[str, Any] = {
            "pool_recycle": 1800,
            "pool_pre_ping": True,
            "json_serializer": _serializer,
            "echo": False,
        }
        if "sqlite" not in self._db_url:  # pragma: no cover
            engine_creation_args.update(
                {
                    "pool_size": 10,
                    "max_overflow": 20,
                    "pool_timeout": 30,
                }
            )
        else:
            engine_creation_args["connect_args"] = {
                "check_same_thread": False,
                "timeout": 60,
            }

        self.engine = create_async_engine(
            self._db_url,
            **engine_creation_args,
        )

        self.session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        if self.is_sqlite:
            listen(self.engine.sync_engine, "connect", _set_sqlite_pragma)

        LOG.info("Database configured with %s", self._db_url)

    @property
    def is_sqlite(self) -> bool:
        """Check if the database is SQLite.

        Returns
        -------
        bool
            True if the database is SQLite, False otherwise.
        """
        return "sqlite" in self._db_url

    async def close(self) -> None:
        """Close the database connection."""
        if self.engine:
            await self.engine.dispose()
            LOG.info("Database connection closed.")
        self.engine = None
        self.session_maker = None

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Get a database session with retries.

        Yields
        ------
        AsyncSession
            The database session.

        Raises
        ------
        RuntimeError
            If the database is not initialized.
        OperationalError
            If the database connection fails after all retries.
        BaseException
            If an error occurs during the session.
        HTTPException
            If an invalid request is made to the database.
        """
        if self.session_maker is None:  # pragma: no cover
            raise RuntimeError("Database not initialized. Call setup() first.")

        session = self.session_maker()
        try:
            yield session
        except Exception:
            # Rollback on error
            with contextlib.suppress(Exception):
                await session.rollback()
            raise
        finally:
            # Always close
            with contextlib.suppress(Exception):
                await session.close()


# noinspection PyUnusedLocal
def _set_sqlite_pragma(
    dbapi_connection: DBAPIConnection,
    connection_record: ConnectionPoolEntry,  # pylint: disable=unused-argument
) -> None:
    """Ensure foreign key constraints are enforced in SQLite.

    Parameters
    ----------
    dbapi_connection : DBAPIConnection
        The database connection.
    connection_record : ConnectionPoolEntry
        The connection pool entry.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=1000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()
