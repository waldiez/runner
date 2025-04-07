# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-type-doc,missing-return-doc
# pylint: disable=missing-yield-doc,unused-argument
"""Test waldiez_runner.tasks.app.cli.*."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from waldiez_runner.tasks.app.cli import TaskParams
from waldiez_runner.tasks.app.main import run

MODULE_TO_PATCH = "waldiez_runner.tasks.app.main"


@pytest.mark.asyncio
@patch(f"{MODULE_TO_PATCH}.FlowRunner")
@patch(f"{MODULE_TO_PATCH}.RedisBroker")
@patch(f"{MODULE_TO_PATCH}.FastStream")
async def test_run_success(
    mock_app: MagicMock,
    mock_broker: MagicMock,
    mock_runner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test the run function with a successful flow."""
    test_file = tmp_path / "file.waldiez"
    test_file.write_text("dummy")
    test_file_path = str(test_file)
    runner_instance = mock_runner.return_value
    runner_instance.run = AsyncMock(return_value={"result": "ok"})

    broker = mock_broker.return_value
    broker.publish = AsyncMock()

    app = mock_app.return_value
    app.start = AsyncMock()
    app.stop = AsyncMock()

    params = TaskParams(
        file_path=test_file_path,
        task_id="task123",
        redis_url="redis://localhost:6379/0",
        input_timeout=5,
    )

    with patch(
        f"{MODULE_TO_PATCH}.FlowRunner.validate_flow",
        return_value={"flow": "data"},
    ):
        await run(params)

    broker.publish.assert_called_once()
    assert broker.publish.call_args[0][1] == "task:task123:status"
    assert "COMPLETED" in broker.publish.call_args[0][0]


@pytest.mark.asyncio
@patch(f"{MODULE_TO_PATCH}.FlowRunner")
@patch(f"{MODULE_TO_PATCH}.RedisBroker")
@patch(f"{MODULE_TO_PATCH}.FastStream")
async def test_run_failure(
    mock_app: MagicMock,
    mock_broker: MagicMock,
    mock_runner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test the run function with a failed flow."""
    test_file = tmp_path / "file.waldiez"
    test_file.write_text("dummy")
    test_file_path = str(test_file)
    broker = mock_broker.return_value
    broker.publish = AsyncMock()
    app = mock_app.return_value
    app.start = AsyncMock()
    app.stop = AsyncMock()

    params = TaskParams(
        file_path=test_file_path,
        task_id="task123",
        redis_url="redis://localhost:6379/0",
        input_timeout=5,
    )

    with patch(
        f"{MODULE_TO_PATCH}.FlowRunner.validate_flow",
        side_effect=ValueError("bad flow"),
    ):
        await run(params)

    assert broker.publish.call_args
    assert "FAILED" in broker.publish.call_args[0][0]
