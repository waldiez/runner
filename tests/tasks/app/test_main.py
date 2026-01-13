# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-type-doc,missing-return-doc
# pylint: disable=missing-yield-doc,unused-argument
"""Test waldiez_runner.tasks.app.cli.*."""

import json
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
@patch(f"{MODULE_TO_PATCH}.a_redis")
async def test_run_success(
    mock_redis: MagicMock,
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
    pool = MagicMock(name="pool")
    mock_redis.ConnectionPool.from_url.return_value = pool
    client = AsyncMock(name="redis_client")
    mock_redis.Redis.return_value = client
    client.publish.return_value = 1

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

    assert client.publish.await_count == 2
    msg = json.loads(client.publish.call_args[0][1])
    assert msg["status"] == "COMPLETED"


# noinspection PyUnusedLocal
@pytest.mark.asyncio
@patch(f"{MODULE_TO_PATCH}.FlowRunner")
@patch(f"{MODULE_TO_PATCH}.RedisBroker")
@patch(f"{MODULE_TO_PATCH}.FastStream")
@patch(f"{MODULE_TO_PATCH}.a_redis")
async def test_run_failure(
    mock_redis: MagicMock,
    mock_app: MagicMock,
    mock_broker: MagicMock,
    mock_runner: MagicMock,
    tmp_path: Path,
) -> None:
    """Test the run function with a failed flow."""
    test_file = tmp_path / "file.waldiez"
    test_file.write_text("dummy")
    test_file_path = str(test_file)
    pool = MagicMock(name="pool")
    mock_redis.ConnectionPool.from_url.return_value = pool
    client = AsyncMock(name="redis_client")
    mock_redis.Redis.return_value = client
    client.publish.return_value = 1
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

    assert client.publish.await_count == 2
    msg = json.loads(client.publish.call_args[0][1])
    assert msg["status"] == "FAILED"
