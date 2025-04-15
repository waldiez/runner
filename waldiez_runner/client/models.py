# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Models for the client and task responses."""
# we prefer to repeat these, instead of importing them
# from the core module. (e.g. make "clients" folder independent)

from datetime import datetime
from enum import Enum
from typing import Any, Generic, List, Optional, TypeVar, Union

try:
    from typing import Annotated, Literal
except ImportError:
    from typing_extensions import Annotated, Literal  # type: ignore

from pydantic import BaseModel, Field

Items = TypeVar("Items")


ClientAudience = Literal["tasks-api", "clients-api"]
"""The possible audiences for a client."""


class TokensResponse(BaseModel):
    """Tokens response."""

    access_token: Annotated[
        str, Field(..., description="Access token for authentication")
    ]
    refresh_token: Annotated[
        str,
        Field(..., description="Refresh token for obtaining new access tokens"),
    ]
    token_type: Annotated[
        str, Field(..., description="Type of the token (e.g., Bearer)")
    ]
    expires_at: Annotated[
        str, Field(..., description="Expiration timestamp of the token")
    ]
    refresh_expires_at: Annotated[
        str,
        Field(..., description="Expiration timestamp of the refresh token"),
    ]
    audience: Annotated[
        ClientAudience,
        Field(..., description="Audience for which the token is valid"),
    ]


class TokensRequest(BaseModel):
    """Token request."""

    client_id: Annotated[
        str, Field(..., description="Client ID for authentication")
    ]
    client_secret: Annotated[
        str, Field(..., description="Client secret for authentication")
    ]
    audience: Annotated[
        ClientAudience,
        Field(..., description="Audience for which the token is requested"),
    ]


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: Annotated[
        str, Field(..., description="Refresh token for obtaining new tokens")
    ]
    audience: Annotated[
        ClientAudience,
        Field(..., description="Audience for which the token is requested"),
    ]


class PaginatedResponse(BaseModel, Generic[Items]):
    """Paginated response structure used in Waldiez Runner."""

    items: List[Items] = Field(..., description="List of returned items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")


class PaginatedRequest(BaseModel):
    """Generic pagination request model."""

    page: Annotated[
        int, Field(1, ge=1, description="Page number (starting at 1)")
    ] = 1
    size: Annotated[int, Field(50, ge=1, le=100, description="Page size")] = 50


class TaskStatus(str, Enum):
    """Possible task statuses."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"


class TaskCreateRequest(BaseModel):
    """Request model for creating a new task."""

    # file_data: bytes, file_name: str, input_timeout: int = 180
    file_data: Annotated[
        bytes, Field(..., description="Task file data in bytes")
    ]
    file_name: Annotated[
        str,
        Field(..., description="Name of the task file (e.g., example.waldiez)"),
    ]
    input_timeout: Annotated[
        int,
        Field(
            180,
            ge=1,
            description="Timeout for input requests (in seconds, default: 180)",
        ),
    ] = 180


class TaskResponse(BaseModel):
    """Response returned when interacting with tasks."""

    id: Annotated[str, Field(..., description="Unique task identifier")]
    created_at: Annotated[
        datetime, Field(..., description="Task creation timestamp")
    ]
    updated_at: Annotated[
        datetime, Field(..., description="Last update timestamp")
    ]
    client_id: Annotated[
        str, Field(..., description="ID of the client who created the task")
    ]
    flow_id: Annotated[
        str, Field(..., description="Hash of the uploaded .waldiez file")
    ]
    filename: Annotated[
        str, Field(..., description="Original uploaded filename")
    ]
    status: Annotated[TaskStatus, Field(..., description="Current task status")]
    input_timeout: Annotated[
        int, Field(..., description="Timeout for input requests (in seconds)")
    ]
    input_request_id: Annotated[
        Optional[str],
        Field(None, description="Expected input request ID if task is waiting"),
    ]
    results: Annotated[
        Optional[Union[dict[str, Any], list[dict[str, Any]]]],
        Field(None, description="Results returned by the task, if completed"),
    ]


class UserInputRequest(BaseModel):
    """Request model for user input."""

    task_id: Annotated[
        str, Field(..., description="ID of the task requesting input")
    ]
    request_id: Annotated[
        str, Field(..., description="Unique ID for the input request")
    ]
    data: Annotated[
        str,
        Field(..., description="The user's response to the input request"),
    ]


# -- Client Models --
class ClientCreateRequest(BaseModel):
    """Request model for creating a new client."""

    client_id: Annotated[
        Optional[str],
        Field(
            None,
            description="Custom client ID (leave blank for auto-generated)",
        ),
    ] = None
    plain_secret: Annotated[
        Optional[str],
        Field(
            None,
            description="Custom client secret (leave blank for auto-generated)",
        ),
    ] = None
    audience: Annotated[
        ClientAudience,
        Field("tasks-api", description="API scope (tasks-api or clients-api)"),
    ] = "tasks-api"
    description: Annotated[
        Optional[str],
        Field(None, description="Optional description of the client"),
    ] = None


class ClientResponse(BaseModel):
    """Base response model for a client."""

    id: Annotated[
        str, Field(..., description="Unique client ID in the database")
    ]
    client_id: Annotated[
        str, Field(..., description="Public client identifier used for auth")
    ]
    audience: Annotated[
        ClientAudience, Field(..., description="Client's allowed API scope")
    ]
    description: Annotated[
        Optional[str], Field(None, description="Optional description")
    ] = None


class ClientCreateResponse(ClientResponse):
    """Response model when a new client is created."""

    client_secret: Annotated[
        str, Field(..., description="The generated client secret")
    ]


TaskItemsRequest = PaginatedRequest
"""Request model for listing tasks."""

TaskItemsResponse = PaginatedResponse[TaskResponse]
"""List of tasks with pagination."""

ClientItemsRequest = PaginatedRequest
"""Request model for listing clients."""

ClientItemsResponse = PaginatedResponse[ClientResponse]
"""List of clients with pagination."""
