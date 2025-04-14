# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Pre start actions to be performed."""

import logging
import os
import secrets
import sys
import tempfile
import traceback
from pathlib import Path
from typing import List, Tuple

import redis
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from tenacity import (
    before_log,
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_fixed,
)
from waldiez.utils.pysqlite3_checker import (
    check_pysqlite3,
    download_sqlite_amalgamation,
    install_pysqlite3,
)

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

LOG = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent.resolve()
MAX_RETRIES = 60 * 10  # 10 minutes
WAIT_SECONDS = 10
DOT_ENV_PATH = ROOT_DIR / ".env"

os.environ["PYTHONUNBUFFERED"] = "1"

try:
    from waldiez_runner.config import ENV_PREFIX, SettingsManager
except ImportError:
    sys.path.append(str(ROOT_DIR))
    from waldiez_runner.config import ENV_PREFIX, SettingsManager


if DOT_ENV_PATH.exists():
    load_dotenv(DOT_ENV_PATH, override=True)
else:
    SettingsManager.load_settings().save()
    load_dotenv(DOT_ENV_PATH, override=True)

os.environ[f"{ENV_PREFIX}TESTING"] = "false"


# pylint: disable=duplicate-code
def try_check_pysqlite3() -> None:
    """Check if pysqlite3 is installed and if not, install it.

    Before waldiez tries:
     if on linux and arm64, pysqlite3-binary is not available
    and we need to install it manually.
    """
    cwd = os.getcwd()
    tmp_dir = tempfile.gettempdir()
    os.chdir(tmp_dir)
    try:
        check_pysqlite3()
    except BaseException:  # pylint: disable=broad-exception-caught
        download_path = download_sqlite_amalgamation()
        install_pysqlite3(download_path)
    finally:
        os.chdir(cwd)
    check_pysqlite3()


@retry(
    reraise=True,
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_fixed(WAIT_SECONDS),
    before=before_log(LOG, logging.DEBUG),
    before_sleep=before_sleep_log(LOG, logging.DEBUG),
)
def check_db_connection() -> None:
    """Ensure the database connection is available.

    Raises
    ------
    RuntimeError
        If the connection fails.
    """
    settings = SettingsManager.load_settings(force_reload=False)
    LOG.info("Settings: \n%s", settings.model_dump_json(indent=2))
    if "--no-postgres" in sys.argv or settings.postgres is not True:
        LOG.info("Skipping PostgreSQL connection check")
        return
    database_url = settings.get_sync_database_url()
    if database_url.startswith("sqlite"):
        LOG.info("Skipping SQLite connection check")
        return
    sync_engine = create_engine(database_url, echo=True)
    try:
        with sync_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except BaseException as exc:
        details = traceback.format_exc()
        LOG.error("Database connection failed: %s", details)
        raise RuntimeError("Database connection failed") from exc
    sync_engine.dispose()
    LOG.info("Connected to database!")


@retry(
    reraise=True,
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_fixed(WAIT_SECONDS),
    before=before_log(LOG, logging.DEBUG),
    before_sleep=before_sleep_log(LOG, logging.DEBUG),
)
def check_redis_connection() -> None:
    """Ensure the Redis connection is available.

    Raises
    ------
    RuntimeError
        If the connection fails.
    """
    settings = SettingsManager.load_settings(force_reload=False)
    redis_url = settings.get_redis_url()
    if not redis_url or "--no-redis" in sys.argv:
        LOG.info("Skipping Redis connection check")
        return
    LOG.info("Checking Redis connection...")
    try:
        connection = redis.Redis.from_url(redis_url)
    except BaseException as exc:
        details = traceback.format_exc()
        LOG.error("Redis connection failed: %s", details)
        raise RuntimeError("Redis connection failed") from exc
    connection.ping()
    LOG.info("Connected to Redis!")


def update_dotenv(key: str, value: str) -> None:
    """Store a key-value pair in the .env file.

    Parameters
    ----------
    key : str
        The key to store.
    value : str
        The value to store.
    """
    # replace if needed, add if not present
    os.environ[key] = value
    with open(DOT_ENV_PATH, "r", encoding="utf-8", newline="\n") as file:
        lines = file.readlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}\n")
    with open(DOT_ENV_PATH, "w", encoding="utf-8", newline="\n") as file:
        file.writelines(lines)


def assert_secrets(entries: List[Tuple[str, str | None]]) -> None:
    """Ensure that the secrets are available.

    Parameters
    ----------
    entries : Tuple[str, str]
        The entries to check (getattr, value)
    Raises
    ------
    RuntimeError
        If the secrets are not available.
    """
    settings = SettingsManager.load_settings(force_reload=True)
    for key, expected in entries:
        if not expected:
            raise RuntimeError(f"{key} is not set")
        if expected == "REPLACE_ME":
            raise RuntimeError(f"{key} is not set, please update the .env file")
        value = os.getenv(f"{ENV_PREFIX}{key.upper()}")
        if not value:
            raise RuntimeError(f"{key} is not available in environment")
        if value != expected:
            raise RuntimeError(
                f"{key} in environment does not match, "
                f"expected {expected}, got {value}"
            )
        in_settings = getattr(settings, key)
        if not in_settings:
            raise RuntimeError(f"Secret {key} is not available in settings")
        if hasattr(in_settings, "get_secret_value"):
            in_settings = in_settings.get_secret_value()
        if in_settings != value:
            raise RuntimeError(
                f"{key} does not match, expected {expected}, got {value}"
            )


def ensure_secrets() -> None:
    """Ensure that the secrets are available."""
    settings = SettingsManager.load_settings(force_reload=False)
    secret_key = settings.secret_key.get_secret_value()
    if not secret_key or len(secret_key) < 64:
        secret_key = secrets.token_urlsafe(64)
    update_dotenv(f"{ENV_PREFIX}SECRET_KEY", secret_key)
    client_id = settings.local_client_id
    if not client_id or client_id == "REPLACE_ME":
        client_id = secrets.token_hex(32)
    update_dotenv(f"{ENV_PREFIX}LOCAL_CLIENT_ID", client_id)
    client_secret = (
        settings.local_client_secret.get_secret_value()
        if settings.local_client_secret
        else None
    )
    if not client_secret or client_secret == "REPLACE_ME":  # nosemgrep # nosec
        client_secret = secrets.token_hex(64)
    update_dotenv(f"{ENV_PREFIX}LOCAL_CLIENT_SECRET", client_secret)
    settings = SettingsManager.load_settings(force_reload=True)
    settings.save()
    LOG.info("Secrets have been checked")
    assert_secrets(
        [
            (
                "secret_key",
                secret_key,
            ),
            (
                "local_client_id",
                client_id,
            ),
            (
                "local_client_secret",
                client_secret,
            ),
        ]
    )


def main() -> None:
    """Perform pre-start actions."""
    try_check_pysqlite3()
    if "--secrets" in sys.argv:
        ensure_secrets()
        return
    testing = os.environ.get("WALDIEZ_RUNNER_TESTING", "false").lower() in (
        "true",
        "yes",
        "1",
    )
    if "--dev" in sys.argv:
        testing = False
    if not testing:
        LOG.info("Performing pre-start actions")
        ensure_secrets()
        check_db_connection()
        check_redis_connection()
        LOG.info("Pre-start actions completed")


if __name__ == "__main__":
    main()
