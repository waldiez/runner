# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-param-doc,missing-yield-doc
"""Test waldiez_runner.config.settings.*."""

import os
from typing import List, Tuple
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from waldiez_runner.config import (
    ENV_PREFIX,
    ROOT_DIR,
    Settings,
    SettingsManager,
)


def test_default_settings_load(settings: Settings) -> None:
    """Ensure default settings are loaded properly."""
    assert settings.host is not None
    assert settings.port > 0
    assert settings.secret_key.get_secret_value() is not None
    assert isinstance(settings.trusted_hosts, list)
    assert isinstance(settings.trusted_origins, list)
    assert settings.redis_url is None  # Default to None


@patch.dict(
    os.environ,
    {f"{ENV_PREFIX}HOST": "test_host", f"{ENV_PREFIX}PORT": "9999"},
)
def test_env_override() -> None:
    """Ensure environment variables override default settings."""
    settings = Settings()
    assert settings.host == "test_host"
    assert settings.port == 9999


@pytest.mark.parametrize(
    "input_value,expected",
    [
        ("http://example.com", ["http://example.com"]),
        ("http://a.com,http://b.com", ["http://a.com", "http://b.com"]),
        ("", []),
    ],
)
def test_trusted_origins_parsing(input_value: str, expected: List[str]) -> None:
    """Test trusted_origins parsing from string to list."""
    settings = Settings(trusted_origins=input_value)
    assert settings.trusted_origins == expected


def test_log_level_validator() -> None:
    """Test log level is converted to uppercase if provided as a string."""
    settings = Settings(log_level="debug")
    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize(
    "redis_enabled,redis_url, redis_password, expected_urls",
    [
        (False, None, "no-care", (None,)),
        (True, "redis://custom_url", None, ("redis://custom_url",)),
        (
            True,
            "unix:///tmp/redis.sock",  # nosemgrep # nosec
            None,
            ("unix:///tmp/redis.sock",),  # nosemgrep # nosec
        ),
        (
            True,
            None,
            None,
            ("redis://localhost:6379/0", "redis://redis:6379/0"),
        ),
        (
            True,
            None,
            "rd_password",
            (
                "redis://:rd_password@localhost:6379/0",
                "redis://:rd_password@redis:6379/0",
            ),
        ),
    ],
)
def test_get_redis_url(
    redis_enabled: bool,
    redis_url: str,
    redis_password: str | None,
    expected_urls: Tuple[str | None, str | None],
) -> None:
    """Test Redis URL generation logic."""
    settings = Settings(
        redis=redis_enabled,
        redis_password=redis_password,  # type: ignore # nosemgrep # nosec
        redis_url=redis_url,
    )
    assert settings.get_redis_url() in expected_urls


def test_get_database_url_testing(
    settings: Settings,
) -> None:
    """Test Redis URL generation logic in testing mode."""
    os.environ[f"{ENV_PREFIX}TESTING"] = "1"
    assert (
        settings.get_database_url()
        == f"sqlite+aiosqlite:///{ROOT_DIR}/{ENV_PREFIX.lower()}test.db"
    )


@patch.dict(
    os.environ,
    {
        f"{ENV_PREFIX}TESTING": "1",
    },
)
def test_get_database_url_not_testing(
    settings: Settings,
) -> None:
    """Test Redis URL generation logic in testing mode."""
    os.environ[f"{ENV_PREFIX}TESTING"] = "0"
    os.environ[f"{ENV_PREFIX}NO_POSTGRES"] = "1"
    db_path = (
        f"sqlite+aiosqlite:///{ROOT_DIR}/{ENV_PREFIX.lower()}database.sqlite3"
    )
    assert settings.get_database_url() == db_path
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ[f"{ENV_PREFIX}TESTING"] = "1"
    os.environ[f"{ENV_PREFIX}NO_POSTGRES"] = "1"


