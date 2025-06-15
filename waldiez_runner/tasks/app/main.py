# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pyright: reportUnusedFunction=false,reportUnnecessaryIsInstance=false
"""The main Faststream app entrypoint."""

import asyncio
import logging
import signal
import sys
import traceback
from pathlib import Path
from types import FrameType
from typing import Any, Dict, List

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


# pylint: disable=unused-argument
def shutdown(signum: int, frame: FrameType | None) -> None:
    """Handle shutdown signals.

    Parameters
    ----------
    signum : int
        The signal number.
    frame : FrameType | None
        The current stack frame.
    """
    LOG.warning("Received signal %s, shutting down...", signum)
    sys.exit(0)


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

    @broker.subscriber(channel=status_channel)
    async def status_handler(message: Dict[str, Any]) -> None:
        """Handle status messages.

        Parameters
        ----------
        message : str
            The message received.
        """
        LOG.info("Received status message: %s", message)
        if message.get("status", "") == "CANCELLED":
            LOG.warning("Task %s cancelled", message.get("task_id", "unknown"))
            shutdown(0, None)

    await app.start()
    await broker.publish(
        {
            "status": "RUNNING",
            "task_id": params.task_id,
        },
        status_channel,
    )
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
        task_status.update(check_results(results))
    except SystemExit:
        LOG.warning("Task %s was cancelled", params.task_id)
        task_status.update(
            {
                "status": "CANCELLED",
                "data": "Task was cancelled by signal",
            }
        )
        return
    except Exception as e:  # pylint: disable=broad-exception-caught
        LOG.error("Task %s failed: %s", params.task_id, e)
        tb = traceback.format_exc()
        data = {
            "error": str(e),
            "traceback": tb,
        }
        task_status.update(
            {
                "status": "FAILED",
                "data": data,
            }
        )
    finally:
        await broker.publish(task_status, status_channel)
        await app.stop()
        LOG.info("App stopped for task %s", params.task_id)


def check_results(
    results: Dict[str, Any] | List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Check the results of the flow execution.

    Parameters
    ----------
    results : Dict[str, Any]
        The results of the flow execution.

    Returns
    -------
    Dict[str, Any]
        The checked results.
    """
    if isinstance(results, dict) and "error" in results:
        return {
            "status": "FAILED",
            "data": results,
        }
    if isinstance(results, list) and len(results) == 0:
        return {
            "status": "FAILED",
            "data": "No results returned",
        }
    if (
        isinstance(results, list)
        and len(results) == 1
        and isinstance(results[0], dict)
        and "error" in results[0]
    ):
        data = {
            "error": results[0]["error"],
        }
        if "traceback" in results[0]:
            data["traceback"] = results[0]["traceback"]
        return {
            "status": "FAILED",
            "data": data,
        }
    return {
        "status": "COMPLETED",
        "data": results,
    }


def setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)


async def main() -> None:
    """Parse the command line arguments and run the app."""

    setup_signal_handlers()
    params = parse_args()
    await run(params=params)


if __name__ == "__main__":
    asyncio.run(main())
