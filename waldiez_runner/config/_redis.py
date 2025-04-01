# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Redis related configuration.

Environment variables (with prefix WALDIEZ_RUNNER_)
---------------------------------------------------
REDIS (bool) # default: True
REDIS_HOST (str) # default: redis if in container else localhost
REDIS_PORT (int) # default: 6379
REDIS_SCHEME (str) # default: redis
REDIS_PASSWORD (str) # default: redis_password
REDIS_DB (int) # default: 0
REDIS_URL (str) # default: None (auto-generated)

Command line arguments (no prefix)
----------------------------------
--redis|--no-redis (bool)
--redis-host (str)
--redis-port (int)
--redis-scheme (str)
--redis-password (str)
--redis-db (int)
--redis-url (str)
"""

import os
import sys
from enum import Enum
from typing import Literal

from ._common import ENV_PREFIX, get_value, in_container, is_testing


class RedisScheme(str, Enum):
    """The Redis scheme type."""

    REDIS = "redis"
    REDISS = "rediss"
    UNIX = "unix"


RedisSchemeType = Literal["redis", "rediss", "unix"]
"""Possible Redis schemes."""


def get_redis_enabled() -> bool:
    """Get whether Redis is enabled.

    Returns
    -------
    bool
        Whether Redis is enabled
    """
    value = get_value("--redis", "REDIS", bool, True)
    if (
        value is False
        and in_container()
        and "--no-redis" not in sys.argv
        and not is_testing()
    ):
        os.environ[f"{ENV_PREFIX}REDIS"] = "true"
    return value


def get_redis_host() -> str:
    """Get the Redis host.

    Returns
    -------
    str
        The Redis host
    """
    fallback = "redis" if in_container() else "localhost"
    return get_value("--redis-host", "REDIS_HOST", str, fallback)


def get_redis_port() -> int:
    """Get the Redis port.

    Returns
    -------
    int
        The Redis port
    """
    return get_value("--redis-port", "REDIS_PORT", int, 6379)


def get_redis_scheme() -> RedisSchemeType:
    """Get the Redis scheme.

    Returns
    -------
    RedisSchemeType
        The Redis scheme
    """
    allowed_schemes = ["redis", "rediss", "unix"]
    value = get_value("--redis-scheme", "REDIS_SCHEME", str, "redis")
    if value not in allowed_schemes:
        value = "redis"
        os.environ[f"{ENV_PREFIX}REDIS_SCHEME"] = value
    return value  # type: ignore


def get_redis_password() -> str | None:
    """Get the Redis password.

    Returns
    -------
    str | None
        The Redis password
    """
    value: str | None = get_value(
        "--redis-password", "REDIS_PASSWORD", str, "redis_password"
    )
    if os.environ.get(f"{ENV_PREFIX}REDIS_PASSWORD") == "":
        value = None
    return value


def get_redis_db() -> int:
    """Get the Redis DB index.

    Returns
    -------
    int
        The Redis DB index
    """
    return get_value("--redis-db", "REDIS_DB", int, 0)


def get_redis_url() -> str | None:
    """Get the Redis URL.

    Returns
    -------
    str | None
        The Redis URL
    """
    value = get_value("--redis-url", "REDIS_URL", str, None)
    return value if value else None
