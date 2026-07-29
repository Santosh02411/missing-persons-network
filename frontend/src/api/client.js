import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

// Tokens live in memory + localStorage (see context/AuthContext.jsx for the
// tradeoffs of that choice, called out explicitly there). This module just
// needs read/write access to them without importing the context (avoids a
// circular import), hence the small local get/set helpers.
const ACCESS_TOKEN_KEY = "mpn_access_token";
const REFRESH_TOKEN_KEY = "mpn_refresh_token";

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}
export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}
export function setTokens({ access_token, refresh_token }) {
  localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token);
}
export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export const apiClient = axios.create({ baseURL: API_BASE_URL });

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Single in-flight refresh promise shared across concurrent 401s, so five
// requests failing at once don't trigger five separate refresh calls.
let refreshPromise = null;

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error;
    const isAuthRoute = config?.url?.includes("/auth/");

    if (response?.status === 401 && !config._retried && !isAuthRoute) {
      config._retried = true;
      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        clearTokens();
        return Promise.reject(error);
      }

      try {
        if (!refreshPromise) {
          refreshPromise = axios
            .post(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken })
            .finally(() => {
              refreshPromise = null;
            });
        }
        const { data } = await refreshPromise;
        setTokens(data);
        config.headers.Authorization = `Bearer ${data.access_token}`;
        return apiClient(config);
      } catch (refreshError) {
        clearTokens();
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

/** Pulls a readable message out of a FastAPI error response. */
export function extractErrorMessage(error, fallback = "Something went wrong. Please try again.") {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // Pydantic validation errors: [{loc, msg, type}, ...]
    return detail.map((d) => d.msg).join(" ");
  }
  return fallback;
}
