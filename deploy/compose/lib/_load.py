# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

"""Load configuration."""

import configparser
import logging
import os
import sys
from pathlib import Path

from ._constants import ENV_FMT_INI
from ._models import (
    BackupCfg,
    BackupConfig,
    FilesCfg,
    NotifyCfg,
    PgCfg,
    RedisCfg,
    RestoreCfg,
    RestoreConfig,
    RuntimeCfg,
    S3Cfg,
    SSHCfg,
    TransportCfg,
)

HERE = Path(__file__).parent.resolve()


# optionally load from env
DOT_ENVS = [".aws.env", ".env"]

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
            HERE.parent.parent.parent / file_candidate,
        ]
        for path_candidate in path_candidates:
            if path_candidate.exists():
                load_dotenv(str(path_candidate))
                break


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
    FileNotFoundError
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
        HERE.parent.parent.parent / f"{base}.ini",
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

    raise FileNotFoundError(
        f"{base}.ini not found (searched script dir + three parents)."
    )


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
    core = RestoreCfg.load(cfg)
    transport = TransportCfg.load(cfg)
    if core.source in ("s3", "ssh") and transport.type != core.source:
        transport.type = core.source  # type: ignore[assignment]
        if core.source == "s3":
            transport.s3 = S3Cfg.load(cfg)
        elif core.source == "ssh":
            transport.ssh = SSHCfg.load(cfg)
    return RestoreConfig(
        core=core,
        runtime=RuntimeCfg.load(cfg),
        transport=transport,
        files=FilesCfg.load_many(cfg),
        postgres=PgCfg.load_many(cfg),
        redis=RedisCfg.load_many(cfg),
        notify=NotifyCfg.load(cfg),
    )
