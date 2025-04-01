# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""The main Faststream app entrypoint."""

import asyncio
import logging
import sys
from pathlib import Path

from faststream import FastStream
from faststream.redis import RedisBroker

try:
    from .cli import TaskParams, parse_args
    from .flow_runner import FlowRunner
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app.cli import TaskParams, parse_args  # type: ignore
    from app.flow_runner import FlowRunner  # type: ignore

LOG = logging.getLogger(__name__)


async def run(params: TaskParams) -> None:
    """Main function to run the Faststream app.

    Parameters
    ----------
    params : TaskParams
        The parameters for the task.
    """
    # just a simulation of a long-running task for now

    broker = RedisBroker(url=params.redis_url)
    app = FastStream(broker=broker)

    @broker.subscriber(params.task_id)
    async def task_handler(message: str) -> None:
        """Handle the task message.

        Parameters
        ----------
        message : str
            The task message.
        """
        LOG.info("Received message: %s", message)

    # Run the Faststream app

    status_channel = f"tasks:{params.task_id}:status"
    await app.start()
    # Load the task file
    try:
        waldiez = FlowRunner.validate_flow(params.file_path)
    except BaseException as e:  # pylint: disable=broad-exception-caught
        LOG.error("Error validating flow: %s", e)
        await broker.publish("FAILED", status_channel)
        await app.stop()
        return
    output_path = params.file_path.replace(".waldiez", ".py")
    try:
        flow_runner = FlowRunner(
            task_id=params.task_id,
            redis_url=params.redis_url,
            waldiez=waldiez,
            output_path=output_path,
            input_timeout=params.input_timeout,
        )
        await flow_runner.run()
    except BaseException as e:  # pylint: disable=broad-exception-caught
        LOG.error("Error running flow: %s", e)
        await broker.publish("FAILED", status_channel)
        await app.stop()
        return
    # TODO: something with the results
    await broker.publish("COMPLETED", status_channel)
    await app.stop()


async def main() -> None:
    """Parse the command line arguments and run the app."""
    params = parse_args()
    await run(params=params)


if __name__ == "__main__":
    asyncio.run(main())
