# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.


"""Backup and restore related utils."""

from pathlib import Path

from ._common import tmp_name
from ._container import container_exec, copy_from_container, copy_to_container


def dump_postgres(
    crt: str,
    container: str,
    user: str,
    database: str,
    password: str,
    out_file: Path,
    dump_extras: str,
    dry_run: bool,
) -> None:
    """Dump postgres data.

    Parameters
    ----------
    crt : str
        The container runtime (docker/podman)
    container : str
        The name/id of the container.
    user : str
        The db user.
    database : str
        The db name.
    password : str
        The db password for authentication.
    out_file : Path
        The dump's destination path.
    dump_extras : str
        Extra arguments (space separated) to use in the pg_dump command.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.
    """
    args = ["pg_dump", "-U", user, "-d", database, "-Fc"]
    if dump_extras:
        args += dump_extras.split()
    tmp_pg = tmp_name("postgres.dump")
    args += ["-f", tmp_pg]
    env = {"PGPASSWORD": password} if password else None
    container_exec(crt, container, args, env=env, dry_run=dry_run)
    # copy out
    copy_from_container(
        crt,
        container,
        tmp_pg,
        out_file,
        dry_run=dry_run,
    )
    # cleanup inside container
    container_exec(crt, container, ["rm", "-f", tmp_pg], dry_run=dry_run)


def restore_postgres(
    crt: str,
    container: str,
    dump_file: Path,
    user: str,
    database: str,
    password: str,
    *,
    restore_extras: str = "--clean --if-exists",  # extra pg_restore flags
    dry_run: bool,
) -> None:
    """Restore a PostgreSQL database from a pg_dump file.

    Parameters
    ----------
    crt : str
        The container runtime (docker/podman)
    container : str
        The name/id of the container.
    user : str
        The db user.
    database : str
        The db name.
    password : str
        The db password for authentication.
    dump_file : Path
        The path of the previously dumped file.
    restore_extras : str
        Extra arguments (space separated) to use in the pg_restore command.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.

    Raises
    ------
    FileNotFoundError
        If the specified dump file is not found.
    """
    if not dump_file.exists() and not dry_run:
        raise FileNotFoundError(f"Dump file not found: {dump_file}")

    # Copy dump file into container
    tmp_in_container = tmp_name("postgres.restore.dump")
    copy_to_container(
        crt, container, dump_file, tmp_in_container, dry_run=dry_run
    )

    # Restore database
    args = [
        "pg_restore",
        "-U",
        user,
        "-d",
        database,
    ]
    if restore_extras:
        args += restore_extras.split()
    args += [tmp_in_container]

    env = {"PGPASSWORD": password} if password else None
    container_exec(crt, container, args, env=env, dry_run=dry_run)
    # Cleanup inside container
    container_exec(
        crt, container, ["rm", "-f", tmp_in_container], dry_run=dry_run
    )
