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

## 📥 Create a New Task

***POST /api/v1/tasks***

Uploads a `.waldiez` flow and creates a new task. Limited to 3 concurrent tasks per client.

***Form Data:***

- `file`: The `.waldiez` file (required)
- `input_timeout`: Timeout for input requests (default: 180 seconds)

***Response***: `TaskResponse`

***Error***: `429` if the task limit is exceeded.

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

## 🧨 Delete All Tasks

<!-- markdownlint-disable MD036 -->
***DELETE /api/v1/tasks***

Soft-deletes all tasks for the current client.
By default, only completed/cancelled tasks are deleted.
Use force=true to delete active ones.

***Query Parameters:***

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
