# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Client schemas."""

from datetime import datetime

import bcrypt
from pydantic import BaseModel, Field

from waldiez_runner.models.client import (
    Client,
    generate_client_id,
    generate_client_secret,
)


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
