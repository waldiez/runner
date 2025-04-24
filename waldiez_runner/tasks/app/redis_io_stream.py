# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# flake8: noqa: E501
# pylint: disable=too-many-try-statements,broad-exception-caught,line-too-long

"""A Redis I/O stream for handling print and input messages.

This module provides a Redis I/O stream for structured messaging.
It is designed to be used with tasks that require input/output handling.

Output

    - Task-specific output stream:    `task:{task_id}:output`
    - Shared/global output stream:   `task-output`

    All print messages, input requests, and input responses are also written to both output streams.

Input Handling (via Pub/Sub)

    Two separate channels are used for input flow:

    - Input request channel:   `task:{task_id}:input_request`
        - Published by the task when input is required
        - Consumed by WebSocket/UI or external tools

    - Input response channel:  `task:{task_id}:input_response`
        - Published by WebSocket or HTTP clients with the user's input
        - Consumed by the task (which is waiting on the response)

Message Structure

All messages are structured JSON payloads with a common schema:

All print and input-related messages are also broadcast to both streams.

Message Formats:

Print messages:
{
    "type": "print",
    "timestamp": 1711210101210,
    "task_id": "abc123",
    "data": "Your log message"
}

Input request messages:
{
    "type": "input_request",
    "timestamp": 1711210101210,
    "task_id": "abc123",
    "request_id": "req-uuid",
    "data": "Enter your name:",
    "password": "False"
}

Input response messages:
{
    "type": "input_response",
    "timestamp": 1711210101210,
    "task_id": "abc123",
    "request_id": "req-uuid",
    "data": "John Doe"
}
"""

import json
import logging
import time
import traceback as tb
import uuid
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Literal,
    Optional,
    Tuple,
    Type,
)

import redis
import redis.asyncio as a_redis
from autogen.io import IOStream  # type: ignore
from autogen.messages import BaseMessage  # type: ignore
from typing_extensions import TypedDict

if TYPE_CHECKING:
    Redis = redis.Redis[bytes]
    AsyncRedis = a_redis.Redis[bytes]
else:
    Redis = redis.Redis
    AsyncRedis = a_redis.Redis

LOG = logging.getLogger(__name__)


class MessageToSend(TypedDict):
    """Message to send."""

    type: Literal["print", "input"]
    data: str


