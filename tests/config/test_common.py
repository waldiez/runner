# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Test waldiez_runner.config._common."""
# pylint: disable=missing-return-doc,missing-param-doc,missing-yield-doc

import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

# noinspection PyProtectedMember
from waldiez_runner.config._common import ENV_PREFIX, get_value

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


def test_get_value() -> None:
    """Test get_value."""
    os.environ[f"{ENV_PREFIX}TEST"] = "test"
    assert get_value("--test", "TEST", str, "default") == "test"

    os.environ[f"{ENV_PREFIX}TEST"] = "1"
    assert get_value("--test", "TEST", bool, False) is True


def test_get_value_no_env() -> None:
    """Test get_value with no environment variable."""
    assert get_value("--test", "TEST", str, "default") == "default"

    assert get_value("--test", "TEST", bool, False) is False

    assert get_value("--test", "TEST", int, 0) == 0

    assert get_value("--test", "TEST", float, 0.0) == 0.0

    os.environ[f"{ENV_PREFIX}TEST"] = ""
    assert get_value("--test", "TEST", str, "default") == "default"
