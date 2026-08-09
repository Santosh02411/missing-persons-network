import { apiClient } from "./client";

export function getAnalyticsOverview() {
  return apiClient.get("/admin/analytics/overview");
}

export function getAnalyticsVolume(weeks = 12) {
  return apiClient.get("/admin/analytics/volume", { params: { weeks } });
}

export function getAnalyticsHeatmap() {
  return apiClient.get("/admin/analytics/heatmap");
}
