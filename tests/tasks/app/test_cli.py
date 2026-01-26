# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-type-doc,missing-return-doc
# pylint: disable=missing-yield-doc
"""Test waldiez_runner.tasks.app.cli.*."""

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from waldiez_runner.tasks.app.cli import (
    DEFAULT_INPUT_TIMEOUT,
    TaskParams,
    get_parser,
    parse_args,
)


def test_valid_params(tmp_path: Path) -> None:
    """Test valid parameters for TaskParams."""
    test_file = tmp_path / "file.waldiez"
    test_file.write_text("dummy")

    params = TaskParams(
        file_path=str(test_file),
        task_id="123",
        redis_url="redis://localhost:6379/0",
        input_timeout=10,
    )
    assert params.task_id == "123"


@pytest.mark.parametrize(
    "file_path, task_id, redis_url, timeout, expected",
    [
        ("missing.waldiez", "123", "redis://", 10, "does not exist"),
        ("test.waldiez", "", "redis://", 10, "Task ID cannot be empty"),
        ("test.waldiez", "123", "", 10, "Redis URL cannot be empty"),
        ("test.waldiez", "123", "redis://", 0, "must be greater than 0"),
    ],
)
def test_invalid_params(
    tmp_path: Path,
    file_path: str,
    task_id: str,
    redis_url: str,
    timeout: int,
    expected: str,
) -> None:
    """Test invalid parameters for TaskParams."""
    if not file_path.startswith("missing"):
        (tmp_path / file_path).write_text("dummy")
    with pytest.raises(ValueError, match=expected):
        TaskParams(
            file_path=str(tmp_path / file_path),
            task_id=task_id,
            redis_url=redis_url,
            input_timeout=timeout,
        )


def test_get_parser_returns_parser() -> None:
    """Test get_parser function returns an argparse.ArgumentParser."""
    parser = get_parser()
    assert isinstance(parser, argparse.ArgumentParser)


def test_from_args_valid(tmp_path: Path) -> None:
    """Test TaskParams.from_args with valid args."""
    file = tmp_path / "task.waldiez"
    file.write_text("dummy")

    args = SimpleNamespace(
        file=str(file),
        task_id="abc",
        redis_url="redis://localhost",
        input_timeout=120,
        debug=True,
        skip_deps=False,
    )
    params = TaskParams.from_args(args)  # type: ignore[arg-type]
    assert isinstance(params, TaskParams)
    assert params.debug is True
    assert params.input_timeout == 120


def test_from_args_applies_default_timeout(tmp_path: Path) -> None:
    """Test TaskParams.from_args with default timeout."""
    file = tmp_path / "task.waldiez"
    file.write_text("dummy")

    args = SimpleNamespace(
        file=str(file),
        task_id="abc",
        redis_url="redis://localhost",
        input_timeout=None,
        debug=False,
        skip_deps=False,
    )
    params = TaskParams.from_args(args)  # type: ignore[arg-type]
    assert params.input_timeout == DEFAULT_INPUT_TIMEOUT  # default fallback


@pytest.mark.parametrize(
    "extra_args",
    [
        [],
        ["--task-id", "x"],
        ["--task-id", "x", "--redis-url", "redis://localhost"],
        [
            "--task-id",
            "x",
            "--redis-url",
            "redis://localhost",
            "--input-timeout",
            "10",
        ],
    ],
)
def test_parse_args_missing(
    monkeypatch: pytest.MonkeyPatch,
    extra_args: list[str],
) -> None:
    """Test parse_args with missing positional arg."""
    monkeypatch.setattr(sys, "argv", ["prog"] + extra_args)
    with pytest.raises(SystemExit):  # argparse exits with error
        parse_args()


def test_parse_args_valid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test parse_args end-to-end with sys.argv."""
    file = tmp_path / "somefile.waldiez"
    file.write_text("dummy")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            str(file),
            "--task-id",
            "test123",
            "--redis-url",
            "redis://localhost",
            "--input-timeout",
            "999",
            "--debug",
            "--no-skip-deps",
        ],
    )
    params = parse_args()
    assert isinstance(params, TaskParams)
    assert params.task_id == "test123"
    assert params.redis_url == "redis://localhost"
    assert params.input_timeout == 999
    assert params.debug is True
