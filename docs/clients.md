# Clients and Authentication

Waldiez Runner uses a **client-based authentication system** powered by JWT tokens.  
All interactions with the API or WebSocket require a valid token linked to a specific **audience**.

---

## 🎭 Audiences

There are two types of clients, each associated with a specific **audience**:

| Audience       | Description                                | Scope              |
|----------------|--------------------------------------------|---------------------|
| `clients-api`  | Manages other clients                      | `/api/v1/clients/*` |
| `tasks-api`    | Submits and interacts with tasks           | `/api/v1/tasks/*`, `/ws/{task_id}` |

---

## 📂 `clients.json`

Upon first startup (or running `initial_data.py`), a file named `clients.json` is generated in the project root.  
It contains initial client credentials for both audiences.

```json
[
  {
    "id": "...",
    "client_id": "...",
    "client_secret": "...",
    "audience": "clients-api",
    "description": "Clients management API"
  },
  {
    "id": "...",
    "client_id": "...",
    "client_secret": "...",
    "audience": "tasks-api",
    "description": "Tasks management API"
  }
]
```

!!!Note
    You’ll need the tasks-api credentials to:

    - Use the example UI at http://localhost
    - Submit or manage tasks via Swagger or scripts

---

## 🔐 Token Endpoints

You can request or refresh a token using the `/auth` routes.

### 🔸 `POST /auth/token`

Request an access + refresh token.

Form data (`application/x-www-form-urlencoded`):

    client_id=...
    client_secret=...

Example response:

```json
{
    "access_token": "...",
    "refresh_token": "...",
    "token_type": "Bearer",
    "expires_at": "...",
    "refresh_expires_at": "...",
    "audience": "tasks-api"
}
```

---

### 🔄 `POST /auth/refresh`

Use your `refresh_token` to renew your tokens.

JSON body:

```json
{
    "refresh_token": "...",
    "audience": "tasks-api" // optional
}
```

---

## 📡 Authenticating Requests

Pass the token in your `Authorization` header:

    Authorization: Bearer <access_token>

This is required for:

- All `/api/v1/*` endpoints
- WebSocket access (`/ws/{task_id}`)

---

## 🔌 WebSocket Authentication Options

You can authenticate WebSocket connections via:

| Method       | Example                              | Use Case                |
|--------------|---------------------------------------|--------------------------|
| Header       | `Authorization: Bearer <token>`      | Best for Python clients |
| Subprotocol  | `task-api,<token>`                   | Recommended for JS      |
| Cookie       | `access_token=<token>`               | Used in browser-based UIs |
| Query Param  | `/ws/{task_id}?access_token=...`     | Fallback only (less secure) |

More info: [websockets authentication](https://websockets.readthedocs.io/en/stable/topics/authentication.html)

---

## 🧪 Managing Clients

To create or delete clients, use the `clients-api` token:

- `POST /api/v1/clients` — create new client
- `GET /api/v1/clients` — list all clients
- `DELETE /api/v1/clients/{client_id}` — remove a client

Only tokens issued for the `clients-api` audience have access to these routes.

---

## Where It’s Used

- 🔐 The **example UI** (`examples/html/`) requires a `tasks-api` client to authenticate.
- 🔧 Swagger UI supports authentication via the lock icon (`/docs`).
- 🧪 All scripts or test clients should load their credentials from `clients.json`.

---

<!-- > Want a CLI or token generator?  
> You can reuse the contents of `initial_data.py` or use the `/clients` API directly. -->
