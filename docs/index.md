# Waldiez Runner

**Waldiez Runner** is a server that executes [Waldiez](https://github.com/waldiez/waldiez) flows in isolated environments (Python virtualenvs or containers), streams logs and input/output over Redis, and provides a full API for managing tasks and clients.

Built with:

- [Waldiez](https://github.com/waldiez/waldiez) + [ag2](https://github.com/ag2ai/ag2) + [FastStream](https://github.com/ag2ai/faststream) for isolated flow execution and streaming
- [FastAPI](https://fastapi.tiangolo.com/) for the API
- [Taskiq](https://taskiq.readthedocs.io/) for async task management
- [Redis](https://redis.io/) for message and log streaming
- [PostgreSQL](https://www.postgresql.org/) for task/client persistence

![Overview](static/images/overview_light.svg#only-light)
![Overview](static/images/overview_dark.svg#only-dark)

---

## 🚀 Features

- Push-to-execute agent/task flows via HTTP
- Live I/O and user interaction over WebSocket or HTTP
- Multi-audience token-based authentication
- Local or containerized dev setups
- Easily extensible for S3/GCS, OIDC, hybrid queueing, and more

👉 Head over to [Getting Started](getting-started.md) to run your first task!
