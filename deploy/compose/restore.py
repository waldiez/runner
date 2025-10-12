#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# flake8: noqa: C901
# pylint: disable=broad-exception-caught,inconsistent-quotes
# pylint: disable=missing-function-docstring,missing-param-doc
# pylint: disable=missing-return-doc,missing-yield-doc,missing-raises-doc
# pylint: disable=too-many-try-statements,too-complex
# pyright: reportConstantRedefinition=false,reportImplicitRelativeImport=false

"""Python restore tool with INI config and multi-source support."""

import argparse
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from functools import partial
from pathlib import Path

_SYS_PATH = str(Path(__file__).parent.parent)

try:
    from compose.lib import (
        RestoreConfig,
        S3Params,
        SSHParams,
        container_exists,
        container_running,
        ensure_dir,
        extract_archive,
        format_size,
        get_logger,
        load_restore_config,
        notify,
        restore_container_files,
        restore_postgres,
        restore_redis,
        s3_cp_download,
        s3_list_backups,
        setup_logging,
        ssh_download,
        ssh_list_remote,
        tempdir,
        try_do,
        verify_checksum,
    )

except ImportError:
    sys.path.insert(0, _SYS_PATH)
    from compose.lib import (
        RestoreConfig,
        S3Params,
        SSHParams,
        container_exists,
        container_running,
        ensure_dir,
        extract_archive,
        format_size,
        get_logger,
        load_restore_config,
        notify,
        restore_container_files,
        restore_postgres,
        restore_redis,
        s3_cp_download,
        s3_list_backups,
        setup_logging,
        ssh_download,
        ssh_list_remote,
        tempdir,
        try_do,
        verify_checksum,
    )

