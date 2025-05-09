# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Client model."""

import secrets

import bcrypt
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .common import Base


def generate_client_id() -> str:
    """Generate a client ID.

    Returns
    -------
    str
        The generated client ID.
    """
    return secrets.token_hex(32)


def generate_client_secret() -> str:
    """Generate a client secret.

    Returns
    -------
    str
        The generated client secret.
    """
    return secrets.token_hex(64)


class Client(Base):
    """Client in database model."""

    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
        unique=True,
        default=generate_client_id,
    )
    client_secret: Mapped[str] = mapped_column(String, nullable=False)
    audience: Mapped[str] = mapped_column(
        String, nullable=False, default="tasks-api"
    )
    name: Mapped[str] = mapped_column(String, nullable=False, default="Default")
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    @classmethod
    def verify(cls, secret: str, hashed_secret: str) -> bool:
        """Verify a secret.

        Parameters
        ----------
        secret : str
            The secret to verify.
        hashed_secret : str
            The hashed secret.

        Returns
        -------
        bool
            True if the secret is verified.
        """
        # pylint: disable=broad-exception-caught
        try:
            return bcrypt.checkpw(secret.encode(), hashed_secret.encode())
        except BaseException:  # pragma: no cover
            return False
