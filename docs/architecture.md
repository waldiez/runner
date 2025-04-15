# Architecture

Waldiez Runner orchestrates the execution of [Waldiez](https://github.com/waldiez/waldiez) flows in isolated environments (e.g. virtualenvs), with full support for live input/output streaming and task management via HTTP or WebSocket.

It uses a modular architecture composed of:


| Component     | Description |
|---------------|-------------|
| **FastAPI**   | HTTP API for tasks, inputs, clients, and authentication |
| **Taskiq**    | Asynchronous job runner (background task execution) |
| **FastStream** | Executes uploaded app in a new virtualenv |
| **Redis**     | Handles message passing (logs, prompts, responses) |
| **PostgreSQL**| Persists task and client state |
| **WebSocket** | Real-time input/output interface for tasks |

## System Overview

```mermaid
graph TD
  A[Client] -->|HTTP| B[FastAPI]
  A -->|WebSocket| G[WebSocket Router]

  B -->|Enqueue Task| C[Taskiq Worker]
  B -->|Store Task| D[PostgreSQL]
  B -->|Save File| F[Storage]

  C -->|Run App| H[FastStream + Waldiez + Ag2]
  C -->|Update Status| D

  H -->|Input/Output + Status| E[Redis]

  G -->|Subscribe + Publish| E

  subgraph Virtualenv
    H
  end

  subgraph Dev Environment
    B
    C
    G
    D
    E
    F
  end
```

## Redis I/O and Status Channels

Tasks use `RedisIOStream` an extension to ag2's [IOStream](https://github.com/ag2ai/ag2/blob/main/autogen/io/base.py#L63) to stream logs and request input. This includes:

- Output:
  - `task:{task_id}:output`: per-task stream
  - `task-output`: global stream for all task messages
- Input:
  - `task:{task_id}:input_request`: prompt user input
  - `task:{task_id}:input_response`: receive user reply
- Control:
  - t`ask:{task_id}:status`: used by the runner to react to cancel requests and broadcast lifecycle events (running, completed, failed, etc.)

## Execution Flow

The diagram below illustrates how the system handles a full task lifecycle — from submission to completion.

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant FastStream
    participant TaskiqWorker
    participant Redis
    participant DB
    participant Storage
    participant WebSocket
    participant AppInVenv

    Client->>API: POST /api/v1/tasks
    API->>DB: Create task
    API->>Storage: Save uploaded file
    API->>TaskiqWorker: Enqueue job

    TaskiqWorker->>Storage: Create venv and copy app files
    TaskiqWorker->>DB: Update task status to running
    TaskiqWorker->>AppInVenv: Start subprocess

    loop Task execution
        AppInVenv->>FastStream: Publish input_request
        FastStream->>Redis: task:{task_id}:input_request

        alt User responds
            Redis-->>FastStream: task:{task_id}:input_response
            FastStream-->>AppInVenv: Deliver input
        else Timeout
            AppInVenv-->>FastStream: Use default input
        end

        AppInVenv->>FastStream: Publish output
        FastStream->>Redis: Stream to task:{task_id}:output and task-output
    end

    opt WebSocket
        Client->>WebSocket: Connect to /ws/{task_id}
        WebSocket->>Redis: Read from task:{task_id}:output
        Redis-->>WebSocket: Forward output or input_request
        Client-->>WebSocket: Send input
        WebSocket->>Redis: task:{task_id}:input_response
    end

    opt HTTP Input
        Client->>API: POST /api/v1/tasks/{task_id}/input
        API->>Redis: task:{task_id}:input_response
    end

    alt Task completes/fails/cancelled
        TaskiqWorker->>DB: Update task status
        TaskiqWorker->>Storage: Move results and clean up
    end
```
