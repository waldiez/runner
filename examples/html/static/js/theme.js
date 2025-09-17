const THEME_KEY = "preferred-theme";
const toggleBtn = document.getElementById("toggle-theme");

function setTheme(theme) {
    document.body.classList.remove("light", "dark");
    document.body.classList.add(theme);
    localStorage.setItem(THEME_KEY, theme);
    updateThemeIcon(theme);
}

function updateThemeIcon(theme) {
    toggleBtn.textContent = theme === "dark" ? "☀️" : "🌙";
}

function detectSystemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
}

function getStoredTheme() {
    return localStorage.getItem(THEME_KEY);
}

function toggleTheme() {
    const current = document.body.classList.contains("dark") ? "dark" : "light";
    const next = current === "dark" ? "light" : "dark";
    setTheme(next);
}

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    const saved = getStoredTheme() || detectSystemTheme();
    setTheme(saved);

    toggleBtn.addEventListener("click", toggleTheme);
});
