# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Test waldiez_runner.config._server."""
# pylint: disable=missing-return-doc,missing-yield-doc,missing-param-doc

import os
import sys
from pathlib import Path
from typing import Generator

import pytest

# noinspection PyProtectedMember
from waldiez_runner.config._common import ENV_PREFIX

# noinspection PyProtectedMember
from waldiez_runner.config._server import (
    get_default_domain_name,
    get_default_host,
    get_default_port,
    get_secret_key,
    get_trusted_hosts,
    get_trusted_origin_regex,
    get_trusted_origins,
)

# noinspection DuplicatedCode
THIS_FILE = Path(__file__).resolve()


@pytest.fixture(scope="function", autouse=True, name="clear_env")
def clear_env_and_args() -> Generator[None, None, None]:
    """Clear environment variables and command-line arguments."""
    for var in os.environ:
        if var.startswith(ENV_PREFIX):
            os.environ.pop(var, None)
    original_argv = sys.argv[:]
    sys.argv = [str(THIS_FILE)]
    yield
    sys.argv = original_argv


def test_get_trusted_hosts_no_env() -> None:
    """Test get_trusted_hosts with no environment variables."""
    domain_name = "example.com"
    host = "localhost"
    assert get_trusted_hosts(domain_name, host) == ["example.com"]


def test_get_trusted_hosts_with_env() -> None:
    """Test get_trusted_hosts with environment variables."""
    os.environ[f"{ENV_PREFIX}TRUSTED_HOSTS"] = "host1,host2"
    domain_name = "example.com"
    host = "localhost"
    assert get_trusted_hosts(domain_name, host) == [
        "host1",
        "host2",
        "example.com",
    ]


def test_get_trusted_hosts_with_cmd_args() -> None:
    """Test get_trusted_hosts with command-line arguments."""
    sys.argv += ["--trusted-hosts", "trustedhost"]
    domain_name = "example.com"
    host = "localhost"
    assert get_trusted_hosts(domain_name, host) == [
        "example.com",
        "trustedhost",
    ]

    sys.argv = [str(THIS_FILE), "--trusted-hosts"]
    os.environ.pop(f"{ENV_PREFIX}TRUSTED_HOSTS", None)
    assert get_trusted_hosts(domain_name, host) == ["example.com"]


def test_get_trusted_origins_no_env() -> None:
    """Test get_trusted_origins with no environment variables."""
    domain_name = "example.com"
    port = 8000
    force_ssl = False
    host = "localhost"
    # noinspection HttpUrlsUsage
    expected = [
        "https://example.com",
        "https://localhost",
        "http://example.com",
        "http://example.com:8000",
        "http://localhost",
        "http://localhost:8000",
    ]
    assert get_trusted_origins(domain_name, port, force_ssl, host) == expected


def test_get_trusted_origins_with_env() -> None:
    """Test get_trusted_origins with environment variables."""
    os.environ[f"{ENV_PREFIX}TRUSTED_ORIGINS"] = (
        "https://custom1,http://custom2"
    )
    domain_name = "example.com"
    port = 8000
    force_ssl = True
    host = "localhost"
    expected = [
        "https://custom1",
        "http://custom2",
        "https://example.com",
        "https://localhost",
    ]
    assert get_trusted_origins(domain_name, port, force_ssl, host) == expected


def test_get_trusted_origin_regex_no_env() -> None:
    """Test get_trusted_origin_regex with no environment variables."""
    os.environ.pop(f"{ENV_PREFIX}TRUSTED_ORIGIN_REGEX", None)
    assert get_trusted_origin_regex() is None


def test_get_trusted_origin_regex_with_env() -> None:
    """Test get_trusted_origin_regex with environment variables."""
    os.environ[f"{ENV_PREFIX}TRUSTED_ORIGIN_REGEX"] = "custom-regex"
    assert get_trusted_origin_regex() == "custom-regex"


def test_get_trusted_origin_regex_with_cmd_args() -> None:
    """Test get_trusted_origin_regex with command-line arguments."""
    sys.argv += ["--trusted-origin-regex", "cmd-regex"]
    assert get_trusted_origin_regex() == "cmd-regex"

    os.environ.pop(f"{ENV_PREFIX}TRUSTED_ORIGIN_REGEX", None)
    sys.argv = [str(THIS_FILE), "--trusted-origin-regex"]
    assert get_trusted_origin_regex() is None


