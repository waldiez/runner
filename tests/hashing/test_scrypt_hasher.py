# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=no-self-use,missing-param-doc,too-many-public-methods

"""Tests for scrypt hasher."""

import base64
import re

from waldiez_runner.hashing._scrypt_hasher import ScryptHasher


class TestScryptHasher:
    """Test scrypt hasher implementation."""

    def test_hash_creates_valid_hash(self) -> None:
        """Test that hash creates a valid scrypt hash."""
        hasher = ScryptHasher()
        password = "test_password_123"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hashed.startswith("scrypt$")
        # Check format: scrypt$n=N$r=R$p=P$SALT$KEY
        pattern = (
            r"^scrypt\$n=\d+\$r=\d+\$p=\d+\$[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+$"
        )
        assert re.match(pattern, hashed)

    def test_hash_format_contains_parameters(self) -> None:
        """Test that hash contains the correct parameters."""
        hasher = ScryptHasher(n=8192, r=4, p=2)
        password = "test"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert "n=8192" in hashed
        assert "r=4" in hashed
        assert "p=2" in hashed

    def test_verify_correct_password(self) -> None:
        """Test that verify works with correct password."""
        hasher = ScryptHasher()
        password = "test_password_123"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)

    def test_verify_incorrect_password(self) -> None:
        """Test that verify fails with incorrect password."""
        hasher = ScryptHasher()
        password = "test_password_123"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert not hasher.verify("wrong_password", hashed)

    def test_verify_non_scrypt_hash(self) -> None:
        """Test that verify returns False for non-scrypt hashes."""
        hasher = ScryptHasher()
        assert not hasher.verify("password", "not_a_scrypt_hash")
        # cspell: disable-next-line
        assert not hasher.verify("password", "$2b$12$somebcrypthash")
        assert not hasher.verify("password", "$argon2id$v=19$m=65536$hash")

    def test_verify_invalid_scrypt_format(self) -> None:
        """Test that verify handles invalid scrypt formats gracefully."""
        hasher = ScryptHasher()
        assert not hasher.verify("password", "scrypt$invalid")
        assert not hasher.verify("password", "scrypt$n=abc$r=8$p=1$salt$key")
        assert not hasher.verify("password", "scrypt$n=16384$r=8$p=1")

    def test_verify_with_invalid_base64(self) -> None:
        """Test that verify handles invalid base64 in salt/key."""
        hasher = ScryptHasher()
        assert not hasher.verify("password", "scrypt$n=16384$r=8$p=1$!!!$!!!")

    def test_needs_rehash_non_scrypt(self) -> None:
        """Test that needs_rehash returns True for non-scrypt hashes."""
        hasher = ScryptHasher()
        assert hasher.needs_rehash("not_a_scrypt_hash")
        # cspell: disable-next-line
        assert hasher.needs_rehash("$2b$12$somebcrypthash")
        assert hasher.needs_rehash("$argon2id$v=19$m=65536$hash")

    def test_needs_rehash_valid_hash(self) -> None:
        """Test needs_rehash returns False for valid hash with same params."""
        hasher = ScryptHasher()
        password = "test_password_123"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert not hasher.needs_rehash(hashed)

    def test_needs_rehash_different_n(self) -> None:
        """Test that needs_rehash detects different n parameter."""
        hasher1 = ScryptHasher(n=8192)
        password = "test"  # nosemgrep # nosec
        hashed = hasher1.hash(password)

        hasher2 = ScryptHasher(n=16384)
        assert hasher2.needs_rehash(hashed)

    def test_needs_rehash_different_r(self) -> None:
        """Test that needs_rehash detects different r parameter."""
        hasher1 = ScryptHasher(r=4)
        password = "test"  # nosemgrep # nosec
        hashed = hasher1.hash(password)

        hasher2 = ScryptHasher(r=8)
        assert hasher2.needs_rehash(hashed)

    def test_needs_rehash_different_p(self) -> None:
        """Test that needs_rehash detects different p parameter."""
        hasher1 = ScryptHasher(p=1)
        password = "test"  # nosemgrep # nosec
        hashed = hasher1.hash(password)

        hasher2 = ScryptHasher(p=2)
        assert hasher2.needs_rehash(hashed)

    def test_needs_rehash_different_dklen(self) -> None:
        """Test that needs_rehash detects different key length."""
        hasher1 = ScryptHasher(dklen=32)
        password = "test"  # nosemgrep # nosec
        hashed = hasher1.hash(password)

        hasher2 = ScryptHasher(dklen=64)
        assert hasher2.needs_rehash(hashed)

    def test_hash_uniqueness(self) -> None:
        """Test hashing the same password twice produces different hashes."""
        hasher = ScryptHasher()
        password = "test_password_123"  # nosemgrep # nosec
        hash1 = hasher.hash(password)
        hash2 = hasher.hash(password)

        assert hash1 != hash2
        assert hasher.verify(password, hash1)
        assert hasher.verify(password, hash2)

    def test_empty_password(self) -> None:
        """Test hashing and verifying empty password."""
        hasher = ScryptHasher()
        password = ""  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)
        assert not hasher.verify("not_empty", hashed)

    def test_unicode_password(self) -> None:
        """Test hashing and verifying unicode password."""
        hasher = ScryptHasher()
        password = "🔐密码test🔐"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)
        assert not hasher.verify("wrong", hashed)

    def test_long_password(self) -> None:
        """Test hashing and verifying very long password."""
        hasher = ScryptHasher()
        password = "a" * 1000  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)
        assert not hasher.verify("a" * 999, hashed)

    def test_special_characters(self) -> None:
        """Test password with special characters."""
        hasher = ScryptHasher()
        password = "p@ssw0rd!#$%^&*()"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)

    def test_custom_parameters(self) -> None:
        """Test hasher with custom parameters."""
        hasher = ScryptHasher(n=8192, r=4, p=2, dklen=32, salt_len=32)
        password = "test_password"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)
        assert "n=8192" in hashed
        assert "r=4" in hashed
        assert "p=2" in hashed

    def test_verify_cross_hasher_compatibility(self) -> None:
        """Test that hash created by one hasher can be verified by another."""
        hasher1 = ScryptHasher(n=8192, r=4, p=1)
        password = "test"  # nosemgrep # nosec
        hashed = hasher1.hash(password)

        # Different hasher instance with same parameters
        hasher2 = ScryptHasher(n=8192, r=4, p=1)
        assert hasher2.verify(password, hashed)

    def test_salt_length_in_hash(self) -> None:
        """Test that different salt lengths work correctly."""
        hasher1 = ScryptHasher(salt_len=16)
        hasher2 = ScryptHasher(salt_len=32)

        password = "test"  # nosemgrep # nosec
        hash1 = hasher1.hash(password)
        hash2 = hasher2.hash(password)

        # Both should verify correctly
        assert hasher1.verify(password, hash1)
        assert hasher2.verify(password, hash2)

        # Extract and check salt lengths
        salt1_b64 = hash1.split("$")[4]
        salt2_b64 = hash2.split("$")[4]

        salt1 = base64.b64decode(salt1_b64)
        salt2 = base64.b64decode(salt2_b64)

        assert len(salt1) == 16
        assert len(salt2) == 32

    def test_needs_rehash_invalid_format(self) -> None:
        """Test that needs_rehash handles invalid formats."""
        hasher = ScryptHasher()
        assert hasher.needs_rehash("scrypt$invalid")
        assert hasher.needs_rehash("scrypt$n=abc$r=8$p=1$salt$key")
        assert hasher.needs_rehash("")

    def test_timing_attack_resistance(self) -> None:
        """Test that verify uses constant-time comparison."""
        hasher = ScryptHasher()
        password = "test_password"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        # Both should return False, ideally in similar time
        result1 = hasher.verify("wrong1", hashed)
        result2 = hasher.verify("wrong2", hashed)

        assert not result1
        assert not result2

    def test_whitespace_password(self) -> None:
        """Test password with whitespace."""
        hasher = ScryptHasher()
        password = "  password with spaces  "  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)
        assert not hasher.verify(password.strip(), hashed)

    def test_case_sensitivity(self) -> None:
        """Test that verification is case-sensitive."""
        hasher = ScryptHasher()
        password = "TestPassword"  # nosemgrep # nosec
        hashed = hasher.hash(password)

        assert hasher.verify(password, hashed)
        assert not hasher.verify("testpassword", hashed)
        assert not hasher.verify("TESTPASSWORD", hashed)
