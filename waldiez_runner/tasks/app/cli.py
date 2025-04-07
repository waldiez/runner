# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""The command line arguments for the app."""

import argparse
import logging
import os
import sys

DEFAULT_INPUT_TIMEOUT = 180

LOG_LEVEL = logging.DEBUG if "--debug" in sys.argv else logging.INFO
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)


def get_parser() -> argparse.ArgumentParser:
    """Get the command line arguments for the app.

    Returns
    -------
    argparse.ArgumentParser
        The command line arguments parser.
    """
    parser = argparse.ArgumentParser(description="Waldiez Runner Task runner.")
    parser.add_argument(
        "file",
        type=str,
        help="The path to the task file.",
    )
    parser.add_argument(
        "--task-id",
        type=str,
        required=True,
        help="The task ID to use.",
    )
    parser.add_argument(
        "--redis-url",
        type=str,
        required=True,
        help="The Redis URL to use.",
    )
    parser.add_argument(
        "--input-timeout",
        type=int,
        required=True,
        help="The timeout for input requests.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode.",
        default=False,
    )
    return parser


class TaskParams:
    """Class to hold the parameters for the task.

    Parameters
    ----------
    task_id : str
        The task ID to use.
    redis_url : str
        The Redis URL to use.
    input_timeout : int
        The timeout for input requests.
    """

    def __init__(
        self,
        file_path: str,
        task_id: str,
        redis_url: str,
        input_timeout: int,
        debug: bool = False,
    ) -> None:
        self.file_path = file_path
        self.task_id = task_id
        self.redis_url = redis_url
        self.input_timeout = input_timeout
        self.debug = debug
        self.validate()

    def validate(self) -> None:
        """Validate the parameters.

        Raises
        -------
        ValueError
            If the parameters are not valid.
        """
        if not os.path.exists(self.file_path):
            raise ValueError(f"File {self.file_path} does not exist.")
        if not self.task_id:
            raise ValueError("Task ID cannot be empty.")
        if not self.redis_url:
            raise ValueError("Redis URL cannot be empty.")
        if self.input_timeout <= 0:
            raise ValueError("Input timeout must be greater than 0.")

    @staticmethod
    def from_args(args: argparse.Namespace) -> "TaskParams":
        """Create a TaskParams object from command line arguments.

        Parameters
        ----------
        args : argparse.Namespace
            The command line arguments.
        Returns
        -------
        TaskParams
            The TaskParams object.
        Raises
        -------
        ValueError
            If the arguments are not valid.
        """
        input_timeout = DEFAULT_INPUT_TIMEOUT
        if args.input_timeout is not None:
            input_timeout = int(args.input_timeout)

        return TaskParams(
            file_path=args.file,
            task_id=args.task_id,
            redis_url=args.redis_url,
            input_timeout=input_timeout,
            debug=args.debug,
        )


def parse_args() -> TaskParams:
    """Parse the command line arguments for the app.

    Returns
    -------
    TaskParams
        The task parameters.
    Raises
    -------
    argparse.ArgumentError
        If the arguments are not provided or invalid.
    """
    parser = get_parser()
    args = parser.parse_args()
    return TaskParams.from_args(args)
