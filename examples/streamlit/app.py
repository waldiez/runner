"""A Streamlit app demo for Waldiez Runner."""

# pyright: reportPrivateUsage=false,reportPrivateImportUsage=false
# pyright: reportUnknownMemberType=false,reportArgumentType=false
# pyright: reportUnknownArgumentType=false,reportUnknownVariableType=false
# pyright: reportMissingTypeStubs=false,reportInvalidTypeForm=false

import json
import os
import sys
import threading
from pathlib import Path
from queue import Queue

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx
from streamlit_autorefresh import st_autorefresh  # type: ignore

# Allow running from /examples/streamlit
try:
    from waldiez_runner.client import (
        TaskCreateRequest,
        TaskResponse,
        TasksClient,
        UserInputRequest,
    )
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from waldiez_runner.client import (
        TaskCreateRequest,
        TaskResponse,
        TasksClient,
        UserInputRequest,
    )

st.set_page_config(
    "Waldiez Runner Streamlit Demo", page_icon="🤖", layout="wide"
)


# -- Streamlit state init
if "client" not in st.session_state:
    st.session_state.client = None
if "task" not in st.session_state:
    st.session_state.task: TaskResponse | None = None  # type: ignore
if "messages" not in st.session_state:
    st.session_state.messages = []
if "messages_queue" not in st.session_state:
    st.session_state.messages_queue = Queue()
if "listening" not in st.session_state:
    st.session_state.listening = False
if "ws_thread" not in st.session_state:
    st.session_state.ws_thread = None
if "ws_stop_event" not in st.session_state:
    st.session_state.ws_stop_event = threading.Event()

# a bit of styling
# Theme toggle button in top-right corner

# pylint: disable=invalid-name
style_str = """
    <style>
    .stAppHeader {
        display: none;
    }
    .st-key-theme_toggle_btn {
        position: fixed;
        top: 2rem;
        right: 2rem;
        z-index: 10000;
    }
    </style>
    """
st.html(style_str)

if "current_theme" not in st.session_state:
    st.session_state["current_theme"] = "light"

if st.button(
    "🌜" if st.session_state["current_theme"] == "light" else "🌞",
    key="theme_toggle_btn",
):
    selected = st.session_state["current_theme"]
    # pylint: disable=protected-access
    if selected == "light":
        st._config.set_option("theme.base", "dark")
        st.session_state["current_theme"] = "dark"
    elif selected == "dark":
        st._config.set_option("theme.base", "light")
        st.session_state["current_theme"] = "light"
    st.rerun()


# -- WebSocket thread logic
def websocket_listener_thread(
    tasks_client: TasksClient,
    task_id: str,
    queue: Queue[str],
) -> None:
    """WebSocket listener thread target.

    Parameters
    ----------
    tasks_client : TasksClient
        The TasksClient instance to use for WebSocket communication.
    task_id : str
        The ID of the task to listen to.
    queue : Queue[str]
        The queue to store incoming messages.
    """

    def on_msg(new_msg: str) -> None:
        """Callback for new WebSocket messages.

        Parameters
        ----------
        new_msg : str
            The new message received from the WebSocket.
        """
        print("WS on message:", new_msg)
        queue.put(new_msg)

    def on_err(err: str) -> None:
        """Callback for WebSocket errors.

        Parameters
        ----------
        err : str
            The error message received from the WebSocket.
        """
        print("WS on error:", err)
        queue.put(json.dumps({"type": "error", "data": err}))

    # pylint: disable=broad-exception-caught
    try:
        tasks_client.start_ws_listener(
            task_id=task_id,
            on_message=on_msg,
            on_error=on_err,
            in_thread=False,
        )
    except Exception as e:
        print("WebSocket error:", e)


def start_ws_thread(
    tasks_client: TasksClient,
    task_id: str,
    queue: Queue[str],
) -> threading.Thread:
    """Start a background thread for WebSocket listening.

    Parameters
    ----------
    tasks_client : TasksClient
        The TasksClient instance to use for WebSocket communication.
    task_id : str
        The ID of the task to listen to.
    queue : Queue[str]
        The queue to store incoming messages.

    Returns
    -------
    threading.Thread
        The thread that runs the WebSocket listener.
    """
    thread = threading.Thread(
        target=websocket_listener_thread,
        args=(tasks_client, task_id, queue),
        daemon=True,
    )
    add_script_run_ctx(thread)
    thread.start()
    return thread


