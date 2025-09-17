export class WebSocketManager {
    constructor(baseUrl, taskId, authManager, onMessage, onClose) {
        this.baseUrl = baseUrl;
        this.taskId = taskId;
        this.authManager = authManager;
        this.onMessage = onMessage;
        this.onClose = onClose;

        this.websocket = null;
        this.subprotocol = "tasks-api";
    }

    async connect() {
        if (this.websocket?.readyState === WebSocket.OPEN) {
            console.log("WebSocket already connected to task:", this.taskId);
            return;
        }

        const token = await this.authManager.getToken();
        const wsUrl = this._makeWsUrl(this.taskId);
        console.log("Connecting to WebSocket:", wsUrl);

        this.websocket = new WebSocket(wsUrl, [this.subprotocol, token]);

        this.websocket.onopen = () => {
            console.log("WebSocket connected to task:", this.taskId);
        };

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.onMessage?.(data);
        };

        this.websocket.onerror = (event) => {
            console.error("WebSocket error:", event);
        };

        this.websocket.onclose = (event) => {
            console.warn("WebSocket closed:", event.code, event.reason);
            this.websocket = null;
            this.onClose?.(event);
        };
    }

    disconnect() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            console.log("Closing WebSocket for task:", this.taskId);
            this.websocket.close(1000, "Manual disconnect");
        }
        this.websocket = null;
    }

    isConnected() {
        return this.websocket?.readyState === WebSocket.OPEN;
    }
    _makeWsUrl(taskId) {
        const url = new URL(`/ws/${taskId}`, this.baseUrl);
        url.protocol = url.protocol.replace("http", "ws");
        return url.toString();
    }
}
