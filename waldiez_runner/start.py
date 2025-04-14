# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=consider-using-with

"""Start the server and the worker in development mode."""

import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from types import FrameType
from typing import Any, Dict, List, Tuple

import uvicorn

from waldiez_runner._logging import LogLevel
from waldiez_runner.config import ENV_PREFIX

LOG = logging.getLogger(__name__)
UVICORN_RELOAD_EXCLUDES = [
    "examples/*",
    "waldiez_out/*",
    ".*",
    ".py[cod]",
    ".sw.*",
    "~*",
    "**/files/**/*",
    ".venv/*",
    "waldiez_runner/storage/*",
    "waldiez_runner/tasks/*",
    "examples/*",
]


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
        reload_includes=["waldiez_runner/**/*.py"] if reload else None,
        reload_excludes=UVICORN_RELOAD_EXCLUDES if reload else None,
        log_level=log_level.lower(),
        log_config=logging_config,
        proxy_headers=True,
        forwarded_allow_ips="*",
        ws_ping_timeout=None,
        ws="websockets",
        # ws="wsproto",
    )


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
        f"{module_name}.worker:broker",
    ]
    if reload:  # pragma: no-branch
        worker_args.append("--reload")
    worker_process = run_process(worker_args, cwd, skip_redis)
    try:
        worker_process.wait()
    except (KeyboardInterrupt, SystemExit):  # pragma: no cover
        LOG.info("Shutting down worker...")
    finally:
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
    finally:
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


def get_uvicorn_command(
    host: str,
    port: int,
    reload: bool,
    log_level: LogLevel,
    module_name: str,
    cwd: str,
) -> List[str]:
    """Get the Uvicorn command.

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
    module_name : str
        The module name.
    cwd : str
        The current working directory.

    Returns
    -------
    List[str]
        The Uvicorn command arguments.
    """
    uvicorn_cmd = [
        "uvicorn",
        f"{module_name}.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        log_level.lower(),
        "--app-dir",
        cwd,
        "--ws",
        "websockets",
        "--proxy-headers",
        "--forwarded-allow-ips",
        "*",
    ]
    if reload:
        uvicorn_cmd += [
            "--reload",
            "--reload-dir",
            cwd,
            *[f"--reload-include={x}" for x in ["waldiez_runner/**/*.py"]],
            *[f"--reload-exclude={x}" for x in UVICORN_RELOAD_EXCLUDES],
        ]
    return uvicorn_cmd


def get_worker_command(
    module_name: str,
    reload: bool,
    log_level: LogLevel,
) -> List[str]:
    """Get the Taskiq worker command.

    Parameters
    ----------
    module_name : str
        The module name.
    reload : bool
        Whether to reload the server when the code changes.
    log_level : LogLevel
        The log level to use.

    Returns
    -------
    List[str]
        The Taskiq worker command arguments.
    """
    worker_cmd = [
        "taskiq",
        "worker",
        "--workers",
        "1",
        "--log-level",
        log_level.upper(),
        f"{module_name}.worker:broker",
    ]
    if reload:
        worker_cmd.append("--reload")
    return worker_cmd


def get_scheduler_command(
    module_name: str,
    log_level: LogLevel,
) -> List[str]:
    """Get the Taskiq scheduler command.

    Parameters
    ----------
    module_name : str
        The module name.
    log_level : LogLevel
        The log level to use.

    Returns
    -------
    List[str]
        The Taskiq scheduler command arguments.
    """
    scheduler_cmd = [
        "taskiq",
        "scheduler",
        "--log-level",
        log_level.upper(),
        f"{module_name}.worker:scheduler",
    ]
    return scheduler_cmd


def start_all(
    host: str,
    port: int,
    reload: bool,
    log_level: LogLevel,
    skip_redis: bool,
) -> None:
    """Start all services (Uvicorn, Taskiq Worker, Scheduler).

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
    skip_redis : bool
        Whether to skip using Redis.
    """
    LOG.info("Starting all services (Uvicorn, Taskiq Worker, Scheduler)")
    module_name, cwd = get_module_and_cwd()

    # Environment
    env = os.environ.copy()
    if skip_redis:
        env[f"{ENV_PREFIX}NO_REDIS"] = "true"
        env[f"{ENV_PREFIX}REDIS"] = "false"

    # Build process commands
    uvicorn_cmd = get_uvicorn_command(
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        module_name=module_name,
        cwd=cwd,
    )
    worker_cmd = get_worker_command(
        module_name=module_name,
        reload=reload,
        log_level=log_level,
    )
    scheduler_cmd = get_scheduler_command(
        module_name=module_name,
        log_level=log_level,
    )

    processes = [
        subprocess.Popen(uvicorn_cmd, cwd=cwd, env=env),
        subprocess.Popen(worker_cmd, cwd=cwd, env=env),
        subprocess.Popen(scheduler_cmd, cwd=cwd, env=env),
    ]

    # pylint: disable=unused-argument
    def shutdown_all(signum: int, frame: FrameType | None) -> None:
        print("\n[DEV] Shutting down all subprocesses...")
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
        sys.exit(0)

    # Register shutdown
    signal.signal(signal.SIGINT, shutdown_all)
    signal.signal(signal.SIGTERM, shutdown_all)

    # Wait for all processes
    try:
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        shutdown_all(signal.SIGINT, None)
