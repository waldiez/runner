# Getting Started

Follow these steps to get Waldiez Runner up and running in your development environment.

---

## 🐳 Quickstart (Docker/Podman Compose)

To launch the full development stack (API + Redis + Postgres + Nginx):

!!!Note
    This could take some minutes on the first run, as it installs all dependencies.

```bash
docker compose -f compose.dev.yaml up --build
```

This setup includes:

- **API server** (waldiez-runner)
- **Redis** + **PostgreSQL**
- **Taskiq** worker + scheduler
- **Nginx** reverse proxy
- A simple static example in `examples/html`

Once started, you can access:

- **Static example UI**: [http://localhost](http://localhost)
- **API**: [http://localhost/docs](http://localhost/docs) (Swagger UI)

![Example Preview](static/images/getting_started_light.webp#only-light)
![Example Preview](static/images/getting_started_dark.webp#only-dark)

!!!Note
    Alternatively, you can open this project in VS Code with Dev Containers enabled — it uses most of the services (not nginx) via .devcontainer/compose.yaml.

---

## 🔑 Authenticating with the API or Example UI

When the server starts, it automatically generates a `clients.json` file in the project root.  
This file contains two API clients:

- One for the `clients-api` audience (managing clients)
- One for the `tasks-api` audience (creating and interacting with tasks)

You'll need the `tasks-api` credentials to:

- Use the Swagger UI (try out endpoints under `/api/v1/tasks`)
- Submit tasks via curl or HTTP clients
- Use the **example UI** at [http://localhost](http://localhost)

!!!INFO
    On the example page, you’ll be asked to paste the base URL, client ID, and secret.  
    Use the values from `clients.json` (specifically the `tasks-api` entry).

🔐 See [Clients & Authentication](clients.md) for more details.

## 🧪 Local Mode (Advanced)

You can also run the server without any external dependencies (Redis/Postgres):

- SQLite for storage
- FakeRedis for message streams

```shell
make dev-no-reload
```

!!!Warning
    Do expect limitations in this mode, [Fake]Redis messages might not work as expected.

Or manually (what `make dev-no-reload` does):

```shell
# drop all tables and remove the .env file if it exists
python scripts/drop.py
# switch to local mode if not already
python scripts/toggle.py --mode local
# make sure the .env file is created and the database is initialized
python scripts/pre_start.py --dev
# make sure the first two Clients are created
python scripts/initial_data.py --dev
# start the server, the broker and the scheduler
python -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000 --trusted-hosts localhost --debug --no-force-ssl --no-redis --no-postgres --dev --all
```

You can now either use the Swagger UI at [http://localhost:8000/docs](http://localhost:8000/docs) or you can also serve the example on another port terminal:

```shell
cd examples/plain
python -m http.server 3000
```

Calling `python -m http.server` will start a simple HTTP server on port 3000, serving the files in the current directory.
You can now access the example UI at [http://localhost:3000](http://localhost:3000).

---

## 📤 Submitting and Managing Tasks

Once the server is running, you can create and interact with tasks:

- **Submit a task** by uploading a `.waldiez` file via:
  - the example UI at [http://localhost](http://localhost)
  - or the Swagger UI at [http://localhost/docs](http://localhost/docs) (`POST /api/v1/tasks`)

- **Monitor task progress** via:
  - the Swagger `GET /api/v1/tasks/{task_id}`
  - or the WebSocket endpoint `/ws/{task_id}` (see [WebSocket](websocket.md))

- **Send input** if the task requests it:
  - Use the input box in the example UI
  - Or call `POST /api/v1/tasks/{task_id}/input`

- **Cancel or delete** tasks using:
  - `POST /api/v1/tasks/{task_id}/cancel`
  - `DELETE /api/v1/tasks/{task_id}`

You can explore all available routes via the interactive API docs at `/docs`.

> 🔎 For more details, check the [Tasks](tasks.md) section.
