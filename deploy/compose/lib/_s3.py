# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=inconsistent-quotes

"""S3 transport related utils."""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import TypedDict

from ._common import run


class S3Params(TypedDict, total=False):
    """S3 params dict"""

    bucket: str
    prefix: str
    aws_profile: str
    aws_region: str
    object_tags: str


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
    """Put object tags using s3api.

    Parameters
    ----------
    params : S3Params
        The S3 connection parameters.
    key : str
        The object to put tags to.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.
    """
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
    """Upload an object to S3.

    Parameters
    ----------
    params : S3Params
        The S3 connection parameters.
    local : Path
        The local path to upload.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.
    """
    bucket = params.get("bucket")
    prefix = params.get("prefix")
    if not bucket or not prefix:
        return
    dest = f"s3://{bucket}/{prefix.strip('/')}/"
    cmd = ["aws", "s3", "cp", local.name, dest] + _aws_base_args(params)
    run(cmd, dry_run=dry_run, cwd=local.parent)
    put_object_tags(
        params=params,
        key=local.name,
        dry_run=dry_run,
    )


def s3_cp_download(
    params: S3Params,
    key: str,
    local: Path,
    dry_run: bool,
) -> None:
    """Download an object from S3.

    Parameters
    ----------
    params : S3Params
        The S3 connection parameters.
    key : str
        The remote object.
    local : Path
        The local destination.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.
    """
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
    """Mirror local path to S3 bucket.

    Parameters
    ----------
    params : S3Params
        The S3 connection parameters.
    local_dir : Path
        The local directory to mirror.
    name_prefix : str
        The bucket's subfolder/prefix.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.
    """
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
    """Return object keys (filenames) for our archives, newest first.

    Parameters
    ----------
    params : S3Params
        The S3 connection parameters
    name_prefix
        The bucket's subfolder/prefix
    dry_run: bool
        Flag to skip actual operation and only log what would be called.

    Returns
    -------
    list[str]
        The objects inside the bucket's prefix.
    """
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
    """Prune S3 objects retaining latest `keep` ones.

    Parameters
    ----------
    params : S3Params
        The S3 connection parameters.
    name_prefix : str
        The bucket's subfolder/prefix.
    keep : int
        The number of entries to keep.
    dry_run: bool
        Flag to skip actual operation and only log what would be called.

    Returns
    -------
    list[str]
        The objects that were deleted.
    """
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
