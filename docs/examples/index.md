# Examples

This section showcases how to interact with Waldiez Runner using different interfaces and technologies. These examples are designed to help you:

- Authenticate with the API
- Upload and manage `.waldiez` tasks
- Stream task output in real-time
- Send user input dynamically (if required by the task)

Each example demonstrates the use of the `waldiez_runner.client` module, which provides a high-level, consistent interface to the backend.

---

## 🌐 HTML + JavaScript (Vanilla)

A frontend-only example using plain HTML, CSS, and JavaScript (no frameworks). Demonstrates:

- Authentication
- File upload via Fetch API
- WebSocket streaming
- Dynamic input prompts

Ideal for minimal, portable frontend integration.

🔗 [HTML + JS Example](./html.md)

---

## 🧪 Jupyter Notebook: Task Demo

This notebook demonstrates how to:

1. Configure and authenticate using the `TasksClient`.
2. Load and submit a `.waldiez` file programmatically.
3. Monitor task status via the REST API.
4. Read results once the task completes.
5. Optionally, visualize or debug flows interactively.

Perfect for exploration and development workflows.

📄 [task_demo.ipynb](./task_demo.ipynb)

---

## 📊 Streamlit Demo

A Streamlit-based interactive UI for triggering tasks and viewing real-time output.

- Client-side theme toggle (dark/light)
- Upload `.waldiez` file
- Chat-like message stream (WebSocket)
- Live user input handling

📄 [Streamlit Demo](./streamlit.md)  
💡 [app.py](./app.py)

---

## 🖥️ Command Line Interface (CLI)

**(Coming soon)** — A terminal-based interface to authenticate, trigger tasks, and stream results.

Useful for:

- Shell scripting
- Headless environments
- CI/CD integrations

📄 CLI Usage — _WIP_
