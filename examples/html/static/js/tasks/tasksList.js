import { initializeChatLive, initializeChatStatic } from "../chat/index.js";

let isLoading = false;

document.addEventListener("DOMContentLoaded", () => {
    const tasksView = document.getElementById("tasks-view");

    // DOM setup
    const taskList = document.createElement("ul");
    taskList.id = "tasks-list";
    tasksView.appendChild(taskList);

    const paginationControls = document.createElement("div");
    paginationControls.classList.add("pagination-controls");
    tasksView.appendChild(paginationControls);

    const pageSize = 10;
    let currentPage = 1;
    let totalPages = 1;

    const tasksNav = document.getElementById("tasks");

    const observer = new MutationObserver(() => {
        if (tasksNav.classList.contains("active")) {
            loadTasks();
        }
    });

    observer.observe(tasksNav, { attributes: true });

    async function loadTasks() {
        if (isLoading) {
            console.log("[Tasks] Already loading, skipping...");
            return;
        }
        isLoading = true;

        const client = window.getClient();
        if (client?.websocketManager) {
            client.websocketManager.disconnect(); // avoid zombie connections
        }

        try {
            const { items, page, pages } = await client.getTasks(
                currentPage,
                pageSize
            );
            totalPages = pages;
            currentPage = page;

            taskList.innerHTML = items.length
                ? items.map((task) => renderTask(task)).join("")
                : "<li>No tasks found.</li>";

            attachTaskActions();
            updatePagination(currentPage, totalPages, items.length);
        } catch (err) {
            console.error(err);
            taskList.innerHTML = "<li>Error loading tasks.</li>";
        } finally {
            isLoading = false;
        }
    }

    function renderTask(task) {
        const actions = [];
        const status = task.status.toUpperCase();
        const statusClass = `status-${status.toLowerCase()}`;
        const isFinal = ["COMPLETED", "CANCELLED", "FAILED"].includes(status);

        if (["RUNNING", "WAITING_FOR_INPUT"].includes(status)) {
            actions.push(
                `<a href="?task=${task.id}" title="View live updates" class="chat-btn live">💬 Live </a>`
            );
        }
        if (status === "COMPLETED") {
            actions.push(
                `<a href="?task=${task.id}" title="View task results" class="chat-btn static">💬 Results</a>`
            );
        }
        if (status === "FAILED") {
            const taskDetails = encodeURIComponent(
                JSON.stringify(task.results) || ""
            );
            actions.push(
                `<button class="details-btn" data-id="${task.id}" data-details="${taskDetails}" title="View error details">📄 Details</button>`
            );
        }
        if (!isFinal) {
            actions.push(
                `<button class="refresh-btn" title="Refresh" data-id="${task.id}">🔄</button>`
            );
            actions.push(
                `<button class="cancel-btn" title="Cancel task" data-id="${task.id}">❌ Cancel</button>`
            );
        } else {
            actions.push(
                `<button class="download-btn" title="Download the task's archive" data-id="${task.id}">📥 Download</button>`
            );
            actions.push(
                `<button class="delete-btn" title="Delete task" data-id="${task.id}">🗑️ Delete</button>`
            );
        }

        return `
      <li class="task-item" data-id="${task.id}">
        <span class="task-info">
          <span class="status-badge ${statusClass}">${status}</span>
          <span class="task-filename">${trimTaskFilename(task.filename)}</span>
        </span>
        <span class="task-actions">${actions.join(" ")}</span>
      </li>
    `;
    }

    function trimTaskFilename(filename) {
        const maxLength = 30;
        return filename.length > maxLength
            ? filename.slice(0, maxLength) + "..."
            : filename;
    }

    function attachTaskActions() {
        const client = window.getClient();

        document.querySelectorAll(".download-btn").forEach((btn) => {
            btn.onclick = () => client.downloadTask(btn.dataset.id);
        });

        document.querySelectorAll(".cancel-btn").forEach((btn) => {
            btn.onclick = async () => {
                await client.cancelTask(btn.dataset.id);
                loadTasks(); // re-fetch the list
            };
        });

        document.querySelectorAll(".delete-btn").forEach((btn) => {
            btn.onclick = async () => {
                await client.deleteTask(btn.dataset.id, true);
                if (currentPage > 1 && taskList.children.length === 1) {
                    currentPage--; // go back if this was the last item
                }
                loadTasks(); // re-fetch
            };
        });

        document.querySelectorAll(".chat-btn").forEach((btn) => {
            btn.addEventListener("click", async (e) => {
                e.preventDefault();
                const taskId = new URL(btn.href).searchParams.get("task");
                const isLive = btn.classList.contains("live");
                const isStatic = btn.classList.contains("static");

                if (taskId && window.getAuthManager()?.isAuthenticated()) {
                    history.replaceState({}, "", "?task=" + taskId);
                    if (isLive) {
                        await initializeChatLive(taskId);
                    } else if (isStatic) {
                        await initializeChatStatic(taskId);
                    }
                }
            });
        });
        document.querySelectorAll(".details-btn").forEach((btn) => {
            btn.onclick = () => {
                const taskId = btn.dataset.id;
                let maybeDetails = null;
                try {
                    const decodedDetails = btn.dataset.details
                        ? decodeURIComponent(btn.dataset.details)
                        : null;
                } catch (_) {
                    //
                }
                showErrorDetailsModal(taskId, maybeDetails);
            };
        });
        document.querySelectorAll(".refresh-btn").forEach((btn) => {
            btn.addEventListener("click", async () => {
                const taskId = btn.dataset.id;
                btn.disabled = true;
                btn.innerText = "⏳";

                try {
                    const updatedTask = await client.getTask(taskId);
                    console.log("Updated task:", updatedTask);
                    const taskItem = btn.closest(".task-item");
                    if (taskItem) {
                        taskItem.outerHTML = renderTask(updatedTask);
                        attachTaskActions(); // re-bind for updated DOM
                    }
                } catch (err) {
                    console.error("Failed to refresh task:", err);
                    btn.innerText = "⚠️";
                } finally {
                    btn.disabled = false;
                }
            });
        });
    }

    function updatePagination(current, total, taskCount) {
        paginationControls.innerHTML = "";

        if (taskCount === 0) {
            paginationControls.classList.add("hidden");
            return;
        }

        paginationControls.classList.remove("hidden");

        const prev = document.createElement("button");
        prev.textContent = "← Previous";
        prev.disabled = current === 1;
        prev.className = "pagination-btn";
        prev.onclick = () => {
            currentPage--;
            loadTasks();
        };

        const next = document.createElement("button");
        next.textContent = "Next →";
        next.disabled = current >= total;
        next.className = "pagination-btn";
        next.onclick = () => {
            currentPage++;
            loadTasks();
        };

        const label = document.createElement("span");
        label.className = "page-info";
        label.textContent = `Page ${current} of ${total}`;

        paginationControls.append(prev, label, next);
    }

    function showErrorDetailsModal(taskId, maybeDetails = null) {
        const modal = document.getElementById("details-modal");
        const modalContent = document.getElementById("details-content");
        const show = (content) => {
            if (typeof content === "object") {
                modalContent.textContent = JSON.stringify(content, null, 2); // pretty-print
            } else {
                modalContent.textContent = content;
            }
            modal.classList.remove("hidden");
        };

        show("Loading...");

        (async () => {
            try {
                if (maybeDetails) {
                    show(maybeDetails);
                    return;
                }
                const client = window.getClient();
                const task = await client.getTask(taskId);
                const details = task.results || "No details available.";
                show(details);
            } catch (err) {
                console.error(err);
                show("Failed to fetch task details.");
            }
        })();
    }
});

export {};
