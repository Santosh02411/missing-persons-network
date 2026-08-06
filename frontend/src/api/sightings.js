import { apiClient } from "./client";

export function submitSighting(payload) {
  return apiClient.post("/sightings", payload);
}

export function listSightingsForCase(caseId) {
  return apiClient.get(`/sightings/case/${caseId}`);
}

export function reviewSighting(sightingId, status) {
  return apiClient.patch(`/sightings/${sightingId}/review`, { status });
}

export function pendingSightings({ limit = 50, offset = 0 } = {}) {
  return apiClient.get("/sightings/pending", { params: { limit, offset } });
}

export function mySightings() {
  return apiClient.get("/sightings/mine");
}

export function nearbySightings({ lat, lng, radius_km = 5, limit = 50 }) {
  return apiClient.get("/sightings/nearby", { params: { lat, lng, radius_km, limit } });
}
