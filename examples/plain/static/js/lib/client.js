import { RestClient } from "./rest.js";
import { WebSocketManager } from "./ws.js";

export class Client {
  constructor(baseUrl, authManager) {
    this.authManager = authManager;
    this.restClient = new RestClient(baseUrl, authManager);
    this.websocketManager = null;
    this.taskId = null;
  }

  async authenticate() {
    return await this.authManager.getToken();
  }

  async triggerTask(file, inputTimeout = 60) {
    return await this.restClient.triggerTask(file, inputTimeout);
  }

  async sendUserInput(taskId, requestId, userInput) {
    return await this.restClient.sendUserInput(taskId, requestId, userInput);
  }

  async getTasks(page = 1, size = 10) {
    return await this.restClient.getTasks(page, size);
  }

  async getTask(taskId) {
    return await this.restClient.getTask(taskId);
  }

  async downloadTask(taskId) {
    return await this.restClient.downloadTask(taskId);
  }

  async cancelTask(taskId) {
    return await this.restClient.cancelTask(taskId);
  }

  async deleteTask(taskId, force = false) {
    return await this.restClient.deleteTask(taskId, force);
  }

  async deleteAllTasks(force = false) {
    return await this.restClient.deleteAllTasks(force);
  }

  async pollTaskStatusLoop(taskId, onUpdate, interval = 2000, stopSignal = { stopped: false }) {
    return await this.restClient.pollTaskStatusLoop(taskId, onUpdate, interval, stopSignal);
  }

  async _onClose(event, taskId, onMessage, onClose) {
    if (event.code === 1000) {
      console.log("WebSocket closed normally");
      return;
    }
    if (event.code === 1006) {
      console.warn("WebSocket closed unexpectedly");
      return;
    }
    if (event.code === 4003 || event.code === 1008) {
      console.warn("WebSocket closed with policy violation");

      if (this.authManager.isTokenExpired()) {
        try {
          await this.authManager.refreshAccessToken();
          await this.connectWebSocket(taskId, onMessage, onClose);
        } catch (err) {
          console.error("Failed to reconnect WebSocket:", err);
          onClose?.(event);
        }
      }
    } else {
      onClose?.(event);
    }
  }

  async connectWebSocket(taskId, onMessage = () => {}, onClose = () => {}) {
    // avoid reconnecting to the same task if already connected or connecting
    const prev = this.websocketManager;
    if (
      prev &&
      prev.taskId === taskId &&
      prev.websocket &&
      [WebSocket.OPEN, WebSocket.CONNECTING].includes(prev.websocket.readyState)
    ) {
      console.log("WebSocket already connected/connecting for", taskId);
      return prev;
    }

    // Ensure cleanup before making a new connection
    if (prev) {
      prev.disconnect();
      this.websocketManager = null;
    }

    this.taskId = taskId;
    this.websocketManager = new WebSocketManager(
        this.authManager.baseUrl,
        taskId,
        this.authManager,
        onMessage,
        async (event) => await this._onClose(event, taskId, onMessage, onClose),
    );

    await this.websocketManager.connect();
    return this.websocketManager;
  }

  closeWebSocket() {
    if (this.websocketManager) {
      this.websocketManager.disconnect();
      this.websocketManager = null;
    }
  }
}
