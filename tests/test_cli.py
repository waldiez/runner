# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-param-doc,unused-argument

"""Test waldiez_runner.cli.*."""

import subprocess  # nosemgrep # nosec
import sys
from typing import List
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from waldiez_runner._version import __version__
from waldiez_runner.cli import app

MODULE_TO_PATCH = "waldiez_runner.cli"

runner = CliRunner()


def get_valid_args() -> List[str]:
    """Get valid arguments.

    Returns
    -------
    List[str]
        Valid cli arguments to start the server.
    """
    secret_key = "1234" * 32
    client_id = "1234" * 16
    client_secret = "1234" * 32
    return [
        "--secret-key",
        secret_key,
        "--local-client-id",
        client_id,
        "--local-client-secret",
        client_secret,
    ]


def test_version() -> None:
    """Test version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_python_m() -> None:
    """Test python3 -m."""
    # just to cover __main__.py
    result = subprocess.run(
        [sys.executable, "-m", "waldiez_runner", "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert __version__ in result.stdout.decode()
    assert result.returncode == 0


def test_help() -> None:
    """Test help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_invalid_log_level() -> None:
    """Test invalid log level."""
    result = runner.invoke(app, ["--log-level", "invalid"] + get_valid_args())
    assert result.exit_code != 0


@patch(f"{MODULE_TO_PATCH}.start_uvicorn")
def test_trusted_hosts(mock_start_uvicorn: MagicMock) -> None:
    """Test trusted hosts."""
    result = runner.invoke(
        app, ["--trusted-hosts", "example.com"] + get_valid_args()
    )
    assert result.exit_code == 0


@patch(f"{MODULE_TO_PATCH}.start_uvicorn")
def test_trusted_hosts_empty(mock_start_uvicorn: MagicMock) -> None:
    """Test trusted hosts."""
    result = runner.invoke(app, ["--trusted-hosts", ""] + get_valid_args())
    assert result.exit_code == 0


@patch(f"{MODULE_TO_PATCH}.start_all")
def test_dev_mode(mock_start_all: MagicMock) -> None:
    """Test dev mode."""
    result = runner.invoke(app, ["--all"] + get_valid_args())
    assert result.exit_code == 0


@patch(f"{MODULE_TO_PATCH}.start_broker_and_scheduler")
def test_worker_mode(mock_start_broker_and_scheduler: MagicMock) -> None:
    """Test worker mode."""
    result = runner.invoke(app, ["--worker"] + get_valid_args())
    assert result.exit_code == 0


@patch(f"{MODULE_TO_PATCH}.start_broker")
def test_broker_mode(mock_start_broker: MagicMock) -> None:
    """Test broker mode."""
    result = runner.invoke(app, ["--broker"] + get_valid_args())
    assert result.exit_code == 0


@patch(f"{MODULE_TO_PATCH}.start_scheduler")
def test_scheduler_mode(mock_start_scheduler: MagicMock) -> None:
    """Test scheduler mode."""
    result = runner.invoke(app, ["--scheduler"] + get_valid_args())
    assert result.exit_code == 0


@patch(f"{MODULE_TO_PATCH}.start_broker_and_scheduler")
def test_broker_and_scheduler(
    mock_start_broker_and_scheduler: MagicMock,
) -> None:
    """Test broker and scheduler."""
    result = runner.invoke(app, ["--broker", "--scheduler"] + get_valid_args())
    assert result.exit_code == 0


@patch(f"{MODULE_TO_PATCH}.start_uvicorn")
def test_default_run(mock_start_uvicorn: MagicMock) -> None:
    """Test default run."""
    result = runner.invoke(
        app,
        get_valid_args(),
    )
    assert result.exit_code == 0


@patch(f"{MODULE_TO_PATCH}.start_uvicorn")
def test_trusted_origins(mock_start_uvicorn: MagicMock) -> None:
    """Test trusted origins."""
    result = runner.invoke(
        app, ["--trusted-origins", "example.com"] + get_valid_args()
    )
    assert result.exit_code == 0


@patch(f"{MODULE_TO_PATCH}.start_uvicorn")
def test_trusted_origins_empty(mock_start_uvicorn: MagicMock) -> None:
    """Test trusted origins."""
    result = runner.invoke(app, ["--trusted-origins", ""] + get_valid_args())
    assert result.exit_code == 0
