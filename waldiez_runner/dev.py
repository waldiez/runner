# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=consider-using-with

"""Start the server and the worker in development mode."""

import logging
import os
import signal
import subprocess
import sys
from multiprocessing import Process
from pathlib import Path
from types import FrameType
from typing import Any, Dict, List, Tuple

import uvicorn

from waldiez_runner._logging import LogLevel
from waldiez_runner.config import ENV_PREFIX

RELOAD_EXCLUDES = [
    "waldiez_out/*",
    ".*",
    ".py[cod]",
    ".sw.*",
    "~*",
    "**/files/**/*",
    ".venv/*",
    "waldiez_runner/storage/*",
    "examples/*",
]

LOG = logging.getLogger(__name__)


def get_module_and_cwd() -> Tuple[str, str]:
    """Get the module name and the current working directory.

    Returns
    -------
    Tuple[str, str]
        The module name and the current working directory.
    """
    module_name = Path(__file__).parent.name
    cwd = str(Path(__file__).parent.parent)
    return module_name, cwd


def run_process(
    command: List[str], cwd: str, skip_redis: bool = False
) -> subprocess.Popen[Any]:
    """Run a process.

    Parameters
    ----------
    command : List[str]
        The command to run.
    cwd : str
        The current working directory.
    skip_redis : bool
        Whether to skip using Redis

    Returns
    -------
    subprocess.Popen
        The process.
    """
    if skip_redis is True:
        os.environ[f"{ENV_PREFIX}NO_REDIS"] = "true"
        os.environ[f"{ENV_PREFIX}REDIS"] = "false"
    return subprocess.Popen(
        command, cwd=cwd, env=os.environ
    )  # nosemgrep # nosec


def start_broker(reload: bool, log_level: LogLevel, skip_redis: bool) -> None:
    """Start the broker.

    Parameters
    ----------
    reload : bool
        Whether to reload the server when the code changes.
    log_level : LogLevel
        The log level to use.
    skip_redis : bool
        Whether to skip using Redis
    """
    LOG.info("Starting the broker")
    module_name, cwd = get_module_and_cwd()

    worker_args = [
        "taskiq",
        "worker",
        "--log-level",
        log_level.upper(),
        "--max-tasks-per-child",
        "3",
        f"{module_name}.worker:broker",
    ]
    if reload:  # pragma: no-branch
        worker_args.append("--reload")
    worker_process = run_process(worker_args, cwd, skip_redis)
    try:
        worker_process.wait()
    except (KeyboardInterrupt, SystemExit):  # pragma: no cover
        LOG.info("Shutting down worker...")
        worker_process.terminate()


def start_scheduler(log_level: LogLevel, skip_redis: bool) -> None:
    """Start the scheduler.

    Parameters
    ----------
    log_level : LogLevel
        The log level to use.
    skip_redis : bool
        Whether to skip using Redis
    """
    LOG.info("Starting the scheduler")

    module_name, cwd = get_module_and_cwd()

    scheduler_args = [
        "taskiq",
        "scheduler",
        "--log-level",
        log_level.upper(),
        f"{module_name}.worker:scheduler",
    ]
    scheduler_process = run_process(scheduler_args, cwd, skip_redis)
    try:
        scheduler_process.wait()
    except (KeyboardInterrupt, SystemExit):  # pragma: no cover
        LOG.info("Shutting down scheduler...")
        scheduler_process.terminate()


def run_worker(worker_args: List[str], cwd: str, skip_redis: bool) -> None:
    """Run the worker.
    Parameters
    ----------
    worker_args : List[str]
        The arguments to pass to the worker.
    cwd : str
        The current working directory.
    skip_redis : bool
        Whether to skip using Redis
    """
    worker_process = run_process(worker_args, cwd, skip_redis)
    worker_process.wait()


def run_scheduler(
    scheduler_args: List[str], cwd: str, skip_redis: bool
) -> None:
    """Run the scheduler.
    Parameters
    ----------
    scheduler_args : List[str]
        The arguments to pass to the scheduler.
    cwd : str
        The current working directory.
    skip_redis : bool
        Whether to skip using Redis
    """
    scheduler_process = run_process(scheduler_args, cwd, skip_redis)
    scheduler_process.wait()


