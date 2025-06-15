# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught
# pyright: reportUnknownVariableType=false,reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false,reportTypedDictNotRequiredAccess=false

"""Watch the status of a task and update the database accordingly.

This module provides functionality to monitor the status of a task
running in a subprocess and update the task status in the database
based on messages received from a Redis pub/sub channel.
"""

import asyncio
import json
import logging
import os
import signal
from asyncio.subprocess import Process
from typing import Any, Dict, List, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from waldiez_runner.dependencies import AsyncRedis
from waldiez_runner.models import TaskStatus
from waldiez_runner.services import TaskService

LOG = logging.getLogger(__name__)


class ParsedStatus(TypedDict, total=False):
    """Parsed task status message.

    Attributes
    ----------
    status : TaskStatus
        The task status.
    input_request_id : str | None
        The input request ID, if applicable.
    results : dict | list[dict] | None
        The results of the task, if applicable.
    should_terminate : bool
        Whether the task should be terminated.
    """

    status: TaskStatus
    input_request_id: str | None
    results: Dict[str, Any] | List[Dict[str, Any]] | None
    should_terminate: bool


def load_redis_message_dict(raw_data: str | bytes) -> Dict[str, Any] | None:
    """Load the message we received from redis.

    Parameters
    ----------
    raw_data: str | bytes
        The raw redis data.

    Returns
    -------
    Dict[str, Any] | None
        The loaded message.
    """
    try:
        message = json.loads(raw_data)
        if isinstance(message, str):
            message = json.loads(message)  # Handle double-encoding
    except BaseException as e:
        LOG.warning("Invalid task status JSON: %s", e)
        return None
    if not isinstance(message, dict):
        return None
    if "data" in message and "status" not in message:
        message = message["data"]
    if isinstance(message, str):  # Handle double-encoding
        try:
            message = json.loads(message)
        except BaseException:
            LOG.warning("Invalid task status JSON: %s", message)
            return None
    if not isinstance(message, dict):
        return None
    return message


def parse_status_message(raw_data: str | bytes) -> ParsedStatus | None:
    """Parses and validates a task status message from Redis.

    Parameters
    ----------
    raw_data : str | bytes
        The raw data received from Redis.
    Returns
    -------
    ParsedStatus | None
        The parsed status message or None if invalid.
    """
    message = load_redis_message_dict(raw_data=raw_data)
    if not message:
        return None
    status_str = message.get("status")
    if not status_str:
        return None
    try:
        status = TaskStatus(status_str)
    except ValueError:
        LOG.warning("Unknown task status: %s", status_str)
        return None

    parsed: ParsedStatus = {"status": status}

    if status == TaskStatus.WAITING_FOR_INPUT:
        parsed["input_request_id"] = message.get("data", {}).get(
            "request_id"
        )  # data: {"request_id": ..., "prompt": ...}
    elif status == TaskStatus.COMPLETED:
        parsed["results"] = message.get("data")
    elif status == TaskStatus.FAILED:
        parsed["results"] = {"error": message.get("data")}
    elif status == TaskStatus.CANCELLED:
        # cast to dict (might be a string)
        error = message.get("data", {"data": message.get("data", "")}).get(
            "data"
        )
        parsed["results"] = {"error": error} if error else None
        parsed["should_terminate"] = True

    return parsed


async def watch_status_and_cancel_if_needed(
    task_id: str,
    process: Process,
    redis: AsyncRedis,
    db_session: AsyncSession,
) -> int:
    """Watch the status of a task and update the database.

    Parameters
    ----------
    task_id : str
        The task ID.
    process : Process
        The subprocess running the task.
    redis : AsyncRedis
        The Redis client.
    db_session : AsyncSession
        The database session.

    Returns
    -------
    int
        The exit code of the process.
    """
    channel = f"task:{task_id}:status"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    # pylint: disable=too-many-try-statements
    try:
        async for message in pubsub.listen():
            if process.returncode is not None:
                break

            LOG.debug("Received message: %s", message)
            if not isinstance(message, dict):
                continue

            parsed = parse_status_message(message.get("data", ""))
            if not parsed:
                continue

            try:
                await TaskService.update_task_status(
                    session=db_session,
                    task_id=task_id,
                    status=parsed["status"],
                    input_request_id=parsed.get("input_request_id"),
                    results=parsed.get("results"),
                )
            except Exception as e:
                LOG.warning("Failed to update task %s in DB: %s", task_id, e)

            if parsed.get("should_terminate") is True:
                await terminate_process(process)
                return signal.SIGTERM

            if parsed["status"] in {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                break

    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()

    return 0


async def terminate_process(process: Process) -> None:
    """Terminate the process.

    Parameters
    ----------
    process : Process
        Process object.
    """
    # pylint: disable=no-member
    if process.returncode is not None:
        return
    LOG.info("Terminating process %s", process.pid)
    try:
        if os.name == "nt":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
        except Exception as e:
            LOG.warning("Failed to force kill process: %s", e)
