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
- A simple static example in `examples/plain`

Once started, you can access:

- **API**: [http://localhost/docs](http://localhost/docs) (Swagger UI)
- **Static example UI**: [http://localhost](http://localhost)

![Example Preview](static/images/getting_started_light.webp#only-light)
![Example Preview](static/images/getting_started_dark.webp#only-dark)

!!!Note
    Alternatively, you can open this project in VS Code with Dev Containers enabled — it uses most of the services (not nginx) via .devcontainer/compose.yaml.

## 🧪 Local Mode (Advanced)

You can also run the server without any external dependencies (Redis/Postgres):

- SQLite for storage
- FakeRedis for message streams

```shell
make dev-no-reload
```

Or manually:

```shell
python3 scripts/pre_start.py --dev
python3 scripts/initial_data.py --dev
python3 -m waldiez_runner --debug --dev
```
