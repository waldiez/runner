# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Test waldiez_runner.config._redis."""
# pylint: disable=missing-return-doc,missing-param-doc,missing-yield-doc

import os
import sys
from pathlib import Path
from typing import Generator

import pytest

# noinspection PyProtectedMember
from waldiez_runner.config._common import ENV_PREFIX

# noinspection PyProtectedMember
from waldiez_runner.config._redis import (
    get_redis_db,
    get_redis_enabled,
    get_redis_host,
    get_redis_password,
    get_redis_port,
    get_redis_scheme,
    get_redis_url,
)

# noinspection DuplicatedCode
THIS_FILE = Path(__file__).resolve()


@pytest.fixture(scope="function", autouse=True, name="clear_env")
def clear_env_and_args() -> Generator[None, None, None]:
    """Clear environment variables and command-line arguments."""
    for var in os.environ:
        if var.startswith(ENV_PREFIX):
            os.environ.pop(var, None)
    original_argv = sys.argv[:]
    sys.argv = [str(THIS_FILE)]
    yield
    sys.argv = original_argv


def test_get_redis_enabled_no_env() -> None:
    """Test get_redis_enabled with no environment variables."""
    assert get_redis_enabled() is True


def test_get_redis_enabled_with_env() -> None:
    """Test get_redis_enabled with environment variables."""
    os.environ[f"{ENV_PREFIX}REDIS"] = "False"
    assert get_redis_enabled() is False


def test_get_redis_enabled_from_cli() -> None:
    """Test get_redis_enabled from command-line arguments."""
    sys.argv.append("--redis")
    assert get_redis_enabled() is True

    sys.argv.remove("--redis")
    sys.argv.append("--no-redis")
    assert get_redis_enabled() is False


def test_get_redis_host_no_env() -> None:
    """Test get_redis_host with no environment variables."""
    assert get_redis_host() in ("localhost", "redis")  # container or not


def test_get_redis_host_with_env() -> None:
    """Test get_redis_host with environment variables."""
    os.environ[f"{ENV_PREFIX}REDIS_HOST"] = "redis-host"
    assert get_redis_host() == "redis-host"


def test_get_redis_host_from_cli() -> None:
    """Test get_redis_host from command-line arguments."""
    sys.argv.extend(["--redis-host", "cli-host"])
    assert get_redis_host() == "cli-host"
    os.environ.pop(f"{ENV_PREFIX}REDIS_HOST", None)

    # Test with no host in args
    sys.argv.remove("cli-host")
    assert get_redis_host() in ("localhost", "redis")  # container or not


def test_get_redis_port_from_cli() -> None:
    """Test get_redis_port from command-line arguments."""
    sys.argv.extend(["--redis-port", "1234"])
    assert get_redis_port() == 1234
    os.environ.pop(f"{ENV_PREFIX}REDIS_PORT", None)

    # Test with no port in args
    sys.argv.remove("1234")
    assert get_redis_port() == 6379


def test_get_redis_port_from_env() -> None:
    """Test get_redis_port from environment variables."""
    os.environ[f"{ENV_PREFIX}REDIS_PORT"] = "1234"
    assert get_redis_port() == 1234

    # Test with no port in env
    os.environ.pop(f"{ENV_PREFIX}REDIS_PORT")
    assert get_redis_port() == 6379


def test_get_redis_port_no_env() -> None:
    """Test get_redis_port with no environment variables."""
    assert get_redis_port() == 6379


def test_get_redis_scheme_no_env() -> None:
    """Test get_redis_scheme with no environment variables."""
    assert get_redis_scheme() == "redis"


def test_get_redis_scheme_with_env() -> None:
    """Test get_redis_scheme with environment variables."""
    os.environ[f"{ENV_PREFIX}REDIS_SCHEME"] = "rediss"
    assert get_redis_scheme() == "rediss"


def test_get_redis_scheme_from_cli() -> None:
    """Test get_redis_scheme from command-line arguments."""
    sys.argv.extend(["--redis-scheme", "unix"])
    assert get_redis_scheme() == "unix"

    # Test with no scheme in args
    sys.argv.remove("--redis-scheme")
    os.environ.pop(f"{ENV_PREFIX}REDIS_SCHEME", None)
    assert get_redis_scheme() == "redis"


def test_get_redis_scheme_invalid() -> None:
    """Test get_redis_scheme with invalid scheme."""
    os.environ[f"{ENV_PREFIX}REDIS_SCHEME"] = "invalid"
    assert get_redis_scheme() == "redis"


def test_get_redis_password_no_env() -> None:
    """Test get_redis_password with no environment variables."""
    assert get_redis_password() == "redis_password"


def test_get_redis_password_with_env() -> None:
    """Test get_redis_password with environment variables."""
    os.environ[f"{ENV_PREFIX}REDIS_PASSWORD"] = "password"
    assert get_redis_password() == "password"

    os.environ.pop(f"{ENV_PREFIX}REDIS_PASSWORD", None)
    os.environ[f"{ENV_PREFIX}REDIS_PASSWORD"] = ""
    assert get_redis_password() is None


def test_get_redis_password_from_cli() -> None:
    """Test get_redis_password from command-line arguments."""
    sys.argv.extend(["--redis-password", "cli-password"])
    assert get_redis_password() == "cli-password"

    # Test with no password in args
    os.environ.pop(f"{ENV_PREFIX}REDIS_PASSWORD", None)
    sys.argv.remove("cli-password")
    assert get_redis_password() == "redis_password"


def test_get_redis_db_no_env() -> None:
    """Test get_redis_db with no environment variables."""
    assert get_redis_db() == 0


def test_get_redis_db_with_env() -> None:
    """Test get_redis_db with environment variables."""
    os.environ[f"{ENV_PREFIX}REDIS_DB"] = "1"
    assert get_redis_db() == 1


def test_get_redis_db_from_cli() -> None:
    """Test get_redis_db from command-line arguments."""
    sys.argv.extend(["--redis-db", "2"])
    assert get_redis_db() == 2

    # Test with no db in args
    os.environ.pop(f"{ENV_PREFIX}REDIS_DB", None)
    sys.argv.remove("2")
    assert get_redis_db() == 0


def test_get_redis_url_no_env() -> None:
    """Test get_redis_url with no environment variables."""
    assert get_redis_url() is None


def test_get_redis_url_with_env() -> None:
    """Test get_redis_url with environment variables."""
    os.environ[f"{ENV_PREFIX}REDIS_URL"] = "redis://localhost:6379/0"
    assert get_redis_url() == "redis://localhost:6379/0"


def test_get_redis_url_from_cli() -> None:
    """Test get_redis_url from command-line arguments."""
    sys.argv.extend(["--redis-url", "redis://cli-host:1234/1"])
    assert get_redis_url() == "redis://cli-host:1234/1"

    # Test with no URL in args
    os.environ.pop(f"{ENV_PREFIX}REDIS_URL", None)
    sys.argv.remove("redis://cli-host:1234/1")
    assert get_redis_url() is None
