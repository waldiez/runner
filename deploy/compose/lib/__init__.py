# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Compose deployment additional python helpers for backup and restore."""

from ._archive import archive_basename, extract_archive, make_archive
from ._common import (
    ensure_dir,
    format_size,
    get_logger,
    setup_logging,
    tempdir,
    try_do,
    utc_now,
    which,
)
from ._container import (
    container_exec,
    container_exec_out,
    container_exists,
    container_restart,
    container_running,
    copy_from_container,
    copy_to_container,
    restore_container_files,
    stage_container_dir,
)
from ._load import load_backup_config, load_restore_config
from ._local import prune_local, stage_host_dir
from ._models import (
    BackupConfig,
    RestoreConfig,
)
from ._postgres import dump_postgres, restore_postgres
from ._redis import dump_redis, restore_redis
from ._s3 import (
    S3Params,
    s3_cp_download,
    s3_cp_upload,
    s3_list_backups,
    s3_prune_retain,
    s3_sync_mirror,
)
from ._ssh import (
    SSHParams,
    ssh_download,
    ssh_list_remote,
    ssh_prune_remote,
    ssh_upload,
)
from ._validation import sha256_file, verify_checksum, write_checksum
from ._webhook import notify

__all__ = [
    "BackupConfig",
    "RestoreConfig",
    "S3Params",
    "SSHParams",
    "archive_basename",
    "container_exec",
    "container_exec_out",
    "container_exists",
    "container_restart",
    "container_running",
    "copy_from_container",
    "copy_to_container",
    "dump_postgres",
    "dump_redis",
    "ensure_dir",
    "extract_archive",
    "format_size",
    "get_logger",
    "load_backup_config",
    "load_restore_config",
    "make_archive",
    "notify",
    "prune_local",
    "restore_container_files",
    "restore_postgres",
    "restore_redis",
    "s3_cp_download",
    "s3_cp_upload",
    "s3_list_backups",
    "s3_prune_retain",
    "s3_sync_mirror",
    "setup_logging",
    "sha256_file",
    "ssh_download",
    "ssh_list_remote",
    "ssh_prune_remote",
    "ssh_upload",
    "stage_container_dir",
    "stage_host_dir",
    "tempdir",
    "try_do",
    "utc_now",
    "verify_checksum",
    "which",
    "write_checksum",
]
