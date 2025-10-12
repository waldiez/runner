# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.


"""SSH transport related utils."""

import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from ._common import run, which


class SSHParams(TypedDict, total=True):
    """SSH params dict"""

    dest: str  # e.g. "user@host:/remote/dir"
    port: int  # e.g. 22
    rsync_opts: str  # e.g. "-av --progress"
    prune_cmd: str  # optional custom prune command to execute remotely


def ssh_upload(
    params: SSHParams,
    local_file: Path,
    checksum_file: Path | None,
    dry_run: bool,
) -> None:
    """Upload to a remote host using rsync and ssh.

    Parameters
    ----------
    params: SSHParams
        The SSH connection parameters.
    local_file: Path
        The local file to upload.
    checksum_file: Path | None
        The file's checksum.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.
    """
    ssh_port = params["port"]
    ssh_dest = params["dest"]
    rsync_opts = params["rsync_opts"]
    host, remote_dir = _split_dest(ssh_dest)

    if which("rsync"):
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
        return

    # Fallback: scp (preserve times, permissions)
    # Note: rsync_opts are not used with scp
    scp_base = ["scp", "-P", str(ssh_port), "-p"]
    remote_stripped = remote_dir.rstrip("/")
    run(
        [*scp_base, str(local_file), f"{host}:{remote_stripped}/"],
        dry_run=dry_run,
    )
    if checksum_file and checksum_file.exists():
        run(
            [*scp_base, str(checksum_file), f"{host}:{remote_stripped}/"],
            dry_run=dry_run,
        )


def ssh_prune_remote(
    params: SSHParams,
    name_prefix: str,
    keep: int,
    dry_run: bool,
) -> None:
    """Remove remote files.

    Parameters
    ----------
    params: SSHParams
        The SSH connection parameters.
    name_prefix : str
        The name prefix to filter.
    keep : int
        The number of remote files to keep.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.
    """
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
    """Download a remote file.

    Parameters
    ----------
    params: SSHParams
        The SSH connection parameters.
    remote_file : str
        The path to the remote file.
    local_path : Path
        The local destination path.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.
    """
    # remote_file is a filename inside ssh.dest dir
    ssh_dest = params["dest"]
    ssh_port = params["port"]
    rsync_opts = params["rsync_opts"]
    host, remote_dir = _split_dest(ssh_dest)
    remote_stripped = remote_dir.rstrip("/")
    src = f"{host}:{remote_stripped}/{remote_file}"
    if which("rsync"):
        rsh = f"ssh -p {ssh_port}"
        run(
            ["rsync", *rsync_opts.split(), "-e", rsh, src, str(local_path)],
            dry_run=dry_run,
        )
        return
    run(
        ["scp", "-P", str(ssh_port), "-p", src, str(local_path)],
        dry_run=dry_run,
    )


def ssh_list_remote(
    params: SSHParams,
    name_prefix: str,
    detailed: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """List remote files (oldest first).

    Parameters
    ----------
    params : SSHParams
        SSH connection params
    name_prefix : str
        Filter pattern prefix, e.g. 'waldiez'
    detailed : bool
        If True, return lines formatted as:
            "YYYY-MM-DD HH:MM:SS  (SIZE)  filename"
        Otherwise just return filenames.
    dry_run : bool
        If True, only logs the SSH command and returns [].

    Returns
    -------
    list[str]
        Filenames (or detailed lines) sorted newest-first.
    """
    host, remote_dir = _split_dest(params["dest"])
    port = params["port"]

    if not detailed:
        # Just filenames, newest-first
        script = (
            f'cd "{remote_dir}" 2>/dev/null || exit 0; '
            f"ls -1t {name_prefix}-*.tar.gz 2>/dev/null || true"
        )
        return _ssh_capture(host, port, script, dry_run)

    # Detailed listing with best-effort portability
    #  (GNU/BSD stat; fallback to ls)
    # We print: "<epoch>\t<size>\t<name>" then sort -nr by epoch, and format.
    script = _build_detailed_list_script(remote_dir, name_prefix)
    lines = _ssh_capture(host, port, script, dry_run)
    parsed = _parse_ls_output(lines)
    return [
        f"{name}\t,{dt:%Y-%m-%d %H:%M:%S}\t{size:>8}"
        for name, dt, size in parsed
    ]


def _parse_ls_output(lines: list[str]) -> list[tuple[str, datetime, float]]:
    parsed: list[tuple[str, datetime, float]] = []
    for line in lines:
        parts = line.strip().split("\t", 2)
        if len(parts) != 3:
            continue
        # pylint: disable=too-many-try-statements
        try:
            epoch = int(parts[0])
            size = float(parts[1])
            name = parts[2]
            epoch_dt = datetime.fromtimestamp(epoch)
            parsed.append((name, epoch_dt, size))
        except ValueError:
            continue

    parsed.sort(key=lambda t: t[0], reverse=False)
    return parsed


def _split_dest(dest: str) -> tuple[str, str]:
    host, _, remote_dir = dest.partition(":")
    return host, remote_dir


def _build_detailed_list_script(remote_dir: str, name_prefix: str) -> str:
    rd = shlex.quote(remote_dir)
    np = shlex.quote(name_prefix)
    # raw+f string: % tokens are preserved; variables are interpolated once
    return rf"""
cd {rd} 2>/dev/null || exit 0
set -e

list=$(ls -1 {np}-*.tar.gz 2>/dev/null || true)
[ -z "$list" ] && exit 0

if stat --version >/dev/null 2>&1; then
  # GNU stat
  for f in $list; do
    printf "%s\t%s\t%s\n" "$(stat -c %Y "$f")" "$(stat -c %s "$f")" "$f"
  done
elif stat -f "%m" . >/dev/null 2>&1; then
  # BSD/Mac stat
  for f in $list; do
    printf "%s\t%s\t%s\n" "$(stat -f %m "$f")" "$(stat -f %z "$f")" "$f"
  done
else
  # Fallback: use date + wc (less precise)
  for f in $list; do
    ts=$(date -r "$f" +%s 2>/dev/null || echo 0)
    sz=$(wc -c < "$f" 2>/dev/null || echo 0)
    printf "%s\t%s\t%s\n" "$ts" "$sz" "$f"
  done
fi
""".strip()


def _ssh_capture(host: str, port: int, script: str, dry_run: bool) -> list[str]:
    """Run an ssh command and capture stdout lines (UTF-8)."""
    cmd = ["ssh", "-p", str(port), host, script]
    if dry_run:
        # Escape newlines for nicer one-line dry-run display
        short_script = " ".join(
            line.strip() for line in script.strip().splitlines()
        )
        display_cmd = ["ssh", "-p", str(port), host, short_script]
        run(display_cmd, dry_run=True)
        return []
    proc = subprocess.run(  # nosemgrep # nosec
        cmd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # splitlines keeps order, removes trailing newline
    return proc.stdout.splitlines()
