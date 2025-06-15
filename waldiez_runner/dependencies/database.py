# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Database connection manager."""

import asyncio
import contextlib
import json
import logging
from asyncio import Lock
from typing import TYPE_CHECKING, Any, AsyncIterator

from fastapi.exceptions import HTTPException
from sqlalchemy.engine import Connection as ConnectionPoolEntry
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.event import listen
from sqlalchemy.exc import IntegrityError, InvalidRequestError, OperationalError
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
            engine_creation_args["connect_args"] = {"check_same_thread": False}

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
    async def session(
        self, retries: int = 3, backoff_factor: int = 2
    ) -> AsyncIterator[AsyncSession]:
        """Get a database session with retries.

        Parameters
        ----------
        retries : int, optional
            Number of retries in case of failure, by default 3.
        backoff_factor : int, optional
            Factor for exponential backoff, by default 2.

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

        attempt = 0
        while attempt < retries:
            async with (
                self._db_lock
            ):  # Prevent multiple failing connections simultaneously
                session = self.session_maker()
                try:
                    yield session
                    return  # Success, exit loop
                except OperationalError as e:
                    attempt += 1
                    LOG.warning(
                        "Database connection failed: %s. Retrying (%d/%d)...",
                        e,
                        attempt,
                        retries,
                    )
                    if attempt < retries:
                        await asyncio.sleep(
                            backoff_factor**attempt
                        )  # Exponential backoff
                    else:
                        LOG.error(
                            "Database connection failed after %d retries.",
                            retries,
                        )
                        raise
                except (IntegrityError, InvalidRequestError) as e:
                    LOG.error("Invalid db execution: %s", e)
                    raise HTTPException(
                        status_code=400, detail={"Invalid request"}
                    ) from e

                except BaseException as e:
                    LOG.error("Unexpected error during session: %s", e)
                    await session.rollback()
                    raise
                finally:
                    await session.close()


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
    cursor.close()
