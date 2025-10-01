# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Client model."""

import secrets

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ..hashing import password_hasher
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
    def verify(cls, secret: str, hashed_secret: str) -> tuple[bool, str | None]:
        """Verify a secret.

        Parameters
        ----------
        secret : str
            The secret to verify.
        hashed_secret : str
            The hashed secret.

        Returns
        -------
        tuple[bool,str | None]
            True if verified and an optional new hash if rehash is needed.
        """
        # pylint: disable=broad-exception-caught,too-many-try-statements
        # noinspection PyBroadException
        try:
            valid = password_hasher.verify(plain=secret, stored=hashed_secret)
            if valid and password_hasher.needs_rehash(hashed_secret):
                new_hash = password_hasher.hash(secret)
                return valid, new_hash
            return valid, None
        except Exception:  # pragma: no cover
            return False, None
