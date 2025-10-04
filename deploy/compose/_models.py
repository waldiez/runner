# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught,inconsistent-quotes
"""Backup and restore related models."""

from __future__ import annotations

import configparser
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

HERE = Path(__file__).parent.resolve()


# ==============================
# Constants
# ==============================
# Section names
SEC_BACKUP = "backup"
# Section for restore
SEC_RESTORE = "restore"
SEC_RUNTIME = "runtime"
SEC_TRANSPORT = "transport"
SEC_TRANSPORT_S3 = "transport.s3"
SEC_TRANSPORT_SSH = "transport.ssh"
SEC_NOTIFY = "notify"
#
PFX_FILES = "files:"
PFX_POSTGRES = "postgres:"
PFX_REDIS = "redis:"

# Env
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

# Restore defaults
DEFAULT_RESTORE_STRATEGY = "select"  # select|all
DEFAULT_RESTORE_SRC = "auto"  # auto|local|s3|ssh

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


class IniNotFoundError(FileNotFoundError):
    """Config (.ini) file not found."""


# ==============================
# INI loading
# ==============================
def load_ini(key: str) -> configparser.ConfigParser:
    """Load an INI by key (e.g. 'backup' or 'restore').

    Respects {KEY}_INI env var, then searches script dir and two parents.
    If key='restore' and not found, falls back to backup.ini search.

    Parameters
    ----------
    key : str
        The key to check for the file/env.
    Returns
    -------
    configparser.ConfigParser
        The config parser.

    Raises
    ------
    IniNotFoundError
        If the config file is not found.
    """
    cfg = configparser.ConfigParser(interpolation=None)

    _key = key.split("_")[0].split(".")[0].upper()
    env_var = ENV_FMT_INI.format(key=_key)
    env_path = os.environ.get(env_var, "").strip()
    if env_path:
        p = Path(env_path)
        if p.exists():
            cfg.read(p, encoding="utf-8")
            return cfg
        logging.error("%s is set but file not found: %s", env_var, p)
        sys.exit(2)

    base = _key.lower()
    candidates = [
        HERE / f"{base}.ini",
        HERE.parent / f"{base}.ini",
        HERE.parent.parent / f"{base}.ini",
    ]
    for candidate in candidates:
        if candidate.exists():
            cfg.read(candidate, encoding="utf-8")
            return cfg

    if base == "restore":
        backup_candidates = [
            HERE / "backup.ini",
            HERE.parent / "backup.ini",
            HERE.parent.parent / "backup.ini",
        ]
        for candidate in backup_candidates:
            if candidate.exists():
                cfg.read(candidate, encoding="utf-8")
                return cfg

    raise IniNotFoundError(
        f"{base}.ini not found (searched script dir + two parents)."
    )


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


# ==============================
# Models
# ==============================
@dataclass
class BackupCfg:
    """Backup config."""

    name: str
    backup_dir: Path
    retention: int
    generate_checksum: bool
    dry_run: bool
    only: Literal["files", "postgres", "redis", "all"]

    @classmethod
    def load(cls, cfg: configparser.ConfigParser) -> "BackupCfg":
        """Load from ini.

        Parameters
        ----------
        cfg : configparser.ConfigParser
            The parsed ini.

        Returns
        -------
        BackupCfg
            The backup core config.
        """
        if not cfg.has_section(SEC_BACKUP):
            return cls(
                name=DEFAULT_BACKUP_NAME,
                backup_dir=Path(DEFAULT_BACKUP_DIR).resolve(),
                retention=DEFAULT_RETENTION,
                generate_checksum=DEFAULT_GENERATE_CHECKSUM,
                dry_run=DEFAULT_DRY_RUN,
                only=DEFAULT_ONLY,  # type: ignore
            )
        s = cfg[SEC_BACKUP]
        only = s.get("only", DEFAULT_ONLY)
        if only not in ("files", "postgres", "redis", "all"):
            only = DEFAULT_ONLY
        return cls(
            name=s.get("name", DEFAULT_BACKUP_NAME),
            backup_dir=Path(
                s.get("backup_dir", f"./{DEFAULT_BACKUP_DIR}")
            ).resolve(),
            retention=max(1, s.getint("retention", DEFAULT_RETENTION)),
            generate_checksum=s.getboolean(
                "generate_checksum", DEFAULT_GENERATE_CHECKSUM
            ),
            dry_run=s.getboolean("dry_run", DEFAULT_DRY_RUN),
            only=only,  # type: ignore
        )


