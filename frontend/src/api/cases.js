import { apiClient } from "./client";

export function listCases({
  status,
  limit = 20,
  offset = 0,
  gender,
  age_min,
  age_max,
  last_seen_after,
  last_seen_before,
  region,
} = {}) {
  return apiClient.get("/cases", {
    params: { status, limit, offset, gender, age_min, age_max, last_seen_after, last_seen_before, region },
  });
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

export function shareCase(caseId, payload) {
  return apiClient.post(`/cases/${caseId}/share`, payload);
}

export function getCaseFlyer(caseId) {
  return apiClient.get(`/cases/${caseId}/flyer`, { responseType: "blob" });
}

export function getWatchStatus(caseId) {
  return apiClient.get(`/cases/${caseId}/watch`);
}

export function watchCase(caseId) {
  return apiClient.post(`/cases/${caseId}/watch`);
}

export function unwatchCase(caseId) {
  return apiClient.delete(`/cases/${caseId}/watch`);
}

export function watchedCases() {
  return apiClient.get("/cases/watched");
}

export function getCaseNotes(caseId) {
  return apiClient.get(`/cases/${caseId}/notes`);
}

export function addCaseNote(caseId, body) {
  return apiClient.post(`/cases/${caseId}/notes`, { body });
}

export function getCaseCollaborators(caseId) {
  return apiClient.get(`/cases/${caseId}/collaborators`);
}

export function addCaseCollaborator(caseId, authorityId) {
  return apiClient.post(`/cases/${caseId}/collaborators`, { authority_id: authorityId });
}

export function removeCaseCollaborator(caseId, userId) {
  return apiClient.delete(`/cases/${caseId}/collaborators/${userId}`);
}

export function checkDuplicates(payload) {
  return apiClient.post("/cases/check-duplicates", payload);
}

export function bulkImportCases(file) {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient.post("/cases/bulk-import", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export function updateAgeProgression(caseId, payload) {
  return apiClient.patch(`/cases/${caseId}/age-progression`, payload);
}

export function reopenCase(caseId, reason) {
  return apiClient.post(`/cases/${caseId}/reopen`, { reason });
}

export function sendCaseAlert(caseId) {
  return apiClient.post(`/cases/${caseId}/alert`);
}
