# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""App dependencies management."""

from .auth import (
    CLIENT_API_AUDIENCE,
    TASK_API_AUDIENCE,
    VALID_AUDIENCES,
    Audience,
    get_client_id_from_token,
    verify_external_auth_token,
)
from .context import RequestContext, get_request_context
from .database import DatabaseManager
from .getters import (
    get_client_id,
    get_db,
    get_external_user_info,
    get_jwks_cache,
    get_settings,
    get_storage,
    get_user_info,
)
from .jwks import JWKSCache
from .lifecycle import AppState, app_state, on_shutdown, on_startup
from .redis import REDIS_MANAGER, AsyncRedis, Redis, RedisManager, skip_redis
from .storage import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    Storage,
    StorageBackend,
    get_storage_backend,
)

__all__ = [
    "app_state",
    "on_startup",
    "on_shutdown",
    "get_settings",
    "get_db",
    "get_jwks_cache",
    "get_client_id",
    "get_client_id_from_token",
    "get_storage",
    "get_storage_backend",
    "skip_redis",
    "AppState",
    "DatabaseManager",
    "RedisManager",
    "Redis",
    "AsyncRedis",
    "Storage",
    "StorageBackend",
    "JWKSCache",
    "REDIS_MANAGER",
    "Audience",
    "VALID_AUDIENCES",
    "CLIENT_API_AUDIENCE",
    "TASK_API_AUDIENCE",
    "ALLOWED_EXTENSIONS",
    "ALLOWED_MIME_TYPES",
    "get_external_user_info",
    "get_user_info",
    "verify_external_auth_token",
    "RequestContext",
    "get_request_context",
]
