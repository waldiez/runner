# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

"""Constants for config sections and default values."""

SEC_BACKUP = "backup"
SEC_RESTORE = "restore"
SEC_RUNTIME = "runtime"
SEC_TRANSPORT = "transport"
SEC_TRANSPORT_S3 = "transport.s3"
SEC_TRANSPORT_SSH = "transport.ssh"
SEC_NOTIFY = "notify"
PFX_FILES = "files:"
PFX_POSTGRES = "postgres:"
PFX_REDIS = "redis:"

ENV_FMT_INI = "{key}_INI"  # e.g. BACKUP_INI or RESTORE_INI
ENV_PG_PASSWORD_FMT = "PG_PASSWORD_{name}"  # nosemgrep # nosec
ENV_REDIS_PASSWORD_FMT = "REDIS_PASSWORD_{name}"  # nosemgrep # nosec
ENV_LOG_LEVEL = "LOG_LEVEL"

# Defaults
DEFAULT_BACKUP_NAME = "waldiez_runner"
DEFAULT_BACKUP_DIR = "backups"
DEFAULT_RETENTION = 7
DEFAULT_GENERATE_CHECKSUM = True
DEFAULT_DRY_RUN = False
DEFAULT_ONLY = "all"  # files|postgres|redis|all

DEFAULT_NOTIFY_ON_SUCCESS = False
DEFAULT_NOTIFY_ON_FAILURE = True
DEFAULT_WEBHOOK_URL = ""
DEFAULT_WEBHOOK_HEADERS = ""  # "Authorization: Bearer xxx, X-Env: prod"
DEFAULT_CONTAINER_CMD = "auto"  # auto|docker|podman|none

DEFAULT_TRANSPORT_TYPE = "none"  # s3|ssh|both|none
DEFAULT_TRANSPORT_MODE = "retain"  # retain|mirror (s3 only)
DEFAULT_S3_PREFIX_FMT = "backups/{name}"
DEFAULT_SSH_DEST = "user@host:/remote/backups"
DEFAULT_SSH_PORT = 22
DEFAULT_SSH_OPTS = "-az --partial --inplace"

DEFAULT_PG_CONTAINER = "postgres"
DEFAULT_PG_USER = "postgres"
DEFAULT_PG_DATABASE = "postgres"

DEFAULT_REDIS_CONTAINER = "redis"
DEFAULT_REDIS_RDB_NAME = "redis_dump.rdb"

# Restore defaults
DEFAULT_RESTORE_STRATEGY = "select"  # select|all
DEFAULT_RESTORE_SRC = "local"  # local|s3|ssh
