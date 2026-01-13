# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-param-doc
"""Test waldiez_runner.start.*."""

import os
import signal
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

# noinspection PyProtectedMember
from waldiez_runner._logging import LogLevel
from waldiez_runner.start import (
    get_module_and_cwd,
    run_process,
    start_all,
    start_broker,
    start_broker_and_scheduler,
    start_scheduler,
    start_uvicorn,
)

MODULE_TO_PATCH = "waldiez_runner.start"


def test_get_module_and_cwd() -> None:
    """Test get_module_and_cwd."""
    module_name, cwd = get_module_and_cwd()
    assert isinstance(module_name, str)
    assert isinstance(cwd, str)


@patch(f"{MODULE_TO_PATCH}.subprocess.Popen")
def test_run_process(mock_popen: MagicMock, tmp_path: Path) -> None:
    """Test run_process."""
    mock_process = MagicMock()
    mock_popen.return_value = mock_process

    command = ["echo", "hello"]
    cwd = str(tmp_path)
    process = run_process(command, cwd)

    mock_popen.assert_called_once_with(
        command,
        cwd=cwd,
        env=os.environ,
    )
    assert process == mock_process


@patch(f"{MODULE_TO_PATCH}.run_process")
def test_start_broker(mock_run_process: MagicMock) -> None:
    """Test start_broker."""
    mock_process = MagicMock()
    mock_run_process.return_value = mock_process

    start_broker(reload=True, log_level=LogLevel.INFO, skip_redis=True)

    mock_run_process.assert_called_once()
    mock_process.wait.assert_called_once()


@patch(f"{MODULE_TO_PATCH}.run_process")
def test_start_scheduler(mock_run_process: MagicMock) -> None:
    """Test start_scheduler."""
    mock_process = MagicMock()
    mock_run_process.return_value = mock_process

    start_scheduler(log_level=LogLevel.INFO, skip_redis=True)

    mock_run_process.assert_called_once()
    mock_process.wait.assert_called_once()


@patch(f"{MODULE_TO_PATCH}.run_process")
def test_start_broker_and_scheduler(mock_run_process: MagicMock) -> None:
    """Test start_broker_and_scheduler."""
    mock_worker_process = MagicMock()
    mock_scheduler_process = MagicMock()
    mock_run_process.side_effect = [mock_worker_process, mock_scheduler_process]

    start_broker_and_scheduler(
        reload=True, log_level=LogLevel.DEBUG, skip_redis=True
    )

    assert mock_run_process.call_count == 2
    mock_worker_process.wait.assert_called_once()
    mock_scheduler_process.wait.assert_called_once()


@patch(f"{MODULE_TO_PATCH}.sys.exit")
@patch(f"{MODULE_TO_PATCH}.signal.signal")
@patch(f"{MODULE_TO_PATCH}.subprocess.Popen")
def test_start_all(
    mock_popen: MagicMock,
    mock_signal: MagicMock,
    mock_sys_exit: MagicMock,
) -> None:
    """Test start_all."""
    mock_uvicorn_process = MagicMock()
    mock_worker_process = MagicMock()
    mock_scheduler_process = MagicMock()

    mock_popen.side_effect = [
        mock_uvicorn_process,
        mock_worker_process,
        mock_scheduler_process,
    ]

    start_all(
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level=LogLevel.INFO,
        skip_redis=True,
    )

    # Assert three processes are started
    assert mock_popen.call_count == 3
    mock_uvicorn_process.wait.assert_called_once()
    mock_worker_process.wait.assert_called_once()
    mock_scheduler_process.wait.assert_called_once()

    # Signal handlers registered
    mock_signal.assert_any_call(signal.SIGINT, mock.ANY)
    mock_signal.assert_any_call(signal.SIGTERM, mock.ANY)

    # Should not exit immediately
    mock_sys_exit.assert_not_called()


@patch(f"{MODULE_TO_PATCH}.uvicorn.run")
def test_start_uvicorn(mock_uvicorn_run: MagicMock) -> None:
    """Test start_uvicorn."""
    start_uvicorn(
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level=LogLevel.INFO,
        logging_config={},
    )
    mock_uvicorn_run.assert_called_once()
