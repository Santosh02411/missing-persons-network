import { apiClient } from "./client";

export function listAuthorityRequests() {
  return apiClient.get("/admin/authority-requests");
}

export function approveAuthorityRequest(userId) {
  return apiClient.post(`/admin/authority-requests/${userId}/approve`);
}

export function listAuditLogs({ targetType, limit = 50, offset = 0 } = {}) {
  return apiClient.get("/admin/audit-logs", {
    params: { target_type: targetType, limit, offset },
  });
}
