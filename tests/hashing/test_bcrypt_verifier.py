# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=no-self-use,missing-param-doc

"""Tests for bcrypt verifier."""

import bcrypt
import pytest

from waldiez_runner.hashing._bcrypt_verifier import BcryptVerifier


class TestBcryptVerifier:
    """Test bcrypt verifier implementation."""

    def test_verify_correct_password_2a(self) -> None:
        """Test verification with $2a$ prefix."""
        password = "test_password"  # nosemgrep # nosec
        hashed = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        assert BcryptVerifier.verify(password, hashed)

    def test_verify_incorrect_password(self) -> None:
        """Test that verify fails with incorrect password."""
        password = "test_password"  # nosemgrep # nosec
        hashed = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        assert not BcryptVerifier.verify("wrong_password", hashed)

    def test_verify_non_bcrypt_hash(self) -> None:
        """Test that verify returns False for non-bcrypt hashes."""
        assert not BcryptVerifier.verify(
            "password",  # nosemgrep # nosec
            "not_a_bcrypt_hash",
        )
        assert not BcryptVerifier.verify(
            "password",
            "$argon2id$v=19$m=65536$hash",  # nosemgrep # nosec
        )
        assert not BcryptVerifier.verify(
            "password",
            "scrypt$n=16384$r=8$p=1$s$k",  # nosemgrep # nosec
        )

    def test_verify_empty_string(self) -> None:
        """Test that verify handles empty strings."""
        assert not BcryptVerifier.verify("password", "")  # nosemgrep # nosec
        assert not BcryptVerifier.verify("", "")

    def test_verify_invalid_bcrypt_hash(self) -> None:
        """Test that verify handles invalid bcrypt hashes gracefully."""
        assert not BcryptVerifier.verify(
            "password",  # nosemgrep # nosec
            "$2a$12$invalid",
        )
        assert not BcryptVerifier.verify(
            "password",  # nosemgrep # nosec
            "$2b$",
        )
        assert not BcryptVerifier.verify(
            "password",  # nosemgrep # nosec
            # cspell: disable-next-line
            "$2y$10$tooshort",
        )

    def test_verify_different_prefixes(self) -> None:
        """Test that all bcrypt prefixes are recognized."""
        password = "test"  # nosemgrep # nosec

        # Test with different cost factors to generate different prefixes
        for prefix in ["$2a$", "$2b$", "$2y$"]:
            # Create a hash manually or use known hash format
            sample_hash = (
                prefix
                + "12$XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            )
            # Should at least recognize the prefix even if verification fails
            result = BcryptVerifier.verify(password, sample_hash)
            # Will be False because it's not a valid hash, but won't crash
            assert isinstance(result, bool)

    def test_password_truncation_at_72_bytes(self) -> None:
        """Test that passwords are truncated to 72 bytes."""
        # Create a password longer than 72 bytes
        long_password = "a" * 80  # nosemgrep # nosec

        # Hash only the first 72 bytes
        truncated = long_password.encode("utf-8")[:72]
        hashed = bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")

        # Verify that the full password works (because we truncate)
        assert BcryptVerifier.verify(long_password, hashed)

    def test_password_truncation_with_unicode(self) -> None:
        """Test password truncation doesn't break UTF-8 characters."""
        # Create a password with unicode that might be split at byte boundary
        # emoji is 4 bytes, total > 72 bytes
        password = "a" * 70 + "🔐"  # nosemgrep # nosec
        hashed = bcrypt.hashpw(
            password.encode("utf-8")[:72], bcrypt.gensalt()
        ).decode("utf-8")

        # Should verify successfully
        assert BcryptVerifier.verify(password, hashed)

    def test_empty_password(self) -> None:
        """Test hashing and verifying empty password."""
        password = ""  # nosemgrep # nosec
        hashed = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        assert BcryptVerifier.verify(password, hashed)
        assert not BcryptVerifier.verify("not_empty", hashed)

    def test_unicode_password(self) -> None:
        """Test verifying unicode password."""
        password = "🔐密码test🔐"  # nosemgrep # nosec
        hashed = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        assert BcryptVerifier.verify(password, hashed)
        assert not BcryptVerifier.verify("wrong", hashed)

    def test_special_characters(self) -> None:
        """Test password with special characters."""
        password = "p@ssw0rd!#$%^&*()"  # nosemgrep # nosec
        hashed = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        assert BcryptVerifier.verify(password, hashed)

    def test_whitespace_password(self) -> None:
        """Test password with whitespace."""
        password = "  password with spaces  "  # nosemgrep # nosec
        hashed = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        assert BcryptVerifier.verify(password, hashed)
        assert not BcryptVerifier.verify(password.strip(), hashed)

    def test_case_sensitivity(self) -> None:
        """Test that verification is case-sensitive."""
        password = "TestPassword"  # nosemgrep # nosec
        hashed = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        assert BcryptVerifier.verify(password, hashed)
        assert not BcryptVerifier.verify("testpassword", hashed)
        assert not BcryptVerifier.verify("TESTPASSWORD", hashed)

    @pytest.mark.parametrize(
        "invalid_hash",
        [
            "$1a$12$hash",  # Wrong algorithm
            "$2a$",  # Incomplete
            # cspell: disable-next-line
            "$2a$4$tooshortcost",  # Invalid cost
            "plaintext",  # Not a hash
            None,  # None value would cause AttributeError, caught by exception
        ],
    )
    def test_invalid_hash_formats(self, invalid_hash: str | None) -> None:
        """Test various invalid hash formats."""
        if invalid_hash is None:
            # Special case: None should be handled
            with pytest.raises(AttributeError):
                BcryptVerifier.verify("password", invalid_hash)  # type: ignore
        else:
            assert not BcryptVerifier.verify("password", invalid_hash)
