# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Common task utilities."""

import os
from pathlib import Path
from typing import Any, Tuple

from taskiq import (
    AsyncBroker,
    AsyncResultBackend,
    SimpleRetryMiddleware,
    TaskiqScheduler,
)

# from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import (
    ListRedisScheduleSource,
    RedisAsyncResultBackend,
    RedisStreamBroker,
)

from waldiez_runner.config import ENV_PREFIX, TRUTHY, SettingsManager
from waldiez_runner.dependencies import REDIS_MANAGER, RedisManager, skip_redis

HERE = Path(__file__).parent
APP_DIR = HERE / "app"


def get_redis_url() -> Tuple[str, bool]:
    """Get the Redis URL and smoke testing status.

    Returns
    -------
    Tuple[str, bool]
        Redis URL and smoke testing status.
    """
    using_fake_redis = skip_redis()
    is_smoke_testing = using_fake_redis
    if using_fake_redis:
        is_smoke_testing = (
            os.environ.get(f"{ENV_PREFIX}SMOKE_TESTING", "false").lower()
            in TRUTHY
        )
        is_running = REDIS_MANAGER.is_using_fake_redis()
        if is_running:
            redis_url = REDIS_MANAGER.redis_url
        else:
            redis_url = REDIS_MANAGER.start_fake_redis_server(new_port=True)
    else:
        settings = SettingsManager.load_settings()
        redis_manager = RedisManager(settings)
        redis_url = redis_manager.redis_url
    return redis_url, is_smoke_testing


def get_broker() -> AsyncBroker:
    """Get the broker instance.

    Returns
    -------
    AsyncBroker
        Broker instance.
    """
    redis_url, is_smoke_testing = get_redis_url()
    redis_async_result_backend: AsyncResultBackend[Any] = (
        RedisAsyncResultBackend(
            redis_url=redis_url,
            result_ex_time=1000,
        )
    )
    broker_instance = RedisStreamBroker(url=redis_url)
    # in smoke tests outside a container and env without redis,
    # we use fake redis, but we don't mock the .kiq() calls
    # in pytest, we use fake redis too, but we mock the .kiq() calls
    setattr(broker_instance, "_is_smoke_testing", is_smoke_testing)
    return broker_instance.with_middlewares(
        SimpleRetryMiddleware(default_retry_count=3)
    ).with_result_backend(redis_async_result_backend)


def get_scheduler(the_broker: AsyncBroker) -> TaskiqScheduler:
    """Get the scheduler instance.

    Parameters
    ----------
    the_broker : AsyncBroker
        The Taskiq broker instance
    Returns
    -------
    TaskiqScheduler
        The Taskiq Scheduler instance.
    """
    redis_url, is_smoke_testing = get_redis_url()
    redis_source = ListRedisScheduleSource(
        url=redis_url,
    )
    the_scheduler = TaskiqScheduler(
        the_broker,
        sources=[redis_source],
    )
    # in smoke tests outside a container and env without redis,
    # we use fake redis, but we don't mock the .kiq() calls
    # in pytest, we use fake redis too, but we mock the .kiq() calls
    setattr(the_scheduler, "_is_smoke_testing", is_smoke_testing)
    return the_scheduler


broker = get_broker()
scheduler = get_scheduler(broker)
