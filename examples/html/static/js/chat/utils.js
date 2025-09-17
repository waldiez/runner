export const USER_COLOR = "rgb(96, 96, 255)";
export const IMG_DIR = "/static/img/";
export const avatarColors = [
    "rgb(163, 82, 224)",
    "rgb(82, 224, 122)",
    "rgb(82, 205, 224)",
    "rgb(255, 149, 0)",
    "rgb(255, 80, 80)",
    "rgb(80, 130, 255)",
    "rgb(255, 204, 0)",
];
export const tryParse = (data) => {
    try {
        if (typeof data === "object" && data !== null && data !== undefined) {
            return data;
        }
        return JSON.parse(data);
    } catch {
        return null;
    }
};
export const getColorForParticipant = (name) => {
    let sum = 0;
    for (const ch of name || "") sum += ch.charCodeAt(0);
    return avatarColors[sum % avatarColors.length];
};

export const escapeHtml = (text) => {
    if (text === "<i>Empty message</i>") return text;
    const div = document.createElement("div");
    div.innerText = text;
    return div.innerHTML;
};
