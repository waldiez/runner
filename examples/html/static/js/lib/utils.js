export async function fetchWithTimeout(
    resource,
    options = {},
    timeout = 30000
) {
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            reject(new Error("Request timed out"));
        }, timeout);

        (async () => {
            try {
                const response = await fetch(resource, options);
                clearTimeout(timer);

                if (!response.ok) {
                    let errorMessage = `Request failed with status ${response.status}`;

                    try {
                        const contentType =
                            response.headers.get("Content-Type") || "";
                        if (contentType.includes("application/json")) {
                            const data = await response.json();
                            errorMessage =
                                data.detail ||
                                data.message ||
                                JSON.stringify(data);
                        } else if (contentType.includes("text/")) {
                            const text = await response.text();
                            if (text) errorMessage = text;
                        }
                    } catch (err) {
                        console.warn("Failed to parse error body:", err);
                    }

                    const error = new Error(errorMessage);
                    error.status = response.status;
                    reject(error);
                    return;
                }

                resolve(response);
            } catch (error) {
                clearTimeout(timer);
                reject(error);
            }
        })();
    });
}
