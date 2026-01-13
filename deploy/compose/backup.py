#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=broad-exception-caught,inconsistent-quotes
# pylint: disable=missing-function-docstring,missing-param-doc
# pylint: disable=missing-return-doc,missing-yield-doc,missing-raises-doc
# pylint: disable=too-many-try-statements,invalid-name
# pyright: reportConstantRedefinition=false,reportImplicitRelativeImport=false

"""Python backup tool with INI config and multi-source support."""

import argparse
import logging
import os
import sys
from functools import partial
from pathlib import Path

_SYS_PATH = str(Path(__file__).parent.parent)

try:
    from compose.lib import (
        BackupConfig,
        S3Params,
        SSHParams,
        archive_basename,
        dump_postgres,
        dump_redis,
        ensure_dir,
        get_logger,
        load_backup_config,
        make_archive,
        notify,
        prune_local,
        s3_cp_upload,
        s3_prune_retain,
        s3_sync_mirror,
        setup_logging,
        ssh_prune_remote,
        ssh_upload,
        stage_container_dir,
        stage_host_dir,
        tempdir,
        try_do,
        utc_now,
        verify_checksum,
        write_checksum,
    )

except ImportError:
    sys.path.insert(0, _SYS_PATH)
    from compose.lib import (
        BackupConfig,
        S3Params,
        SSHParams,
        archive_basename,
        dump_postgres,
        dump_redis,
        ensure_dir,
        get_logger,
        load_backup_config,
        make_archive,
        notify,
        prune_local,
        s3_cp_upload,
        s3_prune_retain,
        s3_sync_mirror,
        setup_logging,
        ssh_prune_remote,
        ssh_upload,
        stage_container_dir,
        stage_host_dir,
        tempdir,
        try_do,
        utc_now,
        verify_checksum,
        write_checksum,
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Backup Waldiez Runner data to local/S3/SSH",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Run backup with default config
  %(prog)s --dry-run          # Preview actions without executing
  %(prog)s --only postgres    # Backup only PostgreSQL databases
  %(prog)s --config backup.ini  # Use specific config file
  %(prog)s --verbose          # Enable debug logging
        """,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to backup.ini (default: auto-discover)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing",
    )
    parser.add_argument(
        "--only",
        choices=["files", "postgres", "redis", "all"],
        help="Backup only specific component (overrides config)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration and exit",
    )
    return parser.parse_args()


def send_notification(cfg: BackupConfig, success: bool, message: str) -> None:
    """Send webhook notification if configured."""
    status = "success" if success else "failure"
    if not cfg.notify.enabled_for(status):
        return
    notify(
        webhook_url=cfg.notify.webhook_url,
        status=status,
        message=message,
        backup_name=cfg.core.name,
        headers=cfg.notify.headers,
    )


def create_archive(
    log: logging.Logger,
    cfg: BackupConfig,
    staging_dir: Path,
    archive_path: Path,
) -> None:
    """Create compressed archive from staging directory."""
    log.info("Creating archive: %s", archive_path)

    if cfg.core.dry_run:
        log.info("  (dry-run) Would create archive")
        return

    dt = utc_now()
    mtime_iso = dt.strftime("%Y%m%dT%H%M%SZ")
    tar_root = archive_basename(cfg.core.name, dt)

    make_archive(
        src_root=staging_dir,
        out_path=archive_path,
        tar_root=tar_root,
        mtime_iso=mtime_iso,
    )

    # Generate checksum
    if cfg.core.generate_checksum:
        log.info("Generating checksum...")
        checksum_file = write_checksum(archive_path)
        log.info("  SHA256: %s", checksum_file.read_text().split()[0])


def backup_files(
    log: logging.Logger, cfg: BackupConfig, staging_dir: Path
) -> None:
    """Backup all configured file sources."""
    if not cfg.files:
        log.info("No file sources configured")
        return

    log.info("Backing up %d file source(s)...", len(cfg.files))
    for f_cfg in cfg.files:
        dest = staging_dir / f"files_{f_cfg.name}"
        log.info("  - %s -> %s", f_cfg.name, dest)

        if f_cfg.mode == "host":
            if not f_cfg.dir or not f_cfg.dir.exists():
                log.warning("    Skipping: directory not found: %s", f_cfg.dir)
                continue
            stage_host_dir(
                src=f_cfg.dir,
                dst=dest,
                excludes=f_cfg.exclude,
                dry_run=cfg.core.dry_run,
            )
        elif f_cfg.mode == "container":
            if not f_cfg.container or not f_cfg.path:
                log.warning("    Skipping: invalid container config")
                continue
            stage_container_dir(
                crt=cfg.runtime.container_command,
                container=f_cfg.container,
                src_path=f_cfg.path,
                dst=dest,
                excludes=f_cfg.exclude,
                dry_run=cfg.core.dry_run,
            )


def backup_postgres(
    log: logging.Logger, cfg: BackupConfig, staging_dir: Path
) -> None:
    """Backup all configured PostgreSQL databases."""
    if not cfg.postgres:
        log.info("No PostgreSQL sources configured")
        return

    log.info("Backing up %d PostgreSQL database(s)...", len(cfg.postgres))
    for pg_cfg in cfg.postgres:
        dest = staging_dir / f"postgres_{pg_cfg.name}.dump"
        log.info("  - %s -> %s", pg_cfg.name, dest)

        dump_postgres(
            crt=cfg.runtime.container_command,
            container=pg_cfg.container,
            user=pg_cfg.user,
            database=pg_cfg.database,
            out_file=dest,
            password=pg_cfg.password,
            dump_extras=pg_cfg.dump_extras,
            dry_run=cfg.core.dry_run,
        )


def backup_redis(
    log: logging.Logger, cfg: BackupConfig, staging_dir: Path
) -> None:
    """Backup all configured Redis instances."""
    if not cfg.redis:
        log.info("No Redis sources configured")
        return

    log.info("Backing up %d Redis instance(s)...", len(cfg.redis))
    for rd_cfg in cfg.redis:
        dest_dir = staging_dir / f"redis_{rd_cfg.name}"
        ensure_dir(dest_dir)
        out_file = dest_dir / rd_cfg.rdb_name  # write with final name
        log.info("  - %s -> %s", rd_cfg.name, out_file)

        dump_redis(
            crt=cfg.runtime.container_command,
            container=rd_cfg.container,
            out_file=out_file,
            password=rd_cfg.password,
            rdb_name=rd_cfg.rdb_name,
            dry_run=cfg.core.dry_run,
        )


def transport_archive(
    log: logging.Logger, cfg: BackupConfig, archive_path: Path
) -> None:
    """Upload archive to configured transport destinations."""
    checksum_path = (
        archive_path.with_suffix(archive_path.suffix + ".sha256")
        if cfg.core.generate_checksum
        else None
    )

    # S3 transport
    if cfg.transport.type in ("s3", "both") and cfg.transport.s3:
        log.info("Uploading to S3...")
        s3_params = S3Params(
            bucket=cfg.transport.s3.bucket,
            prefix=cfg.transport.s3.prefix,
            aws_profile=cfg.transport.s3.aws_profile,
            aws_region=cfg.transport.s3.aws_region,
            object_tags=cfg.transport.s3.object_tags,
        )

        if cfg.transport.mode == "mirror":
            s3_sync_mirror(
                params=s3_params,
                local_dir=cfg.core.backup_dir,
                name_prefix=cfg.core.name,
                dry_run=cfg.core.dry_run,
            )
        else:  # retain
            s3_cp_upload(
                params=s3_params,
                local=archive_path,
                dry_run=cfg.core.dry_run,
            )
            if checksum_path:
                s3_cp_upload(
                    params=s3_params,
                    local=checksum_path,
                    dry_run=cfg.core.dry_run,
                )

            # Prune old backups
            log.info(
                "Pruning old S3 backups if needed (keep=%d)...",
                cfg.core.retention,
            )
            deleted = s3_prune_retain(
                params=s3_params,
                name_prefix=cfg.core.name,
                keep=cfg.core.retention,
                dry_run=cfg.core.dry_run,
            )
            if deleted:
                log.info("  Deleted %d old backup(s)", len(deleted))

    # SSH transport
    if cfg.transport.type in ("ssh", "both") and cfg.transport.ssh:
        log.info("Uploading to SSH...")
        ssh_params = SSHParams(
            dest=cfg.transport.ssh.dest,
            port=cfg.transport.ssh.port,
            rsync_opts=cfg.transport.ssh.rsync_opts,
            prune_cmd=cfg.transport.ssh.prune_cmd,
        )

        ssh_upload(
            params=ssh_params,
            local_file=archive_path,
            checksum_file=checksum_path,
            dry_run=cfg.core.dry_run,
        )

        # Prune old backups
        log.info("Pruning old SSH backups (keep=%d)...", cfg.core.retention)
        ssh_prune_remote(
            params=ssh_params,
            name_prefix=cfg.core.name,
            keep=cfg.core.retention,
            dry_run=cfg.core.dry_run,
        )


def prune_local_backups(log: logging.Logger, cfg: BackupConfig) -> None:
    """Remove old local backups based on retention policy."""
    log.info("Pruning local backups (keep=%d)...", cfg.core.retention)
    removed = prune_local(
        backups_dir=cfg.core.backup_dir,
        name_prefix=cfg.core.name,
        keep=cfg.core.retention,
    )
    if removed:
        log.info("  Deleted %d old backup(s)", len(removed))
        for path in removed:
            log.debug("    - %s", path.name)


def verify_archive(
    log: logging.Logger, archive_path: Path, generate_checksum: bool
) -> bool:
    """Verify archive integrity."""
    if not generate_checksum:
        return True

    log.info("Verifying archive integrity...")
    valid, message = verify_checksum(archive_path)
    if valid:
        log.info("  ✓ Checksum valid")
        return True

    log.error("  ✗ Checksum verification failed: %s", message)
    return False


def run_backup(log: logging.Logger, cfg: BackupConfig) -> bool:
    """Execute backup operation.

    Returns:
        True if successful, False otherwise.
    """
    log.info("=" * 70)
    log.info("Waldiez Runner Backup")
    log.info("=" * 70)
    log.info("Name: %s", cfg.core.name)
    log.info("Backup dir: %s", cfg.core.backup_dir)
    log.info("Retention (keep last N archives): %d", cfg.core.retention)
    log.info("Dry run: %s", cfg.core.dry_run)
    log.info("Only: %s", cfg.core.only)
    log.info("=" * 70)

    # Prepare directories
    ensure_dir(cfg.core.backup_dir)
    dt = utc_now()
    archive_name = f"{archive_basename(cfg.core.name, dt)}.tar.gz"
    archive_path = cfg.core.backup_dir / archive_name

    # Staging area for backup data
    with tempdir(prefix=f"backup-{cfg.core.name}-") as staging_dir:
        log.info("Staging directory: %s", staging_dir)

        # Backup components based on 'only' setting
        if cfg.core.only in ("files", "all"):
            backup_files(log, cfg, staging_dir)

        if cfg.core.only in ("postgres", "all"):
            backup_postgres(log, cfg, staging_dir)

        if cfg.core.only in ("redis", "all"):
            backup_redis(log, cfg, staging_dir)

        # Create archive
        create_archive(log, cfg, staging_dir, archive_path)

    # Verify archive
    if not cfg.core.dry_run:
        if not verify_archive(log, archive_path, cfg.core.generate_checksum):
            return False

    # Transport to remote destinations
    if cfg.transport.type != "none":
        transport_archive(log, cfg, archive_path)

    # Local retention
    prune_local_backups(log, cfg)

    log.info("=" * 70)
    log.info("✓ Backup completed successfully")
    log.info("  Archive: %s", archive_path.name)
    if not cfg.core.dry_run:
        size_mb = archive_path.stat().st_size / (1024 * 1024)
        log.info("  Size: %.2f MB", size_mb)
    log.info("=" * 70)

    return True


def _do(
    args: argparse.Namespace,
    cfg: BackupConfig,
    log: logging.Logger,
) -> int:
    log.debug("Loading configuration...")
    # Apply CLI overrides
    if args.dry_run:
        cfg.core.dry_run = True
    if args.only:
        cfg.core.only = args.only

    # Validate-only mode
    if args.validate:
        log.info("✓ Configuration is valid")
        log.info("  Files: %d", len(cfg.files))
        log.info("  PostgreSQL: %d", len(cfg.postgres))
        log.info("  Redis: %d", len(cfg.redis))
        log.info("  Transport: %s", cfg.transport.type)
        return 0

    # Run backup
    success = run_backup(log, cfg)
    message = "Backup completed successfully" if success else "Backup failed"

    # Send notification
    send_notification(cfg, success, message)

    return 0 if success else 1


def main() -> int:
    """Parse config and backup."""
    args = parse_args()
    setup_logging(args.verbose)

    # Override config file path if specified
    if args.config:
        os.environ["BACKUP_INI"] = args.config
    log = get_logger("backup")
    try:
        cfg = load_backup_config()
    except BaseException as e:
        log.error("Invalid config: %s", e)
        return 1
    what = partial(_do, args, cfg, log)

    def on_interrupt() -> None:
        log.warning("Backup interrupted by user")
        send_notification(cfg, False, "Backup interrupted by user")

    def on_error(error: Exception) -> None:
        log.error("Backup failed: %s", error, exc_info=args.verbose)
        send_notification(cfg, False, f"Backup failed: {error}")

    return try_do(what, on_interrupt=on_interrupt, on_error=on_error)


if __name__ == "__main__":
    _EXIT_CODE = 1
    try:
        _EXIT_CODE = main()
    finally:
        if sys.path[0] == _SYS_PATH:
            sys.path.pop(0)
    sys.exit(_EXIT_CODE)
