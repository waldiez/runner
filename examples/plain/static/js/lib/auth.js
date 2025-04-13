import { fetchWithTimeout } from "./utils.js";

export class AuthManager {
  constructor(baseUrl, clientId, clientSecret, onError = () => {}, onSuccess = () => {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.clientId = clientId;
    this.clientSecret = clientSecret;
    this.tokenData = null;
    this.onError = onError;
    this.onSuccess = onSuccess;
  }

  async authenticate() {
    try {
      const url = `${this.baseUrl}/auth/token`;
      const body = new URLSearchParams({
        client_id: this.clientId,
        client_secret: this.clientSecret,
      });

      const res = await fetchWithTimeout(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body,
      });

      if (!res.ok) throw new Error(`Auth failed: ${res.status}`);

      const data = await res.json();
      this.tokenData = this._parseTokenData(data);

      if (this.tokenData.audience !== "tasks-api") {
        throw new Error("Invalid audience: expected 'tasks-api'");
      }

      this.onSuccess(this.tokenData);
    } catch (err) {
      this.onError(err);
      this.tokenData = null;
    }
  }

  async refreshAccessToken() {
    if (!this.tokenData?.refresh_token) throw new Error("Missing refresh token");

    const url = `${this.baseUrl}/auth/token/refresh`;
    const body = new URLSearchParams({
      refresh_token: this.tokenData.refresh_token,
    });

    const res = await fetchWithTimeout(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
    });

    if (!res.ok) throw new Error(`Refresh failed: ${res.status}`);

    const data = await res.json();
    this.tokenData = this._parseTokenData(data);

    if (this.tokenData.audience !== "tasks-api") {
      throw new Error("Invalid audience after refresh");
    }
  }

  async getToken() {
    if (!this.tokenData) {
      throw new Error("Not authenticated");
    }

    if (this.isTokenExpired()) {
      await this.refreshAccessToken();
    }

    return this.tokenData.access_token;
  }

  isAuthenticated() {
    return this.tokenData && !this.isTokenExpired() && this.tokenData.audience === "tasks-api";
  }

  isTokenExpired() {
    if (!this.tokenData?.expires_at) return true;
    return new Date(this.tokenData.expires_at) <= new Date();
  }

  logout() {
    this.tokenData = null;
  }

  _parseTokenData(data) {
    return {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      token_type: data.token_type,
      expires_at: data.expires_at,
      refresh_expires_at: data.refresh_expires_at,
      audience: data.audience,
    };
  }
}
