# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Command line interface module."""

# flake8: noqa: E501
# pylint: skip-file
import logging
import logging.config
import secrets
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import typer

try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv(override=False)

try:
    from waldiez_runner._version import __version__
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from waldiez_runner._version import __version__

from waldiez_runner._logging import LogLevel, get_log_level, get_logging_config
from waldiez_runner.config import RedisScheme, Settings
from waldiez_runner.start import (
    start_all,
    start_broker,
    start_broker_and_scheduler,
    start_scheduler,
    start_uvicorn,
)

APP_NAME = "waldiez-runner"
APP_HELP = "Waldiez runner"

DEFAULT_SETTINGS = Settings.load()

app = typer.Typer(
    name=APP_NAME,
    help=APP_HELP,
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
    add_completion=False,
    no_args_is_help=False,
    invoke_without_command=True,
    add_help_option=True,
    pretty_exceptions_short=True,
)


@app.command()
def run(
    host: str = typer.Option(
        default=DEFAULT_SETTINGS.host,
        help="The host to run the server on",
    ),
    port: int = typer.Option(
        default=DEFAULT_SETTINGS.port,
        help="The port to run the server on",
    ),
    max_jobs: int = typer.Option(
        default=DEFAULT_SETTINGS.max_jobs,
        help="The maximum number of active jobs to allow",
    ),
    log_level: LogLevel = typer.Option(
        default=get_log_level(),
        help="The log level",
        case_sensitive=False,
    ),
    domain_name: str = typer.Option(
        default=DEFAULT_SETTINGS.domain_name,
        help="The domain name",
    ),
    trusted_hosts: List[str] = typer.Option(
        default=DEFAULT_SETTINGS.trusted_hosts,
        help="Trusted hosts (comma separated)",
    ),
    trusted_origins: List[str] = typer.Option(
        default=DEFAULT_SETTINGS.trusted_origins,
        help="Trusted origins (comma separated)",
    ),
    trusted_origin_regex: Optional[str] = typer.Option(
        default=DEFAULT_SETTINGS.trusted_origin_regex,
        help="Trusted origin regex",
    ),
    force_ssl: bool = typer.Option(
        DEFAULT_SETTINGS.force_ssl,
        "--force-ssl",
        help="Force SSL",
    ),
    secret_key: str = typer.Option(
        default=(
            DEFAULT_SETTINGS.secret_key.get_secret_value()
            if DEFAULT_SETTINGS.secret_key
            else "REPLACE_ME"
        ),
        show_default=False,
        help="The secret key",
    ),
    # Auth CLI options
    use_local_auth: bool = typer.Option(
        DEFAULT_SETTINGS.use_local_auth,
        help="Use local authentication",
    ),
    local_client_id: str = typer.Option(
        default=DEFAULT_SETTINGS.local_client_id,
        help="Local client ID",
    ),
    local_client_secret: str = typer.Option(
        default=(
            DEFAULT_SETTINGS.local_client_secret.get_secret_value()
            if DEFAULT_SETTINGS.local_client_secret
            else "REPLACE_ME"
        ),
        help="Local client secret",
        show_default=False,
    ),
    use_oidc_auth: bool = typer.Option(
        DEFAULT_SETTINGS.use_oidc_auth,
        help="Use OIDC authentication",
    ),
    oidc_issuer_url: str = typer.Option(
        default=DEFAULT_SETTINGS.oidc_issuer_url,
        help="OIDC issuer URL",
    ),
    oidc_audience: str = typer.Option(
        default=DEFAULT_SETTINGS.oidc_audience,
        help="OIDC audience",
    ),
    oidc_jwks_url: str = typer.Option(
        default=DEFAULT_SETTINGS.oidc_jwks_url,
        help="OIDC JWKS URL",
    ),
    oidc_jwks_cache_ttl: int = typer.Option(
        default=DEFAULT_SETTINGS.oidc_jwks_cache_ttl,
        help="OIDC JWKS cache TTL",
    ),
    # Redis CLI options
    redis: bool = typer.Option(
        DEFAULT_SETTINGS.redis,
        help="Disable Redis (use FakeRedis)",
    ),
    redis_host: str = typer.Option(
        default=DEFAULT_SETTINGS.redis_host,
        help="Redis host",
    ),
    redis_port: int = typer.Option(
        default=DEFAULT_SETTINGS.redis_port,
        help="Redis port",
    ),
    redis_db: int = typer.Option(
        default=DEFAULT_SETTINGS.redis_db,
        help="Redis DB index",
    ),
    redis_scheme: RedisScheme = typer.Option(
        default=DEFAULT_SETTINGS.redis_scheme,
        help="Redis connection scheme",
        case_sensitive=False,
    ),
    redis_password: Optional[str] = typer.Option(
        default=(
            DEFAULT_SETTINGS.redis_password.get_secret_value()
            if DEFAULT_SETTINGS.redis_password
            else None
        ),
        help="Redis password",
        show_default=False,
    ),
    redis_url: Optional[str] = typer.Option(
        default=DEFAULT_SETTINGS.redis_url,
        help="Manually specify the Redis URL, overriding the other Redis options",
        show_default=False,
    ),
    # Database CLI options
    postgres: bool = typer.Option(
        DEFAULT_SETTINGS.postgres,
        help="Disable PostgreSQL",
    ),
    db_host: str = typer.Option(
        default=DEFAULT_SETTINGS.db_host,
        help="Postgres host",
    ),
    db_port: int = typer.Option(
        default=DEFAULT_SETTINGS.db_port,
        help="Postgres port",
    ),
    db_user: str = typer.Option(
        default=DEFAULT_SETTINGS.db_user,
        help="Postgres user",
    ),
    db_password: str = typer.Option(
        default=DEFAULT_SETTINGS.db_password.get_secret_value(),
        help="Postgres password",
        show_default=False,
    ),
    db_name: str = typer.Option(
        default=DEFAULT_SETTINGS.db_name,
        help="Database name",
    ),
    db_url: str | None = typer.Option(
        default=DEFAULT_SETTINGS.db_url,
        help="Manually specify the database URL, overriding the other database options",
        show_default=False,
    ),
    # Override the service to start (if not uvicorn)
    broker: bool = typer.Option(
        False,
        "--broker",
        help="Start the broker",
    ),
    scheduler: bool = typer.Option(
        False,
        "--scheduler",
        help="Start the scheduler",
    ),
    worker: bool = typer.Option(
        False,
        "--worker",
        help="Start the worker (broker and scheduler)",
    ),
    # Development options
    reload: bool = typer.Option(
        default="--reload" in sys.argv,
        help="Reload the server on file changes",
    ),
    all: bool = typer.Option(
        False,
        "--all",
        help="Start all services (broker, scheduler, and uvicorn)",
    ),
    dev: bool = typer.Option(
        False,
        "--dev",
        help="Start in development mode",
    ),
    # Version
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the version and exit",
    ),
) -> None:
    """Runner command line interface."""
    if version:
        typer.echo(f"{APP_NAME} {__version__}")
        raise typer.Exit()
    if "--no-debug" in sys.argv:  # pragma: no cover
        log_level = LogLevel.INFO
    logging_config = get_logging_config(log_level.value)
    logging.config.dictConfig(logging_config)
    logger = logging.getLogger(__name__)
    logger.debug("Starting the application")
    dev = dev or "--dev" in sys.argv
    (
        secret_key,
        local_client_id,
        local_client_secret,
    ) = check_secrets(secret_key, local_client_id, local_client_secret, dev)
    settings = Settings(
        host=host,
        port=port,
        max_jobs=max_jobs,
        domain_name=domain_name,
        trusted_hosts=trusted_hosts,
        trusted_origins=trusted_origins,
        trusted_origin_regex=trusted_origin_regex,
        force_ssl=force_ssl,
        secret_key=secret_key,  # type: ignore
        use_local_auth=use_local_auth,
        local_client_id=local_client_id,
        local_client_secret=local_client_secret,  # type: ignore
        use_oidc_auth=use_oidc_auth,
        oidc_issuer_url=oidc_issuer_url,  # type: ignore
        oidc_audience=oidc_audience,
        oidc_jwks_url=oidc_jwks_url,  # type: ignore
        oidc_jwks_cache_ttl=oidc_jwks_cache_ttl,
        redis=redis,
        redis_host=redis_host,
        redis_port=redis_port,
        redis_db=redis_db,
        redis_scheme=redis_scheme,  # type: ignore
        redis_password=redis_password,  # type: ignore
        redis_url=redis_url,
        postgres=postgres,
        db_host=db_host,
        db_port=db_port,
        db_user=db_user,
        db_password=db_password,  # type: ignore
        db_name=db_name,
        db_url=db_url,
        log_level=log_level.value.upper(),
        dev=dev,
    )
    logger.debug("Effective settings: %s", settings.model_dump_json(indent=2))
    settings.save()
    skip_redis = settings.redis is False
    if all:
        start_all(
            host,
            port,
            reload,
            log_level,
            skip_redis=skip_redis,
        )
    elif worker or (broker and scheduler):
        start_broker_and_scheduler(reload, log_level, skip_redis=skip_redis)
    elif broker:
        start_broker(reload, log_level, skip_redis=skip_redis)
    elif scheduler:
        start_scheduler(log_level, skip_redis=skip_redis)
    else:
        start_uvicorn(host, port, reload, log_level, logging_config)


def check_secrets(
    secret_key: str,
    local_client_id: str,
    local_client_secret: str,
    dev: bool,
) -> Tuple[str, str, str]:
    """Check the secret key and the local client id/secret pair."""
    data = {
        "secret_key": secret_key,
        "local_client_id": local_client_id,
        "local_client_secret": local_client_secret,
    }
    for key, value in data.items():
        if not value or value == "REPLACE_ME":  # pragma: no cover
            if not dev:
                raise typer.BadParameter(f"Invalid value for {key}: {value}")
            else:
                length = 64 if key != "local_client_id" else 32
                data[key] = secrets.token_hex(length)
                typer.secho(
                    f"Generated a random value for {key}",
                    fg=typer.colors.YELLOW,
                )
    return (
        data["secret_key"],
        data["local_client_id"],
        data["local_client_secret"],
    )


if __name__ == "__main__":
    app()
