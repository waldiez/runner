# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=no-self-use

"""Tests for Argon2 hasher."""

import pytest

from waldiez_runner.hashing._argon_hasher import HAS_ARGON, Argon2Hasher


@pytest.mark.skipif(not HAS_ARGON, reason="argon2-cffi not installed")
class TestArgon2Hasher:
    """Test Argon2 hasher implementation."""

    def test_hash_creates_valid_hash(self) -> None:
        """Test that hash creates a valid argon2 hash."""
        hasher = Argon2Hasher()
        password = "test_password_123"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hashed.startswith("$argon2")
        assert len(hashed) > 50

    def test_verify_correct_password(self) -> None:
        """Test that verify works with correct password."""
        hasher = Argon2Hasher()
        password = "test_password_123"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)

    def test_verify_incorrect_password(self) -> None:
        """Test that verify fails with incorrect password."""
        hasher = Argon2Hasher()
        password = "test_password_123"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert not hasher.verify("wrong_password", hashed)

    def test_verify_non_argon2_hash(self) -> None:
        """Test that verify returns False for non-argon2 hashes."""
        hasher = Argon2Hasher()
        assert not hasher.verify("password", "not_an_argon2_hash")
        # cspell: disable-next-line
        assert not hasher.verify("password", "$2b$12$somebcrypthash")
        assert not hasher.verify("password", "scrypt$n=16384$r=8$p=1$salt$key")

    def test_verify_invalid_argon2_hash(self) -> None:
        """Test that verify handles invalid argon2 hashes gracefully."""
        hasher = Argon2Hasher()
        assert not hasher.verify("password", "$argon2id$invalid")

    def test_needs_rehash_non_argon2(self) -> None:
        """Test that needs_rehash returns True for non-argon2 hashes."""
        hasher = Argon2Hasher()
        assert hasher.needs_rehash("not_an_argon2_hash")
        # cspell: disable-next-line
        assert hasher.needs_rehash("$2b$12$somebcrypthash")
        assert hasher.needs_rehash("scrypt$n=16384$r=8$p=1$salt$key")

    def test_needs_rehash_valid_hash(self) -> None:
        """Test that needs_rehash returns False for valid recent hash."""
        hasher = Argon2Hasher()
        password = "test_password_123"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert not hasher.needs_rehash(hashed)

    def test_needs_rehash_with_different_parameters(self) -> None:
        """Test that needs_rehash detects parameter changes."""
        # Create hash with default parameters
        hasher1 = Argon2Hasher()
        password = "test_password_123"  # nosemgrep # nosec
        hashed = hasher1.hash(password)

        # Check with different parameters
        hasher2 = Argon2Hasher(time_cost=3, memory_cost=131072)
        assert hasher2.needs_rehash(hashed)

    def test_hash_uniqueness(self) -> None:
        """Test hashing the same password twice produces different hashes."""
        hasher = Argon2Hasher()
        password = "test_password_123"  # nosemgrep # nosec
        hash1 = hasher.hash(password)
        hash2 = hasher.hash(password)

        assert hash1 != hash2
        assert hasher.verify(password, hash1)
        assert hasher.verify(password, hash2)

    def test_empty_password(self) -> None:
        """Test hashing and verifying empty password."""
        hasher = Argon2Hasher()
        password = ""  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)
        assert not hasher.verify("not_empty", hashed)

    def test_unicode_password(self) -> None:
        """Test hashing and verifying unicode password."""
        hasher = Argon2Hasher()
        password = "🔐密码test🔐"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)
        assert not hasher.verify("wrong", hashed)

    def test_long_password(self) -> None:
        """Test hashing and verifying very long password."""
        hasher = Argon2Hasher()
        password = "a" * 1000  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)
        assert not hasher.verify("a" * 999, hashed)

    def test_custom_parameters(self) -> None:
        """Test hasher with custom parameters."""
        hasher = Argon2Hasher(
            time_cost=3,
            memory_cost=131072,
            parallelism=2,
            hash_len=64,
            salt_len=32,
        )
        password = "test_password"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)

    def test_needs_rehash_invalid_hash(self) -> None:
        """Test that needs_rehash handles invalid hashes gracefully."""
        hasher = Argon2Hasher()
        assert hasher.needs_rehash("$argon2id$corrupted")
        assert hasher.needs_rehash("$argon2id$")
        assert hasher.needs_rehash("")
