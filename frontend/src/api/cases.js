import { apiClient } from "./client";

export function listCases({ status, limit = 20, offset = 0 } = {}) {
  return apiClient.get("/cases", { params: { status, limit, offset } });
}

export function getCase(caseId) {
  return apiClient.get(`/cases/${caseId}`);
}

export function createCase(payload) {
  return apiClient.post("/cases", payload);
}

export function updateCase(caseId, payload) {
  return apiClient.patch(`/cases/${caseId}`, payload);
}

export function claimCase(caseId) {
  return apiClient.post(`/cases/${caseId}/claim`);
}

export function updateCaseStatus(caseId, status) {
  return apiClient.patch(`/cases/${caseId}/status`, { status });
}

export function assignedToMe() {
  return apiClient.get("/cases/assigned-to-me");
}

export function pendingApprovalCases() {
  return apiClient.get("/cases/pending-approval");
}

export function myCases() {
  return apiClient.get("/cases/mine");
}

export function approveCase(caseId) {
  return apiClient.post(`/cases/${caseId}/approve`);
}

export function dismissCase(caseId) {
  return apiClient.post(`/cases/${caseId}/dismiss`);
}

export function nearbyCases({ lat, lng, radius_km = 10, limit = 50 }) {
  return apiClient.get("/cases/nearby", { params: { lat, lng, radius_km, limit } });
}