# pylint: disable=line-too-long
@pytest.mark.parametrize(
    "postgres_enabled,db_url,expected_urls",
    [
        (
            False,
            None,
            (
                f"sqlite+aiosqlite:///{ROOT_DIR}/{ENV_PREFIX.lower()}database.sqlite3",  # noqa: E501
            ),
        ),
        (
            True,
            "postgresql://user:pass@host/db",
            ("postgresql://user:pass@host/db",),
        ),
        (
            True,
            None,
            (
                # in container: db (container name) vs localhost
                "postgresql+psycopg://db_user:db_password@db:5432/db_name",
                "postgresql+psycopg://db_user:db_password@localhost:5432/db_name",  # noqa: E501
            ),
        ),
    ],
)
def test_generate_database_url(
    postgres_enabled: bool,
    db_url: str | None,
    expected_urls: Tuple[str | None, str | None],
) -> None:
    """Test database URL generation logic."""
    settings = Settings(
        postgres=postgres_enabled,
        db_url=db_url,
    )
    assert settings.get_database_url(True) in expected_urls


def test_secret_key_handling() -> None:
    """Ensure secret keys are properly handled as `SecretStr`."""
    settings = Settings(
        secret_key="super_secret",  # type: ignore  # nosemgrep # nosec
    )
    assert settings.secret_key.get_secret_value() == "super_secret"


def test_settings_manager_singleton() -> None:
    """Ensure `SettingsManager` maintains a singleton instance."""
    settings1 = SettingsManager.load_settings()
    settings2 = SettingsManager.get_settings()
    assert id(settings1) == id(settings2)  # Should be the same instance


def test_settings_manager_force_reload() -> None:
    """Ensure `force_reload=True` creates a new instance."""
    settings1 = SettingsManager.load_settings()
    settings2 = SettingsManager.load_settings(
        force_reload=True,
    )
    assert id(settings1) != id(settings2)  # Should be a new instance
    print(settings1)
    print(settings2)
    assert settings1 == settings2  # but with the same values


def test_settings_manager_reset() -> None:
    """Ensure `reset_settings()` clears instance cache."""
    settings1 = SettingsManager.load_settings()
    SettingsManager.reset_settings()
    settings2 = SettingsManager.get_settings()
    assert id(settings1) != id(settings2)  # Should be a new instance


def test_invalid_port() -> None:
    """Ensure invalid ports raise validation errors."""
    with pytest.raises(ValidationError):
        os.environ.pop(f"{ENV_PREFIX}PORT", None)
        Settings(port=-1)  # Invalid port


def test_invalid_redis_scheme() -> None:
    """Ensure an invalid Redis scheme raises a validation error."""
    with pytest.raises(ValidationError):
        os.environ.pop(f"{ENV_PREFIX}REDIS_SCHEME", None)
        Settings(redis_scheme="invalid_scheme")  # type: ignore


def test_unix_redis_socket() -> None:
    """Ensure a valid Redis socket URL is correctly parsed."""
    settings = Settings(
        redis=True,
        redis_scheme="unix",
        redis_host="/tmp/redis.sock",  # nosemgrep # nosec
        redis_port=6397,
        redis_db=1,
        redis_password="very-secret",  # type: ignore # nosemgrep # nosec
    )
    url = (
        "unix:///tmp/redis.sock?db=1&password=very-secret"  # nosemgrep # nosec
    )
    redis_url = settings.get_redis_url()
    assert redis_url == url


def test_oidc_settings() -> None:
    """Ensure OIDC settings are validated properly."""
    settings = Settings(
        use_oidc_auth=True,
        oidc_issuer_url="https://example.com/",  # type: ignore
        oidc_audience="test",
        oidc_jwks_url="https://example.com/jwks",  # type: ignore
    )
    assert settings.use_oidc_auth is True
    assert str(settings.oidc_issuer_url) == "https://example.com/"
    assert settings.oidc_audience == "test"
    assert str(settings.oidc_jwks_url) == "https://example.com/jwks"


def test_invalid_oidc_settings() -> None:
    """Ensure invalid OIDC settings raise validation errors."""
    with pytest.raises(ValidationError):
        Settings(
            use_oidc_auth=True,
            oidc_issuer_url="https://example.com",  # type: ignore
        )
    with pytest.raises(ValidationError):
        Settings(use_oidc_auth=True, oidc_audience="test")
    with pytest.raises(ValidationError):
        Settings(
            use_oidc_auth=True,
            oidc_jwks_url="https://example.com/jwks",  # type: ignore
        )
