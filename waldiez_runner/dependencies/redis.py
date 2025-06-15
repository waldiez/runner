# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pyright: reportMissingTypeArgument=false,reportUnknownMemberType=false
# pylint: disable=too-many-try-statements
# pylint: disable=broad-exception-caught, protected-access
"""Redis connection manager."""

import asyncio
import atexit
import logging
import os
from contextlib import asynccontextmanager
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Any, AsyncIterator

import redis
import redis.asyncio as a_redis
from fakeredis import TcpFakeServer

from waldiez_runner.config import (
    ENV_PREFIX,
    TRUTHY,
    Settings,
    SettingsManager,
    in_container,
)

from ._utils import get_available_port, is_port_available

if TYPE_CHECKING:
    Redis = redis.Redis[str]
    AsyncRedis = a_redis.Redis[str]
    ConnectionPool = a_redis.ConnectionPool[Any]
else:
    Redis = redis.Redis
    AsyncRedis = a_redis.Redis
    ConnectionPool = a_redis.ConnectionPool

LOG = logging.getLogger(__name__)


class RedisManager:
    """Redis connection manager with support for Fake Redis."""

    _pool: ConnectionPool | None = None
    _stop_event = Event()
    _server: TcpFakeServer | None = None
    _server_thread: Thread | None = None

    settings: "Settings"
    redis_url: str

    def __init__(self, settings: "Settings", skip_setup: bool = False) -> None:
        """Initialize the Redis manager.

        Parameters
        ----------
        settings : Settings
            The settings instance.
        skip_setup : bool, optional
            Whether to skip setting up the Redis connection, by default False.
        """
        self.settings = settings
        if skip_setup is False:
            self.setup()
        atexit.register(self._atexit_close)

    def _atexit_close(self) -> None:
        """Fallback sync cleanup in case async close wasn't awaited."""
        if self._pool:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
                else:
                    loop.run_until_complete(self.close())
            except Exception:
                pass
        else:
            self.stop_fake_redis_server()

    def setup(self) -> None:
        """Setup the Redis connection, starting Fake Redis if needed.

        Raises
        ------
        RuntimeError
            If no Redis URL is provided and not in testing mode
        """
        redis_url = self.settings.get_redis_url()
        if not redis_url:
            if (
                not self.settings.is_testing() and self.settings.dev is False
            ):  # pragma: no cover
                raise RuntimeError(
                    "No Redis URL provided and not in dev/testing mode."
                )
            redis_url = self.start_fake_redis_server()

        self.redis_url = redis_url
        self._pool = a_redis.ConnectionPool.from_url(
            self.redis_url, decode_responses=True
        )
        LOG.info("Redis pool initialized at %s", self.redis_url)

    async def close(self) -> None:
        """Close the Redis connection and stop Fake Redis if running."""
        if self._pool:
            await self._pool.disconnect()
            LOG.info("Redis connection pool closed")
        self._pool = None
        self.stop_fake_redis_server()

    async def client(self, use_single_connection: bool = False) -> AsyncRedis:
        """Get a Redis client.

        Parameters
        ----------
        use_single_connection : bool, optional
            Whether to use a single connection, by default False.
            If True, a new connection is created and not returned to the pool.

        Returns
        -------
        AsyncRedis
            Redis client instance.

        Raises
        RuntimeError
            If the Redis pool is not initialized.
        """
        if not self._pool:  # pragma: no cover
            self.setup()
        return a_redis.Redis(
            decode_responses=True,
            connection_pool=self._pool,
            single_connection_client=use_single_connection,
        )

    @asynccontextmanager
    async def contextual_client(
        self, use_single_connection: bool = False
    ) -> AsyncIterator[AsyncRedis]:
        """Get a Redis client as a context manager.

        Parameters
        ----------
        use_single_connection : bool
            Whether to use a dedicated connection.

        Yields
        ------
        AsyncIterator[AsyncRedis]
            A usable Redis client with auto-close logic if needed.
        """
        client = await self.client(use_single_connection=use_single_connection)
        try:
            yield client
        finally:
            if use_single_connection:
                await client.aclose()  # type: ignore

    def start_fake_redis_server(self, new_port: bool = False) -> str:
        """Start a Fake Redis server using TcpFakeServer.

        Parameters
        ----------
        new_port : bool, optional
            Whether to use a new port, by default False.
        Returns
        -------
        str
            The Redis connection URL (for Fake Redis or TcpFakeServer).

        Raises
        ------
        RuntimeError
            If the server cannot be started.
        """
        thread_lock = Lock()
        with thread_lock:
            if self._server_thread and self._server_thread.is_alive():
                LOG.debug("Fake Redis already running.")
                return self.redis_url
        port = self.settings.redis_port
        if not is_port_available(port) or new_port is True:
            port = get_available_port()
        scheme = "redis"
        host = "127.0.0.1"
        redis_db = self.settings.redis_db
        new_url = self.settings.generate_redis_url(
            scheme=scheme,
            host=host,
            port=port,
            db=redis_db,
            # on taskiq and / or FastStream broker we get:
            # invalid username-password pair or user is disabled
            password=None,
        )
        try:
            self._server = TcpFakeServer((host, port), server_type="redis")

            def thread_target() -> None:
                """Thread target to run the Fake Redis server."""
                # pylint: disable=broad-exception-caught
                if self._server:
                    try:
                        self._server.serve_forever()
                    except BaseException as error:  # pragma: no cover
                        LOG.debug("Fake Redis server error: %s", error)

            self._server_thread = Thread(
                target=thread_target,
                name="FakeRedisServerThread",
                daemon=True,
            )
            self._stop_event.clear()
            self._server_thread.start()
            LOG.info("Fake Redis server started at %s", new_url)
            self.redis_url = new_url
            self._pool = a_redis.ConnectionPool.from_url(
                new_url, decode_responses=True
            )
            return new_url
        except BaseException as e:
            LOG.error("Error starting Fake Redis server: %s", e)
            raise RuntimeError("Failed to start Fake Redis server") from e

    def stop_fake_redis_server(self) -> None:
        """Stop the Fake Redis server gracefully."""
        self._stop_event.set()
        if self._server:
            try:
                self._server.shutdown()
                LOG.info("Fake Redis server shutdown complete.")
            except Exception as e:
                LOG.warning("Failed to shut down fake Redis server: %s", e)

        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=1)
            if self._server_thread.is_alive():
                LOG.warning("Fake Redis thread is still alive after join!")

        self._server = None
        self._server_thread = None

    def is_using_fake_redis(self) -> bool:
        """Check if Fake Redis is being used.

        Returns
        -------
        bool
            Whether Fake Redis is being used.
        """
        return (
            self._server is not None
            and self._server_thread is not None
            and self._server_thread.is_alive()
            and self._stop_event.is_set() is False
        )


def skip_redis() -> bool:
    """Check if we should use an InMemory broker and a Dummy result backend.

    Returns
    -------
    bool
        Whether to skip using Redis.
    """
    if os.environ.get(f"{ENV_PREFIX}TESTING", "false").lower() in TRUTHY:
        return True
    if os.environ.get(f"{ENV_PREFIX}NO_REDIS", "false").lower() in TRUTHY:
        return True
    if os.environ.get(f"{ENV_PREFIX}REDIS", "true").lower() in TRUTHY:
        return False
    settings = SettingsManager.load_settings()
    if settings.get_redis_url() is None:
        return not in_container()
    return False


REDIS_MANAGER = RedisManager(SettingsManager.load_settings(), skip_setup=True)