class RedisIOStream(IOStream):
    """Redis I/O stream."""

    redis: Redis
    task_id: str
    input_timeout: int
    on_input_request: Optional[Callable[[str, str, str], None]]
    on_input_received: Optional[Callable[[str, str], None]]
    max_stream_size: int
    output_stream: str
    input_request_channel: str
    input_response_channel: str

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        task_id: str | None = None,
        input_timeout: int = 180,
        max_stream_size: int = 1000,
        on_input_request: Optional[Callable[[str, str, str], None]] = None,
        on_input_response: Optional[Callable[[str, str], None]] = None,
        redis_connection_kwargs: Dict[str, Any] | None = None,
    ) -> None:
        """Initialize the Redis I/O stream.

        Parameters
        ----------
        task_id : str, optional
            An ID to use for the input channel and the output stream. If not provided,
            a random UUID will be generated.
        redis_url : str, optional
            The Redis URL, by default "redis://localhost:6379/0".
        input_timeout : int, optional
            The time to wait for user input in seconds, by default 180 (3 minutes).
        on_input_request : Optional[Callable[[str, str, str], None]], optional
            Callback for input request, by default None
            parameters: prompt, request_id, task_id
        on_input_response : Optional[Callable[[str, str], None]], optional
            Callback for input response, by default None.
            parameters: user_input, task_id
        redis_connection_kwargs : Dict[str, Any] | None, optional
            Additional Redis connection kwargs, to be used with `redis.Redis.from_url`,
            by default None.
            See: https://redis-py.readthedocs.io/en/stable/connections.html#redis.Redis.from_url
        """
        self.redis = Redis.from_url(redis_url, **redis_connection_kwargs or {})
        self.task_id = task_id or uuid.uuid4().hex
        self.input_timeout = input_timeout
        self.on_input_request = on_input_request
        self.on_input_response = on_input_response
        self.max_stream_size = max_stream_size
        self.task_output_stream = f"task:{self.task_id}:output"
        self.input_request_channel = f"task:{self.task_id}:input_request"
        self.input_response_channel = f"task:{self.task_id}:input_response"
        self.common_output_stream = "task-output"

    def __enter__(self) -> "RedisIOStream":
        """Enable context manager usage."""
        return self

    def __exit__(
        self,
        exc_type: Type[Exception] | None,
        exc_value: Exception | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the context manager.

        Parameters
        ----------
        exc_type : Type[Exception] | None
            The exception type.
        exc_value : Exception | None
            The exception value.
        traceback : TracebackType | None
            The traceback.
        """
        # cleanup
        RedisIOStream.cleanup_processed_task_requests(
            self.redis, self.task_id, retention_period=86400
        )
        RedisIOStream.trim_task_output_streams(self.redis)
        RedisIOStream.cleanup_processed_requests(self.redis)
        # and close the connection
        self.close()

    def close(self) -> None:
        """Close the Redis client."""
        RedisIOStream.try_do(self.redis.close)

    def _print_to_task_output(self, payload: Dict[str, Any]) -> None:
        """Print message to the task output stream.

        Parameters
        ----------
        message : str
            The message to print.
        message_type : str
            The message type.
        """
        LOG.debug("Sending print message: %s", payload)
        RedisIOStream.try_do(
            self.redis.xadd,
            self.task_output_stream,
            payload,
            maxlen=self.max_stream_size,
            approximate=True,
        )

    def _print_to_common_output(self, payload: Dict[str, Any]) -> None:
        """Print message to the common output stream.

        Parameters
        ----------
        message : str
            The message to print.
        message_type : str
            The message type.
        """
        LOG.debug("Sending print message: %s", payload)
        RedisIOStream.try_do(
            self.redis.xadd,
            self.common_output_stream,
            payload,
            maxlen=self.max_stream_size,
            approximate=True,
        )

    def _print(self, payload: Dict[str, Any]) -> None:
        """Print message to Redis streams.

        Parameters
        ----------
        payload : Dict[str, Any]
            The message to print.
        """
        payload["task_id"] = self.task_id
        payload["timestamp"] = int(time.time() * 1_000_000)
        self._print_to_task_output(payload)
        self._print_to_common_output(payload)

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print message to Redis stream.

        Parameters
        ----------
        args : Any
            The message to print.
        kwargs : Any
            Additional keyword arguments.
        """
        message = " ".join(str(arg) for arg in args)
        if "file" in kwargs:
            file = kwargs.pop("file")
            if hasattr(file, "getvalue"):
                io_value = file.getvalue()
                if isinstance(io_value, bytes):
                    io_value = io_value.decode("utf-8", errors="replace")
                message += io_value
        end = kwargs.get("end", "\n")
        message += end
        payload = {
            "type": "print",
            "data": message,
        }
        self._print(payload)

    def send(self, message: BaseMessage) -> None:
        """Send a structured message to Redis.

        Parameters
        ----------
        message : Dict[str, Any]
            The message to send.
        """
        payload = {
            "type": "print",
            "data": message.model_dump_json(),
        }
        self._print(payload)

    def input(
        self,
        prompt: str = "",
        *,
        password: bool = False,
        request_id: str | None = None,
    ) -> str:
        """Request input via Redis Pub/Sub and wait for response.

        Parameters
        ----------
        prompt : str, optional
            The prompt message, by default "".
        password : bool, optional
            Whether input is masked, by default False.
        request_id : str, optional
            The request ID (for testing), by default None.
        Returns
        -------
        str
            The received user input, or empty string if timeout occurs.
        """
        request_id = request_id or uuid.uuid4().hex
        payload = {
            "type": "input_request",
            "data": prompt,
            "password": str(password),
            "request_id": request_id,
        }
        LOG.debug("Requesting input via Pub/Sub: %s", payload)
        self._print(payload)
        RedisIOStream.try_do(
            self.redis.publish,
            self.input_request_channel,
            json.dumps(payload),
        )
        if self.on_input_request:
            self.on_input_request(prompt, request_id, self.task_id)
        user_input = self._wait_for_input(request_id)
        if self.on_input_response:
            self.on_input_response(user_input, self.task_id)
        payload = {
            "request_id": request_id,
            "type": "input_response",
            "data": user_input,
        }
        LOG.debug("Sending input response: %s", payload)
        self._print(payload)
        return user_input

    def _wait_for_input(self, input_request_id: str) -> str:
        """Wait for user input.

        Parameters
        ----------
        input_request_id : str
            The request ID.
        Returns
        -------
        str
            The user input.
        """
        lock_key = f"lock:{self.task_id}"
        start_time = time.time()

        pubsub = self.redis.pubsub()
        pubsub.subscribe(self.input_response_channel)
        try:
            while (time.time() - start_time) <= self.input_timeout:
                message = pubsub.get_message(ignore_subscribe_messages=True)
                if not message:
                    time.sleep(0.1)
                    continue
                LOG.debug("Received message: %s", message)
                request_id, user_input = self.parse_pubsub_input(message)
                if not request_id or request_id != input_request_id:
                    continue

                if self._acquire_lock(lock_key):
                    try:
                        if self._is_request_processed(request_id):
                            continue

                        self._mark_request_processed(request_id)
                        return user_input or "\n"
                    finally:
                        self._release_lock(lock_key)
        except BaseException:  # pragma: no cover
            LOG.error("Error in _wait_for_input: %s", tb.format_exc())
        finally:
            pubsub.unsubscribe(self.input_response_channel)

        LOG.warning(
            "No input received for %ds on task %s, assuming empty string",
            self.input_timeout,
            self.task_id,
        )
        return "\n"

    def _acquire_lock(self, lock_key: str, lock_expiry: int = 10) -> bool:
        """Try to acquire a lock, returns True if acquired, False otherwise."""
        try:
            return (
                self.redis.set(lock_key, "locked", ex=lock_expiry, nx=True)
                is True
            )
        except redis.RedisError as e:  # pragma: no cover
            LOG.error("Redis error on acquire lock: %s", e)
            return False
        except BaseException as e:  # pragma: no cover
            LOG.error("Error on acquire lock: %s", e)
            return False

    def _release_lock(self, lock_key: str) -> None:
        """Release a lock."""
        RedisIOStream.try_do(self.redis.delete, lock_key)

    def _is_request_processed(self, request_id: str) -> bool:
        """Check if a request is processed for a task."""
        return RedisIOStream.is_request_processed(
            self.redis, task_id=self.task_id, request_id=request_id
        )

    def _mark_request_processed(self, request_id: str) -> None:
        """Mark a request as processed for a task."""
        RedisIOStream.try_do(
            self.redis.zadd,
            f"processed_requests:{self.task_id}",
            {request_id: int(time.time() * 1_000_000)},
        )

    @staticmethod
    def parse_pubsub_input(
        message: Dict[str, Any],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract request ID and user input from a message.

        Parameters
        ----------
        message : Dict[str, Any]
            The message to parse.
        Returns
        -------
        Tuple[Optional[str], Optional[str]]
            The request ID and user's input.
        """
        message_data = message.get("data", "{}")
        try:
            message_dict = json.loads(message_data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None, None
        if not isinstance(message_dict, dict):
            return None, None
        if "request_id" not in message_dict:
            return None, None
        if "data" not in message_dict:
            return None, None
        user_input = str(message_dict.get("data", ""))
        if user_input.lower() in [
            "",
            "\n",
            "/\\n",
            '""',
            "''",
            '"/\\n"',
            "'/\\n'",
            "none",
            "null",
        ]:
            user_input = "\n"
        return message_dict["request_id"], user_input

    @staticmethod
    def try_do(func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Try to execute.

        Just to avoid duplicate try/except blocks.
        To only be used if no return value is expected.
        And if we no't need to re-raise the exception.
        Otherwise, we normally try/except at the call site.

        Parameters
        ----------
        func : Callable[..., Any]
            The function to call.
        args : Any
            The function's positional arguments.
        kwargs : Any
            The function's keyword arguments.
        """
        try:
            func(*args, **kwargs)
        except BaseException:  # pragma: no cover
            LOG.error("Error on try_do:")
            LOG.error(tb.format_exc())

    @staticmethod
    async def a_try_do(
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Async version of try_do.

        Parameters
        ----------
        func : Awaitable[Any]
            The async function to call.
        args : Any
            The positional arguments.
        kwargs : Any
            The keyword arguments.
        """
        try:
            await func(*args, **kwargs)
        except BaseException:  # pragma: no cover
            LOG.error("Error on a_try_do:")
            LOG.error(tb.format_exc())

    @staticmethod
    def is_request_processed(
        redis_client: Redis,
        task_id: str,
        request_id: str,
    ) -> bool:
        """Check if a request is processed for a task.

        Parameters
        ----------
        redis_client : Redis
            The async Redis client to use.
        task_id : str
            The task ID.
        request_id : str
            The request ID.

        Returns
        -------
        bool
            True if the request is processed, False otherwise.
        """
        try:
            return (
                redis_client.zscore(f"processed_requests:{task_id}", request_id)
                is not None
            )
        except BaseException as e:  # pragma: no cover
            LOG.error("Error on check request processed: %s", e)
            return False

    @staticmethod
    async def a_is_request_processed(
        redis_client: AsyncRedis,
        task_id: str,
        request_id: str,
    ) -> bool:
        """Async version of is_request_processed.

        Parameters
        ----------
        redis_client : AsyncRedis
            The async Redis client to use.
        task_id : str
            The task ID.
        request_id : str
            The request ID.

        Returns
        -------
        bool
            True if the request is processed, False otherwise.
        """
        try:
            return (
                await redis_client.zscore(
                    f"processed_requests:{task_id}", request_id
                )
                is not None
            )
        except BaseException as e:  # pragma: no cover
            LOG.error("Error on check request processed: %s", e)
            return False

    # other static methods for cleanup
    # to be used externally (like in periodic tasks) if needed
    # or after task completion
    @staticmethod
    def cleanup_processed_task_requests(
        redis_client: Redis,
        task_id: str,
        retention_period: int = 86400,
    ) -> None:
        """Cleanup old processed request logs.

        Parameters
        ----------
        redis_client : Redis
            The Redis client.
        task_id : str
            The task ID.
        retention_period : int, optional
            The retention period in seconds, by default 86400.
        """
        key = f"processed_requests:{task_id}"
        cutoff_time = int(time.time()) - retention_period
        RedisIOStream.try_do(redis_client.zremrangebyscore, key, 0, cutoff_time)

    @staticmethod
    def cleanup_processed_requests(
        redis_client: Redis, retention_period: int = 86400
    ) -> None:
        """Cleanup stale processed requests.

        Parameters
        ----------
        redis_client : Redis
            The Redis client.
        retention_period : int, optional
            The retention period in seconds
        """
        cutoff_time = int(time.time()) - retention_period
        for key in redis_client.scan_iter("processed_requests:*", count=100):
            RedisIOStream.try_do(
                redis_client.zremrangebyscore, key, 0, cutoff_time
            )

    @staticmethod
    def trim_task_output_streams(
        redis_client: Redis, maxlen: int = 1000, approximate: bool = True
    ) -> None:
        """Trim task output streams to a max length.

        Parameters
        ----------
        redis_client : Redis
            The Redis client.
        maxlen : int
            The maximum number of entries per stream.
        approximate : bool
            Whether to use approximate trimming (more efficient).
        """
        for key in redis_client.scan_iter("task:*:output", count=100):
            RedisIOStream.try_do(
                redis_client.xtrim, key, maxlen=maxlen, approximate=approximate
            )

    @staticmethod
    async def a_cleanup_processed_task_requests(
        redis_client: AsyncRedis, task_id: str, retention_period: int = 86400
    ) -> None:
        """Async version of cleanup task processed requests.

        Parameters
        ----------
        redis_client : AsyncRedis
            The Redis client.
        task_id : str
            The task ID.
        retention_period : int, optional
            The retention period in seconds, by default 86400.
        """
        key = f"processed_requests:{task_id}"
        cutoff_time = int(time.time()) - retention_period
        await RedisIOStream.a_try_do(
            redis_client.zremrangebyscore, key, 0, cutoff_time
        )

    @staticmethod
    async def a_cleanup_processed_requests(
        redis_client: AsyncRedis,
        retention_period: int = 86400,
    ) -> None:
        """Async version of cleanup stale processed requests.

        Parameters
        ----------
        redis_client : Redis
            The Redis client.
        retention_period : int, optional
            The retention period in seconds, by default 86400.
        """
        cutoff_time = int(time.time()) - retention_period
        async for key in redis_client.scan_iter(
            "processed_requests:*", count=100
        ):
            await RedisIOStream.a_try_do(
                redis_client.zremrangebyscore, key, 0, cutoff_time
            )

    @staticmethod
    async def a_trim_task_output_streams(
        redis_client: AsyncRedis,
        maxlen: int = 1000,
        approximate: bool = True,
        scan_count: int = 100,
    ) -> None:
        """Trim task output Redis streams to a max length.

        Parameters
        ----------
        redis_client : AsyncRedis
            The Redis client.
        maxlen : int
            The maximum number of entries per stream.
        approximate : bool
            Whether to use approximate trimming (more efficient).
        scan_count : int
            The number of keys to scan per iteration.
        """
        trimmed_count = 0

        async for key in redis_client.scan_iter(
            "task:*:output", count=scan_count
        ):
            before = await redis_client.xlen(key)
            await RedisIOStream.a_try_do(
                redis_client.xtrim,
                key,
                maxlen=maxlen,
                approximate=approximate,
            )
            after = await redis_client.xlen(key)
            if before > after:
                trimmed = before - after
                trimmed_count += trimmed
                LOG.debug("Trimmed %d entries from %s", trimmed, key)

        LOG.info("Total trimmed entries: %d", trimmed_count)
        # we might also want to use prometheus metrics here,
        # to check and fine-tune the (maxlen, scan_count) parameters
        # e.g.:
        # from prometheus_client import Counter

        # trimmed_entries = Counter("redis_stream_trimmed_entries_total", "Total trimmed entries from Redis streams")
        # trimmed_streams = Counter("redis_stream_trimmed_streams_total", "Total number of trimmed Redis streams")
        # ...
        # if before > after:
        #     trimmed_entries.inc(before - after)
        #     trimmed_streams.inc()
