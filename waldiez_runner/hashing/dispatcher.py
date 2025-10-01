# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pylint: disable=too-many-try-statements,broad-exception-caught,invalid-name
# pylint: disable=too-complex,no-self-use,redefined-variable-type,line-too-long
# flake8: noqa: E501,C901
"""Password hasher dispatcher supporting multiple hash formats."""

from ._argon_hasher import HAS_ARGON, Argon2Hasher
from ._bcrypt_verifier import BcryptVerifier
from ._scrypt_hasher import ScryptHasher
from .protocol import Hasher


class PasswordHasherDispatcher(Hasher):
    """Dispatcher that uses best available hasher but verifies all formats."""

    def __init__(self) -> None:
        """Initialize the hasher."""
        self._argon2 = Argon2Hasher() if HAS_ARGON else None
        self._scrypt = ScryptHasher()

    def hash(self, plain: str) -> str:
        """Hash with best available algorithm.

        Parameters
        ----------
        plain : str
            The plain secret to hash.

        Returns
        -------
        str
            The hashed secret.
        """
        if self._argon2:
            return self._argon2.hash(plain)
        return self._scrypt.hash(plain)  # pragma: no cover

    def verify(self, plain: str, stored: str) -> bool:
        """Verify against any known format.

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
        if stored.startswith("$argon2"):
            if self._argon2:
                return self._argon2.verify(plain, stored)
            return False  # pragma: no cover
        if stored.startswith("scrypt$"):  # pragma: no cover
            return self._scrypt.verify(plain, stored)
        if stored.startswith(("$2a$", "$2b$", "$2y$")):
            return BcryptVerifier.verify(plain, stored)
        # Unknown format
        return False  # pragma: no cover

    def needs_rehash(self, stored: str) -> bool:
        """Check if hash needs upgrade.

        Parameters
        ----------
        stored : str
            The stored hash

        Returns
        -------
        bool
            True if secret needs rehash, False otherwise
        """
        if stored.startswith("$argon2"):
            # If argon2 unavailable, encourage rehash to scrypt
            if not self._argon2:  # pragma: no cover
                return True
            return self._argon2.needs_rehash(stored)
        if stored.startswith("scrypt$"):  # pragma: no cover
            # If argon2 available, prefer upgrading to argon2
            return True if self._argon2 else self._scrypt.needs_rehash(stored)
        # Bcrypt hashes (always upgrade)
        if stored.startswith(("$2a$", "$2b$", "$2y$")):  # pragma: no cover
            return True
        # Unknown format
        return True  # pragma: no cover


__all__ = ["PasswordHasherDispatcher"]
