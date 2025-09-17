export function showSnackbar(
    message,
    level = "info",
    details = null,
    duration,
    includeCloseButton = false
) {
    const existing = document.querySelector(".snackbar");
    if (existing) existing.remove();

    const snackbar = document.createElement("div");
    // if not close button, let's have a default duration
    let snackbarDuration = duration;
    if (!includeCloseButton && !snackbarDuration) {
        snackbarDuration = 3000;
    }
    snackbar.className = `snackbar ${level}`;
    snackbar.innerHTML = `
  <div class="snackbar-header">
    <div class="message">${message}</div>
    ${
        includeCloseButton
            ? `<div class="close clickable" title="Close">&times;</div>`
            : ""
    }
  </div>
  ${
      details
          ? `<details class="snackbar-details">
           <summary>Details</summary>
           <div class="details-text">${
               typeof details === "string" ? details : details.message
           }</div>
         </details>`
          : ""
  }
`;

    document.body.appendChild(snackbar);

    const closeBtn = snackbar.querySelector(".close");
    if (closeBtn) {
        closeBtn.onclick = () => snackbar.remove();
    }

    if (snackbarDuration && !includeCloseButton) {
        setTimeout(() => snackbar.remove(), snackbarDuration);
    }
}