@dataclass
class RestoreCfg:
    """Restore config."""

    # Which archive to restore (local path OR object key)
    archive: str
    # Where to fetch from
    source: Literal[
        "auto", "local", "s3", "ssh"
    ]  # auto picks based on presence/transport
    # What to restore
    strategy: Literal[
        "select", "all"
    ]  # select respects selections; all restores everything
    # Optional selective restore toggles (override Transport and sources)
    restore_files: bool | None
    restore_postgres: bool | None
    restore_redis: bool | None
    # Local staging / temp dir (optional; callers can default to mkdtemp)
    staging_dir: Path | None
    dry_run: bool

    def __post_init__(self) -> None:
        archive = self.archive
        if self.source in ("local", "auto"):
            archive_path = Path(archive)
            # Check for parent directory traversal
            try:
                # Will raise ValueError if path escapes via ..
                if archive_path.is_absolute():
                    archive_path.resolve()
                else:
                    (Path.cwd() / archive_path).resolve()
            except (ValueError, OSError) as e:
                raise ValueError(
                    f"[{SEC_RESTORE}] Unsafe archive path: {archive}"
                ) from e

            # Additional checks for sensitive paths
            if str(archive_path.resolve()).startswith(
                ("/etc", "/sys", "/proc")
            ):
                raise ValueError(
                    f"[{SEC_RESTORE}] Cannot restore from system directory"
                )

        # For S3/SSH keys, basic validation
        elif archive.startswith(("/", "~", "..")):
            raise ValueError(
                f"[{SEC_RESTORE}] Invalid remote archive key: {archive}"
            )

    @classmethod
    def load(cls, cfg: configparser.ConfigParser) -> "RestoreCfg":
        """Load from ini.

        Parameters
        ----------
        cfg : configparser.ConfigParser
            The parsed ini.

        Returns
        -------
        RestoreCfg
            The restore config.

        Raises
        ------
        ValueError
            If a required section is not found in ini.
        """
        if not cfg.has_section(SEC_RESTORE):
            # Minimal, explicit config required for restore; fail loudly.
            raise ValueError(
                f"[{SEC_RESTORE}] section is required for restore; "
                "please set at least 'archive = <path-or-key>'."
            )
        s = cfg[SEC_RESTORE]
        archive = s.get("archive", "").strip()
        if not archive:
            raise ValueError(f"[{SEC_RESTORE}] 'archive' is required")
        source = s.get("source", DEFAULT_RESTORE_SRC)
        if source not in ("auto", "local", "s3", "ssh"):
            source = DEFAULT_RESTORE_SRC

        strategy = s.get("strategy", DEFAULT_RESTORE_STRATEGY)
        if strategy not in ("select", "all"):
            strategy = DEFAULT_RESTORE_STRATEGY

        def _opt_bool(key: str) -> bool | None:
            val = s.get(key, "").strip().lower()
            if val in ("true", "1", "yes", "on", "t", "y"):
                return True
            if val in ("false", "0", "no", "off", "f", "n"):
                return False
            return None

        staging = s.get("staging_dir", "").strip()
        staging_dir = Path(staging).resolve() if staging else None
        dry_run = _opt_bool("dry_run")
        if dry_run is None:
            dry_run = False

        return cls(
            archive=archive,
            source=source,  # type: ignore
            strategy=strategy,  # type: ignore
            restore_files=_opt_bool("restore_files"),
            restore_postgres=_opt_bool("restore_postgres"),
            restore_redis=_opt_bool("restore_redis"),
            staging_dir=staging_dir,
            dry_run=dry_run,
        )

    def resolve_source(
        self, transport: TransportCfg
    ) -> Literal["local", "s3", "ssh"]:
        """Resolve 'auto' source based on archive path and transport config.

        Logic:
        - If archive looks like absolute/relative path → local
        - If archive looks like S3 key AND transport.s3 exists → s3
        - If transport.ssh exists → ssh
        - Default → local

        Parameters
        ----------
        transport : TransportCfg
            The transport config.

        Returns
        -------
        Literal["local", "s3", "ssh"]
            The resolved source.
        """
        if self.source != "auto":
            return self.source

        # Check if archive looks like a filesystem path
        if self.archive.startswith("/") or self.archive.startswith("."):
            return "local"

        # Check transport availability
        if transport.s3 is not None:
            return "s3"
        if transport.ssh is not None:
            return "ssh"

        # Default fallback
        return "local"


