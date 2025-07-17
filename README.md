# Waldiez Runner

Run your [Waldiez](https://github.com/waldiez/waldiez) flows in isolated environments and stream AG2 logs/input/output via Redis.

<!-- markdownlint-disable MD034 -->

<video
  src="https://github.com/user-attachments/assets/596ee25a-362e-4202-a4b0-894a4713e041"
  controls="controls" autoplay="autoplay" loop="loop"
  muted="muted" playsinline="playsinline" width="100%" height="100%">
</video>

## Overview

Waldiez Runner enables executing flows in isolated Python virtual environments or containers, with full I/O streaming via Redis and task management via FastAPI + Taskiq.

Backed by:

- [FastAPI](https://fastapi.tiangolo.com/) for the HTTP API
- [Taskiq](https://taskiq.readthedocs.io/) for async task queuing and scheduling
- [Redis](https://redis.io/) for messaging and log/input/output streaming
- [PostgreSQL](https://www.postgresql.org/) for task and client persistence
- [Waldiez](https://github.com/waldiez/waldiez) + [ag2](https://github.com/ag2ai/ag2) + [FastStream](https://github.com/ag2ai/faststream) for defining, executing, and streaming interactive flows in isolation

![overview](https://raw.githubusercontent.com/waldiez/runner/refs/heads/main/docs/overview.jpg)

## Getting Started

Follow these steps to get Waldiez Runner up and running in your development environment.

---

### 🐳 Quickstart (Docker/Podman Compose)

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

![Example Preview](https://raw.githubusercontent.com/waldiez/runner/refs/heads/main/docs/static/images/getting_started_dark.webp#only-dark)

!!!Note
    Alternatively, you can open this project in VS Code with Dev Containers enabled — it uses most of the services (not nginx) via .devcontainer/compose.yaml.

---

### 🔑 Authenticating with the API or Example UI

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

🔐 See [Clients & Authentication](https://waldiez.github.io/runner/clients/) for more details.

### 🧪 Local Mode (Advanced)

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

### 📤 Submitting and Managing Tasks

Once the server is running, you can create and interact with tasks:

- **Submit a task** by uploading a `.waldiez` file via:
  - the example UI at [http://localhost](http://localhost)
  - or the Swagger UI at [http://localhost/docs](http://localhost/docs) (`POST /api/v1/tasks`)

- **Monitor task progress** via:
  - the Swagger `GET /api/v1/tasks/{task_id}`
  - or the WebSocket endpoint `/ws/{task_id}` (see [WebSocket](https://waldiez.github.io/runner/websocket/))

- **Send input** if the task requests it:
  - Use the input box in the example UI
  - Or call `POST /api/v1/tasks/{task_id}/input`

- **Cancel or delete** tasks using:
  - `POST /api/v1/tasks/{task_id}/cancel`
  - `DELETE /api/v1/tasks/{task_id}`

You can explore all available routes via the interactive API docs at `/docs`.

## Contributors ✨

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://scholar.google.com/citations?user=JmW9DwkAAAAJ"><img src="https://avatars.githubusercontent.com/u/29335277?v=4?s=100" width="100px;" alt="Panagiotis Kasnesis"/><br /><sub><b>Panagiotis Kasnesis</b></sub></a><br /><a href="#projectManagement-ounospanas" title="Project Management">📆</a> <a href="#research-ounospanas" title="Research">🔬</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/lazToum"><img src="https://avatars.githubusercontent.com/u/4764837?v=4?s=100" width="100px;" alt="Lazaros Toumanidis"/><br /><sub><b>Lazaros Toumanidis</b></sub></a><br /><a href="https://github.com/waldiez/waldiez/commits?author=lazToum" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://humancentered.gr/"><img src="https://avatars.githubusercontent.com/u/3456066?v=4?s=100" width="100px;" alt="Stella Ioannidou"/><br /><sub><b>Stella Ioannidou</b></sub></a><br /><a href="#promotion-siioannidou" title="Promotion">📣</a> <a href="#design-siioannidou" title="Design">🎨</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/amaliacontiero"><img src="https://avatars.githubusercontent.com/u/29499343?v=4?s=100" width="100px;" alt="Amalia Contiero"/><br /><sub><b>Amalia Contiero</b></sub></a><br /><a href="https://github.com/waldiez/vscode/commits?author=amaliacontiero" title="Code">💻</a> <a href="https://github.com/waldiez/vscode/issues?q=author%3Aamaliacontiero" title="Bug reports">🐛</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/hchris0"><img src="https://avatars.githubusercontent.com/u/23460824?v=4?s=100" width="100px;" alt="Christos Chatzigeorgiou"/><br /><sub><b>Christos Chatzigeorgiou</b></sub></a><br /><a href="https://github.com/waldiez/runner/commits?author=hchris0" title="Code">💻</a></td>
    </tr>
  </tbody>
  <tfoot>
    <tr>
      <td align="center" size="13px" colspan="7">
        <img src="https://raw.githubusercontent.com/all-contributors/all-contributors-cli/1b8533af435da9854653492b1327a23a4dbd0a10/assets/logo-small.svg">
          <a href="https://all-contributors.js.org/docs/en/bot/usage">Add your contributions</a>
        </img>
      </td>
    </tr>
  </tfoot>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!

## License

This project is licensed under the [Apache License, Version 2.0 (Apache-2.0)](https://github.com/waldiez/runner/blob/main/LICENSE).
