import { showSnackbar } from "./snackbar.js";

function clearTaskQuery() {
    const url = new URL(window.location);
    url.searchParams.delete("task");
    window.history.replaceState({}, document.title, url.toString());
}
function handleEscape(e) {
    if (e.key === "Escape") {
        closeModal();
    }
}
function closeModal() {
    const modal = document.getElementById("details-modal");
    if (modal) {
        modal.classList.add("hidden");
    }
    const modalContent = document.getElementById("details-content");
    if (modalContent) {
        modalContent.textContent = "";
    }
    window.removeEventListener("keydown", handleEscape); // clean up
}
document.addEventListener("DOMContentLoaded", () => {
    const baseUrlInput = document.getElementById("base_url");
    const clientIdInput = document.getElementById("client_id");
    const clientSecretInput = document.getElementById("client_secret");
    const authenticateBtn = document.getElementById("authenticate-btn");
    const logoutLink = document.getElementById("logout");
    const drawer = document.getElementById("drawer");
    const mainContent = document.querySelector(".main-content");
    const drawerToggle = document.getElementById("toggle-drawer");
    const closeBtn = document.querySelector(".modal-close");
    const modal = document.getElementById("details-modal");
    if (baseUrlInput) {
        baseUrlInput.value = window.location.origin;
        if (clientIdInput) {
            clientIdInput.focus();
        }
    }
    closeBtn.onclick = closeModal;
    window.addEventListener("keydown", handleEscape);
    if (modal) {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
    }

    drawerToggle?.addEventListener("click", () => {
        drawer.classList.toggle("collapsed");
        mainContent.classList.toggle("collapsed");
    });

    const views = {
        home: document.getElementById("home-view"),
        tasks: document.getElementById("tasks-view"),
        "new-task": document.getElementById("new-task-view"),
        "task-chat-live": document.getElementById("task-chat-live-view"),
        "task-chat-static": document.getElementById("task-chat-static-view"),
    };

    const navLinks = {
        home: document.getElementById("home"),
        tasks: document.getElementById("tasks"),
        "new-task": document.getElementById("new-task"),
        logout: logoutLink,
        "task-chat-live": document.getElementById("task-chat-live-view"),
        "task-chat-static": document.getElementById("task-chat-static-view"),
    };

    function showView(viewId) {
        Object.entries(views).forEach(([id, el]) => {
            el.classList.toggle("hidden", id !== viewId);
            if (!id.startsWith("task-chat-")) {
                navLinks[id]?.classList.toggle("active", id === viewId);
            }
        });
        mainContent.scrollTop = 0;
        clearTaskQuery();
    }
    const focusableInputs = [baseUrlInput, clientIdInput, clientSecretInput];
    focusableInputs.forEach((input, index) => {
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const next = focusableInputs[index + 1];
                if (next) {
                    next.focus();
                } else {
                    authenticateBtn.click();
                }
            }
        });
    });
    authenticateBtn.addEventListener("click", async () => {
        const baseUrl = document.getElementById("base_url").value;
        const clientId = document.getElementById("client_id").value;
        const clientSecret = document.getElementById("client_secret").value;

        if (!baseUrl || !clientId || !clientSecret) {
            showSnackbar("Please fill in all fields", "warning", null, 4000);
            return;
        }

        authenticateBtn.disabled = true;
        authenticateBtn.textContent = "Authenticating...";

        window.initializeAuthManager(
            baseUrl,
            clientId,
            clientSecret,
            (error) => {
                showSnackbar(
                    "Authentication failed",
                    "error",
                    error.message,
                    6000,
                    true
                );
                authenticateBtn.disabled = false;
                authenticateBtn.textContent = "Authenticate";
                checkAuthentication();
            },
            () => {
                showSnackbar(
                    "Authenticated successfully!",
                    "success",
                    null,
                    4000
                );
                authenticateBtn.textContent = "Authenticate";
                authenticateBtn.disabled = false;
                checkAuthentication();
            }
        );

        try {
            await window.getAuthManager().authenticate();
        } catch {
            // already handled
        }
    });

    logoutLink.addEventListener("click", () => {
        window.destroyAuthManager();

        showSnackbar("Logged out", "success", null, 3000);
        checkAuthentication();
        showView("home");
    });

    Object.entries(views).forEach(([id]) => {
        const link = navLinks[id];
        if (link) {
            link.addEventListener("click", () => showView(id));
        }
    });

    document.querySelector(".modal-close").onclick = () => {
        document.getElementById("details-modal").classList.add("hidden");
        window.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                document
                    .getElementById("details-modal")
                    .classList.add("hidden");
            }
        });
    };

    checkAuthentication();

    if (window.getAuthManager()?.isAuthenticated()) {
        showView("home");
    } else {
        clearTaskQuery(); // just to be sure
    }
});