def test_get_trusted_origins_with_cmd_args() -> None:
    """Test get_trusted_origins with command-line arguments."""
    sys.argv += ["--trusted-origins", "https://cmd-origin"]
    domain_name = "example.com"
    port = 8000
    force_ssl = False
    host = "localhost"
    # noinspection HttpUrlsUsage
    expected = [
        "https://example.com",
        "https://localhost",
        "http://example.com",
        "http://example.com:8000",
        "http://localhost",
        "http://localhost:8000",
        "https://cmd-origin",
    ]
    assert get_trusted_origins(domain_name, port, force_ssl, host) == expected

    sys.argv = [str(THIS_FILE), "--trusted-origins"]
    parsed_origins = get_trusted_origins(domain_name, port, force_ssl, host)
    assert parsed_origins == expected[:-1]


def test_get_default_domain_name() -> None:
    """Test get_default_domain_name."""
    os.environ[f"{ENV_PREFIX}DOMAIN_NAME"] = "env-domain.com"
    assert get_default_domain_name() == "env-domain.com"

    sys.argv += ["--domain-name", "cmd-domain.com"]
    assert get_default_domain_name() == "cmd-domain.com"
    os.environ.pop(f"{ENV_PREFIX}DOMAIN_NAME", None)

    sys.argv = [str(THIS_FILE), "--domain-name"]
    assert get_default_domain_name() == "localhost"

    sys.argv = [str(THIS_FILE)]
    os.environ.pop(f"{ENV_PREFIX}DOMAIN_NAME", None)
    assert get_default_domain_name() == "localhost"


def test_get_default_host() -> None:
    """Test get_default_host."""
    os.environ[f"{ENV_PREFIX}HOST"] = "env-host"
    assert get_default_host() == "env-host"

    sys.argv += ["--host", "cmd-host"]
    assert get_default_host() == "cmd-host"
    os.environ.pop(f"{ENV_PREFIX}HOST", None)

    sys.argv = [str(THIS_FILE), "--host"]
    assert get_default_host() in ("localhost", "0.0.0.0")  # container or not

    sys.argv = [str(THIS_FILE)]
    os.environ.pop(f"{ENV_PREFIX}HOST", None)
    assert get_default_host() in ("localhost", "0.0.0.0")


def test_get_default_port() -> None:
    """Test get_default_port."""
    os.environ[f"{ENV_PREFIX}PORT"] = "8080"
    assert get_default_port() == 8080

    sys.argv += ["--port", "9090"]
    assert get_default_port() == 9090

    sys.argv = [str(THIS_FILE)]
    os.environ[f"{ENV_PREFIX}PORT"] = "invalid"
    assert get_default_port() == 8000
    os.environ.pop(f"{ENV_PREFIX}PORT", None)

    sys.argv += ["--port", "invalid"]
    assert get_default_port() == 8000

    sys.argv = [str(THIS_FILE)]
    sys.argv += ["--port"]
    assert get_default_port() == 8000


def test_get_trusted_hosts_custom_host() -> None:
    """Test get_trusted_hosts."""
    domain_name = "example.com"
    host = "custom_host.com"
    assert get_trusted_hosts(domain_name, host) == [
        "example.com",
        "custom_host.com",
    ]


def test_get_secret_key() -> None:
    """Test get_secret_key."""
    os.environ[f"{ENV_PREFIX}SECRET_KEY"] = "env-secret-key"
    assert get_secret_key() == "env-secret-key"
    os.environ.pop(f"{ENV_PREFIX}SECRET_KEY", None)

    sys.argv += ["--secret-key", "cmd-secret-key"]
    assert get_secret_key() == "cmd-secret-key"
    sys.argv = [str(THIS_FILE)]
    os.environ.pop(f"{ENV_PREFIX}SECRET_KEY", None)

    sys.argv += ["--secret-key"]
    os.environ.pop(f"{ENV_PREFIX}SECRET_KEY", None)
    assert get_secret_key() == "REPLACE_ME"

    sys.argv = [str(THIS_FILE)]
    os.environ.pop(f"{ENV_PREFIX}SECRET_KEY", None)
    sys.argv += ["--secret-key", ""]
    assert get_secret_key() == "REPLACE_ME"
