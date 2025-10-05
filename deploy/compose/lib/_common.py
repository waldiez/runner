# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Backup and restore related utils."""

import atexit
import logging
import secrets
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Generator, Sequence

HERE = Path(__file__).parent.resolve()
SENSITIVE_TOKENS = (
    "PGPASSWORD=",
    "AWS_ACCESS_KEY_ID=",
    "AWS_SECRET_ACCESS_KEY=",
    "AWS_SESSION_TOKEN=",
    "REDISCLI_AUTH=",
    "Authorization:",
    "authorization:",
)
REDACT_FOLLOWING_FLAGS = {
    "-a",
    "--password",
    "--auth",
    "--secret",
    "--header",
    "--headers",
    "-H",
}


def redact(cmd: Sequence[str]) -> str:
    """Redact sensitive data in a command.

    Parameters
    ----------
    cmd : Sequence[str]
        The command to check.

    Returns
    -------
    str
        The string with sensitive data redacted.
    """
    parts = list(cmd)
    i = 0
    while i < len(parts):
        p = parts[i]
        for tok in SENSITIVE_TOKENS:
            if tok in p:
                parts[i] = p.split(tok, 1)[0] + tok + "***REDACTED***"
        if p in REDACT_FOLLOWING_FLAGS and i + 1 < len(parts):
            # redact the following token (header value, password, etc.)
            parts[i + 1] = "***REDACTED***"
            i += 2
            continue
        i += 1
    return " ".join(parts)


_temp_files: list[Path] = []


def setup_logging(verbose: bool = False) -> None:
    """Configure logging.

    Parameters
    ----------
    verbose : bool
        Enable debug logging.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(op: str) -> logging.Logger:
    """Get or create a logger for an operation (backup/restore).

    Parameters
    ----------
    op : str
        The operation for the logger's name suffix.

    Returns
    -------
    logging.Logger
        The logger.
    """
    return logging.getLogger(f"waldiez.runner.compose.{op}")


def tmp_name(basename: str) -> str:
    """Get a unique name to be used in (a container's) temp dir.

    Parameters
    ----------
    basename : str
        The base name.

    Returns
    -------
    str
        The tmp name.
    """
    path = f"/tmp/{basename}.{secrets.token_hex(6)}"  # nosemgrep # nosec
    _temp_files.append(Path(path))
    return str(path)


def _cleanup_temp_files() -> None:
    for path in _temp_files:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:  # pylint: disable=broad-exception-caught
            pass


atexit.register(_cleanup_temp_files)


def run(cmd: Sequence[str], dry_run: bool, cwd: Path | None = None) -> None:
    """Run a command.

    Parameters
    ----------
    cmd : Sequence[str]
        The command and the arguments.
    dry_run : bool
        Flag to skip actual operation and only log what would be called.
    cwd : Path | None
        The cwd to use for the command.
    """
    cmd_str = redact(cmd)
    if dry_run:
        logging.info("Would run:\t%s", cmd_str)
        return
    logging.info("Running: \n%s\n", cmd_str)
    subprocess.run(
        cmd, check=True, cwd=str(cwd) if cwd else None
    )  # nosemgrep # nosec


def pipe_run(left: Sequence[str], right: Sequence[str], dry_run: bool) -> None:
    """Run two commands one after the other.

    Parameters
    ----------
    left : Sequence[str]
        The first part.
    right : Sequence[str]
        The second part.
    dry_run : bool
        Flag to skip running, just show what would be run.

    Raises
    ------
    subprocess.CalledProcessError
        If any of the commands fails.
    """
    left_str = redact(left)
    right_str = redact(right)
    cmd_str = f"{left_str} | {right_str}"
    if dry_run:
        logging.info("Would run:\n%s\n", cmd_str)
        return
    logging.info("Running:\n%s\n", cmd_str)
    # pylint: disable=consider-using-with
    p1 = subprocess.Popen(left, stdout=subprocess.PIPE)  # nosemgrep # nosec
    p2 = subprocess.Popen(right, stdin=p1.stdout)  # nosemgrep # nosec
    p1.stdout.close()  # type: ignore
    if p1.wait() != 0 or p2.wait() != 0:
        raise subprocess.CalledProcessError(1, "pipeline")


def which(cmd: str) -> bool:
    """Check if a command can be resolved.

    Parameters
    ----------
    cmd : str
        The command to check.

    Returns
    -------
    bool
        True if the command is resolved, False otherwise.
    """
    return shutil.which(cmd) is not None


def utc_now() -> datetime:
    """Get the current UTc datetime.

    Returns
    -------
    datetime
        The current datetime in UTC.
    """
    return datetime.now(timezone.utc)


def split_list(raw: str) -> list[str]:
    """Split a raw string to a list of strings.

    Parameters
    ----------
    raw : str
        The raw parsed string

    Returns
    -------
    list[str]
        The list of strings after split.
    """
    if not raw:
        return []
    return [x.strip() for x in raw.replace(",", "\n").splitlines() if x.strip()]


def format_size(num_bytes: float) -> str:
    """Format bytes into a human-readable string.

    Parameters
    ----------
    num_bytes : int
        The number of bytes.

    Returns
    -------
    str
        The human-readable string.
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


@contextmanager
def tempdir(
    prefix: str = "wlz-", path: Path | None = None
) -> Generator[Path, None]:
    """Enter a temp context.

    Parameters
    ----------
    prefix : str
        The temp folder's prefix
    path : Path | None
        Specific path to use instead of creating a new tmp one.
    Yields
    ------
    Path
        The context's temp directory.
    """
    d = Path(tempfile.mkdtemp(prefix=prefix)) if not path else path
    if path:
        path.mkdir(parents=True, exist_ok=True)
    try:
        yield d
    finally:
        if not path:
            shutil.rmtree(d, ignore_errors=True)


def ensure_dir(path: Path) -> None:
    """Ensure a directory exists.

    Parameters
    ----------
    path : Path
        The directory to create if needed.
    """
    path.mkdir(parents=True, exist_ok=True)


def try_do(
    what: Callable[[], int],
    on_interrupt: Callable[[], None],
    on_error: Callable[[Exception], None],
) -> int:
    """Try calling a callable.

    Parameters
    ----------
    what : Callable[[], int]
        The callable to try.
    on_interrupt : Callable[[], None]
        The handler for a KeyboardInterrupt
    on_error: Callable[[Exception], None]
        The handler for other exceptions.

    Returns
    -------
    int
        The result of the operation.
    """
    try:
        return what()
    except KeyboardInterrupt:
        on_interrupt()
        # log.warning("\nRestore interrupted by user")
        # if cfg:
        #     send_notification(cfg, False, "Restore interrupted by user")
        return 130  # Standard exit code for SIGINT

    except Exception as e:  # pylint: disable=broad-exception-caught
        on_error(e)
        # log.error("Restore failed: %s", e, exc_info=args.verbose)
        # if cfg:
        #     send_notification(cfg, False, f"Restore failed: {e}")
        return 1
