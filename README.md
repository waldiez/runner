# Waldiez Runner

Run your [Waldiez](https://github.com/waldiez/waldiez) flows in isolated environments and stream AG2 logs/input/output via Redis.


https://github.com/user-attachments/assets/596ee25a-362e-4202-a4b0-894a4713e041


## Overview

Waldiez Runner enables executing flows in isolated Python virtual environments or containers, with full I/O streaming via Redis and task management via FastAPI + Taskiq.

Backed by:

- [FastAPI](https://fastapi.tiangolo.com/) for the HTTP API
- [Taskiq](https://taskiq.readthedocs.io/) for async task queuing and scheduling
- [Redis](https://redis.io/) for messaging and log/input/output streaming
- [PostgreSQL](https://www.postgresql.org/) for task and client persistence
- [Waldiez](https://github.com/waldiez/waldiez) + [ag2](https://github.com/ag2ai/ag2) + [FastStream](https://github.com/ag2ai/faststream) for defining, executing, and streaming interactive flows in isolation

![overview](https://raw.githubusercontent.com/waldiez/runner/refs/heads/main/docs/overview.jpg)

## License

This project is licensed under the [Apache License, Version 2.0 (Apache-2.0)](https://github.com/waldiez/vscode/blob/main/LICENSE).
