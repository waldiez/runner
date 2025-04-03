# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# mypy: ignore-errors
# pylint: disable=too-many-try-statements
# pylint: disable=broad-exception-caught, protected-access
"""Redis connection manager."""

import asyncio
import atexit
import logging
import os
from asyncio.locks import Lock
from threading import Event, Thread
from typing import TYPE_CHECKING

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
    Redis = redis.Redis[bytes]
    AsyncRedis = a_redis.Redis[bytes]
else:
    Redis = redis.Redis
    AsyncRedis = a_redis.Redis


LOG = logging.getLogger(__name__)


class RedisManager:
    """Redis connection manager with support for Fake Redis."""

    _client: AsyncRedis | None = None
    _lock = Lock()
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
        LOG.info("Using Redis at %s", redis_url)

    async def close(self) -> None:
        """Close the Redis connection and stop Fake Redis if running."""
        if self._client:
            if hasattr(self._client, "aclose"):
                await self._client.aclose()
            else:  # pragma: no cover
                await self._client.close()
            LOG.info("Redis connection closed.")
        self._client = None

        self._stop_fake_redis_server()

    async def client(
        self, retries: int = 3, backoff_factor: int = 2
    ) -> AsyncRedis:
        """Get a Redis client with retries.

        Parameters
        ----------
        retries : int, optional
            Number of retries in case of failure, by default 3.
        backoff_factor : int, optional
            Factor for exponential backoff, by default 2.

        Returns
        -------
        Redis
            Redis client instance.

        Raises
        ------
        ConnectionError
            If the Redis connection fails after all retries.
        RuntimeError
            If the client cannot be initialized.
        """
        if self._client is not None:
            return self._client  # Return existing client
        attempt = 0
        while attempt < retries:
            async with self._lock:
                try:
                    self._client = await a_redis.from_url(
                        self.redis_url, decode_responses=True
                    )
                    await self._client.ping()  # Test connection
                    LOG.info("Connected to Redis at %s", self.redis_url)
                    return self._client
                except ConnectionError as e:
                    attempt += 1
                    LOG.warning(
                        "Redis connection failed: %s. Retrying (%d/%d)...",
                        e,
                        attempt,
                        retries,
                    )
                    if attempt < retries:
                        await asyncio.sleep(backoff_factor**attempt)
                    else:
                        raise ConnectionError(
                            "Failed to connect to Redis."
                        ) from e
        raise RuntimeError("Could not connect to Redis")

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
        if (
            self._server is not None
            and self._server_thread is not None
            and self._server_thread.is_alive()
        ):
            LOG.warning("Fake Redis server is already running.")
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
            self._server = TcpFakeServer(  # type: ignore
                (host, port), server_type="redis"
            )

            def thread_target() -> None:
                """Thread target for starting the Fake Redis server.

                Ignoring exceptions, it's a fake server after all
                On shutdown, we might get race conditions, but that's ok
                """
                try:
                    self._server.serve_forever()  # type: ignore
                except BaseException:
                    pass

            self._server_thread = Thread(
                target=thread_target,
                daemon=True,
            )
            self._stop_event.clear()
            self._server_thread.start()
            atexit.register(self._stop_fake_redis_server)
            LOG.info("Fake Redis server started at %s", new_url)
            self.redis_url = new_url
            self._client = a_redis.from_url(new_url, decode_responses=True)
            return new_url
        except BaseException as e:
            LOG.error("Error starting Fake Redis server: %s", e)
            raise RuntimeError("Failed to start Fake Redis server") from e

    def _stop_fake_redis_server(self) -> None:
        """Stop the Fake Redis server gracefully."""
        if self._server and getattr(self._server, "_is_running", False) is True:
            try:
                self._stop_event.set()
                self._server.shutdown()
                self._server.server_close()
                LOG.info("Fake Redis server stopped.")
            except BaseException:
                pass
        if self._server_thread is not None and self._server_thread.is_alive():
            try:
                self._server_thread.join(timeout=1)
            except BaseException:
                pass
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
