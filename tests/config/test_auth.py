# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Test waldiez_runner.config._auth."""
# pylint: disable=missing-return-doc,missing-param-doc,missing-yield-doc

import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

# noinspection PyProtectedMember
from waldiez_runner.config import ENV_PREFIX, _auth

THIS_FILE = Path(__file__).resolve()


@pytest.fixture(scope="module", autouse=True, name="clear_env")
def clear_env_and_args() -> Generator[None, None, None]:
    """Clear environment variables and command-line arguments."""
    env_keys = (
        "USE_LOCAL_AUTH",
        "LOCAL_CLIENT_ID",
        "LOCAL_CLIENT_SECRET",
    )
    original_envs = {
        key: os.environ.pop(key) for key in env_keys if key in os.environ
    }
    original_argv = sys.argv[:]
    sys.argv = [str(THIS_FILE)]
    yield
    for key, value in original_envs.items():
        os.environ[key] = value
    sys.argv = original_argv


def test_get_use_local_auth_no_env() -> None:
    """Test get_use_local_auth with no environment variables."""
    os.environ.pop(f"{ENV_PREFIX}USE_LOCAL_AUTH", None)
    assert _auth.get_use_local_auth() is True


def test_get_use_local_auth_with_env() -> None:
    """Test get_use_local_auth with environment variables."""
    os.environ[f"{ENV_PREFIX}USE_LOCAL_AUTH"] = "False"
    assert _auth.get_use_local_auth() is False


def test_get_use_local_auth_from_cli() -> None:
    """Test get_use_local_auth from command-line arguments."""
    sys.argv.append("--use-local-auth")
    assert _auth.get_use_local_auth() is True

    sys.argv.remove("--use-local-auth")
    sys.argv.append("--no-use-local-auth")
    assert _auth.get_use_local_auth() is False


def test_get_local_client_id_no_env() -> None:
    """Test get_local_client_id with no environment variables."""
    assert _auth.get_local_client_id() == "REPLACE_ME"


def test_get_local_client_id_with_env() -> None:
    """Test get_local_client_id with environment variables."""
    os.environ[f"{ENV_PREFIX}LOCAL_CLIENT_ID"] = "test-client-id"
    assert _auth.get_local_client_id() == "test-client-id"


def test_get_local_client_id_from_cli() -> None:
    """Test get_local_client_id from command-line arguments."""
    sys.argv.append("--local-client-id")
    sys.argv.append("test-client-id")
    assert _auth.get_local_client_id() == "test-client-id"


def test_get_local_client_secret_no_env() -> None:
    """Test get_local_client_secret with no environment variables."""
    assert _auth.get_local_client_secret() == "REPLACE_ME"


def test_get_local_client_secret_with_env() -> None:
    """Test get_local_client_secret with environment variables."""
    os.environ[f"{ENV_PREFIX}LOCAL_CLIENT_SECRET"] = "test-client-secret"
    assert _auth.get_local_client_secret() == "test-client-secret"
