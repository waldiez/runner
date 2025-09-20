# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Test waldiez_runner.config._auth."""
# pylint: disable=missing-return-doc,missing-param-doc,missing-yield-doc

import os
import sys
from pathlib import Path
from typing import Generator

import pytest

# noinspection PyProtectedMember
from waldiez_runner.config import ENV_PREFIX, _tasks

THIS_FILE = Path(__file__).resolve()


@pytest.fixture(scope="module", autouse=True, name="clear_env")
def clear_env_and_args() -> Generator[None, None, None]:
    """Clear environment variables and command-line arguments."""
    env_keys = (
        "INPUT_TIMEOUT",
        "KEEP_TASKS_FOR_DAYS",
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


def test_get_input_timeout_no_env() -> None:
    """Test get_input_timeout with no environment variables."""
    os.environ.pop(f"{ENV_PREFIX}INPUT_TIMEOUT", None)
    assert _tasks.get_input_timeout() == _tasks.DEFAULT_INPUT_TIMEOUT


def test_get_input_timeout_with_env() -> None:
    """Test get_input_timeout with environment variables."""
    os.environ[f"{ENV_PREFIX}INPUT_TIMEOUT"] = "30"
    assert _tasks.get_input_timeout() == 30


def test_get_input_timeout_from_cli() -> None:
    """Test get_input_timeout from cli arg."""
    sys.argv.extend(["--input-timeout", "60"])
    assert _tasks.get_input_timeout() == 60


def test_get_keep_task_for_days_no_env() -> None:
    """Test get_keep_task_for_days with no environment variables."""
    os.environ.pop(f"{ENV_PREFIX}KEEP_TASKS_FOR_DAYS", None)
    assert _tasks.get_keep_task_for_days() == _tasks.DEFAULT_DAYS_TO_KEEP_TASKS


def test_get_keep_task_for_days_with_env() -> None:
    """Test get_keep_task_for_days with environment variables."""
    os.environ[f"{ENV_PREFIX}KEEP_TASKS_FOR_DAYS"] = "31"
    assert _tasks.get_keep_task_for_days() == 31


def test_get_keep_task_for_days_from_cli() -> None:
    """Test get_keep_task_for_days from cli arg."""
    sys.argv.extend(["--keep-tasks-for-days", "61"])
    assert _tasks.get_keep_task_for_days() == 61
