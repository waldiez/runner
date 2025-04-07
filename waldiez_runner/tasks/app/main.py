# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""The main Faststream app entrypoint."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

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
    broker = RedisBroker(url=params.redis_url)
    app = FastStream(broker=broker)
    status_channel = f"task:{params.task_id}:status"

    await app.start()
    task_status: Dict[str, Any] = {
        "task_id": params.task_id,
    }
    # pylint: disable=too-many-try-statements
    try:
        waldiez = FlowRunner.validate_flow(params.file_path)
        output_path = params.file_path.replace(".waldiez", ".py")

        flow_runner = FlowRunner(
            task_id=params.task_id,
            redis_url=params.redis_url,
            waldiez=waldiez,
            output_path=output_path,
            input_timeout=params.input_timeout,
        )

        results = await flow_runner.run()
        task_status.update(
            {
                "status": "COMPLETED",
                "data": results,
            }
        )

    except BaseException as e:  # pylint: disable=broad-exception-caught
        LOG.error("Task %s failed: %s", params.task_id, e)
        task_status.update(
            {
                "status": "FAILED",
                "data": str(e),
            }
        )
    finally:
        await broker.publish(json.dumps(task_status), status_channel)
        await app.stop()
        LOG.info("App stopped for task %s", params.task_id)


async def main() -> None:
    """Parse the command line arguments and run the app."""
    params = parse_args()
    await run(params=params)


if __name__ == "__main__":
    asyncio.run(main())