def start_broker_and_scheduler(
    reload: bool, log_level: LogLevel, skip_redis: bool
) -> None:
    """Start the broker and the scheduler.

    Parameters
    ----------
    reload : bool
        Whether to reload the server when the code changes.
    log_level : LogLevel
        The log level to use.
    skip_redis : bool
        Whether to skip using Redis
    """
    LOG.info("Starting the broker and the scheduler")

    module_name, cwd = get_module_and_cwd()

    worker_args = [
        "taskiq",
        "worker",
        "--log-level",
        log_level.upper(),
        f"{module_name}.worker:broker",
    ]
    if reload:  # pragma: no-branch
        worker_args.append("--reload")
    scheduler_args = [
        "taskiq",
        "scheduler",
        "--log-level",
        log_level.upper(),
        f"{module_name}.worker:scheduler",
    ]
    worker_process = run_process(worker_args, cwd, skip_redis)
    scheduler_process = run_process(scheduler_args, cwd, skip_redis)
    try:
        # Wait for both to complete
        worker_process.wait()
        scheduler_process.wait()
    except (KeyboardInterrupt, SystemExit):  # pragma: no cover
        LOG.info("Shutting down worker and scheduler...")
        worker_process.terminate()
        scheduler_process.terminate()


def start_all(
    host: str,
    port: int,
    reload: bool,
    log_level: LogLevel,
    logging_config: Dict[str, Any],
    skip_redis: bool,
) -> None:
    """Start both the uvicorn server and the worker.

    Parameters
    ----------
    host : str
        The host to bind the server to.
    port : int
        The port to bind the server to.
    reload : bool
        Whether to reload the server when the code changes.
    log_level : LogLevel
        The log level to use.
    logging_config : Dict[str, Any]
        The logging configuration.
    skip_redis : bool
        Whether to skip using Redis.
    """
    LOG.info("Starting the server and the worker")
    this_dir = Path(__file__).parent
    module_name = this_dir.name
    cwd = str(this_dir.parent)
    worker_args = [
        "taskiq",
        "worker",
        "--workers",
        "1",
        "--log-level",
        log_level.upper(),
        f"{module_name}.worker:broker",
    ]
    if reload:  # pragma: no-branch
        worker_args.append("--reload")
    scheduler_args = [
        "taskiq",
        "scheduler",
        "--log-level",
        log_level.upper(),
        f"{module_name}.worker:scheduler",
    ]

    processes = [
        Process(
            target=start_uvicorn,
            name="FastAPI",
            args=(host, port, reload, log_level, logging_config),
        ),
        Process(
            target=run_worker,
            name="TaskiqWorker",
            args=(worker_args, cwd, skip_redis),
        ),
        Process(
            target=run_scheduler,
            name="TaskiqScheduler",
            args=(scheduler_args, cwd, skip_redis),
        ),
    ]

    for proc in processes:
        proc.start()

    # pylint: disable=unused-argument
    def shutdown_all(signum: int, frame: FrameType | None) -> None:
        """Shutdown all processes.
        Parameters
        ----------
        signum : int
            The signal number.
        frame : FrameType
            The current stack frame.
        """
        print("\n[DEV] Shutting down all services...")
        for proc in processes:
            proc.terminate()
            proc.join(timeout=1)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_all)
    signal.signal(signal.SIGTERM, shutdown_all)
    signal.signal(signal.SIGQUIT, shutdown_all)

    for proc in processes:
        proc.join()


def start_uvicorn(
    host: str,
    port: int,
    reload: bool,
    log_level: LogLevel,
    logging_config: Dict[str, Any],
) -> None:
    """Start the Uvicorn server.

    Parameters
    ----------
    host : str
        The host to bind the server to.
    port : int
        The port to bind the server to.
    reload : bool
        Whether to reload the server when the code changes.
    log_level : LogLevel
        The log level to use.
    logging_config : Dict[str, Any]
        The logging configuration.
    """
    module_name, cwd = get_module_and_cwd()
    app_module_path = f"{module_name}.main"
    if host in ("localhost", "127.0.0.1"):  # pragma: no cover
        host = "0.0.0.0"
    LOG.info("Starting the server on %s:%s", host, port)
    uvicorn.run(
        f"{app_module_path}:app",
        host=host,
        port=port,
        reload=reload,
        app_dir=cwd,
        date_header=False,
        server_header=False,
        reload_dirs=[str(cwd)] if reload else None,
        reload_excludes=RELOAD_EXCLUDES if reload else None,
        log_level=log_level.lower(),
        log_config=logging_config,
        proxy_headers=True,
        forwarded_allow_ips="*",
        ws_ping_timeout=None,
        ws="websockets",
        # ws="wsproto",
    )
