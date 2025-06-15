# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=line-too-long
"""Clients management service."""

import logging
from typing import Any, List, Sequence

from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import asc, desc, or_
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import delete

from waldiez_runner.models.client import Client
from waldiez_runner.schemas.client import (
    ClientCreate,
    ClientCreateResponse,
    ClientResponse,
    ClientUpdate,
)

LOG = logging.getLogger(__name__)


async def create_client(
    session: AsyncSession,
    client_create: ClientCreate,
) -> ClientCreateResponse:
    """Create a new client.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    client_create : ClientCreate
        The client data.

    Returns
    -------
    Client
        The created client.
    """
    hashed_secret = client_create.hashed_secret()
    audience = client_create.audience
    client = Client(
        client_id=client_create.client_id,
        client_secret=hashed_secret,
        audience=audience,
        description=client_create.description,
        name=client_create.name,
    )
    session.add(client)
    await session.commit()
    await session.refresh(client)
    return ClientCreateResponse.from_client(client, client_create.plain_secret)


async def verify_client(
    session: AsyncSession, client_id: str, client_secret: str
) -> ClientResponse | None:
    """Verify a client.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    client_id : str
        The client ID.
    client_secret : str
        The client secret.

    Returns
    -------
    bool
        Whether the client is valid.
    """
    client = await get_client_in_db(session, None, client_id)
    if not client or client.deleted_at is not None:
        LOG.warning("Client not found or deleted: %s", client_id)
        return None
    if not client.verify(client_secret, client.client_secret):
        LOG.warning("Invalid client secret for client: %s", client_id)
        return None
    return ClientResponse.from_client(client)


async def get_client(
    session: AsyncSession, client_id: str
) -> ClientResponse | None:
    """Get a client by ID.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    client_id : str
        The client ID.

    Returns
    -------
    Client
        The client.
    """
    result = await session.execute(
        # select(Client).where(Client.client_id == client_id)
        select(Client).where(Client.id == client_id)
    )
    client = result.scalars().first()
    if not client:
        return None
    return ClientResponse.from_client(client)


async def get_clients(
    session: AsyncSession,
    params: Params,
    search: str | None = None,
    order_by: str | None = None,
    descending: bool = False,
) -> Page[ClientResponse]:
    """Get all clients.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    params : Params
        The pagination parameters.
    search : str | None
        An optional search string to filter by name, client_id or description.
    order_by : str | None
        An optional field to order the clients by.
    descending : bool
        Whether to order the clients in descending order.

    Returns
    -------
    List[Client]
        The clients

    Raises
    ------
    ValueError
        If an invalid field is provided for ordering.
    """

    def _client_transformer(
        items: Sequence[Client],
    ) -> Sequence[ClientResponse]:
        """Transform clients to responses.

        Parameters
        ----------
        items : Sequence[Client]
            The clients.

        Returns
        -------
        List[ClientResponse]
            The client responses
        """
        return [ClientResponse.from_client(client) for client in items]

    query = select(Client)

    if search:
        # a simple ilike
        query = query.where(
            or_(
                Client.name.ilike(f"%{search}%"),
                Client.description.ilike(f"%{search}%"),
                Client.client_id.ilike(f"%{search}%"),
            )
        )

    if order_by:
        if order_by in Client.__table__.columns:
            field = getattr(Client, order_by)
            query = query.order_by(desc(field) if descending else asc(field))
        else:  # pragma: no cover
            # already validated in the router
            raise ValueError(f"Invalid order_by field: {order_by}")
    else:
        query = query.order_by(
            desc(Client.created_at) if descending else asc(Client.created_at)
        )

    page = await apaginate(
        session,
        query,
        params=params,
        transformer=_client_transformer,
    )
    return page


async def update_client(
    session: AsyncSession, client_id: str, client_update: ClientUpdate
) -> ClientResponse | None:
    """Update a client.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    client_id : str
        The client ID.
    client_update : ClientUpdate
        The client data.

    Returns
    -------
    ClientResponse
        The updated client.
    """
    client = await get_client_in_db(session, client_id)
    if client is None:
        return None
    have_changes = False
    if (
        client_update.description is not None
        and client.description != client_update.description
    ):
        have_changes = True
        client.description = client_update.description
    if client_update.name is not None and client.name != client_update.name:
        have_changes = True
        client.name = client_update.name
    if have_changes:
        await session.commit()
        await session.refresh(client)
    return ClientResponse.from_client(client)


async def delete_client(session: AsyncSession, client_id: str) -> None:
    """Delete a client.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    client_id : str
        The client ID.
    """
    client = await get_client_in_db(session, client_id)
    if client is None:
        return
    await session.delete(client)
    await session.commit()


async def delete_clients(
    session: AsyncSession,
    ids: List[str] | None = None,
    audiences: List[str] | None = None,
    excluded: List[str] | None = None,
) -> List[str]:
    """Delete multiple clients.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    excluded : List[str] | None
        An optional list of client IDs to exclude.
    ids : List[str] | None
        An optional list of client IDs to filter.
    audiences : List[str]
        Optional list of audiences to filter.

    Returns
    -------
    List[str]
        The list of deleted client IDs.
    """
    filters: list[Any] = []
    if ids:
        filters.append(Client.id.in_(ids))
    if audiences:
        filters.append(Client.audience.in_(audiences))
    if excluded and len(excluded) > 0:
        filters.append(Client.id.notin_(excluded))
    if filters:
        query = delete(Client).where(*filters).returning(Client.id)
    else:  # pragma: no cover
        # always the client that is used for the request is excluded
        query = delete(Client).returning(Client.id)
    result = await session.execute(query)
    deleted_ids = list(result.scalars().all())
    await session.commit()
    return deleted_ids


async def get_client_in_db(
    session: AsyncSession,
    client_id: str | None = None,
    client_client_id: str | None = None,
) -> Client | None:
    """Get a client by its ID or its client ID.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    client_id : str
        The client's ID.
    client_client_id : str
        The client's client ID.

    Returns
    -------
    Client | None
        The client or None if not found.
    """
    if client_id and client_client_id:
        result = await session.execute(
            select(Client)
            .where(Client.id == client_id)
            .where(Client.client_id == client_client_id)
        )
        return result.scalars().first()
    if client_id:
        result = await session.execute(
            select(Client).where(Client.id == client_id)
        )
        return result.scalars().first()
    if client_client_id:
        result = await session.execute(
            select(Client).where(Client.client_id == client_client_id)
        )
        return result.scalars().first()
    return None