def process_messages() -> None:
    """Pull messages from queue and store in session state."""
    queue = st.session_state.messages_queue
    while not queue.empty():
        raw = queue.get()
        # pylint: disable=broad-exception-caught
        try:
            parsed = json.loads(raw)
            st.session_state.messages.append(parsed)
        except Exception as e:
            st.session_state.messages.append({"type": "error", "data": str(e)})


# --- Autorefresh every 2s
st_autorefresh(interval=2000, key="autorefresh", limit=None)
process_messages()

# --- UI ---
st.title("Waldiez Runner - Streamlit Demo")
# pylint: disable=invalid-name
md_body = (
    "This demo shows how to authenticate, "
    "upload a `.waldiez` file, and stream its output in real-time."
)
st.markdown(md_body)

# --- Step 1: Authentication ---
with st.expander("1. Authentication (Tasks management API)", expanded=True):
    base_url = st.text_input(
        "Base URL", value=os.getenv("BASE_URL", "http://localhost:8000")
    )
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Client Secret", type="password")
    if st.button("Authenticate"):
        client = TasksClient()
        client.configure(
            base_url,
            client_id,
            client_secret,
        )
        if not client.authenticate():
            st.error("Could not authenticate")
            st.session_state.client = None
        else:
            st.session_state.client = client
            st.success("Authenticated successfully.")

# --- Step 2: Submit Task ---
if st.session_state.client:
    with st.expander("2. Submit a Task", expanded=True):
        uploaded = st.file_uploader(
            "Upload a .waldiez file", type=["json", "waldiez"]
        )
        input_timeout = st.number_input(
            "Input timeout (seconds)", min_value=5, value=180
        )
        if st.button("Submit Task") and uploaded:
            # pylint: disable=broad-exception-caught,too-many-try-statements
            try:
                file_data = uploaded.read()
                task_req = TaskCreateRequest(
                    file_data=file_data,
                    file_name=uploaded.name,
                    input_timeout=input_timeout,
                )
                task = st.session_state.client.create_task(task_req)
                st.session_state.task = task
                st.session_state.messages.clear()
                st.session_state.messages_queue.queue.clear()
                st.success(f"Task submitted: {task.id}")
            except Exception as e:
                st.error(f"Task submission failed: {e}")


# --- Step 3: Live Output ---
def display_messages() -> None:
    """Display messages in the chat interface."""
    for msg in st.session_state.messages:
        kind = msg.get("type")
        content = msg.get("data")

        if kind == "input_request":
            request_id = msg.get("request_id")
            with st.form(key=f"form_{request_id}"):
                user_input = st.text_input("Input requested:")
                submitted = st.form_submit_button("Send")
                if submitted:
                    # pylint: disable=broad-exception-caught
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
        else:
            role = "assistant"
            if kind == "input_response":
                role = "user"
            elif kind == "error":
                role = "system"

            with st.chat_message(role):
                st.markdown(
                    content
                    if isinstance(content, str)
                    else json.dumps(content, indent=2)
                )


# pylint: disable=too-complex
if st.session_state.task:  # noqa: C901
    with st.expander("3. Live Task Output", expanded=True):
        if not st.session_state.listening:
            st.session_state.ws_thread = start_ws_thread(
                st.session_state.client,
                st.session_state.task.id,
                st.session_state.messages_queue,
            )
            st.session_state.listening = True
            st.success("Started WebSocket listener.")

        if st.button("Stop Listening"):
            if (
                st.session_state.ws_stop_event
                and not st.session_state.ws_stop_event.is_set()
            ):
                st.session_state.ws_stop_event.set()
                st.session_state.listening = False
                st.success("Listener stop signal sent.")

        if not st.session_state.messages:
            st.info("Waiting for messages...")

        display_messages()
