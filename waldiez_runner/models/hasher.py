# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Password hashing protocol."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Hasher(Protocol):  # pragma: no cover
    """Protocol for password hashing implementations."""

    def hash(self, plain: str) -> str:  # pyright:ignore
        """Hash a plain text password.

        Parameters
        ----------
        plain : str
            The plain text password

        Returns
        -------
        str
            The hashed password
        """

    def verify(self, plain: str, stored: str) -> bool:  # pyright:ignore
        """Verify a plain text password against a stored hash.

        Parameters
        ----------
        plain : str
            The plain text password
        stored : str
            The stored hash

        Returns
        -------
        bool
            True if password matches, False otherwise
        """
