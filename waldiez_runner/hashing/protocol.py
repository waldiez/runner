# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=unnecessary-ellipsis

"""Password hashing protocol."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Hasher(Protocol):  # pragma: no cover
    """Protocol for password hashing implementations."""

    def hash(self, plain: str) -> str:
        """Hash a plain text password.

        Parameters
        ----------
        plain : str
            The plain text password
        """
        ...

    def verify(self, plain: str, stored: str) -> bool:
        """Verify a plain text password against a stored hash.

        Parameters
        ----------
        plain : str
            The plain text password
        stored : str
            The stored hash
        """
        ...

    def needs_rehash(self, stored: str) -> bool:
        """Check if the stored hashed secret needs rehash.

        Parameters
        ----------
        stored : str
            The stored hash
        """
        ...


__all__ = ["Hasher"]
