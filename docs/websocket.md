# WebSocket API

Waldiez Runner supports live task interaction via WebSocket — enabling real-time logs, prompts, and input responses.

---

## 🛣️ Endpoint

`/ws/{task_id}`

- Requires a valid JWT token with the `tasks-api` audience
- Only works while the task is **running** or **waiting for input**

---

## 🔐 Authentication Options

You can authenticate your WebSocket connection in any of the following ways:

| Method        | Example                                   | Recommended for     |
|---------------|-------------------------------------------|----------------------|
| **Header**    | `Authorization: Bearer <token>`           | Python clients       |
| **Subprotocol** | `task-api,<token>`                     | JavaScript clients   |
| **Cookie**    | `access_token=<token>`                    | Browser UIs          |
| **Query Param** | `/ws/{task_id}?access_token=...`       | Fallback only        |

> 🔐 For info on getting tokens: see [Clients & Authentication](clients.md)

---

## 🔁 Message Format

All messages are JSON objects with the following schema:

```json
{
  "type": "print | input_request | input_response | termination",
  "task_id": "abc123",
  "timestamp": 1711210101210,
  "data": "Message string or structured content",
  "request_id": "uuid (optional)",
  "password": "string (optional, only in input_request)"
}
```

---

## 📤 Receiving Messages

You may receive:

- `type: "print"` → A log or output line from the task
- `type: "input_request"` → A prompt requesting user input
- `type: "termination"` → Signals end of task or current turn

---

## 🎤 Sending Input

To respond to a prompt:

```json
{
  "type": "input_response",
  "task_id": "abc123",
  "request_id": "same-as-request",
  "timestamp": 1711210111111,
  "data": "Your input"
}
```

> 🧠 `request_id` must match the one from the latest `input_request`!

---

## ⚙️ Use Cases

- Stream task logs to a UI
- Handle human-in-the-loop flows
- Use WebSocket for fast feedback vs polling
- Match input/output easily using `request_id`

---

## 🧪 Example UI

Try it at [http://localhost](http://localhost) using the `tasks-api` credentials from `clients.json`.

See the source in `examples/plain/static/js/lib/ws.js`.

---

## 📚 See Also

- [Tasks](tasks.md)
- [Clients & Authentication](clients.md)
- [Getting Started](getting-started.md)