_NAME_PREFIX_RE = re.compile(r"^([A-Za-z0-9_.-]+)-\d{8}T\d{6}Z(?:\.tar\.gz)?$")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Restore Waldiez Runner data from local/S3/SSH backups",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --archive backup-20250115.tar.gz           # Restore from auto-detected source
  %(prog)s --archive /path/to/backup.tar.gz --source local  # Restore from local file
  %(prog)s --archive backup.tar.gz --source s3        # Restore from S3
  %(prog)s --list-local                               # List available local backups
  %(prog)s --list-s3                                  # List available S3 backups
  %(prog)s --list-ssh                                 # List available SSH backups
  %(prog)s --dry-run --archive backup.tar.gz          # Preview restore actions
  %(prog)s --config restore.ini                       # Use specific config file
  %(prog)s --verbose                                  # Enable debug logging
        """,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to restore.ini (default: auto-discover)",
    )
    parser.add_argument(
        "--archive",
        metavar="PATH",
        help="Archive to restore (overrides config)",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "local", "s3", "ssh"],
        help="Source location (overrides config)",
    )
    parser.add_argument(
        "--strategy",
        choices=["select", "all"],
        help="Restore strategy (overrides config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing",
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
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available backups and exit",
    )
    parser.add_argument(
        "--list-local",
        action="store_true",
        help="List available local backups and exit",
    )
    parser.add_argument(
        "--list-s3",
        action="store_true",
        help="List available S3 backups and exit",
    )
    parser.add_argument(
        "--list-ssh",
        action="store_true",
        help="List available SSH backups and exit",
    )
    return parser.parse_args()


def send_notification(cfg: RestoreConfig, success: bool, message: str) -> None:
    """Send webhook notification if configured."""
    status = "success" if success else "failure"
    if not cfg.notify.enabled_for(status):
        return
    notify(
        webhook_url=cfg.notify.webhook_url,
        status=status,
        message=message,
        backup_name=cfg.core.archive,
        headers=cfg.notify.headers,
    )


def fetch_archive(
    log: logging.Logger,
    cfg: RestoreConfig,
    source: str,
    archive_str: str,
    staging_dir: Path,
) -> Path:
    """Fetch archive from the specified source to staging directory."""
    if source == "local":
        archive_path = Path(archive_str)
        if not archive_path.exists():
            archive_path = Path(cfg.core.archive_path)
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")
        log.info("Using local archive: %s", archive_path)
        return archive_path

    # For remote sources, download to staging
    local_archive = staging_dir / Path(archive_str).name

    if source == "s3":
        if not cfg.transport.s3:
            if not cfg.core.dry_run:
                raise ValueError("S3 transport not configured")
            logging.error("S3 transport not configured")
            return local_archive
        log.info("Downloading from S3: %s", archive_str)
        s3_params = S3Params(
            bucket=cfg.transport.s3.bucket,
            prefix=cfg.transport.s3.prefix,
            aws_profile=cfg.transport.s3.aws_profile,
            aws_region=cfg.transport.s3.aws_region,
        )
        s3_cp_download(
            key=archive_str,
            local=local_archive,
            params=s3_params,
            dry_run=cfg.core.dry_run,
        )
        # Also download checksum if available
        checksum_key = f"{archive_str}.sha256"
        checksum_local = staging_dir / f"{Path(archive_str).name}.sha256"
        try:
            s3_cp_download(
                key=checksum_key,
                local=checksum_local,
                params=s3_params,
                dry_run=cfg.core.dry_run,
            )
        except Exception as e:
            log.warning("Could not download checksum: %s", e)

    elif source == "ssh":
        if not cfg.transport.ssh:
            raise ValueError("SSH transport not configured")
        log.info("Downloading from SSH: %s", archive_str)
        ssh_params = SSHParams(
            dest=cfg.transport.ssh.dest,
            port=cfg.transport.ssh.port,
            rsync_opts=cfg.transport.ssh.rsync_opts,
            prune_cmd=cfg.transport.ssh.prune_cmd,
        )
        ssh_download(
            params=ssh_params,
            remote_file=archive_str,
            local_path=local_archive,
            dry_run=cfg.core.dry_run,
        )
        # Also download checksum if available
        checksum_file = f"{archive_str}.sha256"
        checksum_local = staging_dir / f"{Path(archive_str).name}.sha256"
        try:
            ssh_download(
                params=ssh_params,
                remote_file=checksum_file,
                local_path=checksum_local,
                dry_run=cfg.core.dry_run,
            )
        except Exception as e:
            log.warning("Could not download checksum: %s", e)

    return local_archive


def verify_archive_integrity(
    log: logging.Logger, archive: Path, dry_run: bool
) -> bool:
    """Verify archive integrity using checksum if available."""
    checksum_file = archive.with_suffix(archive.suffix + ".sha256")
    if not checksum_file.exists():
        log.warning("No checksum file found, skipping verification")
        return True

    if dry_run and not archive.exists():
        log.info("Would verify archive integrity")
        return True

    log.info("Verifying archive integrity...")
    valid, message = verify_checksum(archive)
    if valid:
        log.info("  ✓ Checksum valid")
        return True

    log.error("  ✗ Checksum verification failed: %s", message)
    return False


def _can_restore(
    src: Path, name: str, log: logging.Logger, dry_run: bool
) -> bool:
    if not src.exists():
        if not dry_run:
            log.warning("  - Skipping %s: not found in archive", name)
        else:
            log.info("  - Would restore %s from archive", name)
        return False
    return True


def restore_files_from_archive(
    log: logging.Logger,
    cfg: RestoreConfig,
    extracted_root: Path,
    dry_run: bool,
) -> None:
    """Restore file sources from extracted archive."""
    if not cfg.core.restore_files or not cfg.files:
        log.info("Skipping file restoration")
        return

    log.info("Restoring %d file source(s)...", len(cfg.files))
    for f_cfg in cfg.files:
        src = extracted_root / f"files_{f_cfg.name}"
        if not _can_restore(src, f_cfg.name, log=log, dry_run=dry_run):
            continue
        log.info("  - Restoring %s", f_cfg.name)

        if f_cfg.mode == "host":
            if not f_cfg.dir:
                log.warning("    Skipping: no destination directory configured")
                continue
            dest = f_cfg.dir
            log.info("    %s -> %s (host)", src, dest)
            if not dry_run:
                ensure_dir(dest.parent)
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
        elif f_cfg.mode == "container":
            # Use tar to copy directory into container
            if not f_cfg.container or not f_cfg.path:
                log.warning("    Skipping: invalid container config")
                continue
            if not dry_run:
                if not container_exists(
                    cfg.runtime.container_command, f_cfg.container
                ):
                    log.error(
                        "    Container %s does not exist", f_cfg.container
                    )
                    return
                if not container_running(
                    cfg.runtime.container_command, f_cfg.container
                ):
                    log.error(
                        "    Container %s is not running", f_cfg.container
                    )
                    return

            log.info(
                "    %s -> %s:%s (container)", src, f_cfg.container, f_cfg.path
            )
            restore_container_files(
                crt=cfg.runtime.container_command,
                container=f_cfg.container,
                src=src,
                dst_path=f_cfg.path,
                dry_run=dry_run,
            )


def restore_postgres_from_archive(
    log: logging.Logger,
    cfg: RestoreConfig,
    extracted_root: Path,
    dry_run: bool,
) -> None:
    """Restore PostgreSQL databases from extracted archive."""
    if not cfg.core.restore_postgres or not cfg.postgres:
        log.info("Skipping PostgreSQL restoration")
        return

    log.info("Restoring %d PostgreSQL database(s)...", len(cfg.postgres))
    for pg_cfg in cfg.postgres:
        dump_file = extracted_root / f"postgres_{pg_cfg.name}.dump"
        if not dump_file.exists():
            if not dry_run:
                log.warning(
                    "  - Skipping %s: dump not found in archive", pg_cfg.name
                )
                continue

        log.info("  - Restoring %s from %s", pg_cfg.name, dump_file)

        if not dry_run:
            if not container_exists(
                cfg.runtime.container_command, pg_cfg.container
            ):
                log.error("    Container %s does not exist", pg_cfg.container)
                continue
            if not container_running(
                cfg.runtime.container_command, pg_cfg.container
            ):
                log.error("    Container %s is not running", pg_cfg.container)
                continue

        restore_postgres(
            crt=cfg.runtime.container_command,
            container=pg_cfg.container,
            user=pg_cfg.user,
            database=pg_cfg.database,
            dump_file=dump_file,
            password=pg_cfg.password,
            restore_extras=pg_cfg.dump_extras,  # Reuse dump_extras for restore
            dry_run=dry_run,
        )


def restore_redis_from_archive(
    log: logging.Logger,
    cfg: RestoreConfig,
    extracted_root: Path,
    dry_run: bool,
) -> None:
    """Restore Redis instances from extracted archive."""
    if not cfg.core.restore_redis or not cfg.redis:
        log.info("Skipping Redis restoration")
        return

    log.info("Restoring %d Redis instance(s)...", len(cfg.redis))
    for rd_cfg in cfg.redis:
        rdb_dir = extracted_root / f"redis_{rd_cfg.name}"
        rdb_file = rdb_dir / rd_cfg.rdb_name
        if not rdb_file.exists() and not dry_run:
            log.warning(
                "  - Skipping %s: RDB not found in archive", rd_cfg.name
            )
            continue

        log.info("  - Restoring %s from %s", rd_cfg.name, rdb_file)

        if not dry_run:
            if not container_exists(
                cfg.runtime.container_command, rd_cfg.container
            ):
                log.error("    Container %s does not exist", rd_cfg.container)
                continue
            if not container_running(
                cfg.runtime.container_command, rd_cfg.container
            ):
                log.error("    Container %s is not running", rd_cfg.container)
                continue

        restore_redis(
            crt=cfg.runtime.container_command,
            container=rd_cfg.container,
            rdb_file=rdb_file,
            password=rd_cfg.password,
            dry_run=dry_run,
        )


def _guess_name_prefix_from_archive_str(archive_str: str) -> str | None:
    base = Path(archive_str).name
    m = _NAME_PREFIX_RE.match(base)
    if m:
        return m.group(1)
    # if passed only the prefix (no date), accept it as-is
    if not base.endswith(".tar.gz") and "-" not in base:
        return base
    return None


def list_available_backups(
    log: logging.Logger,
    cfg: RestoreConfig,
    source: str,
    dry_run: bool,
) -> list[str]:
    if source != "s3":
        if source == "ssh":
            if not cfg.transport.ssh:
                log.error("ssh not configured, cannot list backups.")
                return []
            ssh_params = SSHParams(
                dest=cfg.transport.ssh.dest,
                port=cfg.transport.ssh.port,
                rsync_opts=cfg.transport.ssh.rsync_opts,
                prune_cmd=cfg.transport.ssh.prune_cmd,
            )
            # Try to infer prefix from --archive (if provided)
            name_prefix = _guess_name_prefix_from_archive_str(
                cfg.core.archive or ""
            )
            if not name_prefix:
                # last resort: use the backup name commonly used in examples
                # (adjust this if you add a 'name' to restore.ini later)
                name_prefix = "waldiez_runner"
                msg = (
                    "No explicit archive prefix detected; "
                    f"defaulting to '{name_prefix}'. "
                    "Pass --archive <prefix> (e.g. 'waldiez_runner') to refine."
                )
                log.info(msg)
            return ssh_list_remote(
                params=ssh_params,
                name_prefix=name_prefix,
                detailed=True,
                dry_run=dry_run,
            )
        if cfg.core.backup_dir:
            entries: list[tuple[datetime, str, str]] = []
            for name in os.listdir(cfg.core.backup_dir):
                path = cfg.core.backup_dir / name
                if not path.is_file():
                    continue
                try:
                    stat = path.stat()
                    mtime = datetime.fromtimestamp(stat.st_mtime)
                    size = format_size(stat.st_size)
                    entries.append((mtime, size, name))
                except OSError:
                    continue

            entries.sort(key=lambda x: x[0], reverse=True)

            # Format: "YYYY-MM-DD HH:MM:SS  42.3 MB  filename.tar.gz"
            return [
                f"  {t:%Y-%m-%d %H:%M:%S}    {s:>8}    {n}"
                for t, s, n in entries
            ]
        log.error("No backup dir configured, cannot list local backups.")
        return []

    if not cfg.transport.s3:
        log.error("S3 transport not configured")
        return []

    s3_params = S3Params(
        bucket=cfg.transport.s3.bucket,
        prefix=cfg.transport.s3.prefix,
        aws_profile=cfg.transport.s3.aws_profile,
        aws_region=cfg.transport.s3.aws_region,
    )

    # Try to infer prefix from --archive (if provided)
    name_prefix = _guess_name_prefix_from_archive_str(cfg.core.archive or "")
    if not name_prefix:
        # last resort: use the backup name commonly used in examples
        # (adjust this if you add a 'name' to restore.ini later)
        name_prefix = "waldiez_runner"
        msg = (
            "No explicit archive prefix detected; "
            f"defaulting to '{name_prefix}'. "
            "Pass --archive <prefix> (e.g. 'waldiez_runner') to refine."
        )
        log.info(msg)

    return s3_list_backups(
        params=s3_params, name_prefix=name_prefix, dry_run=dry_run
    )


def run_restore(log: logging.Logger, cfg: RestoreConfig) -> bool:
    """Execute restore operation.

    Returns:
        True if successful, False otherwise.
    """
    log.info("=" * 70)
    log.info("Waldiez Runner Restore")
    log.info("=" * 70)
    log.info("Archive: %s", cfg.core.archive)
    log.info("Source: %s", cfg.core.source)
    log.info("Strategy: %s", cfg.core.strategy)
    log.info("Dry run: %s", cfg.core.dry_run)
    log.info("=" * 70)

    staging_dir_path = cfg.core.staging_dir

    if staging_dir_path:
        ensure_dir(staging_dir_path)
        temp_context = tempdir(path=staging_dir_path)
    else:
        temp_context = tempdir()

    with temp_context as staging_dir:
        log.info("Staging directory: %s", staging_dir)

        # Fetch archive
        archive_path = fetch_archive(
            log, cfg, cfg.core.source, cfg.core.archive, staging_dir
        )

        # Verify integrity
        if not verify_archive_integrity(log, archive_path, cfg.core.dry_run):
            log.error("Archive verification failed, aborting restore")
            return False

        # Extract archive
        log.info("Extracting archive...")
        if cfg.core.dry_run:
            log.info("  (dry-run) Would extract archive to staging directory")
            extracted_root = staging_dir / "extracted"
        else:
            extracted_root = extract_archive(
                archive=archive_path,
                dest=staging_dir / "extracted",
                allow_links=False,
            )
            log.info("  Extracted to: %s", extracted_root)

        # Restore components based on strategy
        if cfg.core.strategy == "all" or cfg.core.restore_files:
            restore_files_from_archive(
                log, cfg, extracted_root, cfg.core.dry_run
            )

        if cfg.core.strategy == "all" or cfg.core.restore_postgres:
            restore_postgres_from_archive(
                log, cfg, extracted_root, cfg.core.dry_run
            )

        if cfg.core.strategy == "all" or cfg.core.restore_redis:
            restore_redis_from_archive(
                log, cfg, extracted_root, cfg.core.dry_run
            )

    log.info("=" * 70)
    log.info("✓ Restore completed successfully")
    log.info("=" * 70)

    return True


def _do_list(
    args: argparse.Namespace,
    cfg: RestoreConfig,
    log: logging.Logger,
) -> None:
    transport = cfg.core.source
    do_s3 = (args.list and transport == "s3") or args.list_s3
    do_ssh = (args.list and transport == "ssh") or args.list_ssh
    do_local = (args.list and transport == "local") or args.list_local
    if do_s3:
        log.info("Listing available S3 backups...")
        backups = list_available_backups(
            log, cfg, "s3", dry_run=cfg.core.dry_run
        )
        if backups:
            log.info("Available backups:")
            for backup in backups:
                print(f"  {backup}")
        else:
            log.info("No backups found")
    if do_ssh:
        log.info("Listing available SSH backups...")
        backups = list_available_backups(
            log, cfg, "ssh", dry_run=cfg.core.dry_run
        )
        if backups:
            log.info("Available backups:")
            for backup in backups:
                print(f"  {backup}")
        else:
            log.info("No backups found or listing not supported")

    if do_local:
        log.info("Listing available local backups...")
        backups = list_available_backups(
            log, cfg, "local", dry_run=cfg.core.dry_run
        )
        if backups:
            log.info("Available backups:")
            for backup in backups:
                print(f"  {backup}")
        else:
            log.info("No backups found or listing not supported")


def _do(
    args: argparse.Namespace,
    cfg: RestoreConfig,
    log: logging.Logger,
) -> int:
    """Parse config and restore."""
    # List mode
    if args.list or args.list_s3 or args.list_ssh or args.list_local:
        _do_list(args=args, cfg=cfg, log=log)
        return 0

    # Validate archive is set
    if not cfg.core.archive:
        log.error("No archive specified. Use --archive or set in config.")
        return 1
    # Validate-only mode
    if args.validate:
        log.info("✓ Configuration is valid")
        log.info("  Archive: %s", cfg.core.archive)
        log.info("  Source: %s", cfg.core.source)
        log.info("  Strategy: %s", cfg.core.strategy)
        log.info("  Files: %d", len(cfg.files))
        log.info("  PostgreSQL: %d", len(cfg.postgres))
        log.info("  Redis: %d", len(cfg.redis))
        return 0

    # Run restore
    success = run_restore(log, cfg)
    message = "Restore completed successfully" if success else "Restore failed"

    # Send notification
    send_notification(cfg, success, message)

    return 0 if success else 1


def main() -> int:
    """Parse config and backup."""
    args = parse_args()
    setup_logging(args.verbose)

    log = get_logger("restore")
    log.debug("Loading configuration...")
    try:
        cfg = load_restore_config()
    except BaseException as e:
        log.error("Invalid config: %s", e)
        return 1
    # Override config file path if specified
    if args.config:
        os.environ["RESTORE_INI"] = args.config
        # Apply CLI overrides
    if args.archive:
        cfg.core.archive = args.archive
    if args.source:
        cfg.core.source = args.source
    if args.strategy:
        cfg.core.strategy = args.strategy
    if args.dry_run:
        cfg.core.dry_run = True
    what = partial(_do, args, cfg, log)

    def on_interrupt() -> None:
        log.warning("Restore interrupted by user")
        send_notification(cfg, False, "Restore interrupted by user")

    def on_error(error: Exception) -> None:
        log.error("Restore failed: %s", error, exc_info=args.verbose)
        send_notification(cfg, False, f"Restore failed: {error}")

    return try_do(what, on_interrupt=on_interrupt, on_error=on_error)


if __name__ == "__main__":
    _EXIT_CODE = 1
    try:
        _EXIT_CODE = main()
    finally:
        if sys.path[0] == _SYS_PATH:
            sys.path.pop(0)
    sys.exit(_EXIT_CODE)
