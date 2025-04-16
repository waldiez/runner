import { showSnackbar } from "../snackbar.js";
import { avatarColors, escapeHtml, IMG_DIR, USER_COLOR } from "./utils.js";
function getColorForParticipant(name) {
  let sum = 0;
  for (const ch of name || "") sum += ch.charCodeAt(0);
  return avatarColors[sum % avatarColors.length];
}

function renderMessage({ name, role, content, type }) {
  const chatBox = document.getElementById("chatBoxStatic");
  if (!chatBox) return;

  const isUser = role === "user";
  const isSystem = role === "system";

  const container = document.createElement("div");
  container.classList.add(
    "message-container",
    isUser ? "user-container" : isSystem ? "system-container" : "ai-container"
  );

  const avatar = document.createElement("img");
  avatar.classList.add("avatar");
  avatar.style.backgroundColor = isUser
    ? USER_COLOR
    : isSystem
    ? "#999"
    : getColorForParticipant(name || role);
  avatar.src = isSystem
    ? `${IMG_DIR}/system.webp`
    : isUser
    ? `${IMG_DIR}/user.webp`
    : `${IMG_DIR}/ai.webp`;
  avatar.alt = name || role;

  const bubble = document.createElement("div");
  bubble.classList.add(
    isUser ? "user-message" : isSystem ? "system-message" : "ai-message"
  );

  const nameTag = document.createElement("div");
  nameTag.classList.add("sender-info");
  let infoInnerHTML = name || role;
  if (isSystem) {
    infoInnerHTML = `<span class="system-icon">⚙️</span> ${infoInnerHTML}`;
  }
  nameTag.innerHTML = infoInnerHTML;
  bubble.appendChild(nameTag);

  let text = String(content || "")
    .replace(/\\n/g, "<br>")
    .trim();
  if (!text || text === "<br>" || text === "None") {
    text = "<i>Empty</i>";
  } else {
    text = escapeHtml(text);
  }

  const messageContent = document.createElement("div");
  messageContent.classList.add("message-content");
  let innerHTML = `[${type}]<br>${text}`;
  if (type === "text") {
    innerHTML = text;
  }
  messageContent.innerHTML = innerHTML;
  bubble.appendChild(messageContent);

  container.append(avatar, bubble);
  chatBox.appendChild(container);
}

export const renderStaticChat = (task) => {
  const chatBox = document.getElementById("chatBoxStatic");
  if (!chatBox || !task?.results?.length) {
    showSnackbar("No chat results available", "error");
    return;
  }

  chatBox.innerHTML = "";

  const result = task.results[0]; // assume 1 result per task
  const chat = result.chat_history || [];
  const humanInputs = new Set(result.human_input || []);

  // Infer user by checking who sent the human inputs
  let currentUser = null;
  for (const msg of chat) {
    if (
      msg.content &&
      typeof msg.content === "string" &&
      humanInputs.has(msg.content.trim()) &&
      msg.name
    ) {
      currentUser = msg.name;
      break;
    }
  }
  if (!currentUser) {
    // Fallback: If only one participant besides tools/system, assume them
    const participantCounts = {};
    for (const msg of chat) {
      if (msg.name && msg.role !== "tool") {
        participantCounts[msg.name] = (participantCounts[msg.name] || 0) + 1;
      }
    }
    const candidates = Object.entries(participantCounts).filter(
      ([name]) => name.toLowerCase() === "user"
    );
    if (candidates.length === 1) {
      currentUser = candidates[0][0];
    }
  }

  for (const msg of chat) {
    const { content, name, role } = msg;

    // Determine actual message role
    let effectiveRole = "assistant"; // default
    if (name === currentUser) {
      effectiveRole = "user";
    } else if (role === "tool") {
      effectiveRole = "system";
    }

    // Render tool calls
    if (msg.tool_calls) {
      renderMessage({
        type: "tool_call",
        name,
        role: effectiveRole,
        content: JSON.stringify(msg.tool_calls, null, 2),
      });
    }

    // Render tool responses
    if (msg.tool_responses) {
      renderMessage({
        type: "tool_response",
        name,
        role: effectiveRole,
        content: JSON.stringify(msg.tool_responses, null, 2),
      });
    }

    // Render function calls (if any — not seen in your example but good to cover)
    if (msg.function_call) {
      renderMessage({
        type: "function_call",
        name,
        role: effectiveRole,
        content: JSON.stringify(msg.function_call, null, 2),
      });
    }

    // Finally, render main message content (if not "None")
    if (content && content !== "None") {
      renderMessage({
        type: "text",
        name,
        role: effectiveRole,
        content,
      });
    }
  }

  chatBox.scrollTop = chatBox.scrollHeight;
};

export async function initializeChatStatic(taskId) {
  const staticChatView = document.getElementById("task-chat-static-view");
  const authenticatedView = document.getElementById("authenticated-view");

  for (const el of authenticatedView.querySelectorAll(".main-content > div")) {
    el.classList.add("hidden");
  }
  staticChatView.classList.remove("hidden");

  const chatBox = document.getElementById("chatBoxStatic");
  chatBox.innerHTML = "";

  try {
    const client = window.getClient();
    const task = await client.getTask(taskId);

    if (Array.isArray(task.results)) {
      renderStaticChat(task);
    }
  } catch (err) {
    console.error("Failed to load task messages", err);
    showSnackbar("Error loading task chat", "error", err);
  }
}
