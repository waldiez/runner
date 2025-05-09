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

from pydantic import BaseModel, ConfigDict, Field

Items = TypeVar("Items")


ClientAudience = Literal["tasks-api", "clients-api"]
"""The possible audiences for a client."""


class ModelBase(BaseModel):
    """Base model to inherit."""

    model_config = ConfigDict(
        extra="ignore",
    )


class StatusResponse(ModelBase):
    """Server status type."""

    healthy: Annotated[
        bool, Field(..., description="whether the app is up and running")
    ]
    active_tasks: Annotated[
        int, Field(..., description="Number of active tasks")
    ]
    pending_tasks: Annotated[
        int, Field(..., description="Number of pending tasks")
    ]
    max_capacity: Annotated[
        int,
        Field(..., description="The maximum number of parallel active tasks"),
    ]
    cpu_count: Annotated[
        Optional[int], Field(..., description="Number of cpus")
    ]
    cpu_percent: Annotated[
        float, Field(..., description="CPU usage percentage")
    ]
    total_memory: Annotated[
        int, Field(..., description="The total memory on the host.")
    ]
    used_memory: Annotated[
        int, Field(..., description="The used memory on the host.")
    ]
    memory_percent: Annotated[
        int,
        Field(..., description="The used memory in percentage on the host."),
    ]


class TokensResponse(ModelBase):
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


class TokensRequest(ModelBase):
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


class RefreshTokenRequest(ModelBase):
    """Refresh token request."""

    refresh_token: Annotated[
        str, Field(..., description="Refresh token for obtaining new tokens")
    ]
    audience: Annotated[
        ClientAudience,
        Field(..., description="Audience for which the token is requested"),
    ]


class PaginatedResponse(ModelBase, Generic[Items]):
    """Paginated response structure used in Waldiez Runner."""

    items: List[Items] = Field(..., description="List of returned items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")


class PaginatedRequest(ModelBase):
    """Generic pagination request model."""

    page: Annotated[
        int, Field(1, ge=1, description="Page number (starting at 1)")
    ] = 1
    size: Annotated[int, Field(50, ge=1, le=100, description="Page size")] = 50


class OrderSearchRequest(ModelBase):
    """Generic order and search request model."""

    order_by: Annotated[
        Optional[str],
        Field(
            None,
            description="Field to order by (e.g., 'created_at', 'updated_at')",
        ),
    ] = None
    order_type: Annotated[
        Optional[Literal["asc", "desc"]],
        Field(None, description="Order direction: 'asc' or 'desc'"),
    ] = None
    search: Annotated[
        Optional[str],
        Field(None, description="Search term for filtering results"),
    ] = None


class TaskStatus(str, Enum):
    """Possible task statuses."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"


class TaskScheduleBase(ModelBase):
    """Common schedule-related fields (mirrors TaskBase on server)."""

    schedule_type: Annotated[
        Optional[Literal["once", "cron"]],
        Field(None, description="Type of schedule: 'once' or 'cron'"),
    ] = None

    scheduled_time: Annotated[
        Optional[datetime],
        Field(
            None, description="Datetime to run task if scheduled (for 'once')"
        ),
    ] = None

    cron_expression: Annotated[
        Optional[str],
        Field(None, description="Cron expression if scheduled (for 'cron')"),
    ] = None

    expires_at: Annotated[
        Optional[datetime],
        Field(
            None, description="Optional expiration datetime for scheduled task"
        ),
    ] = None


class TaskCreateRequest(TaskScheduleBase):
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


class TaskUpdateRequest(TaskScheduleBase):
    """Request model for updating a task."""

    input_timeout: Annotated[
        Optional[int],
        Field(
            None,
            ge=1,
            description="Optional timeout for input requests (in seconds)",
        ),
    ] = None


class TaskResponse(TaskScheduleBase):
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
    triggered_at: Annotated[
        Optional[datetime],
        Field(
            None,
            description="Time when the task was triggered (if applicable)",
        ),
    ] = None


class UserInputRequest(ModelBase):
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
class ClientCreateRequest(ModelBase):
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
    name: Annotated[str, Field("Default", description="Name of the client")] = (
        Field("Default", min_length=1)
    )
    description: Annotated[
        Optional[str],
        Field(None, description="Optional description of the client"),
    ] = None


class ClientResponse(ModelBase):
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
    name: Annotated[
        str, Field(..., description="Name of the client (default: Default)")
    ]
    created_at: Annotated[
        datetime, Field(..., description="Client creation timestamp")
    ]
    updated_at: Annotated[
        datetime, Field(..., description="Last update timestamp")
    ]
    description: Annotated[
        Optional[str], Field(None, description="Optional description")
    ] = None


class ClientCreateResponse(ClientResponse):
    """Response model when a new client is created."""

    client_secret: Annotated[
        str, Field(..., description="The generated client secret")
    ]


class TaskItemsRequest(PaginatedRequest, OrderSearchRequest):
    """Request model for listing tasks."""


TaskItemsResponse = PaginatedResponse[TaskResponse]
"""List of tasks with pagination."""


class ClientItemsRequest(PaginatedRequest, OrderSearchRequest):
    """Request model for listing clients."""


ClientItemsResponse = PaginatedResponse[ClientResponse]
"""List of clients with pagination."""
