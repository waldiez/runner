# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Client service."""

from ._client_service import (
    create_client,
    delete_client,
    delete_clients,
    get_client,
    get_client_in_db,
    get_clients,
    update_client,
    verify_client,
)


# pylint: disable=too-few-public-methods
class ClientService:
    """Client service."""

    create_client = staticmethod(create_client)
    delete_client = staticmethod(delete_client)
    delete_clients = staticmethod(delete_clients)
    get_client = staticmethod(get_client)
    get_client_in_db = staticmethod(get_client_in_db)
    get_clients = staticmethod(get_clients)
    update_client = staticmethod(update_client)
    verify_client = staticmethod(verify_client)


__all__ = ["ClientService"]
