import { apiClient } from "./client";

export function registerAccount({ email, password, full_name, role, org_name }) {
  return apiClient.post("/auth/register", { email, password, full_name, role, org_name });
}

export function login({ email, password }) {
  return apiClient.post("/auth/login", { email, password });
}

export function logout() {
  return apiClient.post("/auth/logout");
}

export function fetchCurrentUser() {
  return apiClient.get("/auth/me");
}
