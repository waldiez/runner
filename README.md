# Waldiez Runner

Run your [Waldiez](https://github.com/waldiez/waldiez) flows in isolated environments and stream logs/input/output via Redis.

## Overview

Waldiez Runner enables executing flows in isolated Python virtual environments or containers, with full I/O streaming via Redis and task management via FastAPI + Taskiq.

Backed by:

- [FastAPI](https://fastapi.tiangolo.com/) for the HTTP API
- [Taskiq](https://taskiq.readthedocs.io/) for async task queuing and scheduling
- [Redis](https://redis.io/) for messaging and log/input/output streaming
- [PostgreSQL](https://www.postgresql.org/) for tasks and clients persistence
- [Waldiez](https://github.com/waldiez/waldiez) + [ag2](https://github.com/ag2ai/ag2) + [FastStream](https://github.com/ag2ai/faststream)  
  for defining, executing, and streaming interactive flows in isolation

## Architecture

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant FastStream
    participant TaskiqWorker
    participant Redis
    participant DB
    participant Storage
    participant Filesystem
    participant WebSocket
    participant AppInVenv

    Client->>API: POST /api/v1/tasks (with the file to use for the flow)
    API->>DB: Create task (status: pending)
    API->>Storage: Save uploaded file
    API->>TaskiqWorker: Enqueue job

    TaskiqWorker-->> Storage: Copy file locally (if needed)
    TaskiqWorker->>Filesystem: Create venv and copy app files
    TaskiqWorker->>DB: Update status to running
    TaskiqWorker->>AppInVenv: Run subprocess (start FastStream app)

    loop Task flow
        AppInVenv->>FastStream: Publish input_request
        FastStream->>Redis: Publish to task:{id}:input_request

        alt Wait for input
            Redis-->>FastStream: task:{id}:input_response
            FastStream-->>AppInVenv: Deliver input response
        else Timeout
            AppInVenv-->>FastStream: Proceed with default input ("\n")
        end

        AppInVenv->>FastStream: Publish output
        FastStream->>Redis: Stream to task:{id}:output and task-output
    end

    opt WebSocket
        Client->>WebSocket: Connect to /ws/{task_id}
        WebSocket->>Redis: Read from task:{id}:output
        Redis-->>WebSocket: Deliver logs or input prompt
        Client-->>WebSocket: Send input
        WebSocket->>Redis: Publish to task:{id}:input_response
    end

    opt HTTP Input
        Client->>API: POST /api/v1/tasks/{id}/input
        API->>Redis: Publish input response to task:{id}:input_response
    end

    alt Task completes/fails/cancelled
        TaskiqWorker->>DB: Update task status
        TaskiqWorker->>Filesystem: Move results and cleanup
        TaskiqWorker->>Storage: Copy/Upload results (if needed)
    end
```

## License

This project is licensed under the [Apache License, Version 2.0 (Apache-2.0)](https://github.com/waldiez/vscode/blob/main/LICENSE).
