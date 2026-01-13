# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

"""Tests for the logging configuration."""
# pylint: disable=missing-return-doc,missing-param-doc,missing-raises-doc

import os
import sys
from typing import Any
from unittest.mock import patch

import pytest

# noinspection PyProtectedMember
from waldiez_runner._logging import (
    ENV_PREFIX,
    get_log_level,
    get_logging_config,
)


@pytest.fixture(name="mock_logging_config")
def mock_logging_config_fixture() -> dict[str, Any]:
    """Fixture to mock the uvicorn logging configuration."""
    return {
        "formatters": {"default": {"fmt": "%(message)s"}},
        "loggers": {
            "uvicorn": {"level": "DEBUG", "handlers": []},
            "uvicorn.error": {"level": "DEBUG", "handlers": []},
            "uvicorn.access": {"level": "DEBUG", "handlers": []},
        },
    }


def test_get_logging_config(mock_logging_config: dict[str, Any]) -> None:
    """Test the get_logging_config function."""
    with patch("uvicorn.config.LOGGING_CONFIG", mock_logging_config):
        log_level = "WARNING"
        config = get_logging_config(log_level)
        assert (
            config["formatters"]["default"]["fmt"]
            == "%(levelprefix)s %(asctime)s.%(msecs)06d [%(name)s:%(filename)s:%(lineno)d] %(message)s"  # pylint: disable=line-too-long # noqa: E501
        )
        assert config["formatters"]["default"]["datefmt"] == "%Y-%m-%d %H:%M:%S"
        assert config["loggers"]["uvicorn"]["level"] == log_level
        assert config["loggers"]["uvicorn.error"]["level"] == log_level
        assert config["loggers"]["uvicorn.access"]["level"] == log_level
        assert "httpx" in config["loggers"]
        httpx_logger = config["loggers"]["httpx"]
        assert httpx_logger["handlers"] == ["default"]
        assert httpx_logger["level"] == "INFO"
        assert "httpcore" in config["loggers"]
        httpcore_logger = config["loggers"]["httpcore"]
        assert httpcore_logger["handlers"] == ["default"]
        assert httpcore_logger["level"] == "INFO"
        for module in [
            "watchgod",
            "httpcore",
            "httpx",
        ]:
            assert module in config["loggers"]
            module_logger = config["loggers"][module]
            assert module_logger["level"] == "INFO"
            assert module_logger["handlers"] == ["default"]
            assert module_logger["propagate"] is False

        root_logger = config["loggers"][""]
        assert root_logger["level"] == log_level
        assert root_logger["handlers"] == ["default"]
        assert root_logger["propagate"] is False


def test_get_log_level() -> None:
    """Test get_log_level."""
    os.environ[f"{ENV_PREFIX}LOG_LEVEL"] = "DEBUG"
    assert get_log_level() == "DEBUG"

    os.environ.pop(f"{ENV_PREFIX}LOG_LEVEL", "INVALID")
    assert get_log_level() == "INFO"

    sys.argv = ["test_lib.py", "--debug"]
    assert get_log_level() == "DEBUG"

    sys.argv = ["test_lib.py", "--log-level", "WARNING"]
    assert get_log_level() == "WARNING"

    os.environ.pop(f"{ENV_PREFIX}LOG_LEVEL", None)
    sys.argv = ["test_lib.py", "--log-level"]
    assert get_log_level() == "INFO"

    os.environ.pop(f"{ENV_PREFIX}LOG_LEVEL", None)
    sys.argv = ["test_lib.py", "--log-level", "INVALID"]
    assert get_log_level() == "INFO"

    sys.argv = ["test_lib.py"]
    os.environ.pop(f"{ENV_PREFIX}LOG_LEVEL", None)
    os.environ[f"{ENV_PREFIX}LOG_LEVEL"] = "INVALID"
    assert get_log_level() == "INFO"

    sys.argv = ["test_lib.py"]
    os.environ.pop(f"{ENV_PREFIX}LOG_LEVEL", None)
    assert get_log_level() == "INFO"
