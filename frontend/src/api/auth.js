import { apiClient } from "./client";

export function registerAccount({ email, password, full_name, role, org_name, jurisdiction_location }) {
  return apiClient.post("/auth/register", {
    email,
    password,
    full_name,
    role,
    org_name,
    jurisdiction_location,
  });
}

export function updateJurisdiction(jurisdiction_location) {
  return apiClient.patch("/auth/me/jurisdiction", { jurisdiction_location });
}

export function updateAlertPreferences(payload) {
  return apiClient.patch("/auth/me/alert-preferences", payload);
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

export function verifyEmail(token) {
  return apiClient.post("/auth/verify-email", { token });
}

export function resendVerification() {
  return apiClient.post("/auth/resend-verification");
}

export function forgotPassword(email) {
  return apiClient.post("/auth/forgot-password", { email });
}

export function resetPassword(token, new_password) {
  return apiClient.post("/auth/reset-password", { token, new_password });
}

export function loginWith2FA(mfa_token, code) {
  return apiClient.post("/auth/2fa/login", { mfa_token, code });
}

export function resendMfaCode(mfa_token) {
  return apiClient.post("/auth/2fa/resend", { mfa_token });
}

export function setup2FA() {
  return apiClient.post("/auth/2fa/setup");
}

export function verify2FASetup(code) {
  return apiClient.post("/auth/2fa/verify", { code });
}

export function disable2FA(code) {
  return apiClient.post("/auth/2fa/disable", { code });
}

export function setupEmailOtp() {
  return apiClient.post("/auth/2fa/email-otp/setup");
}

export function verifyEmailOtpSetup(code) {
  return apiClient.post("/auth/2fa/email-otp/verify", { code });
}

export function disableEmailOtp() {
  return apiClient.post("/auth/2fa/email-otp/disable");
}

export function setupSmsOtp(phone_number) {
  return apiClient.post("/auth/2fa/sms-otp/setup", { phone_number });
}

export function verifySmsOtpSetup(code) {
  return apiClient.post("/auth/2fa/sms-otp/verify", { code });
}

export function disableSmsOtp() {
  return apiClient.post("/auth/2fa/sms-otp/disable");
}

export function listSessions() {
  return apiClient.get("/auth/sessions");
}

export function deleteSession(sessionId) {
  return apiClient.delete(`/auth/sessions/${sessionId}`);
}

export function logoutAll() {
  return apiClient.post("/auth/logout-all");
}
