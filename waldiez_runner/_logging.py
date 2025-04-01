# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Logging configuration module."""

import os
import sys
from enum import Enum
from typing import Any, Dict, Literal, Tuple, get_args

import uvicorn.config

ENV_PREFIX = "WALDIEZ_RUNNER_"


class LogLevel(str, Enum):
    """The log level type."""

    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


LogLevelType = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
"""Possible log levels."""


# fmt: off
def get_logging_config(log_level: str) -> Dict[str, Any]:
    """Get logging config dict.

    Parameters
    ----------
    log_level : str
        The log level

    Returns
    -------
    Dict[str, Any]
        The logging config dict
    """
    # skip spamming logs from these modules
    modules_to_have_level_info = [
        "watchgod",
        # "watchfiles",
        "httpcore",
        "httpx",
    ]
    modules_to_inherit_level = [
        "waldiez",
        "autogen",
        # "sqlalchemy",
        "watchfiles",
    ]
    logging_config = uvicorn.config.LOGGING_CONFIG
    logging_config["formatters"]["default"]["fmt"] = (
        "%(levelprefix)s %(asctime)s.%(msecs)06d [%(name)s:%(filename)s:%(lineno)d] %(message)s"  # pylint: disable=line-too-long # noqa: E501
    )
    logging_config["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    logging_config["loggers"]["uvicorn"]["level"] = log_level
    logging_config["loggers"]["uvicorn.error"]["level"] = log_level
    logging_config["loggers"]["uvicorn.access"]["level"] = log_level
    httpx_logger = logging_config["loggers"].get("httpx", {})
    logging_config["loggers"]["httpx"] = httpx_logger
    logging_config["loggers"]["httpx"]["level"] = log_level
    logging_config["loggers"]["httpx"]["handlers"] = ["default"]
    http_core_logger = logging_config["loggers"].get("httpcore", {})
    logging_config["loggers"]["httpcore"] = http_core_logger
    logging_config["loggers"]["httpcore"]["handlers"] = ["default"]
    logging_config["loggers"]["httpcore"]["level"] = log_level
    for module in modules_to_have_level_info:
        logging_config["loggers"][module] = {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        }
    logging_config["loggers"][""] = {
        "handlers": ["default"],
        "level": log_level,
        "propagate": False,
    }
    for module in modules_to_inherit_level:
        logging_config["loggers"][module] = {
            "handlers": ["default"],
            "level": log_level,
            "propagate": False,
        }
    return logging_config
# fmt: on


# pyright: reportInvalidTypeForm=false
def get_log_level() -> LogLevelType:
    """Get the default log level.

    Returns
    -------
    LogLevel
        The default log level
    """
    if "--debug" in sys.argv:
        os.environ[f"{ENV_PREFIX}LOG_LEVEL"] = "DEBUG"
        return "DEBUG"
    possible_log_levels: Tuple[LogLevelType, ...] = get_args(LogLevelType)
    if "--log-level" in sys.argv:
        log_level_index = sys.argv.index("--log-level") + 1
        if log_level_index < len(sys.argv):
            log_level = sys.argv[log_level_index]
            if log_level in possible_log_levels:
                os.environ[f"{ENV_PREFIX}LOG_LEVEL"] = log_level
                return log_level  # type: ignore[return-value]
    for_env = os.environ.get(f"{ENV_PREFIX}LOG_LEVEL", "INFO")
    if for_env in possible_log_levels:
        return for_env  # type: ignore[return-value]
    os.environ[f"{ENV_PREFIX}LOG_LEVEL"] = "INFO"
    return "INFO"
