import { showSnackbar } from "../snackbar.js";
import { avatarColors, IMG_DIR, tryParse, USER_COLOR } from "./utils.js";
let currentUser = null;
const knownSenders = new Set();
const pendingInputRequests = new Map(); // request_id -> timestamp
const inputResponses = new Map(); // request_id -> content
let lastUserCandidate = null;

// Helper to assign consistent color per sender
const senderColorMap = new Map();
function getColorForParticipant(name) {
  if (!senderColorMap.has(name)) {
    const index = senderColorMap.size % avatarColors.length;
    senderColorMap.set(name, avatarColors[index]);
  }
  return senderColorMap.get(name);
}

// Escape HTML
function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderMessage({ sender, role, content, type }) {
  const box = document.getElementById("chatBoxLive");
  if (!box) return;

  const isUser = sender === currentUser;
  // const name = isUser ? "You" : sender;

  const container = document.createElement("div");
  container.classList.add(
    "message-container",
    role === "system"
      ? "system-container"
      : isUser
      ? "user-container"
      : "ai-container"
  );

  const avatar = document.createElement("img");
  avatar.classList.add("avatar");
  avatar.alt = sender;
  avatar.style.backgroundColor =
    role === "system"
      ? "#888"
      : isUser
      ? USER_COLOR
      : getColorForParticipant(sender);
  avatar.src = isUser
    ? `${IMG_DIR}/user.webp`
    : role === "system"
    ? `${IMG_DIR}/system.webp`
    : `${IMG_DIR}/ai.webp`;

  const bubble = document.createElement("div");
  bubble.classList.add(
    role === "system"
      ? "system-message"
      : isUser
      ? "user-message"
      : "ai-message"
  );

  const nameTag = document.createElement("div");
  nameTag.classList.add("sender-info");
  nameTag.innerText = sender;
  bubble.appendChild(nameTag);

  // Format message text
  let text = (content || "").replace(/\\n/g, "<br>").trim();
  if (!text || text === "<br>" || text == "\n") {
    text = "<i>Empty message</i>";
  } else {
    text = escapeHtml(text);
  }

  const messageContent = document.createElement("div");
  messageContent.classList.add("message-content");
  messageContent.innerHTML = text;
  // role === "system"
  //   ? text
  //   : `<span class="msg-type">[${type}]</span> ${text}`;
  bubble.appendChild(messageContent);

  container.append(avatar, bubble);
  box.appendChild(container);
  box.scrollTop = box.scrollHeight;
}
function handleWSMessage(msg) {
  const { type } = msg;

  const msgData = msg.data || msg;

  if (type === "print") {
    const parsed = tryParse(msgData);
    if (!parsed) {
      if (
        typeof msgData === "string" &&
        msgData.includes("Copying the results to") &&
        msgData.includes("waldiez_out")
      ) {
        renderMessage({
          type: "system",
          content: "Workflow completed.",
          sender: "system",
          role: "system",
        });
      }
      return;
    }

    const innerType = parsed.type;
    const content = parsed.content;

    // Handle visible message types
    if (["text", "tool_call", "function_call"].includes(innerType)) {
      const sender = content.sender || content.speaker || "unknown";
      knownSenders.add(sender);

      if (innerType === "text") {
        if (!currentUser && pendingInputRequests.size > 0) {
          lastUserCandidate = {
            sender,
            content: content.content,
            timestamp: msg.timestamp,
          };
        } else if (!currentUser && knownSenders.size === 1) {
          currentUser = sender;
        }

        renderMessage({
          type: innerType,
          content: content.content,
          sender,
          role: sender === currentUser ? "user" : "assistant",
        });
      } else {
        renderMessage({
          type: innerType,
          content: JSON.stringify(
            content.function_call || content.tool_calls || content,
            null,
            2
          ),
          sender,
          role: "agent",
        });
      }
    }

    // Hide raw group_chat_run_chat unless it's a visible message
    if (
      innerType === "group_chat_run_chat" &&
      content?.speaker &&
      content?.silent === false &&
      content?.uuid
    ) {
      const speaker = content.speaker;
      knownSenders.add(speaker);
      // Don’t render this unless needed; used only for speaker detection
    }

    // Detect per-turn termination
    if (innerType === "termination") {
      renderMessage({
        type: "termination",
        content: `Turn ended: ${content?.termination_reason}`,
        sender: "system",
        role: "system",
      });
    }
  }

  // Handle input_request
  if (type === "input_request") {
    pendingInputRequests.set(msg.request_id, {
      timestamp: msg.timestamp,
    });

    const inputField = document.getElementById("userInputLive");
    const sendButton = document.getElementById("sendButtonLive");
    const container = document.getElementById("inputContainerLive");

    if (!inputField || !sendButton || !container) {
      console.error("[ChatLive] Input field or button not found");
      return;
    }
    inputField.dataset.requestId = msg.request_id;
    inputField.value = "";
    sendButton.disabled = false;
    container.classList.remove("hidden");
    inputField.focus();
    inputField.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendButton.click();
      }
    });
    sendButton.onclick = () => {
      const message = inputField.value.trim() || "\n";
      const requestId = inputField.dataset.requestId;
      if (!requestId) {
        console.warn("[ChatLive] Missing request ID");
        return;
      }
      const ws = client.websocketManager?.websocket;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({
            type: "input_response",
            request_id: requestId,
            data: message,
          })
        );
        console.log("[ChatLive] Sent input via WebSocket");
      } else {
        console.warn("[ChatLive] WebSocket not connected");
      }
      inputResponses.set(requestId, {
        content: message,
        timestamp: Date.now(),
      });
      pendingInputRequests.delete(requestId);
      container.classList.add("hidden");
    };
  }

  // Handle input_response
  if (type === "input_response") {
    const reqId = msg.request_id;
    if (pendingInputRequests.has(reqId)) {
      const { timestamp } = pendingInputRequests.get(reqId);
      inputResponses.set(reqId, {
        content: msg.data,
        timestamp,
      });
      pendingInputRequests.delete(reqId);
    }
  }

  // Match print to input to confirm user
  if (
    type === "print" &&
    msg.data &&
    typeof msg.data === "string" &&
    lastUserCandidate
  ) {
    const parsed = tryParse(msg.data);
    if (
      parsed?.type === "text" &&
      parsed.content?.sender === lastUserCandidate.sender
    ) {
      const timeDiff = Math.abs(
        Number(msg.timestamp) - Number(lastUserCandidate.timestamp)
      );
      if (timeDiff < 10000) {
        currentUser = lastUserCandidate.sender;
        lastUserCandidate = null;
      }
    }
  }
}

export const initializeChatLive = async (taskId) => {
  const liveChatView = document.getElementById("task-chat-live-view");
  const authenticatedView = document.getElementById("authenticated-view");

  for (const el of authenticatedView.querySelectorAll(".main-content > div")) {
    el.classList.add("hidden");
  }
  liveChatView.classList.remove("hidden");

  const chatBox = document.getElementById("chatBoxLive");
  chatBox.innerHTML = "";

  const client = window.getClient();
  await client.connectWebSocket(taskId, handleWSMessage, () => {
    showSnackbar("Disconnected from chat", "warning");
  });
};
