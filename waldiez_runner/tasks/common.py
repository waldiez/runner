# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Common task utilities."""

import os
from typing import Any

from taskiq import (
    AsyncBroker,
    AsyncResultBackend,
    SimpleRetryMiddleware,
    TaskiqScheduler,
)
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from waldiez_runner.config import ENV_PREFIX, TRUTHY, SettingsManager
from waldiez_runner.dependencies import REDIS_MANAGER, RedisManager, skip_redis


def get_broker() -> AsyncBroker:
    """Get the broker instance.

    Returns
    -------
    AsyncBroker
        Broker instance.
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
    redis_async_result_backend: AsyncResultBackend[Any] = (
        RedisAsyncResultBackend(redis_url=redis_url)
    )
    broker_instance = ListQueueBroker(url=redis_url)
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
    the_scheduler = TaskiqScheduler(
        the_broker, sources=[LabelScheduleSource(the_broker)]
    )
    return the_scheduler


def redis_status_key(task_id: str) -> str:
    """Get the Redis status key for a task.

    Parameters
    ----------
    task_id : str
        Task ID.

    Returns
    -------
    str
        The Redis status key.
    """
    return f"task:{task_id}:status"


broker = get_broker()
scheduler = get_scheduler(broker)
