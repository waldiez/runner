# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=broad-exception-caught,line-too-long
# flake8: noqa: C901

"""Container related functions."""

import logging
import shlex
import subprocess
import tarfile
from collections.abc import Sequence
from pathlib import Path

from ._common import pipe_run, run


def container_exists(crt: str, container: str) -> bool:
    """Check if a container exists.

    Parameters
    ----------
    crt : str
        The container runtime engine (docker/podman).
    container : str
        The container's name/id

    Returns
    -------
    bool
        True if {crt} inspect {container} succeeds, False otherwise.
    """
    try:
        subprocess.run(  # nosemgrep # nosec
            [crt, "inspect", container],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def container_running(crt: str, container: str) -> bool:
    """Check if a container is running.

    Parameters
    ----------
    crt : str
        The container runtime engine (docker/podman).
    container : str
        The container's name/id

    Returns
    -------
    bool
        True if inspect succeeds, False if not.
    """
    try:
        out = subprocess.check_output(
            [crt, "inspect", "-f", "{{.State.Running}}", container]
        )  # nosemgrep # nosec
        return out.decode().strip() == "true"
    except Exception:
        return False


def container_exec(
    crt: str,
    container: str,
    args: Sequence[str],
    dry_run: bool,
    env: dict[str, str] | None = None,
) -> None:
    """Execute a command inside a container.

    Parameters
    ----------
    crt : str
        The container runtime engine (docker/podman).
    container : str
        The container's name/id
    args : Sequence[str]
        The command and its arguments to call
    dry_run: bool
        Flag to skip actual operation and only log what would be called.
    env : dict[str, str] | None
        Environment variables to pass to the call.

    Raises
    ------
    RuntimeError
        If the container is not running.
    """
    if not dry_run and not container_running(crt, container):
        raise RuntimeError(f"Container {container} is not running")
    cmd = [crt, "exec"]
    if env:
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
    cmd += [container] + list(args)
    run(cmd, dry_run=dry_run)


def container_exec_out(
    crt: str,
    container: str,
    args: Sequence[str],
    env: dict[str, str] | None,
    dry_run: bool,
) -> str:
    """Execute a command inside a container and get its output.

    Parameters
    ----------
    crt : str
        The container runtime engine (docker/podman).
    container : str
        The container's name/id
    args : Sequence[str]
        The command and its arguments to call
    env : dict[str, str] | None
        Environment variables to pass to the call.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.

    Returns
    -------
    str
        The output of the call.

    Raises
    ------
    RuntimeError
        If the container is not running.
    """
    if not dry_run and not container_running(crt, container):
        raise RuntimeError(f"Container {container} is not running")
    cmd = [crt, "exec"]
    if env:
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
    cmd += [container] + list(args)
    if dry_run:
        cmd_str = " ".join(cmd)
        logging.info("Would call: %s", cmd_str)
    return subprocess.check_output(cmd).decode(
        encoding="utf-8", errors="replace"
    )  # nosec


def copy_from_container(
    crt: str,
    container: str,
    src_path: str,
    dst: Path,
    dry_run: bool,
) -> None:
    """Copy a path from a container to the host.

    Parameters
    ----------
    crt : str
        The container runtime engine (docker/podman).
    container : str
        The container's name/id
    src_path : str
        The path in the container.
    dst: Path
        The destination path in the host.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.

    Raises
    ------
    RuntimeError
        If the container is not running.
    """
    if not dry_run and not container_running(crt, container):
        raise RuntimeError(f"Container {container} is not running")
    # Use 'cp' for docker/podman (supports container:path)
    if not dry_run:
        run([crt, "cp", f"{container}:{src_path}", str(dst)], dry_run=False)
    else:
        msg = f"Would copy from {container}:{src_path} to {dst}"
        logging.info(msg)


def _container_default_ids(
    crt: str, container: str, dry_run: bool = False
) -> tuple[str, str]:
    """Return (uid, gid) that processes run as by default in the container."""
    # Runs without --user: detects the container’s default runtime user
    out_uid = (
        container_exec_out(
            crt,
            container,
            ["sh", "-c", "id -u"],
            dry_run=dry_run,
            env=None,
        )
        or "0"
    )
    out_gid = (
        container_exec_out(
            crt,
            container,
            ["sh", "-c", "id -g"],
            dry_run=dry_run,
            env=None,
        )
        or "0"
    )
    return out_uid.strip(), out_gid.strip()


def _container_exec_as_root(
    crt: str, container: str, args: list[str], dry_run: bool
) -> None:
    """Execute a command as root inside the container."""
    cmd = [crt, "exec", "--user", "0:0", container, "sh", "-c", " ".join(args)]
    run(cmd, dry_run=dry_run)


def _chown_path_in_container(
    crt: str, container: str, container_path: str, dry_run: bool
) -> None:
    """Chown to default user if needed."""
    uid, gid = _container_default_ids(crt, container, dry_run=dry_run)
    if uid != "0" and gid != "0":
        _container_exec_as_root(
            crt,
            container,
            args=["chown", "-R", f"{uid}:{gid}", container_path],
            dry_run=dry_run,
        )


def copy_to_container(
    crt: str,
    container: str,
    src: str | Path,
    dst_path: str,
    dry_run: bool,
) -> None:
    """Copy a local file into a container (docker/podman cp).

    Parameters
    ----------
    crt : str
        The container runtime engine (docker/podman).
    container : str
        The container's name/id.
    src : str | Path
        The path in the host.
    dst_path: str
        The destination path in the container.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.

    Raises
    ------
    RuntimeError
        If the container is not running.
    """
    if not dry_run and not container_running(crt, container):
        raise RuntimeError(f"Container {container} is not running")
    if not dry_run:
        run([crt, "cp", str(src), f"{container}:{dst_path}"], dry_run=dry_run)
        _chown_path_in_container(crt, container, dst_path, dry_run=dry_run)
    else:
        msg = f"Would copy {src} to {container}:{dst_path}"
        logging.info(msg)


def container_restart(crt: str, container: str, dry_run: bool) -> None:
    """Restart a container (docker/podman).

    Parameters
    ----------
    crt : str
        The container runtime engine (docker/podman).
    container : str
        The container's name/id.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.

    Raises
    ------
    RuntimeError
        If the container is not running.
    """
    if not dry_run and not container_running(crt, container):
        raise RuntimeError(f"Container {container} is not running")
    if not dry_run:
        run([crt, "restart", container], dry_run=dry_run)
    else:
        msg = f"Would restart container {container}"
        logging.info(msg)


def stage_container_dir(
    crt: str,
    container: str,
    src_path: str,
    dst: Path,
    excludes: list[str],
    dry_run: bool,
) -> None:
    """Stage a directory in a container.

    Parameters
    ----------
    crt : str
        The container runtime engine (docker/podman).
    container : str
        The container's name/id
    src_path : str
        The path in the container.
    dst: Path
        The destination path in the host.
    excludes : list[str]
        Patterns to exclude in the operation.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.

    Raises
    ------
    RuntimeError
        If the container is not running.
    """
    if not dry_run and not container_running(crt, container):
        raise RuntimeError(f"Container {container} is not running")
    if not dry_run:
        dst.mkdir(parents=True, exist_ok=True)

    left: list[str] = [
        crt,
        "exec",
        container,
        "tar",
        "--no-same-owner",
        "-C",
        src_path,
        "-c",
        "-f",
        "-",
    ]
    if excludes:
        for pat in _expand_exclude_patterns(excludes):
            # use separate args to avoid shell expansion issues
            left += [f"--exclude={pat}"]
    left += ["."]
    right = ["tar", "--no-same-owner", "-C", str(dst), "-xf", "-"]
    if dry_run:
        left_str = " ".join(left)
        right_str = " ".join(right)
        msg = (
            f"Would tar from {container}:{src_path} -> {dst}:"
            f"\n{left_str} | {right_str}"
        )
        logging.info(msg)
        return

    pipe_run(left, right, dry_run=False)


def restore_container_files(
    crt: str,
    container: str,
    src: Path,
    dst_path: str,
    dry_run: bool,
) -> None:
    """Restore container files from an archive.

    Parameters
    ----------
    crt : str
        The container runtime engine (docker/podman).
    container : str
        The container's name/id.
    src : str | Path
        The path in the host.
    dst_path: str
        The destination path in the container.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.
    """
    if not container or not dst_path:
        return
    if not container or not dst_path:
        logging.warning("    Skipping: invalid container config")
        return

    if not dry_run:
        if not container_exists(crt, container):
            logging.error("    Container %s does not exist", container)
            return
        if not container_running(crt, container):
            logging.error("    Container %s is not running", container)
            return

    logging.info("    %s -> %s:%s (container)", src, container, dst_path)
    # Create tar of the source directory
    tar_file = src.parent / f"{src.name}.tar"
    if not dry_run:
        with tarfile.open(tar_file, "w") as archive:
            for item in src.rglob("*"):
                archive_name = item.relative_to(src)
                # cspell: disable-next-line
                archive.add(item, arcname=str(archive_name))

    # Copy tar to container
    container_tar = f"/tmp/{tar_file.name}"  # nosemgrep # nosec
    copy_to_container(crt, container, tar_file, container_tar, dry_run=dry_run)
    dst = shlex.quote(dst_path)
    tar = shlex.quote(container_tar)
    script = f"mkdir -p {dst}"
    container_exec(crt, container, ["sh", "-c", script], dry_run=dry_run)
    script = f"find {dst} -mindepth 1 -delete || true"
    container_exec(crt, container, ["sh", "-c", script], dry_run=dry_run)
    script = f"tar --no-same-owner -xf {tar} -C {dst} || exit 1"
    container_exec(crt, container, ["sh", "-c", script], dry_run=dry_run)
    # Cleanup
    script = f"rm -f {tar} || true"
    container_exec(crt, container, ["sh", "-c", script], dry_run=dry_run)
    tar_file.unlink()


def _expand_exclude_patterns(pats: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in pats or []:
        p = raw.strip()
        if not p:
            continue
        # normalize: strip leading "./", strip trailing "/"
        if p.startswith("./"):
            p = p[2:]
        if p.endswith("/"):
            p = p[:-1]

        variants = {
            p,
            f"{p}/*",
            f"./{p}",
            f"./{p}/*",
        }
        # If user didn't start with "*", also match anywhere in the tree
        if not p.startswith("*"):
            variants.update(
                {
                    f"*/{p}",
                    f"*/{p}/*",
                }
            )

        for v in variants:
            if v not in seen:
                seen.add(v)
                out.append(v)
    return out
