# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-type-doc,missing-return-doc
# pylint: disable=missing-yield-doc
"""Tests for the client service."""

import pytest
from fastapi_pagination import Params
from sqlalchemy.ext.asyncio import AsyncSession

from tests.types import CreateClientCallable
from waldiez_runner.schemas.client import ClientCreate, ClientUpdate
from waldiez_runner.services import ClientService


@pytest.mark.anyio
async def test_get_clients(async_session: AsyncSession) -> None:
    """Test retrieving all clients."""
    await ClientService.delete_clients(async_session, excluded=[])
    client_create1 = ClientCreate()
    client_create2 = ClientCreate()
    await ClientService.create_client(async_session, client_create1)
    await ClientService.create_client(async_session, client_create2)
    params = Params(page=1, size=20)
    clients = await ClientService.get_clients(
        async_session,
        params=params,
        descending=True,
    )

    assert len(clients.items) >= 2
    client_ids = [client.client_id for client in clients.items]
    assert client_create1.client_id in client_ids
    assert client_create2.client_id in client_ids
    await ClientService.delete_clients(
        async_session, ids=[client.id for client in clients.items]
    )


@pytest.mark.anyio
async def test_get_clients_search(async_session: AsyncSession) -> None:
    """Test searching clients by name, description, and client_id."""
    client1 = ClientCreate(
        name="Alpha", description="First", client_id="alpha123"
    )
    client2 = ClientCreate(
        name="Beta", description="Second", client_id="beta456"
    )
    await ClientService.create_client(async_session, client1)
    await ClientService.create_client(async_session, client2)

    params = Params(page=1, size=10)

    # Search by name
    result = await ClientService.get_clients(
        async_session, params=params, search="Alpha"
    )
    assert len(result.items) == 1
    assert result.items[0].name == "Alpha"

    # Search by description
    result = await ClientService.get_clients(
        async_session, params=params, search="Second"
    )
    assert len(result.items) == 1
    assert result.items[0].description == "Second"

    # Search by client_id
    result = await ClientService.get_clients(
        async_session, params=params, search="beta"
    )
    assert len(result.items) == 1
    assert "beta" in result.items[0].client_id.lower()


@pytest.mark.anyio
async def test_get_clients_sort(async_session: AsyncSession) -> None:
    """Test sorting clients."""
    client1 = ClientCreate(
        name="Charlie", description="Third", client_id="charlie123"
    )
    client2 = ClientCreate(
        name="Delta", description="Fourth", client_id="delta456"
    )
    await ClientService.create_client(async_session, client1)
    await ClientService.create_client(async_session, client2)

    params = Params(page=1, size=10)

    # Sort by name ascending
    result = await ClientService.get_clients(
        async_session, params=params, order_by="name", descending=False
    )
    names = [client.name for client in result.items]
    assert names == sorted(names)

    # Sort by name descending
    result = await ClientService.get_clients(
        async_session, params=params, order_by="name", descending=True
    )
    names = [client.name for client in result.items]
    assert names == sorted(names, reverse=True)


@pytest.mark.anyio
async def test_get_clients_invalid_sort_field(
    async_session: AsyncSession,
) -> None:
    """Test providing invalid order_by field."""
    client1 = ClientCreate(
        name="Echo", description="Fifth", client_id="echo123"
    )
    await ClientService.create_client(async_session, client1)

    params = Params(page=1, size=10)

    with pytest.raises(ValueError):
        await ClientService.get_clients(
            async_session, params=params, order_by="invalid_field"
        )


@pytest.mark.anyio
async def test_create_client(async_session: AsyncSession) -> None:
    """Test creating a client."""
    client_create = ClientCreate()
    created_client = await ClientService.create_client(
        async_session, client_create
    )

    assert created_client.client_id == client_create.client_id
    assert created_client.audience == client_create.audience
    assert created_client.description == client_create.description
    client_in_db = await ClientService.get_client_in_db(
        async_session, created_client.id
    )
    assert client_in_db is not None
    assert client_in_db.client_id == created_client.client_id
    assert client_in_db.audience == created_client.audience
    assert client_in_db.description == created_client.description
    assert client_in_db.client_secret is not None
    assert client_in_db.client_secret != client_create.plain_secret


