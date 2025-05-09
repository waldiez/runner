# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Client routes."""

from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi_pagination import Page
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Literal

from waldiez_runner.dependencies import (
    CLIENT_API_AUDIENCE,
    VALID_AUDIENCES,
    get_client_id,
    get_db,
)
from waldiez_runner.schemas.client import (
    ClientCreate,
    ClientCreateResponse,
    ClientResponse,
    ClientUpdate,
)
from waldiez_runner.services.client_service import ClientService

from ._common import Order, get_pagination_params

REQUIRED_AUDIENCES = [CLIENT_API_AUDIENCE]

CLientSort = Literal[
    "client_id",
    "audience",
    "description",
    "name",
]
"""The field to sort the clients."""


validate_clients_audience = get_client_id(*REQUIRED_AUDIENCES)

client_router = APIRouter()


@client_router.get("/clients/", include_in_schema=False)
@client_router.get(
    "/clients",
    response_model=Page[ClientResponse],
    summary="Get all clients",
    description="Get all clients.",
)
async def get_clients(
    _: Annotated[str, Depends(validate_clients_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
    search: Annotated[str | None, Query()] = None,
    order_by: Annotated[CLientSort | None, Query()] = None,
    order_type: Annotated[Order | None, Query()] = None,
) -> Page[ClientResponse]:
    """Get all clients.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    search : str | None
        A search term to filter the clients.
    order_by : CLientSort | None
        The field to sort the clients.
    order_type : Order | None
        The order type to sort the clients. Can be "asc" or "desc".

    Returns
    -------
    Page[ClientResponse]
        The clients.
    """
    params = get_pagination_params()
    return await ClientService.get_clients(
        session,
        params=params,
        search=search,
        order_by=order_by,
        descending=order_type == "desc",
    )


@client_router.post("/clients/", include_in_schema=False)
@client_router.post(
    "/clients",
    response_model=ClientCreateResponse,
    summary="Create a client",
    description="Create a new client.",
)
async def create_client(
    client: ClientCreate,
    _: Annotated[str, Depends(validate_clients_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ClientCreateResponse:
    """Create a client.

    Parameters
    ----------
    client : ClientCreate
        The client data.
    session : AsyncSession
        The database session.

    Returns
    -------
    ClientResponse
        The created client.

    Raises
    ------
    HTTPException
        If the client cannot be created.
    """
    try:
        return await ClientService.create_client(session, client)
    except BaseException as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(e)) from e


@client_router.get("/clients/{client_id}/", include_in_schema=False)
@client_router.get(
    "/clients/{client_id}",
    response_model=ClientResponse,
    summary="Get a client",
    description="Get a client by ID.",
)
async def get_client(
    client_id: str,
    _: Annotated[str, Depends(validate_clients_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ClientResponse:
    """Get a client.

    Parameters
    ----------
    client_id : str
        The client ID.
    session : AsyncSession
        The database session.

    Returns
    -------
    ClientResponse
        The client.

    Raises
    ------
    HTTPException
        If the client is not found.
    """
    client = await ClientService.get_client(session, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


@client_router.patch("/clients/{client_id}/", include_in_schema=False)
@client_router.patch(
    "/clients/{client_id}",
    response_model=ClientResponse,
    summary="Update a client",
    description="Update a client by ID.",
)
async def update_client(
    client_id: str,
    client_update: ClientUpdate,
    _: Annotated[str, Depends(validate_clients_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ClientResponse:
    """Update a client.

    Parameters
    ----------
    client_id : str
        The client ID.
    client_update : ClientUpdate
        The client data.
    session : AsyncSession
        The database session.

    Returns
    -------
    Client
        The updated client.

    Raises
    ------
    HTTPException
        If the client is not found.
    """
    client = await ClientService.update_client(
        session, client_id, client_update
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


@client_router.delete("/clients/{client_id}/", include_in_schema=False)
@client_router.delete(
    "/clients/{client_id}",
    response_model=None,
    summary="Delete a client",
    description="Delete a client by ID.",
)
async def delete_client(
    client_id: str,
    request_client_id: Annotated[str, Depends(validate_clients_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Delete a client.

    Parameters
    ----------
    client_id : str
        The client ID.
    request_client_id : str
        The client ID from the request.
    session : AsyncSession
        The database session.

    Returns
    -------
    Response
        The response.

    Raises
    ------
    HTTPException
        If the client is not found or the client is not allowed to delete.
    """
    if client_id == request_client_id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to delete this client.",
        )
    await ClientService.delete_client(session, client_id)
    return Response(status_code=204)


@client_router.delete("/clients/", include_in_schema=False)
@client_router.delete(
    "/clients",
    response_model=None,
    summary="Delete multiple clients",
    description="Delete multiple clients.",
)
async def delete_clients(
    client_id: Annotated[str, Depends(validate_clients_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
    ids: Annotated[List[str] | None, Query()] = None,
    audiences: Annotated[List[str] | None, Query()] = None,
    excluded: Annotated[List[str] | None, Query()] = None,
) -> Response:
    """Delete multiple clients.

    The current client will not be deleted.
    An optional audience filter can be provided to delete only clients
    with a specific audience.

    Parameters
    ----------
    client_id : str
        The current client ID.
    session : AsyncSession
        The database session.
    ids: List[str] | None
        An optional list of client IDs to include in the deletion.
    audiences : List[str] | None
        An optional list of audience to filter the clients.
    excluded : List[str] | None
        An optional list of client IDs to exclude from deletion.

    Returns
    -------
    Response
        The response.

    Raises
    ------
    HTTPException
        If the client is not found or the client is not allowed to delete.
    """
    if ids and client_id in ids:
        raise HTTPException(
            status_code=400,
            detail="You cannot delete the client you use to make this request.",
        )
    audience_filter = (
        [audience for audience in audiences if audience in VALID_AUDIENCES]
        if audiences
        else []
    )
    # for sure, not the one that was used for this request
    excluded = [client_id]
    if excluded:
        excluded = [client_id] + excluded
    excluded = list(set(excluded))
    await ClientService.delete_clients(
        session, audiences=audience_filter, excluded=[client_id], ids=ids
    )
    return Response(status_code=204)
