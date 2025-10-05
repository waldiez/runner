# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Backup and restore related utils."""

import logging
import subprocess
from pathlib import Path

from ._common import tmp_name
from ._container import (
    container_exec,
    container_exec_out,
    container_restart,
    container_running,
    copy_from_container,
    copy_to_container,
)


def dump_redis(
    crt: str,
    container: str,
    out_file: Path,
    password: str,
    rdb_name: str,
    dry_run: bool,
) -> None:
    """Dump redis data.

    Parameters
    ----------
    crt : str
        The container runtime (docker/podman)
    container : str
        The name/id of the container.
    out_file : Path
        The destination path.
    password : str
        The redis password for authentication.
    rdb_name : str
        The dump's name.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.
    """
    args = ["redis-cli"]
    env = {"REDISCLI_AUTH": password} if password else None
    tmp_rdb = tmp_name("redis_dump.rdb")
    args += ["--rdb", tmp_rdb]
    container_exec(crt, container, args, dry_run=dry_run, env=env)
    copy_from_container(
        crt,
        container,
        tmp_rdb,
        out_file,
        dry_run=dry_run,
    )
    # rename locally if desired
    if not dry_run and out_file.name != rdb_name:
        out_file.rename(out_file.parent / rdb_name)
    # cleanup inside container
    container_exec(crt, container, ["rm", "-f", tmp_rdb], dry_run=dry_run)


def _redis_get_config(
    crt: str,
    container: str,
    password: str,
    key: str,
    dry_run: bool,
) -> str | None:
    """Returns CONFIG GET <key> value or None if not available."""
    env = {"REDISCLI_AUTH": password} if password else None
    args = ["redis-cli"] + ["CONFIG", "GET", key]
    try:
        output = container_exec_out(crt, container, args, env, dry_run=dry_run)
    except subprocess.CalledProcessError as e:
        logging.warning("Failed to get Redis config for %s: %s", key, e)
        return None

    # Check for error response
    if output.strip().startswith("(error)"):
        logging.warning("Redis error getting config %s: %s", key, output)
        return None

    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]

    # Try array format: 1) "key" 2) "value"
    for i, line in enumerate(lines):
        if line.lower() == key.lower() and i + 1 < len(lines):
            return lines[i + 1].strip('"')  # Remove quotes if present

    # Try simple format: key\nvalue
    if len(lines) == 2 and lines[0].lower().strip('"') == key.lower():
        return lines[1].strip('"')

    logging.warning(
        "Could not parse Redis CONFIG GET %s output: %r", key, output
    )
    return None


def restore_redis(
    crt: str,
    container: str,
    rdb_file: Path,
    password: str,
    dry_run: bool,
) -> None:
    """Restore a Redis database from an RDB file.

    Steps:
      - Discover Redis 'dir' and 'dbfilename' via CONFIG GET
      - Copy the provided RDB into that location
      - Restart container

    Parameters
    ----------
    crt : str
        The container runtime (docker/podman)
    container : str
        The name/id of the container.
    rdb_file : Path
        The path of the dump to restore.
    password : str
        The redis password for authentication.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.

    Raises
    ------
    FileNotFoundError
        If the specified dump rdb not found.
    RuntimeError
        If the specified container is not running.
    """
    if not rdb_file.exists() and not dry_run:
        raise FileNotFoundError(f"RDB file not found: {rdb_file}")

    # Check if Redis is running
    if not dry_run and not container_running(crt, container):
        raise RuntimeError(f"Container {container} is not running")

    # Shutdown Redis gracefully
    args = ["redis-cli"]
    env = {"REDISCLI_AUTH": password} if password else None

    if dry_run:
        logging.info("Would shutdown Redis in %s", container)
    else:
        try:
            container_exec(
                crt,
                container,
                args + ["SHUTDOWN", "SAVE"],
                env=env,
                dry_run=False,
            )
        except subprocess.CalledProcessError as e:
            # Redis might already be stopped
            logging.warning(
                "Redis shutdown failed (may already be stopped): %s", e
            )

    # Copy RDB file into container
    data_dir = (
        _redis_get_config(crt, container, password, "dir", dry_run=dry_run)
        or "/data"
    )
    dbfilename = (
        _redis_get_config(
            crt, container, password, "dbfilename", dry_run=dry_run
        )
        or "dump.rdb"
    )
    # pylint: disable=inconsistent-quotes
    target_path = f"{data_dir.rstrip('/')}/{dbfilename}"
    tmp_rdb = tmp_name("redis_restore.rdb")
    # Copy to temp location first
    copy_to_container(crt, container, rdb_file, tmp_rdb, dry_run=dry_run)
    if not dry_run:
        # Move to final location (overwrites existing)
        container_exec(
            crt, container, ["mv", tmp_rdb, target_path], dry_run=False
        )
    else:
        msg = f"Would move {tmp_rdb} to {target_path} in container"
        logging.info(msg)

    # Restart Redis
    container_restart(crt, container, dry_run=dry_run)