@pytest.mark.anyio
async def test_get_client(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test retrieving a client."""
    client, _ = await create_client(async_session)
    fetched_client = await ClientService.get_client(async_session, client.id)

    assert fetched_client is not None
    assert fetched_client.client_id == client.client_id


@pytest.mark.anyio
async def test_get_nonexistent_client(async_session: AsyncSession) -> None:
    """Test getting a non-existent client."""
    fetched_client = await ClientService.get_client(
        async_session, "nonexistent-id"
    )
    assert fetched_client is None


@pytest.mark.anyio
async def test_update_client_description(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test updating a client's description."""
    client, _ = await create_client(
        async_session, description="Initial description"
    )

    update_data = ClientUpdate(description="Updated description")
    updated_client = await ClientService.update_client(
        async_session, client.id, update_data
    )

    assert updated_client is not None
    assert updated_client.description == "Updated description"


@pytest.mark.anyio
async def test_update_client_name(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test updating a client's name."""
    client, _ = await create_client(async_session, name="Initial name")

    update_data = ClientUpdate(name="Updated name")
    updated_client = await ClientService.update_client(
        async_session, client.id, update_data
    )

    assert updated_client is not None
    assert updated_client.name == "Updated name"


@pytest.mark.anyio
async def test_update_client_no_change(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test updating a client with no changes."""
    client, _ = await create_client(
        async_session, description="Initial description"
    )

    assert client.description == "Initial description"

    update_data = ClientUpdate()
    updated_client = await ClientService.update_client(
        async_session, client.id, update_data
    )

    assert updated_client is not None
    assert updated_client.description == client.description


@pytest.mark.anyio
async def test_update_nonexistent_client(async_session: AsyncSession) -> None:
    """Test updating a non-existent client."""
    update_data = ClientUpdate(description="New description")
    updated_client = await ClientService.update_client(
        async_session, "nonexistent-id", update_data
    )

    assert updated_client is None


@pytest.mark.anyio
async def test_delete_client(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test deleting a client."""
    client, _ = await create_client(async_session)
    await ClientService.delete_client(async_session, client.id)

    deleted_client = await ClientService.get_client(async_session, client.id)

    assert deleted_client is None


@pytest.mark.anyio
async def test_delete_nonexistent_client(async_session: AsyncSession) -> None:
    """Test deleting a non-existent client (should not raise errors)."""
    await ClientService.delete_client(async_session, "nonexistent-id")
    # Should not raise an error


@pytest.mark.anyio
async def test_verify_client(async_session: AsyncSession) -> None:
    """Test verifying a client."""
    client_create = ClientCreate()
    created_client = await ClientService.create_client(
        async_session, client_create
    )

    verified_client = await ClientService.verify_client(
        async_session, created_client.client_id, client_create.plain_secret
    )

    assert verified_client is not None
    assert verified_client.client_id == created_client.client_id

    # Verify with incorrect secret
    verified_client = await ClientService.verify_client(
        async_session, created_client.client_id, "incorrect-secret"
    )
    assert verified_client is None

    # soft-deleted client
    client_create = ClientCreate()
    new_client = await ClientService.create_client(async_session, client_create)
    client_in_db = await ClientService.get_client_in_db(
        async_session, new_client.id
    )
    assert client_in_db is not None
    client_in_db.mark_deleted()
    await async_session.commit()
    await async_session.refresh(client_in_db)
    verified_client = await ClientService.verify_client(
        async_session, client_in_db.client_id, client_create.plain_secret
    )
    assert verified_client is None


@pytest.mark.anyio
async def test_verify_nonexistent_client(async_session: AsyncSession) -> None:
    """Test verifying a non-existent client."""
    verified_client = await ClientService.verify_client(
        async_session, "nonexistent-id", "secret"
    )
    assert verified_client is None


@pytest.mark.anyio
async def test_verify_deleted_client(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test verifying a deleted client."""
    _, response = await create_client(async_session)

    await ClientService.delete_client(async_session, response.id)

    verified_client = await ClientService.verify_client(
        async_session, response.client_id, response.client_secret
    )

    assert verified_client is None


@pytest.mark.anyio
async def test_get_client_in_db(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test getting a client from the database."""
    client, _ = await create_client(async_session)

    client_in_db = await ClientService.get_client_in_db(
        async_session, client.id
    )

    assert client_in_db is not None
    assert client_in_db.client_id == client.client_id


@pytest.mark.anyio
async def test_get_nonexistent_client_in_db(
    async_session: AsyncSession,
) -> None:
    """Test getting a non-existent client from the database."""
    client_in_db = await ClientService.get_client_in_db(
        async_session, "nonexistent-id"
    )
    assert client_in_db is None


@pytest.mark.anyio
async def test_get_client_by_client_id(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test getting a client by client_id."""
    client, _ = await create_client(async_session)

    client_in_db = await ClientService.get_client_in_db(
        async_session, client.id
    )

    assert client_in_db is not None
    assert client_in_db.client_id == client.client_id


@pytest.mark.anyio
async def test_get_nonexistent_client_by_client_id(
    async_session: AsyncSession,
) -> None:
    """Test getting a non-existent client by client_id."""
    client_in_db = await ClientService.get_client_in_db(
        async_session, "nonexistent-id"
    )
    assert client_in_db is None


@pytest.mark.anyio
async def test_get_client_by_id_and_client_id(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test getting a client by ID and client_id."""

    client, _ = await create_client(async_session)

    client_in_db = await ClientService.get_client_in_db(
        async_session, client.id, client.client_id
    )

    assert client_in_db is not None
    assert client_in_db.client_id == client.client_id


@pytest.mark.anyio
async def test_get_nonexistent_client_by_id_and_client_id(
    async_session: AsyncSession,
) -> None:
    """Test getting a non-existent client by ID and client_id."""
    client_in_db = await ClientService.get_client_in_db(
        async_session, "nonexistent-id", "nonexistent-client-id"
    )
    assert client_in_db is None


@pytest.mark.anyio
async def test_get_client_by_id_and_nonexistent_client_id(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test getting a client by ID and non-existent client_id."""
    client, _ = await create_client(async_session)

    client_in_db = await ClientService.get_client_in_db(
        async_session, client.id, "nonexistent-client-id"
    )

    assert client_in_db is None


@pytest.mark.anyio
async def test_get_client_by_nonexistent_id_and_client_id(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test getting a client by non-existent ID and client_id."""
    client, _ = await create_client(async_session)

    client_in_db = await ClientService.get_client_in_db(
        async_session, "nonexistent-id", client.client_id
    )

    assert client_in_db is None


@pytest.mark.anyio
async def test_get_client_by_id_without_idz(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test getting a client by ID without ID."""
    await create_client(async_session)
    client_in_db = await ClientService.get_client_in_db(async_session)

    assert client_in_db is None


@pytest.mark.anyio
async def test_delete_clients(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test deleting all clients."""
    params = Params(page=1, size=100)
    current_clients = await ClientService.get_clients(
        async_session, params=params
    )
    current_client_ids = [client.id for client in current_clients.items]
    assert len(current_clients.items) >= 0
    await create_client(async_session)
    await create_client(async_session)

    await ClientService.delete_clients(
        async_session, excluded=current_client_ids
    )
    clients = await ClientService.get_clients(async_session, params=params)
    assert len(clients.items) == len(current_client_ids)


@pytest.mark.anyio
async def test_delete_clients_with_excluded(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test deleting all clients with excluded IDs."""
    params = Params(page=1, size=100)
    current_clients = await ClientService.get_clients(
        async_session, params=params
    )
    current_client_ids = [client.id for client in current_clients.items]
    assert len(current_clients.items) >= 0
    client1, _ = await create_client(async_session)
    client2, _ = await create_client(async_session)
    client3, _ = await create_client(async_session)

    await ClientService.delete_clients(
        async_session, excluded=[client1.id, client2.id] + current_client_ids
    )
    clients = await ClientService.get_clients(async_session, params=params)
    assert len(clients.items) == len(current_client_ids) + 2
    assert client3.id not in [client.id for client in clients.items]


@pytest.mark.anyio
async def test_delete_clients_with_audiences(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test deleting all clients with audiences."""
    params = Params(page=1, size=100)
    current_clients = await ClientService.get_clients(
        async_session, params=params
    )
    new_clients = [
        await create_client(async_session, audience=f"audience{i}")
        for i in range(1, 4)
    ]

    await ClientService.delete_clients(
        async_session, audiences=["audience1", "audience2"]
    )
    clients = await ClientService.get_clients(async_session, params=params)
    assert len(clients.items) == len(current_clients.items) + 1
    client_with_audience3 = [
        client for client in clients.items if client.audience == "audience3"
    ]
    assert len(client_with_audience3) == 1
    assert client_with_audience3[0].client_id == new_clients[-1][0].client_id


@pytest.mark.anyio
async def test_delete_clients_with_ids(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test deleting all clients with IDs."""
    params = Params(page=1, size=100)
    current_clients = await ClientService.get_clients(
        async_session, params=params
    )
    client1, _ = await create_client(async_session)
    client2, _ = await create_client(async_session)
    client3, _ = await create_client(async_session)
    await ClientService.delete_clients(
        async_session, ids=[client1.id, client2.id]
    )
    clients = await ClientService.get_clients(async_session, params=params)
    assert len(clients.items) == len(current_clients.items) + 1
    assert client1.id not in [client.id for client in clients.items]
    assert client2.id not in [client.id for client in clients.items]
    assert client3.id in [client.id for client in clients.items]


@pytest.mark.anyio
async def test_delete_clients_with_audiences_and_ids(
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test deleting all clients with audiences and IDs."""
    audience_to_delete = "audience1"
    audience_other = "audience2"

    # 3 clients:
    # - client1: matching id and audience → should be deleted
    # - client2: matching id, wrong audience → should NOT be deleted
    # - client3: matching audience, not in id list → should NOT be deleted
    client1, _ = await create_client(async_session, audience=audience_to_delete)
    client2, _ = await create_client(async_session, audience=audience_other)
    client3, _ = await create_client(async_session, audience=audience_to_delete)

    # Attempt to delete only client1 (matches both id and audience)
    deleted_ids = await ClientService.delete_clients(
        async_session,
        ids=[client1.id, client2.id],  # client1 + client2
        audiences=[audience_to_delete],  # only audience1
    )

    # Fetch remaining clients
    params = Params(page=1, size=100)
    updated_clients = await ClientService.get_clients(
        async_session, params=params
    )
    updated_ids = [client.id for client in updated_clients.items]

    assert client1.id not in updated_ids
    assert client2.id in updated_ids
    assert client3.id in updated_ids

    # Double check return value
    assert deleted_ids == [client1.id]
    assert client1.id not in updated_ids
    assert client2.id in updated_ids
    assert client3.id in updated_ids

    # Double check return value
    assert deleted_ids == [client1.id]