@dataclass
class RuntimeCfg:
    """Container runtime config."""

    container_command: Literal["auto", "docker", "podman", "none"]

    @staticmethod
    def is_engine_running(engine_name: str) -> bool:
        """Check if the selected engine is running.

        Parameters
        ----------
        engine_name : str
            The engine to check (docker | podman)

        Returns
        -------
        bool
            True if '{engine} ps' works, False otherwise.
        """
        try:
            subprocess.run(
                [engine_name, "ps"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )  # nosec
            return True
        except Exception:
            return False

    def __post_init__(self) -> None:
        """Validate the engine."""
        cmd = self.container_command
        if cmd in ("docker", "podman"):
            if not RuntimeCfg.is_engine_running(cmd):
                logging.warning("%s not running; falling back to none", cmd)
                self.container_command = "none"
            return
        if cmd == "auto":
            for engine in ("podman", "docker"):
                if RuntimeCfg.is_engine_running(engine):
                    self.container_command = engine
                    break
            else:
                self.container_command = "none"
            return
        if self.container_command not in ("docker", "podman", "none"):
            self.container_command = "none"

    @classmethod
    def load(cls, cfg: configparser.ConfigParser) -> RuntimeCfg:
        """Load from ini.

        Parameters
        ----------
        cfg : configparser.ConfigParser
            The parsed ini.

        Returns
        -------
        RuntimeCfg
            The runtime config.
        """
        if not cfg.has_section(SEC_RUNTIME):
            container_command = DEFAULT_CONTAINER_CMD
        else:
            section = cfg[SEC_RUNTIME]
            container_command = section.get(
                "container_command", DEFAULT_CONTAINER_CMD
            )
        if container_command not in ("auto", "docker", "podman", "none"):
            container_command = DEFAULT_CONTAINER_CMD
        return cls(container_command=container_command)  # type: ignore # noqa


@dataclass
class NotifyCfg:
    """Notification hook config."""

    webhook_url: str
    notify_on_success: bool
    notify_on_failure: bool
    headers: str  # raw comma/newline separated header lines

    @classmethod
    def load(cls, cfg: configparser.ConfigParser) -> NotifyCfg:
        """Load from ini.

        Parameters
        ----------
        cfg : configparser.ConfigParser
            The config parser.

        Returns
        -------
        NotifyCfg
            The notification config.
        """
        if not cfg.has_section(SEC_NOTIFY):
            return cls(
                webhook_url=DEFAULT_WEBHOOK_URL,
                notify_on_success=DEFAULT_NOTIFY_ON_SUCCESS,
                notify_on_failure=DEFAULT_NOTIFY_ON_FAILURE,
                headers=DEFAULT_WEBHOOK_HEADERS,
            )
        s = cfg[SEC_NOTIFY]
        return cls(
            webhook_url=s.get("webhook_url", DEFAULT_WEBHOOK_URL).strip(),
            notify_on_success=s.getboolean(
                "notify_on_success", DEFAULT_NOTIFY_ON_SUCCESS
            ),
            notify_on_failure=s.getboolean(
                "notify_on_failure", DEFAULT_NOTIFY_ON_FAILURE
            ),
            headers=s.get("headers", DEFAULT_WEBHOOK_HEADERS),
        )

    def enabled_for(self, status: str) -> bool:
        """Check if notification is enabled for a status.

        Parameters
        ----------
        status : str
            The status to check (success, failure)

        Returns
        -------
        bool
            True if enabled for this status, else False
        """
        if not self.webhook_url:
            return False
        return (status == "success" and self.notify_on_success) or (
            status == "failure" and self.notify_on_failure
        )


@dataclass
class S3Cfg:
    """S3 Config."""

    bucket: str
    prefix: str
    aws_profile: str
    aws_region: str
    object_tags: str

    def __post_init__(self) -> None:
        """Validate config.

        Raises
        ------
        ValueError
            If a setting is invalid.
        """
        if not self.bucket or not self.bucket.strip():
            raise ValueError("S3 bucket cannot be empty")


@dataclass
class SSHCfg:
    """SSH config."""

    dest: str
    port: int
    rsync_opts: str
    prune_cmd: str

    def __post_init__(self) -> None:
        """Validate config.

        Raises
        ------
        ValueError
            If a setting is invalid.
        """
        if not self.dest or not self.dest.strip():
            raise ValueError("SSH dest cannot be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError(f"Invalid SSH port: {self.port}")


@dataclass
class TransportCfg:
    """Transport config."""

    type: Literal["s3", "ssh", "both", "none"]
    mode: Literal["retain", "mirror"]  # (s3 only)
    s3: S3Cfg | None
    ssh: SSHCfg | None

    def __post_init__(self) -> None:
        """Validate the config."""
        has_s3 = self.s3 is not None
        has_ssh = self.ssh is not None

        if self.type == "s3" and not has_s3:
            logging.warning(
                "transport type 's3' but [%s] missing", SEC_TRANSPORT_S3
            )
            self.type = "none"
        elif self.type == "ssh" and not has_ssh:
            logging.warning(
                "transport type 'ssh' but [%s] missing", SEC_TRANSPORT_SSH
            )
            self.type = "none"
        elif self.type == "both":
            if has_s3 and has_ssh:
                pass
            elif has_s3:
                logging.warning(
                    "'both' requested but [%s] missing. using 's3' only",
                    SEC_TRANSPORT_SSH,
                )
                self.type = "s3"
            elif has_ssh:
                logging.warning(
                    "'both' requested but [%s] missing. using 'ssh' only",
                    SEC_TRANSPORT_S3,
                )
                self.type = "ssh"
            else:
                logging.warning(
                    "'both' requested but no transports configured."
                    " using 'none'"
                )
                self.type = "none"

        if self.mode == "mirror" and self.type not in ("s3", "both"):
            logging.warning(
                "mode 'mirror' ignored because S3 transport is not active"
            )
            self.mode = "retain"

    @classmethod
    def load(cls, cfg: configparser.ConfigParser) -> TransportCfg:
        """Load from ini.

        Parameters
        ----------
        cfg : configparser.ConfigParser
            The parsed ini.

        Returns
        -------
        TransportCfg
            The transport config.
        """
        ttype = DEFAULT_TRANSPORT_TYPE
        mode = DEFAULT_TRANSPORT_MODE
        if cfg.has_section(SEC_TRANSPORT):
            base = cfg[SEC_TRANSPORT]
            ttype = base.get("type", DEFAULT_TRANSPORT_TYPE)
            if ttype not in ("s3", "ssh", "both", "none"):
                ttype = DEFAULT_TRANSPORT_TYPE
            mode = base.get("mode", DEFAULT_TRANSPORT_MODE)
            if mode not in ("retain", "mirror"):
                mode = DEFAULT_TRANSPORT_MODE

        backup_name = (
            cfg[SEC_BACKUP].get("name", DEFAULT_BACKUP_NAME)
            if cfg.has_section(SEC_BACKUP)
            else DEFAULT_BACKUP_NAME
        )

        s3: S3Cfg | None = None
        if ttype in ("s3", "both") and cfg.has_section(SEC_TRANSPORT_S3):
            s = cfg[SEC_TRANSPORT_S3]
            try:
                s3 = S3Cfg(
                    bucket=s.get("bucket", ""),
                    prefix=s.get(
                        "prefix", DEFAULT_S3_PREFIX_FMT.format(name=backup_name)
                    ).lstrip("/"),
                    aws_profile=s.get("aws_profile", ""),
                    aws_region=s.get("aws_region", ""),
                    object_tags=s.get("object_tags", ""),
                )
            except ValueError as e:
                logging.warning("Invalid [%s] config: %s", SEC_TRANSPORT_S3, e)
                s3 = None

        ssh: SSHCfg | None = None
        if ttype in ("ssh", "both") and cfg.has_section(SEC_TRANSPORT_SSH):
            s = cfg[SEC_TRANSPORT_SSH]
            try:
                ssh = SSHCfg(
                    dest=s.get("dest", DEFAULT_SSH_DEST),
                    port=s.getint("port", DEFAULT_SSH_PORT),
                    rsync_opts=s.get("rsync_opts", DEFAULT_SSH_OPTS),
                    prune_cmd=s.get("prune_cmd", ""),
                )
            except ValueError as e:
                logging.warning("Invalid [%s] config: %s", SEC_TRANSPORT_SSH, e)
                ssh = None

        return cls(ttype, mode, s3, ssh)  # type: ignore # noqa


@dataclass
class FilesCfg:
    """Files cfg."""

    name: str
    mode: Literal["host", "container"]
    dir: Path | None
    container: str | None
    path: str | None
    exclude: list[str]

    def __post_init__(self) -> None:
        """Validate config.

        Raises
        ------
        ValueError
            If a setting is invalid.
        """
        if self.mode == "container" and not self.container:
            raise ValueError(
                f"files:{self.name} container mode requires container name"
            )
        if self.container and not re.match(
            r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$", self.container
        ):
            raise ValueError(f"Invalid container name: {self.container}")

    @staticmethod
    def load_many(cfg: configparser.ConfigParser) -> list[FilesCfg]:
        """Parse all files:* sections.

        Parameters
        ----------
        cfg : configparser.ConfigParser
            The ini config parser.

        Returns
        -------
        list[FilesCfg]
            The files related configs.

        Raises
        ------
        ValueError
            If a (sub)section is misconfigured.
        """
        configs: list[FilesCfg] = []
        for sec in cfg.sections():
            if not isinstance(sec, str) or not sec.startswith(PFX_FILES):
                continue
            sub = cfg[sec]
            name = sec.split(":", 1)[1]
            if not name:
                logging.warning("Invalid section name: %s", sec)
                continue
            mode = sub.get("mode", "host")
            exclude = split_list(sub.get("exclude", ""))
            if mode == "host":
                raw_dir = sub.get("dir", "").strip()
                if not raw_dir:
                    raise ValueError(f"files:{name} (host) requires 'dir'")
                dir_path = Path(raw_dir).resolve()
                configs.append(
                    FilesCfg(
                        name=name,
                        mode=mode,  # type: ignore # noqa
                        dir=dir_path,
                        container=None,
                        path=None,
                        exclude=exclude,
                    )
                )
            elif mode == "container":
                container = sub.get("container", "").strip()
                container_path = sub.get("path", "").strip()
                if not container or not container_path:
                    raise ValueError(
                        f"files:{name} (container) "
                        "requires both 'container' and 'path'"
                    )
                configs.append(
                    FilesCfg(
                        name=name,
                        mode=mode,  # type: ignore # noqa
                        dir=None,
                        container=container,
                        path=container_path,
                        exclude=exclude,
                    )
                )
            else:
                raise ValueError(f"files:{name} has invalid mode '{mode}'")
        return configs


@dataclass
class PgCfg:
    """Postgres config."""

    name: str
    container: str
    user: str
    database: str
    password: str
    dump_extras: str

    def __post_init__(self) -> None:
        """Validate config.

        Raises
        ------
        ValueError
            If a setting is invalid.
        """
        if not self.name or not self.container:
            raise ValueError("Invalid postgres config")

    @staticmethod
    def load_many(cfg: configparser.ConfigParser) -> list[PgCfg]:
        """Parse all postgres:* sections.

        Parameters
        ----------
        cfg : configparser.ConfigParser
            The ini config parser.

        Returns
        -------
        list[PgCfg]
            The postgres related configs.

        Raises
        ------
        ValueError
            If a (sub)section is misconfigured.
        """
        configs: list[PgCfg] = []
        for sec in cfg.sections():
            if not isinstance(sec, str) or not sec.startswith(PFX_POSTGRES):
                continue
            sub = cfg[sec]
            name = sec.split(":", 1)[1]
            if not name:
                logging.warning("Invalid section name: %s", sec)
                continue
            password = sub.get("password", "") or os.environ.get(
                ENV_PG_PASSWORD_FMT.format(name=name.upper()), ""
            )
            pg = PgCfg(
                name=name,
                container=sub.get("container", DEFAULT_PG_CONTAINER),
                user=sub.get("user", DEFAULT_PG_USER),
                database=sub.get("database", DEFAULT_PG_DATABASE),
                password=password,
                dump_extras=sub.get("dump_extras", ""),
            )
            configs.append(pg)
        return configs


@dataclass
class RedisCfg:
    """Redis config."""

    name: str
    container: str
    password: str
    rdb_name: str

    def __post_init__(self) -> None:
        """Validate config.

        Raises
        ------
        ValueError
            If a setting is invalid.
        """
        if not self.name or not self.container or not self.rdb_name:
            raise ValueError("Invalid redis config")

    @staticmethod
    def load_many(cfg: configparser.ConfigParser) -> list[RedisCfg]:
        """Parse all redis:* sections.

        Parameters
        ----------
        cfg : configparser.ConfigParser
            The ini config parser.

        Returns
        -------
        list[RedisCfg]
            The redis related configs.

        Raises
        ------
        ValueError
            If a (sub)section is misconfigured.
        """
        configs: list[RedisCfg] = []
        for sec in cfg.sections():
            if not isinstance(sec, str) or not sec.startswith(PFX_REDIS):
                continue
            sub = cfg[sec]
            name = sec.split(":", 1)[1]
            if not name:
                logging.warning("Invalid section name: %s", sec)
                continue
            password = sub.get("password", "") or os.environ.get(
                ENV_REDIS_PASSWORD_FMT.format(name=name.upper()), ""
            )
            rd = RedisCfg(
                name=name,
                container=sub.get("container", DEFAULT_REDIS_CONTAINER),
                password=password,
                rdb_name=sub.get("rdb_name", DEFAULT_REDIS_RDB_NAME),
            )
            configs.append(rd)
        return configs


@dataclass
class BackupConfig:
    """Complete backup config."""

    core: BackupCfg
    runtime: RuntimeCfg
    transport: TransportCfg
    files: list[FilesCfg]
    postgres: list[PgCfg]
    redis: list[RedisCfg]
    notify: NotifyCfg

    def __post_init__(self) -> None:
        """Validate config.

        Raises
        ------
        RuntimeError
            If a container engine is needed but none is used.
        """
        if not self.core.dry_run and self.runtime.container_command == "none":
            if (
                self.postgres
                or self.redis
                or any(cfg.mode == "container" for cfg in self.files)
            ):
                raise RuntimeError("Cannot find a running container engine.")


@dataclass
class RestoreConfig:
    """Complete restore config."""

    core: RestoreCfg
    runtime: RuntimeCfg
    transport: TransportCfg
    files: list[FilesCfg]
    postgres: list[PgCfg]
    redis: list[RedisCfg]
    notify: NotifyCfg

    def __post_init__(self) -> None:
        """Validate config.

        Raises
        ------
        RuntimeError
            If a container engine is needed but none is used.
        """
        if not self.core.dry_run and self.runtime.container_command == "none":
            if (
                self.postgres
                or self.redis
                or any(cfg.mode == "container" for cfg in self.files)
            ):
                raise RuntimeError("Cannot find a running container engine.")


def load_backup_config() -> BackupConfig:
    """Load all backup config settings.

    Returns
    -------
    ParsedBackupConfig
        The parsed settings from config file.
    """
    cfg = load_ini("backup")
    return BackupConfig(
        core=BackupCfg.load(cfg),
        runtime=RuntimeCfg.load(cfg),
        transport=TransportCfg.load(cfg),
        files=FilesCfg.load_many(cfg),
        postgres=PgCfg.load_many(cfg),
        redis=RedisCfg.load_many(cfg),
        notify=NotifyCfg.load(cfg),
    )


def load_restore_config() -> RestoreConfig:
    """Load all restore settings.

    Returns
    -------
    ParsedRestoreConfig
        The parsed settings from the config file.
    """
    cfg = load_ini("restore")
    return RestoreConfig(
        core=RestoreCfg.load(cfg),
        runtime=RuntimeCfg.load(cfg),
        transport=TransportCfg.load(cfg),
        files=FilesCfg.load_many(cfg),
        postgres=PgCfg.load_many(cfg),
        redis=RedisCfg.load_many(cfg),
        notify=NotifyCfg.load(cfg),
    )
