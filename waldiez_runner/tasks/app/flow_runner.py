# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""FlowRunner class for running Waldiez flows with Redis I/O stream."""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List

import redis
import redis.asyncio as a_redis
from waldiez import Waldiez, WaldiezRunner

from .redis_io_stream import RedisIOStream
from .results_serialization import serialize_results

if TYPE_CHECKING:
    Redis = redis.Redis[bytes]
    AsyncRedis = a_redis.Redis[bytes]
else:
    Redis = redis.Redis
    AsyncRedis = a_redis.Redis

LOG = logging.getLogger(__name__)


class FlowRunner:
    """Class to run a Waldiez flow with Redis I/O stream.

    Parameters
    ----------
    task_id : str
        The task ID to subscribe to.
    redis_url : str
        The Redis URL to connect to.
    waldiez : Waldiez
        The Waldiez flow to run.
    output_path : str
        The path to save the output.
    input_timeout : int, optional
        The timeout for input requests, by default 60
    """

    def __init__(
        self,
        task_id: str,
        redis_url: str,
        waldiez: Waldiez,
        output_path: str,
        input_timeout: int = 180,
    ) -> None:
        self.task_id = task_id
        self.redis_url = redis_url
        self.waldiez = waldiez
        self.output_path = output_path
        self.input_timeout = input_timeout
        self.status_channel = f"task:{task_id}:status"
        self.results_channel = f"task:{task_id}:results"
        self.io_stream = RedisIOStream(
            redis_url=self.redis_url,
            task_id=self.task_id,
            on_input_request=self.on_input_request,
            on_input_response=self.on_input_received,
            input_timeout=self.input_timeout,
        )
        self.redis: Redis | None = None
        self.a_redis: AsyncRedis | None = None

    async def run(self) -> List[Dict[str, Any]]:
        """Run the Waldiez flow and return the results.

        Returns
        -------
        List[Dict[str, Any]]]
            The results of the flow execution.
        """
        self.redis = Redis.from_url(self.redis_url)
        self.a_redis = AsyncRedis.from_url(self.redis_url)
        if not self.waldiez.is_async:
            results = await asyncio.to_thread(self.run_sync)
            serialized_results = serialize_results(results)
            await self.a_redis.publish(
                self.results_channel, json.dumps(serialized_results)
            )
            return serialized_results
        with RedisIOStream.set_default(self.io_stream):
            runner = WaldiezRunner(self.waldiez)
            results = await runner.a_run(output_path=self.output_path)
        serialized_results = serialize_results(results)
        await self.a_redis.publish(
            self.results_channel, json.dumps(serialized_results)
        )
        self.io_stream.close()
        await self.a_redis.close()
        return serialized_results

    def run_sync(self) -> List[Dict[str, Any]]:
        """Run the Waldiez flow synchronously and return the results.

        Returns
        -------
        List[Dict[str, Any]]
            The results of the flow execution.
        """
        self.redis = Redis.from_url(self.redis_url)
        with RedisIOStream.set_default(self.io_stream):
            try:
                runner = WaldiezRunner(self.waldiez)
                results = runner.run(output_path=self.output_path)
            finally:
                self.io_stream.close()
                self.redis.close()

        return serialize_results(results)

    def on_input_request(
        self, prompt: str, request_id: str, task_id: str
    ) -> None:
        """Callback for input request.

        Parameters
        ----------
        prompt : str
            The input prompt.
        request_id : str
            The request ID.
        task_id : str
            The task ID.
        """
        LOG.debug(
            "Requesting input, prompt: %s, request_id: %s, task_id: %s",
            prompt,
            request_id,
            task_id,
        )
        if task_id != self.task_id:
            LOG.warning(
                "Received input request for a different task ID: %s", task_id
            )
            return
        if not self.redis:
            LOG.error("Redis connection is not initialized.")
            return
        self.redis.set(self.status_channel, "WAITING_FOR_INPUT", ex=60)

    def on_input_received(self, user_input: str, task_id: str) -> None:
        """Callback for input received.

        Parameters
        ----------
        user_input : str
            The user input received.
        task_id : str
            The task ID.
        """
        LOG.debug("Received input: %s, task_id: %s", user_input, task_id)
        if task_id != self.task_id:
            LOG.warning("Received input for a different task ID: %s", task_id)
            return
        if not self.redis:
            LOG.error("Redis connection is not initialized.")
            return
        self.redis.set(self.status_channel, "RUNNING", ex=60)

    @staticmethod
    def validate_flow(flow_path: str) -> Waldiez:
        """Validate and load a flow from disk.

        Parameters
        ----------
        flow_path : str
            The path to the flow file.
        Returns
        -------
        Waldiez
            The loaded Waldiez flow.
        Raises
        -------
        ValueError
            If the flow file is invalid or cannot be loaded.
        """
        try:
            return Waldiez.load(flow_path)
        except Exception as e:
            LOG.error("Error loading flow %s: %s", flow_path, e)
            raise ValueError(str(e)) from e
