# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pylint: disable=too-many-try-statements,broad-exception-caught,
# pylint: disable=too-complex,no-self-use,redefined-variable-type,line-too-long
# flake8: noqa: E501,C901
"""Runtime hasher to use, try argon2, fallback to scrypt."""

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field

from .hasher import Hasher

password_hasher: Hasher

try:
    from argon2 import (
        PasswordHasher,  # type: ignore[unused-ignore, import-not-found, import-untyped]
    )

    @dataclass(frozen=True)
    class Argon2Hasher:
        """Argon2 hasher"""

        _ph: PasswordHasher = field(init=False)

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
            except BaseException:
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
            except BaseException:
                return True

    password_hasher = Argon2Hasher()

except ImportError:  # pragma: no cover
    # Fallback to scrypt
    _SCRYPT_RE = re.compile(
        r"^scrypt\$n=(\d+)\$r=(\d+)\$p=(\d+)\$([A-Za-z0-9+/=]+)\$([A-Za-z0-9+/=]+)$"
    )

    @dataclass(frozen=True)
    class ScryptHasher:
        """Scrypt password hasher."""

        n: int = 16384  # 2^14
        r: int = 8
        p: int = 1
        dklen: int = 64
        salt_len: int = 16

        def _encode(self, salt: bytes, key: bytes) -> str:
            """Encode a key."""
            # pylint: disable=inconsistent-quotes
            return (
                f"scrypt$n={self.n}$r={self.r}$p={self.p}$"
                f"{base64.b64encode(salt).decode('ascii')}$"
                f"{base64.b64encode(key).decode('ascii')}"
            )

        @staticmethod
        def _derive(
            plain: str, salt: bytes, n: int, r: int, p: int, dklen: int
        ) -> bytes:
            return hashlib.scrypt(
                plain.encode("utf-8"),
                salt=salt,
                n=n,
                r=r,
                p=p,
                dklen=dklen,
            )

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
            salt = secrets.token_bytes(self.salt_len)
            key = self._derive(plain, salt, self.n, self.r, self.p, self.dklen)
            return self._encode(salt, key)

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
            m = _SCRYPT_RE.match(stored)
            if not m:
                return False
            try:
                n, r, p = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                salt = base64.b64decode(m.group(4).encode("ascii"))
                stored_key = base64.b64decode(m.group(5).encode("ascii"))
                key = self._derive(plain, salt, n, r, p, len(stored_key))
                return hmac.compare_digest(key, stored_key)
            except Exception:
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
            m = _SCRYPT_RE.match(stored)
            if not m:
                return True
            try:
                n, r, p = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                return (n != self.n) or (r != self.r) or (p != self.p)
            except Exception:
                return True

    password_hasher = ScryptHasher()


__all__ = ["password_hasher"]
