# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-type-doc,missing-return-doc
# pylint: disable=missing-yield-doc,unused-argument
# pyright: reportUnknownArgumentType=false,reportUnknownLambdaType=false
"""Test waldiez_runner.tasks.app.flow_runner.*."""

from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from waldiez_runner.tasks.app.flow_runner import FlowRunner

MODULE_TO_PATCH = "waldiez_runner.tasks.app.flow_runner"


@pytest.mark.asyncio
async def test_run_async_flow_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the run method of FlowRunner with asynchronous flow."""
    waldiez = MagicMock()
    waldiez.is_async = True
    runner_mock = AsyncMock()
    runner_mock.a_run.return_value = [{"result": 42}]
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.WaldiezRunner", lambda _: runner_mock
    )
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.make_serializable_results",
        lambda x: x,
    )

    fr = FlowRunner("task1", "redis://...", waldiez, "out.py", 120)
    fr.io_stream = MagicMock()

    result = await fr.run()
    assert result == [{"result": 42}]
    runner_mock.a_run.assert_called_once()


@pytest.mark.asyncio
async def test_run_sync_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the run method of FlowRunner with synchronous flow."""
    waldiez = MagicMock()
    waldiez.is_async = False
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.make_serializable_results", lambda x: x
    )

    async def fake_to_thread(
        fn: Callable[[Any], Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Fake to_thread function."""
        return fn(*args, **kwargs)

    monkeypatch.setattr(f"{MODULE_TO_PATCH}.asyncio.to_thread", fake_to_thread)

    fr = FlowRunner("task1", "redis://...", waldiez, "out.py", 120)
    fr.run_sync = MagicMock(return_value=[{"result": "ok"}])  # type: ignore
    result = await fr.run()
    assert result == [{"result": "ok"}]
    fr.run_sync.assert_called_once()


def test_run_sync_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the run_sync method of FlowRunner with error handling."""
    waldiez = MagicMock()
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.make_serializable_results", lambda x: x
    )
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.WaldiezRunner",
        lambda _: MagicMock(run=MagicMock(side_effect=RuntimeError("Boom!"))),
    )

    fr = FlowRunner("task1", "redis://...", waldiez, "out.py", 120)
    results = fr.run_sync()
    assert "error" in results


def test_validate_flow_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the validate_flow method of FlowRunner."""
    mock_waldiez = MagicMock()
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.Waldiez.load", lambda _: mock_waldiez
    )
    assert FlowRunner.validate_flow("somefile") == mock_waldiez


def test_validate_flow_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the validate_flow method of FlowRunner with an error."""
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.Waldiez.load",
        lambda _: (_ for _ in ()).throw(Exception("Invalid!")),
    )
    with pytest.raises(ValueError):
        FlowRunner.validate_flow("bad_file")


def test_on_input_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the on_input_request method of FlowRunner."""
    fr = FlowRunner("task1", "redis://...", MagicMock(), "out.py")
    fr.io_stream.redis = MagicMock()
    fr.on_input_request("Enter your name", "req-1", "task1")
    fr.io_stream.redis.publish.assert_called()


def test_on_input_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the on_input_response method of FlowRunner."""
    fr = FlowRunner("task1", "redis://...", MagicMock(), "out.py")
    fr.io_stream.redis = MagicMock()
    fr.on_input_response("hello!", "task1")
    fr.io_stream.redis.publish.assert_called()
