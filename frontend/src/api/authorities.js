import { apiClient } from "./client";

export function nearbyAuthorities({ lat, lng, radius_km = 100, limit = 10 }) {
  return apiClient.get("/authorities/nearby", { params: { lat, lng, radius_km, limit } });
}

export function searchAuthorities(q) {
  return apiClient.get("/authorities/search", { params: { q } });
}
