# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Waldiez runner worker."""

import logging
import logging.config

from ._logging import get_log_level, get_logging_config
from .config import SettingsManager
from .tasks import broker, scheduler

SettingsManager.load_settings(force_reload=True)
logging.config.dictConfig(get_logging_config(get_log_level()))


__all__ = ["broker", "scheduler"]
