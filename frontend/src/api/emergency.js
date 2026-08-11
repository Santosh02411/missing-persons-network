import axios from "axios";

// Deliberately a plain axios call, not the shared apiClient -- this
// endpoint is intentionally public (no auth header needed, and it must
// still work for a signed-out visitor), so it shouldn't go through the
// same interceptor that attaches a bearer token / redirects to login on 401.
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export function getEmergencyContacts() {
  return axios.get(`${API_BASE}/emergency-contacts`);
}
