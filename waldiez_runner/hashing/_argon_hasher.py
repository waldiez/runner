# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=line-too-long,too-complex,invalid-name
# flake8: noqa: E501,C901
# pyright: reportConstantRedefinition=false,reportRedeclaration=false,reportAssignmentType=false
"""Argon2id password hasher implementation (preferred algorithm)."""

from dataclasses import dataclass, field

HAS_ARGON = False
try:
    from argon2 import (  # type: ignore[unused-ignore, import-not-found, import-untyped]
        PasswordHasher,
    )

    HAS_ARGON = True

    @dataclass(frozen=True)
    class Argon2Hasher:
        """Argon2 hasher"""

        _ph: PasswordHasher = field(init=False, repr=False)

        time_cost: int = 2
        memory_cost: int = 65536  # 64 MiB
        parallelism: int = 1
        hash_len: int = 32
        salt_len: int = 16

        def __post_init__(self) -> None:
            object.__setattr__(
                self,
                "_ph",
                PasswordHasher(
                    time_cost=self.time_cost,
                    memory_cost=self.memory_cost,
                    parallelism=self.parallelism,
                    hash_len=self.hash_len,
                    salt_len=self.salt_len,
                ),
            )

        def hash(self, plain: str) -> str:
            """Hash password using argon2.

            Parameters
            ----------
            plain : str
                The plain secret to hash.

            Returns
            -------
            str
                The hashed secret.
            """
            return self._ph.hash(plain)

        def verify(self, plain: str, stored: str) -> bool:
            """Verify password against argon2 hash.

            Parameters
            ----------
            plain : str
                The plain secret to check.
            stored : str
                The stored hashed secret.

            Returns
            -------
            bool
                True if the verification succeeds, false otherwise.
            """
            if not stored.startswith("$argon2"):
                return False
            try:
                self._ph.verify(stored, plain)
                return True
            except Exception:  # pylint: disable=broad-exception-caught
                return False

        def needs_rehash(self, stored: str) -> bool:
            """Check if the stored hashed secret needs rehash.

            Parameters
            ----------
            stored : str
                The stored hash

            Returns
            -------
            bool
                True if secret needs rehash, False otherwise
            """
            if not stored.startswith("$argon2"):
                return True
            try:
                return self._ph.check_needs_rehash(stored)
            except Exception:  # pylint: disable=broad-exception-caught
                return True

except ImportError:  # pragma: no cover
    # pylint: disable=invalid-name
    Argon2Hasher = None  # type: ignore


__all__ = ["Argon2Hasher", "HAS_ARGON"]
