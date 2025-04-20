# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Client model."""

import secrets
from datetime import datetime

import bcrypt
from pydantic import BaseModel, Field
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


class ClientCreate(BaseModel):
    """Client create model."""

    client_id: str = Field(default_factory=generate_client_id)
    plain_secret: str = Field(default_factory=generate_client_secret)
    audience: str = Field(default="tasks-api")
    name: str = Field(default="Default")
    description: str | None = None

    @classmethod
    def hash(cls, secret: str) -> str:
        """Hash a secret.

        Parameters
        ----------
        secret : str
            The secret to hash.

        Returns
        -------
        str
            The hashed secret.
        """
        return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()

    def hashed_secret(self) -> str:
        """Return the hashed version of `plain_secret`.

        Returns
        -------
        str
            The hashed secret.
        """
        return self.hash(self.plain_secret)


class ClientUpdate(BaseModel):
    """Client update model."""

    name: str | None = None
    description: str | None = None


class ClientResponseBase(BaseModel):
    """Client response base model."""

    id: str
    client_id: str
    audience: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class ClientResponse(ClientResponseBase):
    """Client response model."""

    @classmethod
    def from_client(cls, client: Client) -> "ClientResponse":
        """Create a response model from a client.

        Parameters
        ----------
        client : Client
            The client in database.

        Returns
        -------
        ClientResponse
            The client response.
        """
        return cls(
            id=str(client.id),
            client_id=client.client_id,
            audience=client.audience,
            name=client.name,
            description=client.description,
            created_at=client.created_at,
            updated_at=client.updated_at,
        )


class ClientCreateResponse(ClientResponseBase):
    """Client create response model."""

    client_secret: str

    @classmethod
    def from_client(
        cls, client: Client, plain_secret: str
    ) -> "ClientCreateResponse":
        """Create a response model from a client.

        Parameters
        ----------
        client : Client
            The client in database.
        plain_secret : str
            The plain secret.

        Returns
        -------
        ClientCreateResponse
            The client response.
        """
        return cls(
            id=str(client.id),
            client_id=client.client_id,
            client_secret=plain_secret,
            audience=client.audience,
            name=client.name,
            description=client.description,
            created_at=client.created_at,
            updated_at=client.updated_at,
        )
