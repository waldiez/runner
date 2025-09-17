import { fetchWithTimeout } from "./utils.js";

export class RestClient {
    constructor(baseUrl, authManager) {
        this.baseUrl = baseUrl.replace(/\/$/, "");
        this.authManager = authManager;
    }

    async request(url, options = {}, timeout = 10000) {
        const token = await this.authManager.getToken();

        const response = await fetchWithTimeout(
            url,
            {
                ...options,
                headers: {
                    ...(options.headers || {}),
                    Authorization: `Bearer ${token}`,
                },
            },
            timeout
        );

        if (response.status === 401) {
            console.warn("401 - token expired, retrying...");
            await this.authManager.refreshAccessToken();
            const newToken = await this.authManager.getToken();

            return await fetchWithTimeout(
                url,
                {
                    ...options,
                    headers: {
                        ...(options.headers || {}),
                        Authorization: `Bearer ${newToken}`,
                    },
                },
                timeout
            );
        }

        if (!response.ok) {
            throw new Error(`Request failed: ${response.status}`);
        }

        return response;
    }

    async parseJsonSafe(res) {
        const contentType = res.headers.get("Content-Type") || "";
        if (res.status === 204 || !contentType.includes("application/json")) {
            return null;
        }

        try {
            return await res.json();
        } catch {
            return null;
        }
    }

    async triggerTask(file, inputTimeout = 60) {
        const url = `${this.baseUrl}/api/v1/tasks?input_timeout=${inputTimeout}`;
        const formData = new FormData();
        formData.append("file", file);

        const res = await this.request(url, {
            method: "POST",
            body: formData,
        });
        return await this.parseJsonSafe(res);
    }

    async sendUserInput(taskId, requestId, userInput) {
        const url = `${this.baseUrl}/api/v1/tasks/${taskId}/input`;
        const body = JSON.stringify({
            request_id: requestId,
            data: userInput,
        });

        const res = await this.request(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body,
        });

        return await this.parseJsonSafe(res); // won't throw on 204
    }

    async getTasks(page = 1, size = 10) {
        const url = new URL(`${this.baseUrl}/api/v1/tasks`);
        url.searchParams.append("page", page);
        url.searchParams.append("size", size);
        const res = await this.request(url);
        return await this.parseJsonSafe(res);
    }

    async getTask(taskId) {
        const url = `${this.baseUrl}/api/v1/tasks/${taskId}`;
        const res = await this.request(url);
        return await this.parseJsonSafe(res);
    }

    async downloadTask(taskId) {
        const url = `${this.baseUrl}/api/v1/tasks/${taskId}/download`;
        const res = await this.request(url);
        const blob = await res.blob();

        const rawDisposition = res.headers.get("Content-Disposition") || "";
        const match = rawDisposition.match(/filename="?([^"]+)"?/);
        const filename = match?.[1] || `task-${taskId}.zip`;
        // const filename = res.headers.get("Content-Disposition")?.split("filename=")[1] || `task-${taskId}.zip`;
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    async cancelTask(taskId) {
        const url = `${this.baseUrl}/api/v1/tasks/${taskId}/cancel`;
        const res = await this.request(url, { method: "POST" });
        return await this.parseJsonSafe(res);
    }

    async deleteTask(taskId, force = false) {
        const url = new URL(`${this.baseUrl}/api/v1/tasks/${taskId}`);
        if (force) url.searchParams.append("force", "true");
        await this.request(url, { method: "DELETE" });
    }

    async deleteAllTasks(force = false) {
        const url = new URL(`${this.baseUrl}/api/v1/tasks`);
        if (force) url.searchParams.append("force", "true");
        await this.request(url, { method: "DELETE" });
    }

    async pollTaskStatusLoop(
        taskId,
        onUpdate,
        interval = 2000,
        stopSignal = { stopped: false }
    ) {
        let lastStatus = null;
        let lastInputRequestId = null;

        const isTerminal = (status) =>
            ["COMPLETED", "FAILED", "CANCELLED"].includes(status);

        const poll = async () => {
            while (!stopSignal.stopped) {
                try {
                    const task = await this.getTask(taskId);

                    if (!task) {
                        console.warn("[Polling] Task not found.");
                        break;
                    }

                    const changedStatus = task.status !== lastStatus;
                    const changedInput =
                        task.input_request_id !== lastInputRequestId;

                    if (changedStatus || changedInput) {
                        onUpdate(task);
                        lastStatus = task.status;
                        lastInputRequestId = task.input_request_id;
                    }

                    if (isTerminal(task.status)) {
                        break;
                    }
                } catch (err) {
                    console.error("[Polling] Error fetching task:", err);
                }

                await new Promise((resolve) => setTimeout(resolve, interval));
            }

            console.log("[Polling] Stopped for task", taskId);
        };

        poll(); // start async loop
    }
}
