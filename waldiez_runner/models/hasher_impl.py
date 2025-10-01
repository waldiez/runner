# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Runtime hasher to use, try argon2, fallback to scrypt."""

import base64
import hashlib
import os

from .hasher import Hasher

password_hasher: Hasher

# pylint: disable=too-many-try-statements,broad-exception-caught,
# pylint: disable=too-complex,no-self-use
try:  # noqa: C901
    from argon2 import PasswordHasher as Argon2PasswordHasher

    class _Argon2Hasher:
        """Argon2id password hasher."""

        def __init__(self) -> None:
            self._ph = Argon2PasswordHasher(
                time_cost=2,  # iterations
                memory_cost=65536,  # 64 MB
                parallelism=1,  # threads
                hash_len=32,  # output length
                salt_len=16,  # salt length
            )

        def hash(self, plain: str) -> str:
            """Hash password using Argon2id.

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
            """Verify password against Argon2id hash.

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
            try:
                self._ph.verify(stored, plain)
                return True
            except BaseException:
                return False

    password_hasher = _Argon2Hasher()

except ImportError:  # pragma: no cover
    # Fallback to scrypt
    class _ScryptHasher:
        """Scrypt password hasher."""

        def hash(self, plain: str) -> str:
            """Hash password using scrypt.

            Parameters
            ----------
            plain : str
                The plain secret to hash.

            Returns
            -------
            str
                The hashed secret.
            """
            salt = os.urandom(32)
            key = hashlib.scrypt(
                plain.encode("utf-8"),
                salt=salt,
                n=16384,  # CPU/memory cost (2^14)
                r=8,  # block size
                p=1,  # parallelization
                dklen=64,  # derived key length
            )
            # Store salt + hash together, encode as base64
            return base64.b64encode(salt + key).decode("utf-8")

        def verify(self, plain: str, stored: str) -> bool:
            """Verify password against scrypt hash.
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
            try:
                decoded = base64.b64decode(stored.encode("utf-8"))
                salt = decoded[:32]
                stored_key = decoded[32:]

                key = hashlib.scrypt(
                    plain.encode("utf-8"),
                    salt=salt,
                    n=16384,
                    r=8,
                    p=1,
                    dklen=64,
                )
                return key == stored_key
            except Exception:
                return False

    password_hasher = _ScryptHasher()


__all__ = ["password_hasher"]
