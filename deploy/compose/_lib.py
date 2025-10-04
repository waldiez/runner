# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught,inconsistent-quotes
# pylint: disable=missing-function-docstring,missing-param-doc
# pylint: disable=missing-return-doc,missing-yield-doc,missing-raises-doc

"""Backup and restore related utils."""

import atexit
import hashlib
import json
import logging
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Sequence, TypedDict
from urllib.request import Request, urlopen

HERE = Path(__file__).parent.resolve()
# optionally load from env
DOT_ENVS = [".env", ".aws.env"]

try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    for file_candidate in DOT_ENVS:
        path_candidates = [
            HERE / file_candidate,
            HERE.parent / file_candidate,
            HERE.parent.parent / file_candidate,
        ]
        for path_candidate in path_candidates:
            if path_candidate.exists():
                load_dotenv(str(path_candidate))
                break


SENSITIVE_TOKENS = (
    "PGPASSWORD=",
    "AWS_ACCESS_KEY_ID=",
    "AWS_SECRET_ACCESS_KEY=",
    "AWS_SESSION_TOKEN=",
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


class S3Params(TypedDict, total=False):
    """S3 params dict"""

    bucket: str
    prefix: str
    aws_profile: str
    aws_region: str
    object_tags: str


class SSHParams(TypedDict, total=True):
    """SSH params dict"""

    dest: str
    port: int
    rsync_opts: str
    prune_cmd: str


def _redact(cmd: Sequence[str]) -> str:
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
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(op: str) -> logging.Logger:
    """Get or create the backup logger."""
    return logging.getLogger(f"waldiez.runner.compose.{op}")


def _tmp_name(basename: str) -> str:
    path = f"/tmp/{basename}.{secrets.token_hex(6)}"  # nosemgrep # nosec
    _temp_files.append(Path(path))
    return str(path)


def _cleanup_temp_files() -> None:
    for path in _temp_files:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass


atexit.register(_cleanup_temp_files)


# ---------------------------
# Shell helpers
# ---------------------------
def run(cmd: Sequence[str], dry_run: bool, cwd: Path | None = None) -> None:
    """Run a command.

    Parameters
    ----------
    cmd : Sequence[str]
        The command and the arguments.
    dry_run : bool
        Flag to skip running and only log what to run.
    cwd : Path | None
        Optional cwd to chdir to.
    """
    cmd_str = _redact(cmd)
    if dry_run:
        logging.info("Would run:\t%s", cmd_str)
        return
    logging.info("Running: %s", {cmd_str})
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
    left_str = _redact(left)
    right_str = _redact(right)
    cmd_str = f"{left_str} | {right_str}"
    if dry_run:
        logging.info("Would run:\n%s\n", {cmd_str})
        return
    logging.info("Would run:\n%s\n", {cmd_str})
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
        True if the command can be resolved, False otherwise.
    """
    return shutil.which(cmd) is not None


# ---------------------------
# Time + naming
# ---------------------------
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ts_compact(dt: datetime | None = None) -> str:
    dt = dt or utc_now()
    return dt.strftime("%Y%m%dT%H%M%SZ")


def archive_basename(name: str, dt: datetime | None = None) -> str:
    return f"{name}-{ts_compact(dt)}"


@contextmanager
def tempdir(prefix: str = "wlz-") -> Generator[Path, None]:
    d = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


# ---------------------------
# Checksums
# ---------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256(usedforsecurity=False)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_checksum(path: Path) -> Path:
    digest = sha256_file(path)
    out = path.with_suffix(path.suffix + ".sha256")
    out.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return out


def verify_checksum(archive: Path) -> tuple[bool, str]:
    """Returns (is_valid, message)"""
    check = archive.with_suffix(archive.suffix + ".sha256")
    if not check.exists():
        return False, "Checksum file not found"

    line = check.read_text(encoding="utf-8").strip()
    parts = line.split()
    if len(parts) < 2:
        return False, "Invalid checksum format"

    expected, filepart = parts[0], parts[-1]
    if Path(filepart).name != archive.name:
        return False, f"Filename mismatch: {filepart} != {archive.name}"

    actual = sha256_file(archive)
    if actual != expected:
        return False, f"Checksum mismatch: {actual} != {expected}"

    return True, "Valid"


# ---------------------------
# Container cmd helpers
# ---------------------------
def container_exists(crt: str, name: str) -> bool:
    try:
        subprocess.run(  # nosemgrep # nosec
            [crt, "inspect", name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except BaseException:
        return False


def container_running(crt: str, name: str) -> bool:
    try:
        out = subprocess.check_output(
            [crt, "inspect", "-f", "{{.State.Running}}", name]
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
    env: dict[str, str] | None = None,
) -> bytes:
    cmd = [crt, "exec"]
    if env:
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
    cmd += [container] + list(args)
    return subprocess.check_output(cmd)  # nosec


def copy_from_container(
    crt: str, container: str, src_path: str, dst: Path, dry_run: bool
) -> None:
    # Use 'cp' for docker/podman (supports container:path)
    if not dry_run:
        run([crt, "cp", f"{container}:{src_path}", str(dst)], dry_run=False)
    else:
        msg = f"Would copy from {container}:{src_path} to {dst}"
        logging.info(msg)


def copy_to_container(
    crt: str, container: str, src: str | Path, dst_path: str, *, dry_run: bool
) -> None:
    """Copy a local file into a container (docker/podman cp)."""
    if not dry_run:
        run([crt, "cp", str(src), f"{container}:{dst_path}"], dry_run=dry_run)
    else:
        msg = f"Would copy {src} to {container}:{dst_path}"
        logging.info(msg)


def container_restart(rt: str, container: str, *, dry_run: bool) -> None:
    """Restart a container (docker/podman)."""
    if not dry_run:
        run([rt, "restart", container], dry_run=dry_run)
    else:
        msg = f"Would restart container {container}"
        logging.info(msg)


# ---------------------------
# Staging helpers
# ---------------------------
def stage_host_dir(
    src: Path, dst: Path, excludes: list[str], dry_run: bool
) -> None:
    ensure_dir(dst)
    # Prefer rsync if available for speed & excludes, fall back to shutil
    if which("rsync"):
        cmd = ["rsync", "-a", "--delete-excluded"]
        for ex in excludes:
            cmd += ["--exclude", ex]
        cmd += [str(src) + "/", str(dst) + "/"]
        run(cmd, dry_run=dry_run)
    else:
        # simple copy (no delete/exclude)
        if excludes:
            msg = (
                "Note: excludes are ignored without rsync; "
                "fallback will copy everything."
            )
            logging.warning(msg)
        if dry_run:
            msg = f"Would copy (recursive): {src} -> {dst}"
            logging.info(msg)
            return
        shutil.copytree(src, dst, dirs_exist_ok=True)


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


def stage_container_dir(
    crt: str,
    container: str,
    src_path: str,
    dst: Path,
    excludes: list[str],
    dry_run: bool,
) -> None:
    if not dry_run and not container_running(crt, container):
        raise RuntimeError(f"Container {container} is not running")
    ensure_dir(dst)

    left: list[str] = [
        crt,
        "exec",
        container,
        "tar",
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
    right = ["tar", "-C", str(dst), "-xf", "-"]
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


def dump_postgres(
    crt: str,
    container: str,
    user: str,
    database: str,
    out_file: Path,
    password: str,
    dump_extras: str,
    dry_run: bool,
) -> None:
    args = ["pg_dump", "-U", user, "-d", database, "-Fc"]
    if dump_extras:
        args += dump_extras.split()
    tmp_pg = _tmp_name("postgres.dump")
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
    user: str,
    database: str,
    dump_file: Path,
    *,
    password: str = "",  # nosemgrep # nosec
    restore_extras: str = "--clean --if-exists",  # extra pg_restore flags
    dry_run: bool,
) -> None:
    """Restore a PostgreSQL database from a pg_dump file."""
    if not dump_file.exists():
        raise FileNotFoundError(f"Dump file not found: {dump_file}")

    # Copy dump file into container
    tmp_in_container = _tmp_name("postgres.restore.dump")
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


def dump_redis(
    crt: str,
    container: str,
    out_file: Path,
    password: str,
    rdb_name: str,
    dry_run: bool,
) -> None:
    args = ["redis-cli"]
    env = {"REDISCLI_AUTH": password} if password else None
    tmp_rdb = _tmp_name("redis_dump.rdb")
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
    crt: str, container: str, password: str, key: str
) -> str | None:
    """Returns CONFIG GET <key> value or None if not available."""
    env = {"REDISCLI_AUTH": password} if password else None
    args = ["redis-cli"] + ["CONFIG", "GET", key]
    try:
        out = container_exec_out(crt, container, args, env)
    except subprocess.CalledProcessError as e:
        logging.warning("Failed to get Redis config for %s: %s", key, e)
        return None

    output = out.decode()

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
    """
    if not rdb_file.exists():
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
    data_dir = _redis_get_config(crt, container, password, "dir") or "/data"
    dbfilename = (
        _redis_get_config(crt, container, password, "dbfilename") or "dump.rdb"
    )
    target_path = f"{data_dir.rstrip('/')}/{dbfilename}"
    tmp_rdb = _tmp_name("redis_restore.rdb")
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


# ---------------------------
# Local retention
# ---------------------------
def prune_local(backups_dir: Path, name_prefix: str, keep: int) -> list[Path]:
    """Keep the newest N .tar.gz for a given name prefix."""
    glob = list(backups_dir.glob(f"{name_prefix}-*.tar.gz"))
    glob.sort(key=lambda p: p.name, reverse=True)
    removed: list[Path] = []
    for old in glob[keep:]:
        old.unlink(missing_ok=True)
        (old.parent / (old.name + ".sha256")).unlink(missing_ok=True)
        removed.append(old)
    return removed


# ---------------------------
# S3 transport (aws cli)
# ---------------------------
def _aws_base_args(params: S3Params) -> list[str]:
    args: list[str] = []
    profile = params.get("aws_profile", "")
    if profile:
        args += ["--profile", profile]
    region = params.get("aws_region", "")
    if region:
        args += ["--region", region]
    return args


def put_object_tags(
    params: S3Params,
    key: str,
    dry_run: bool,
) -> None:
    object_tags = params.get("object_tags", "")
    bucket = params.get("bucket")
    prefix = params.get("prefix")
    if not object_tags or not prefix or not bucket:
        return
    # "k=v,k2=v2" -> [{"Key":"k","Value":"v"}, ...]
    tag_set: list[dict[str, str]] = []
    for pair in object_tags.split(","):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        k, v = k.strip(), v.strip()

        # AWS S3 tag validation
        if not k or len(k) > 128:
            continue
        if len(v) > 256:
            continue

        tag_set.append({"Key": k, "Value": v})
    if not tag_set:
        return
    cmd = [
        "aws",
        "s3api",
        "put-object-tagging",
        "--bucket",
        bucket,
        "--key",
        f"{prefix.strip('/')}/{key}",
        "--tagging",
        json.dumps({"TagSet": tag_set}),
    ] + _aws_base_args(params)
    run(cmd, dry_run=dry_run)


def s3_cp_upload(
    params: S3Params,
    local: Path,
    dry_run: bool,
) -> None:
    bucket = params.get("bucket")
    prefix = params.get("prefix")
    if not bucket or not prefix:
        return
    dest = f"s3://{bucket}/{prefix.strip('/')}/"
    cmd = ["aws", "s3", "cp", str(local), dest] + _aws_base_args(params)
    run(cmd, dry_run=dry_run)
    put_object_tags(
        params=params,
        key=local.name,
        dry_run=dry_run,
    )


def s3_cp_download(
    key: str,
    local: Path,
    params: S3Params,
    dry_run: bool,
) -> None:
    bucket = params.get("bucket")
    prefix = params.get("prefix")
    if not bucket or not prefix:
        return
    src = f"s3://{bucket}/{prefix.strip('/')}/{key}"
    cmd = ["aws", "s3", "cp", src, str(local)] + _aws_base_args(params)
    run(cmd, dry_run=dry_run)


def s3_sync_mirror(
    params: S3Params,
    local_dir: Path,
    name_prefix: str,
    dry_run: bool,
) -> None:
    bucket = params.get("bucket")
    prefix = params.get("prefix")
    if not bucket or not prefix:
        return
    dest = f"s3://{bucket}/{prefix.strip('/')}/"
    # include only our backup + checksum files
    cmd = [
        "aws",
        "s3",
        "sync",
        str(local_dir) + "/",
        dest,
        "--exact-timestamps",
        "--delete",
        "--exclude",
        "*",
        "--include",
        f"{name_prefix}-*.tar.gz",
        "--include",
        f"{name_prefix}-*.tar.gz.sha256",
    ] + _aws_base_args(params)
    run(cmd, dry_run=dry_run)


def s3_list_backups(
    params: S3Params,
    name_prefix: str,
    dry_run: bool,
) -> list[str]:
    """Return object keys (filenames) for our archives, newest first."""
    bucket = params.get("bucket")
    prefix = params.get("prefix")
    if not bucket or not prefix:
        return []
    dest = f"s3://{bucket}/{prefix.strip('/')}/"
    cmd = ["aws", "s3", "ls", dest] + _aws_base_args(params)
    if dry_run:
        cmd_str = " ".join(cmd)
        logging.info("Would run: %s", cmd_str)
        return []
    env = dict(os.environ)
    env.setdefault("LC_ALL", "C")
    out = subprocess.check_output(cmd, env=env)  # nosemgrep # nosec
    keys: list[str] = []
    for line in out.decode().splitlines():
        if line.strip().startswith("PRE "):
            continue
        parts = line.strip().split()
        if len(parts) == 4:
            key = parts[3]
            if key.startswith(f"{name_prefix}-") and key.endswith(".tar.gz"):
                keys.append(key)
    keys.sort(reverse=True)
    return keys


def s3_prune_retain(
    params: S3Params,
    name_prefix: str,
    keep: int,
    dry_run: bool,
) -> list[str]:
    bucket = params.get("bucket")
    prefix = params.get("prefix")
    if not bucket or not prefix:
        return []
    keys = s3_list_backups(
        params,
        name_prefix=name_prefix,
        dry_run=dry_run,
    )
    to_delete = keys[keep:]
    base_args = _aws_base_args(params)
    for key in to_delete:
        args = [
            "aws",
            "s3",
            "rm",
            f"s3://{bucket}/{prefix.strip('/')}/{key}",
        ] + base_args
        run(args, dry_run=dry_run)
        # try checksum
        args = [
            "aws",
            "s3",
            "rm",
            f"s3://{bucket}/{prefix.strip('/')}/{key}.sha256",
        ] + base_args
        run(args, dry_run=dry_run)
    return to_delete


# ---------------------------
# SSH transport (rsync/scp)
# ---------------------------
def ssh_upload(
    params: SSHParams,
    local_file: Path,
    checksum_file: Path | None,
    dry_run: bool,
) -> None:
    ssh_port = params["port"]
    ssh_dest = params["dest"]
    rsync_opts = params["rsync_opts"]
    rsh = f"ssh -p {ssh_port}"
    run(
        [
            "rsync",
            *rsync_opts.split(),
            "-e",
            rsh,
            str(local_file),
            f"{ssh_dest}/",
        ],
        dry_run=dry_run,
    )
    if checksum_file and checksum_file.exists():
        run(
            [
                "rsync",
                *rsync_opts.split(),
                "-e",
                rsh,
                str(checksum_file),
                f"{ssh_dest}/",
            ],
            dry_run=dry_run,
        )


def ssh_prune_remote(
    params: SSHParams,
    name_prefix: str,
    keep: int,
    dry_run: bool,
) -> None:
    ssh_dest = params["dest"]
    ssh_port = params["port"]
    ssh_prune = params["prune_cmd"]
    host, _, remote_dir = ssh_dest.partition(":")
    if ssh_prune:
        # custom prune
        cmd = ["ssh", "-p", str(ssh_port), host, ssh_prune]
        run(cmd, dry_run=dry_run)
        return
    # default simple prune based on filename order
    # pylint: disable=line-too-long
    script = (
        # cspell: disable-next-line
        f'set -Eeuo pipefail; cd "{remote_dir}"; '
        f"ls -1t {name_prefix}-*.tar.gz 2>/dev/null | awk 'NR>{keep}' | "
        'while read -r f; do echo "rm $f"; rm -f -- "$f" "$f.sha256"; done || true'  # noqa: E501
    )
    cmd = ["ssh", "-p", str(ssh_port), host, script]
    run(cmd, dry_run=dry_run)


def ssh_download(
    params: SSHParams,
    remote_file: str,
    local_path: Path,
    dry_run: bool,
) -> None:
    # remote_file is a filename inside ssh.dest dir
    ssh_dest = params["dest"]
    ssh_port = params["port"]
    rsync_opts = params["rsync_opts"]
    host, _, remote_dir = ssh_dest.partition(":")
    src = f"{host}:{remote_dir.rstrip('/')}/{remote_file}"
    rsh = f"ssh -p {ssh_port}"
    run(
        ["rsync", *rsync_opts.split(), "-e", rsh, src, str(local_path)],
        dry_run=dry_run,
    )


# ---------------------------
# Webhook notifier (optional)
# ---------------------------
def _split_headers(raw: str | None) -> list[tuple[str, str]]:
    # Accept comma- or newline-separated "Key: Value" pairs
    if not raw:
        return []
    # Replace commas with newlines, then split lines
    lines = [ln.strip() for ln in raw.replace(",", "\n").splitlines()]
    headers: list[tuple[str, str]] = []
    for ln in lines:
        if not ln:
            continue
        if ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        headers.append((k.strip(), v.strip()))
    return headers


def notify(
    webhook_url: str | None,
    status: str,
    message: str,
    backup_name: str,
    headers: str | None = None,
) -> None:
    if not webhook_url:
        return
    payload: dict[str, str] = {
        "status": status,
        "backup_name": backup_name,
        "timestamp": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "message": message,
        "hostname": (
            os.uname().nodename
            if hasattr(os, "uname")
            else socket.gethostname()
        ),
    }
    data = json.dumps(payload).encode("utf-8")
    hdr: list[tuple[str, str]] = [
        ("Content-Type", "application/json"),
        *_split_headers(headers),
    ]
    try:
        req = Request(  # nosemgrep  # nosec
            webhook_url,
            data=data,
            headers=dict(hdr),
            method="POST",
        )
        with urlopen(req, timeout=10):  # nosemgrep # nosec
            pass
    except Exception:
        # best effort only
        pass
