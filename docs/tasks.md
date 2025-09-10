<!-- markdownlint-disable MD036 -->

Waldiez Runner provides a set of HTTP endpoints to manage, run, and interact with tasks.
All routes are under the **`/api/v1/tasks`** path and require a valid JWT token with a ***`tasks-api`*** audience.

---

## 📄 List All Tasks

***GET /api/v1/tasks***

Returns a paginated list of all tasks for the current client.

***Query Parameters (optional, for pagination)***

- `page` (default: 1)
- `size` (default: 50)

Response: `Page[TaskResponse]`

---

## List All Tasks (Admin Only)

***GET /api/v1/admin/tasks***

Returns a paginated list of all tasks from all clients. Requires a valid JWT token with an ***`admin-api`*** audience.

***Query Parameters (optional)***

- `page` (default: 1)
- `size` (default: 50)
- `search`: Search term to filter tasks by filename or status
- `order_by`: Field to sort by (`id`, `flow_id`, `filename`, `status`)
- `order_type`: Sort order (`asc` or `desc`, default: `desc`)

Response: `Page[TaskResponse]`

!!! warning
    This endpoint requires admin privileges and will return tasks from all clients in the system.

---

## 📥 Create a New Task

***POST /api/v1/tasks***

Uploads a `.waldiez` flow and creates a new task. Limited to 3 concurrent tasks per client.

***Form Data:***

- `file`: The `.waldiez` file (required)
- `input_timeout`: Timeout for input requests (default: 180 seconds)

***Response***: `TaskResponse`

***Error***: `429` if the task limit is exceeded.

### Permission Check

Before creating a task, the system performs a permission verification by sending a GET request to a configurable external endpoint. This check ensures the user has permission to run tasks.

**Request Details:**
- **URL**: Configured via `TASK_PERMISSION_VERIFY_URL` environment variable
- **Parameters**: `user_id` (extracted from JWT token)
- **Headers**: `X-Runner-Secret-Key` (configured via `TASK_PERMISSION_SECRET`)

**Expected Response:**
- **200 OK** with `{"can_run": true}` if permission is granted
- **429 Too Many Requests** with `{"can_run": false, "reason": "custom reason"}` if permission is denied

**Error Handling:**
- If permission is denied (429), the API returns `429` with the reason from the response
- If the permission check fails (network error, invalid response), the API returns `500`
- Permission check is skipped if external auth is disabled or not configured

This feature allows integration with external authorization systems to control task execution based on user permissions, quotas, or other business logic.

---

## 📄 Get Task by ID

***GET /api/v1/tasks/{task_id}***

Returns metadata about the specified task.

***Response***: `TaskResponse`

---

## 🎤 Send Input to Task

**POST /api/v1/tasks/{task_id}/input**

Send a response to an active input_request.

***Request Body***:

```json
{
  "request_id": "uuid-string",
  "data": "your input message"
}
```

***Response***: 204 No Content

***Error Conditions:***

- Invalid task ID or client
- Task is not waiting for input
- request_id does not match the active prompt

---

## ⬇️ Download Task Results

**GET /api/v1/tasks/{task_id}/download**

Downloads a .zip archive with task outputs.

**Response:** `FileResponse`

---

## 🚫 Cancel Task

**POST /api/v1/tasks/{task_id}/cancel**

Cancels a running or waiting task.

***Response:*** Updated `TaskResponse`

***Error:*** `400` if task is already finished or cannot be cancelled

---

## 🧹 Delete a task

***DELETE /api/v1/tasks/{task_id}***

Soft-deletes the task (schedules removal of files and DB records). Active tasks require `?force=true` to be deleted.

***Query Parameters:***

- `force`: set true to delete even active tasks

**Response:** `204` No Content

---

## 🧨 Delete Multiple Tasks

<!-- markdownlint-disable MD036 -->
***DELETE /api/v1/tasks***

Soft-deletes all tasks for the current client.
By default, only completed/cancelled tasks are deleted.
Use force=true to delete active ones.

***Query Parameters:***

- `ids`: Ids of tasks to delete (optional, repeated)
- `force`: true to also delete active tasks

***Response:*** `204` No Content

---

!!!Warning
    - Clients can only have up to a limited (defaulting to 3) concurrent active tasks (pending, running, waiting_for_input).
    - Input timeout can be configured per task.
    - Input messages must match the expected request_id.
    - Deleted tasks are soft-deleted and hidden from future listings.

---

## 📚 See Also

- Full API reference: [OpenAPI Docs](reference/openapi.md)
- Related topics:
  - [Authentication](clients.md)
  - [Live Input/Output](websocket.md)
  - [Admin Operations](clients.md#admin-api)
