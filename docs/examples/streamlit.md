from docs.examples.app import base_urlThis page demonstrates how to build an interactive web application using [Streamlit](https://streamlit.io/) and the `waldiez_runner.client` to interact with the Waldiez Runner backend.

## Overview

The Streamlit demo guides you through:

1. Authenticating with the API.
2. Uploading a `.waldiez` file to trigger a task.
3. Viewing real-time output using a WebSocket connection.
4. Sending user input interactively when requested.
5. Displaying task status and results.

![Streamlit example overview](../static/images/streamlit_1_light.webp#only-light)
![Streamlit example overview](../static/images/streamlit_1_dark.webp#only-dark)

## How to Run

To run the example:

```bash
cd examples/streamlit
# install dependencies (streamlit and streamlit-autorefresh)
# use a venv if not already in one
# python3 -m venv venv
# `source venv/bin/activate` or `venv\Scripts\activate`
python3 -m pip install -r requirements.txt
streamlit run app.py
```

!!!NOTE Backend Requirement
    Make sure the backend is running and accessible at the specified `BASE_URL`.  
    If running locally:
    ```shell
    docker compose -f compose.dev.yaml up --build
    ```
    The `BASE_URL` would then be: `http://localhost:8000`.
    <!-- or
    ```shell
    docker run -p 8000:8000 waldiez/runner
    ``` -->
!!!INFO Using Local Credentials
    If running locally, the root of the project should include a `clients.json` file with two predefined clients:
    - `clients-api`: For managing clients.
    - `tasks-api`: For submitting and managing tasks.
    You can use the `tasks-api` credentials to authenticate and interact with the tasks API.

![Streamlit example overview with user input ](../static/images/streamlit_2_light.webp#only-light)
![Streamlit example overview with user input ](../static/images/streamlit_2_dark.webp#only-dark)

## Code Highlights

This section highlights the key parts of the code that interact with the `waldiez_runner.client` module. The full code is available in the [app.py](./app.py) file.

<!-- markdownlint-disable MD036 -->
**Authentication**

```python
from  waldiez_runner.client import TasksClient
base_url = "http://localhost:8000"  # or your backend URL
client_id = "your_client_id"  # from clients.json
client_secret = "your_client_secret"  # from clients.json
client = TasksClient()
client.configure(base_url, client_id, client_secret)
client.authenticate()
```

**Task Submission**

```python
from waldiez_runner.client import TaskCreateRequest
task_req = TaskCreateRequest(file_data=..., file_name="...", input_timeout=...)
task = client.create_task(task_req)
```

**WebSocket Listener**

```python
client.start_ws_listener(
    task.id,
    on_message=on_msg,
    on_error=on_err,
    in_thread=False,
)
```

**User Input Handling**

```python
kind = msg.get("type")
if kind == "input_request":
    request_id = msg.get("request_id")
    with st.form(key=f"form_{request_id}"):
        user_input = st.text_input("Input requested:")
        submitted = st.form_submit_button("Send")
        if submitted:
            try:
                user_input_req = UserInputRequest(
                    task_id=st.session_state.task.id,
                    request_id=request_id,
                    data=user_input,
                )
                st.session_state.client.send_user_input(user_input_req)
                st.success("Input sent.")
            except Exception as e:
                st.error(f"Failed to send input: {e}")
```
