// Phase 10 endpoints: public config and privacy policy, my data, my sessions, two-step verification, and (staff) users and
// the audit log. Same conventions as api/index.js: lists resolve to {items, pagination}, the rest to the bare data.
import { api, data, paged, publicApi } from "./client";

// ---- public (anonymous, no cookies)
export const getPublicConfig = () => publicApi.get("/public-config/").then(data); // {site_name, consent_mode, analytics_enabled, contact_email}
export const getPrivacyPolicy = () => publicApi.get("/privacy-policy/").then(data);

// ---- my data and my sessions
export const exportMyData = () => api.get("/auth/me/export/").then(data);
// Body: {password} for accounts with a password, {email} for Google-only accounts, plus {code} when two-step is on.
export const deleteMyAccount = (body) => api.delete("/auth/me/", { data: body }).then(data);
export const listMySessions = () => api.get("/auth/sessions/").then(data);
export const revokeAllSessions = () => api.post("/auth/sessions/revoke-all/").then(data);

// ---- two-step verification (staff)
export const mfaStatus = () => api.get("/auth/mfa/status/").then(data); // {enabled, verified, required, recovery_codes_left}
export const mfaSetup = () => api.post("/auth/mfa/setup/").then(data); // {secret, otpauth_uri}
export const mfaConfirm = (code) => api.post("/auth/mfa/confirm/", { code }).then(data); // {recovery_codes, ...}
export const mfaVerify = (body) => api.post("/auth/mfa/verify/", body).then(data); // {code} or {recovery_code}
export const mfaDisable = (body) => api.post("/auth/mfa/disable/", body).then(data); // {password, code}
export const mfaNewRecoveryCodes = (body) => api.post("/auth/mfa/recovery-codes/", body).then(data); // {password, code}

// ---- staff: users and audit log
export const listUsers = (params) => api.get("/admin/users/", { params }).then(paged);
export const patchUser = (id, body) => api.patch(`/admin/users/${id}/`, body).then(data); // only {is_active, is_staff}
export const revokeUserSessions = (id) => api.post(`/admin/users/${id}/revoke-sessions/`).then(data);
export const resendUserVerification = (id) => api.post(`/admin/users/${id}/resend-verification/`).then(data);
export const listAuditLogs = (params) => api.get("/admin/audit-logs/", { params }).then(paged);
