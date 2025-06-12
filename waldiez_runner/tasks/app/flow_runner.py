# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""FlowRunner class for running Waldiez flows with Redis I/O stream."""

import asyncio
import json
import logging
import traceback
from typing import Any

from autogen import ChatResult  # type: ignore[import-untyped]
from waldiez import Waldiez, WaldiezRunner

from .redis_io_stream import RedisIOStream
from .results_serialization import make_serializable_results

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
        The timeout for input requests, by default 180.
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
        self.io_stream = RedisIOStream(
            redis_url=self.redis_url,
            task_id=self.task_id,
            on_input_request=self.on_input_request,
            on_input_response=self.on_input_response,
            input_timeout=self.input_timeout,
        )

    async def run(self) -> list[dict[str, Any]]:
        """Run the Waldiez flow and return the results.

        Returns
        -------
        List[Dict[str, Any]]]
            The results of the flow execution.
        """
        results: (
            ChatResult
            | dict[str, ChatResult]
            | list[dict[str, ChatResult]]
            | dict[str, Any]
            | dict[int, Any]
        )
        if not self.waldiez.is_async:
            results = await asyncio.to_thread(self.run_sync)
            serializable_results = make_serializable_results(results)
            return serializable_results
        with RedisIOStream.set_default(self.io_stream):
            try:
                runner = WaldiezRunner(self.waldiez)
                results = await runner.a_run(  # pyright: ignore
                    output_path=self.output_path,
                )
            except BaseException as e:  # pylint: disable=broad-exception-caught
                tb = traceback.format_exc()
                results = {
                    "error": str(e),
                    "traceback": tb,
                }
        serializable_results = make_serializable_results(results)
        self.io_stream.close()
        return serializable_results

    def run_sync(self) -> list[dict[str, Any]]:
        """Run the Waldiez flow synchronously and return the results.

        Returns
        -------
        List[Dict[str, Any]]
            The results of the flow execution.
        """
        results: (
            ChatResult
            | dict[str, ChatResult]
            | list[dict[int, ChatResult]]
            | dict[str, Any]
            | dict[int, Any]
        )
        with RedisIOStream.set_default(self.io_stream):
            try:
                runner = WaldiezRunner(self.waldiez)
                results = runner.run(  # pyright: ignore
                    output_path=self.output_path,
                )
            except BaseException as e:  # pylint: disable=broad-exception-caught
                tb = traceback.format_exc()
                results = {  # pylint: disable=redefined-variable-type
                    "error": str(e),
                    "traceback": tb,
                }
            finally:
                self.io_stream.close()

        return make_serializable_results(results)

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

    def on_input_request(
        self,
        prompt: str,
        request_id: str,
        task_id: str,
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
        LOG.debug("Got input request: %s", prompt)
        task_status: dict[str, Any] = {
            "status": "WAITING_FOR_INPUT",
            "task_id": task_id,
            "data": {"prompt": prompt, "request_id": request_id},
        }
        chanel = f"task:{task_id}:status"
        try:
            self.io_stream.redis.publish(
                channel=chanel,
                message=json.dumps(task_status),
            )
        except BaseException as e:  # pylint: disable=broad-exception-caught
            LOG.error("Error publishing input request: %s", e)

    def on_input_response(
        self,
        user_input: str,
        task_id: str,
    ) -> None:
        """Callback for input response.

        Parameters
        ----------
        user_input : str
            The user input received.
        task_id : str
            The task ID.
        """
        LOG.debug("Got user input: %s", user_input)
        task_status: dict[str, Any] = {
            "status": "RUNNING",
            "task_id": task_id,
            "data": None,
        }
        chanel = f"task:{task_id}:status"
        # pylint: disable=broad-exception-caught
        try:
            self.io_stream.redis.publish(
                channel=chanel,
                message=json.dumps(task_status),
            )
        except BaseException as e:  # pragma: no cover
            LOG.error("Error publishing input response: %s", e)
