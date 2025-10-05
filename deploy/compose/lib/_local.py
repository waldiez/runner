# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# flake8: noqa: C901
# pylint: disable=line-too-long

"""Staging related utils."""

import logging
import shutil
from functools import partial
from pathlib import Path, PurePosixPath

from ._common import ensure_dir, run, which


def _validate_stage_host(src: Path, dst: Path) -> None:
    if not src.exists() or not src.is_dir():
        raise FileNotFoundError(
            f"Source directory does not exist or is not a dir: {src}"
        )
    # Prevent recursive/self copy: dst must not be within src
    src_resolved = src.resolve()
    dst_resolved = dst.resolve()

    try:
        dst_resolved.relative_to(src_resolved)
        is_inside = True
    except ValueError:
        is_inside = False

    if is_inside:
        raise ValueError(f"Destination {dst} is inside source {src}")

    ensure_dir(dst)


def _do_rsync(
    src: Path,
    dst: Path,
    excludes: list[str],
    dry_run: bool,
) -> None:
    cmd = ["rsync", "-a", "--delete-excluded"]
    for ex in excludes:
        cmd += ["--exclude", ex]
    src_dir = str(src)
    if not src_dir.endswith("/"):
        src_dir += "/"
    dst_dir = str(dst)
    if not dst_dir.endswith("/"):
        dst_dir += "/"
    cmd += [src_dir, dst_dir]
    run(cmd, dry_run=dry_run)


def stage_host_dir(
    src: Path,
    dst: Path,
    excludes: list[str],
    dry_run: bool,
) -> None:
    """Stage a dir on the host.

    Prefer rsync if available, fall back to shutil

    Parameters
    ----------
    src : Path
        The src path on the host.
    dst : Path
        The destination path.
    excludes : list[str]
        The matches to exclude if rsync is used.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.

    Raises
    ------
    FileNotFoundError
        If the source directory does not exist or is not a dir.
    Exception
        If the operation fails.
    Notes
    -----
    - rsync path: uses `--delete-excluded` (strict clone semantics).
    - shutil path: honors excludes but does **not** delete extra files already in dst.
    - shutil path preserves symlinks (symlinks=True) to match `rsync -a`.
    """
    _validate_stage_host(src=src, dst=dst)
    if which("rsync"):
        _do_rsync(src=src, dst=dst, excludes=excludes, dry_run=dry_run)
        return

    root = src.resolve()
    ignore_func = partial(ignore_in_copy, root, excludes)

    if excludes:
        logging.info("Using shutil.copytree with excludes: %s", excludes)

    if dry_run:
        msg = f"Would copy (recursive, ignoring patterns): {src} -> {dst}"
        logging.info(msg)
        # pylint: disable=too-many-try-statements
        try:
            top_names = sorted([p.name for p in src.iterdir()])
            ignored = ignore_func(str(src), top_names)
            if ignored:
                logging.info("Top-level ignored by patterns: %s", ignored)
        except Exception:  # pylint: disable=broad-exception-caught
            # best-effort in dry-run
            pass
        return
    # Match rsync's symlink preservation with symlinks=True.
    # This remains a sync/merge (no deletion) unlike rsync --delete-excluded.
    try:
        shutil.copytree(
            src, dst, dirs_exist_ok=True, symlinks=True, ignore=ignore_func
        )
    except OSError as e:
        # Windows: lack of symlink privilege (WinError 1314): retry without symlinks
        if getattr(e, "winerror", None) == 1314:
            # A required privilege is not held by the client
            logging.warning(
                "Symlink creation not permitted on Windows; retrying without symlinks."
            )
            shutil.copytree(
                src, dst, dirs_exist_ok=True, symlinks=False, ignore=ignore_func
            )
        else:
            logging.error("Failed to copy %s to %s: %s", src, dst, e)
            raise


def prune_local(backups_dir: Path, name_prefix: str, keep: int) -> list[Path]:
    """Keep the newest N .tar.gz for a given name prefix.

    Parameters
    ----------
    backups_dir : Path
        The path of the backups.
    name_prefix : str
        The prefix to filter files in the backups.
    keep : int
        The number of files to keep.

    Returns
    -------
    list[Path]
        The files that were removed.
    """
    backups = list(backups_dir.glob(f"{name_prefix}-*.tar.gz"))
    if not backups:
        logging.info("No backups found matching %s-*.tar.gz", name_prefix)
        return []

    # glob.sort(key=lambda p: p.name, reverse=True)
    backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    keep = max(keep, 0)

    if keep >= len(backups):
        logging.info("Keeping all %s backups (keep=%s)", len(backups), keep)
        return []

    removed: list[Path] = []
    for backup in backups[keep:]:
        backup.unlink(missing_ok=True)
        (backup.parent / (backup.name + ".sha256")).unlink(missing_ok=True)
        removed.append(backup)
    return removed


def ignore_in_copy(
    root: Path,
    excludes: list[str],
    current_src: str,
    names: list[str],
) -> list[str]:
    """Ignore names in copytree operation.

    Parameters
    ----------
    root : Path
        The root directory.
    excludes : list[str]
        The patterns to exclude.
    current_src : str
        The current src in operation (the directory being visited by copytree())
    names : list[str]
        The list of src contents, as returned by os.listdir()

    Returns
    -------
    list[str]
        A list of names relative to the src directory that should be ignored
    """
    cur = Path(current_src)
    # Relative dir from src root; "" at root
    try:
        rel_dir = Path(".") if cur == root else cur.relative_to(root)
    except ValueError:
        logging.warning("Path %s is not relative to %s", cur, root)
        return []
    ignored: list[str] = []

    for name in names:
        # POSIX-style for pattern matching
        rel_path = (rel_dir / name).as_posix()
        # If any pattern matches the rel path OR the basename, ignore it
        p = PurePosixPath(rel_path)
        if any(
            p.match(pat) or PurePosixPath(name).match(pat) for pat in excludes
        ):
            ignored.append(name)
    return ignored
