
This example demonstrates how to build a frontend-only integration with the Waldiez Runner backend using plain HTML, CSS, and JavaScript — no frameworks, no build step, just files you can serve statically.

## ✅ Features

- 🔐 Auth via client ID / secret
- 📤 Upload .waldiez files to trigger tasks
- 📡 Real-time WebSocket streaming
- 💬 Live chat interface with user input support
- ♻️ Reconnect and deduplication logic

### 📁 Folder Structure

```text
html/
├── index.html                 # Main UI entry point
├── static/
│   ├── css/
│   │   └── index.css         # Basic styling
│   |   |__ ...
│   ├── js/
│   │   ├── main.js                # Main JS file
│   │   ├── lib/                   # Client-side libraries
│   │   │   ├── index.js           # Library entry point
│   │   │   ├── auth.js             # Authentication logic
│   │   │   ├── client.js           # Client API wrapper
│   │   │   ├── rest.js             # REST API calls
│   │   │   ├── utils.js            # Utility functions
│   │   │   └── ws.js               # WebSocket handling
│   │   ├── tasks/                 # Task-related logic
│   │   │   ├── index.js            # Task entry point
│   │   │   ├── newTask.js          # New task creation
│   │   │   └── tasksList.js        # Task list management
│   │   ├── chat/                  # Chat-related logic
│   │   │   ├── index.js            # Chat entry point
│   │   │   ├── live.js             # Live chat handling
│   │   │   ├── static.js           # Static chat messages (finished tasks)
│   │   │   └── utils.js            # Chat utility functions
│   │   ├── snackbar.js             # Snackbar notifications
│   │   ├── theme.js                # Theme management (dark/light)
│   ├── img/                   # Logo, icons, favicon, etc.
│   │── icons/                 # Icons included in app manifest
│   └── screenshots/           # Screenshots included in app manifest
└── favicon.ico            # App icon
├── site.webmanifest       # Web app manifest
```

## 🚀 How to Run

Serve the folder statically (no backend code needed here):

```shell
cd examples/html
python3 -m http.server 8001
# Open: http://localhost:8001
```

!!!INFO "Need a backend?"
    You can run it locally via:

    ```bash
    docker compose -f compose.dev.yaml up --build
    ```

    Then the backend will be available at: `http://localhost:8000`

---

### 🔐 Authentication

To use the UI:

- Enter your client_id and client_secret
- If running locally with the default `clients.json`, use the tasks-api credentials

Authentication is handled by the auth.js module.

---

### 📡 WebSocket Streaming

Once a task is running, the WebSocket connection begins streaming messages:

client.ws.listen(taskId, onMessage, onError);

Messages are received and rendered in the chat interface. Supported types:

- print
- input_request
- input_response
- tool_call
- termination

Handled through chatLive.js and client.js.

---

### ✍️ User Input

When a task requires user input:

- The UI prompts the user dynamically
- Responses are sent via:

```javascript
client.sendInput({
  task_id,
  request_id,
  data: userInput,
});
```

## ⚠️ TODO / Improvements

- Persist login across page reloads
- Improve error handling and fallback UI

## 🧪 Summary

This minimal yet functional example demonstrates how to:

- Interact with Waldiez Runner via REST + WebSocket
- Handle dynamic input/output
- Build a no-dependency frontend for .waldiez tasks

Use it as:

- A reference for building your own UIs
- A fallback or lightweight frontend
- A base for debugging or experimenting with workflows
