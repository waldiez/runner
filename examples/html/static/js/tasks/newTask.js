import { initializeChatLive } from "../chat/index.js";
import { showSnackbar } from "../snackbar.js";

const ALLOWED_EXTENSION = ".waldiez";
const MAX_FILE_SIZE = 2 * 1024 * 1024; // 2MB

function initializeDropzone() {
    const newTaskView = document.getElementById("new-task-view");

    newTaskView.innerHTML = `
    <div class="dropzone" id="dropzone">
      <p>Drop your <strong>${ALLOWED_EXTENSION}</strong> file here or click to select</p>
      <input type="file" id="file-input" accept="${ALLOWED_EXTENSION}" />
    </div>
  `;

    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("file-input");

    dropzone.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length) {
            handleFile(e.target.files[0]);
        }
    });

    ["dragenter", "dragover"].forEach((evt) =>
        dropzone.addEventListener(evt, (e) => {
            e.preventDefault();
            dropzone.classList.add("dragover");
        })
    );

    ["dragleave", "drop"].forEach((evt) =>
        dropzone.addEventListener(evt, () =>
            dropzone.classList.remove("dragover")
        )
    );

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });
}

async function handleFile(file) {
    if (!file.name.endsWith(ALLOWED_EXTENSION)) {
        showSnackbar(`Only ${ALLOWED_EXTENSION} files allowed`, "error");
        return;
    }

    if (file.size > MAX_FILE_SIZE) {
        showSnackbar("File too large (max 2MB)", "error");
        return;
    }

    document.getElementById(
        "dropzone"
    ).innerHTML = `<p>File selected: <strong>${file.name}</strong></p>`;

    try {
        const client = window.getClient();
        const task = await client.triggerTask(file);
        showSnackbar("Task triggered!", "success");

        // Update view (hide all, show live chat)
        const views = document.querySelectorAll(".main-content > div");
        views.forEach((v) => v.classList.add("hidden"));
        document
            .getElementById("task-chat-live-view")
            .classList.remove("hidden");

        // Update drawer state
        document
            .querySelectorAll(".drawer-content .navigation")
            .forEach((item) => item.classList.remove("active"));
        // if we also want the navigation button:
        // document.getElementById("task-chat-live").classList.remove("hidden");
        // document.getElementById("task-chat-live").classList.add("active");

        // Set URL & initialize live chat
        history.replaceState({}, "", "?task=" + task.id);
        await initializeChatLive(task.id);
    } catch (err) {
        console.error(err);
        showSnackbar("Failed to start task", "error", err);
    }
}

// Observe new-task nav
document.addEventListener("DOMContentLoaded", () => {
    const newTaskNav = document.getElementById("new-task");

    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            if (
                mutation.attributeName === "class" &&
                newTaskNav.classList.contains("active")
            ) {
                initializeDropzone();
            }
        }
    });

    observer.observe(newTaskNav, { attributes: true });
});

export {};
