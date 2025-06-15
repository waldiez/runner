# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Waldiez runner settings module."""

import logging
import os
from typing import Any, List, Optional, Tuple

from dotenv import load_dotenv
from pydantic import (
    Field,
    HttpUrl,
    SecretStr,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated, Self

from ._auth import (
    get_local_client_id,
    get_local_client_secret,
    get_oidc_audience,
    get_oidc_issuer_url,
    get_oidc_jwks_cache_ttl,
    get_oidc_jwks_url,
    get_use_local_auth,
    get_use_oidc_auth,
)
from ._common import (
    DOT_ENV_PATH,
    ENV_PREFIX,
    ROOT_DIR,
    get_enable_external_auth,
    get_external_auth_secret,
    get_external_auth_verify_url,
    is_testing,
    to_kebab,
)
from ._postgres import (
    get_db_host,
    get_db_name,
    get_db_password,
    get_db_port,
    get_db_url,
    get_db_user,
    get_postgres_enabled,
)
from ._redis import (
    RedisSchemeType,
    get_redis_db,
    get_redis_enabled,
    get_redis_host,
    get_redis_password,
    get_redis_port,
    get_redis_scheme,
)
from ._redis import get_redis_url as get_redis_url_
from ._server import (
    get_default_domain_name,
    get_default_host,
    get_default_port,
    get_force_ssl,
    get_max_jobs,
    get_secret_key,
    get_trusted_hosts,
    get_trusted_origin_regex,
    get_trusted_origins,
)
from ._tasks import get_input_timeout

LOG = logging.getLogger(__name__)


def _get_redis_password() -> SecretStr | None:
    rd_password = get_redis_password()
    if rd_password:
        return SecretStr(rd_password)
    return None


def _get_oidc_issuer_url() -> HttpUrl | None:
    oidc_issuer_url = get_oidc_issuer_url()
    if oidc_issuer_url:
        return HttpUrl(oidc_issuer_url)
    return None


def _get_oidc_jwks_url() -> HttpUrl | None:
    oidc_jwks_url = get_oidc_jwks_url()
    if oidc_jwks_url:
        return HttpUrl(oidc_jwks_url)
    return None


class Settings(BaseSettings):
    """Settings class."""

    host: str = get_default_host()
    port: Annotated[int, Field(ge=1, le=65535)] = get_default_port()
    domain_name: str = get_default_domain_name()
    max_jobs: Annotated[int, Field(ge=1, le=100)] = get_max_jobs()
    force_ssl: bool = get_force_ssl()
    trusted_hosts: str | List[str] = get_trusted_hosts(
        domain_name=domain_name, host=host
    )
    trusted_origins: str | List[str] = get_trusted_origins(
        domain_name=domain_name,
        port=port,
        force_ssl=force_ssl,
        host=host,
    )
    trusted_origin_regex: Optional[str] = get_trusted_origin_regex()
    secret_key: SecretStr = SecretStr(get_secret_key())
    log_level: str = "INFO"
    # Database
    postgres: bool = get_postgres_enabled()
    db_host: str = get_db_host()
    db_port: Annotated[int, Field(ge=1, le=65535)] = get_db_port()
    db_user: str = get_db_user()
    db_password: SecretStr = SecretStr(get_db_password())
    db_name: str = get_db_name()
    db_url: Optional[str] = get_db_url()
    # Redis
    redis: bool = get_redis_enabled()
    redis_host: str = get_redis_host()
    redis_port: Annotated[int, Field(ge=1, le=65535)] = get_redis_port()
    redis_db: Annotated[int, Field(ge=0, le=15)] = get_redis_db()
    redis_scheme: RedisSchemeType = get_redis_scheme()
    redis_password: Optional[SecretStr] = _get_redis_password()
    redis_url: Optional[str] = get_redis_url_()
    dev: bool = False
    #
    # Auth
    # Pre-OIDC (HS256) internal token setup
    #
    use_local_auth: bool = get_use_local_auth()
    local_client_id: str = get_local_client_id()
    local_client_secret: SecretStr = SecretStr(get_local_client_secret())
    #
    # OIDC/OAuth2 provider setup (Keycloak, Auth0, Google, etc.)
    use_oidc_auth: bool = get_use_oidc_auth()
    # e.g., https://keycloak.example.com/realms/myrealm
    oidc_issuer_url: Optional[HttpUrl] = _get_oidc_issuer_url()
    oidc_audience: Optional[str] = get_oidc_audience()
    oidc_jwks_url: Optional[HttpUrl] = _get_oidc_jwks_url()
    oidc_jwks_cache_ttl: Annotated[int, Field(ge=1, le=3600)] = (
        get_oidc_jwks_cache_ttl()
    )
    # External authentication settings
    enable_external_auth: bool = get_enable_external_auth()
    external_auth_verify_url: str = get_external_auth_verify_url()
    external_auth_secret: str = get_external_auth_secret()
    # Task specific
    input_timeout: Annotated[int, Field(ge=1, le=3600)] = get_input_timeout()

    model_config = SettingsConfigDict(
        alias_generator=to_kebab,
        populate_by_name=True,
        env_prefix=ENV_PREFIX,
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
        cli_parse_args=False,  # we use typer
    )

    @classmethod
    def load(cls) -> "Settings":
        """Load the settings.

        Returns
        -------
        Settings
            The settings instance
        """
        if DOT_ENV_PATH.exists():
            load_dotenv(DOT_ENV_PATH, override=True)
        instance = cls()
        # instance.save()
        return instance

    @classmethod
    def is_testing(cls) -> bool:
        """Check if the settings are for testing.

        Returns
        -------
        bool
            Whether the settings are for testing
        """
        return is_testing()

    def get_redis_url(self) -> str | None:
        """Get the Redis URL.

        Returns
        -------
        str
            The Redis URL
        """
        if self.redis is False:
            return None
        if self.redis_url:
            return self.redis_url
        rd_scheme = self.redis_scheme
        rd_host = self.redis_host
        rd_port = self.redis_port
        rd_db = self.redis_db
        rd_password = (
            self.redis_password.get_secret_value()
            if self.redis_password
            else None
        )
        return self.generate_redis_url(
            rd_scheme, rd_host, rd_port, rd_db, rd_password
        )

    @staticmethod
    def generate_redis_url(
        scheme: str, host: str, port: int, db: int, password: str | None
    ) -> str:
        """Generate a Redis URL.

        Parameters
        ----------
        scheme : str
            The Redis scheme
        host : str
            The Redis host
        port : int
            The Redis port
        db : int
            The Redis DB index
        password : str | None
            The Redis password

        Returns
        -------
        str
            The Redis URL
        """
        # redis://[[username]:[password]]@localhost:6379/0
        # rediss://[[username]:[password]]@localhost:6379/0
        # unix://[username@]/path/to/socket.sock?db=0[&password=password]
        if scheme == "unix":
            url = f"{scheme}://{host}?db={db}"
            if password:  # pragma: no branch
                url += f"&password={password}"
            return url
        if password:  # pragma: no cover
            return f"{scheme}://:{password}@{host}:{port}/{db}"
        return f"{scheme}://{host}:{port}/{db}"

    def get_database_url(self, skip_test_check: bool = False) -> str:
        """Get the database URL.

        Parameters
        ----------
        skip_test_check : bool, optional
            Whether to skip the test check, by default False

        Returns
        -------
        str
            The database URL
        """
        if self.postgres is False:
            name_prefix = ENV_PREFIX.lower()
            db_name = f"{name_prefix}database.sqlite3"
            if self.is_testing() and not skip_test_check:
                db_name = f"{name_prefix}test.db"
            return f"sqlite+aiosqlite:///{ROOT_DIR}/{db_name}"
        if self.db_url:
            return self.db_url
        return self.generate_database_url(
            "postgresql+psycopg",
            self.db_user,
            self.db_password.get_secret_value() if self.db_password else None,
            self.db_host,
            self.db_port,
            self.db_name,
        )

    def get_sync_database_url(self) -> str:
        """Get the sync database URL.

        Returns
        -------
        str
            The sync database URL

        Raises
        ------
        ValueError
            If the URL is invalid
        """
        url = self.get_database_url()
        if "sqlite" in url:
            return url.replace("+aiosqlite", "")
        return url

    @staticmethod
    def generate_database_url(
        scheme: str,
        user: str,
        password: str | None,
        host: str,
        port: int,
        db: str,
    ) -> str:
        """Generate a database URL.

        Parameters
        ----------
        scheme : str
            The database scheme
        user : str
            The database user
        password : str
            The database password
        host : str
            The database host
        port : int
            The database port
        db : str
            The database name

        Returns
        -------
        str
            The database URL
        """
        user_spec = ""
        if user:  # pragma: no cover
            if password:
                user_spec = f"{user}:{password}@"
            else:
                user_spec = f"{user}@"
        return f"{scheme}://{user_spec}{host}:{port}/{db}"

    def save(self) -> None:
        """Save the environment variables.

        Raises
        ------
        RuntimeError
            If a required environment variable
            is not set or is invalid
        """
        env_items: List[Tuple[str, Any]] = []
        for key, value in self.model_dump().items():
            key_upper = key.upper()
            env_key = f"{ENV_PREFIX}{key_upper}"
            env_value = value
            if isinstance(value, SecretStr):
                env_value = value.get_secret_value()
            if isinstance(value, bool):
                env_value = str(value).lower()
            if isinstance(value, (list, tuple)):
                env_value = ",".join(value)  # pyright: ignore
            if isinstance(value, (int, float)):
                env_value = str(int(value))
            if not isinstance(env_value, str):
                env_value = str(value)  # pyright: ignore
            env_value = env_value if env_value != "None" else ""
            self._handle_special_key_value(key, env_value)
            os.environ[env_key] = env_value
            env_items.append((env_key, env_value))
        with open(DOT_ENV_PATH, "w", encoding="utf-8") as file:
            for env_key, env_value in env_items:
                file.write(f"{env_key}={env_value}\n")

    def _handle_special_key_value(self, key: str, env_value: str) -> str:
        """Handle special key values.

        Parameters
        ----------
        key : str
            The key
        env_value : str
            The environment value

        Returns
        -------
        str
            The environment value
        """
        special_keys = (
            "secret_key",
            "local_client_id",
            "local_client_secret",
        )
        if key not in special_keys:
            return env_value
        if not env_value or len(env_value) < 32:
            if not self.is_testing():  # pragma: no cover
                # we should not reach here if not testing
                raise RuntimeError(f"{key} is not (correctly) set: {env_value}")

            warning_msg = (
                f"Using default value for {key} in testing mode: {env_value} "
                f"please make sure that the {DOT_ENV_PATH} file "
                "is updated/removed if needed"
            )
            LOG.warning(warning_msg)
            length = 32 if key == "local_client_id" else 64
            # a fixed string (for all tests) to avoid randomness
            # and to ensure the length is correct
            env_value = (ENV_PREFIX.lower() + key) * length
        return env_value

    # pylint: disable=unused-argument
    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, value: Any, info: ValidationInfo) -> Any:
        """Validate the log level.

        Parameters
        ----------
        value : Any
            The value
        info : ValidationInfo
            The validation info

        Returns
        -------
        LogLevelType
            The log level
        """
        if isinstance(value, str):
            return value.upper()
        return value  # pragma: no cover

    @field_validator("trusted_hosts", "trusted_origins", mode="before")
    @classmethod
    def split_str_value(cls, value: Any, info: ValidationInfo) -> List[str]:
        """Split the value if it is a string.

        Parameters
        ----------
        value : Any
            The value
        info : ValidationInfo
            The validation info

        Returns
        -------
        List[str]
            The value as a list
        """
        if isinstance(value, str):
            if value.count(",") >= 1:
                return [item for item in value.split(",") if item]

            return [value] if value else []
        if isinstance(value, list):
            return [item for item in value if item]  # pyright: ignore
        return []  # pragma: no cover

    @model_validator(mode="after")
    def validate_oidc_settings(self) -> Self:
        """Validate the OIDC settings.

        Returns
        -------
        Settings
            The settings instance after validation

        Raises
        ------
        ValueError
            If the OIDC settings are invalid
        """
        if self.use_oidc_auth is False:
            return self
        if not self.oidc_issuer_url:
            raise ValueError("OIDC issuer URL is required")
        if not self.oidc_audience:
            raise ValueError("OIDC audience is required")
        if not self.oidc_jwks_url:
            raise ValueError("OIDC JWKS URL is required")
        return self
