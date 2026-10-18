import axios from "axios";

export const MFA_EVENT = "sb:mfa-needed";
const MFA_CODES = ["mfa_required", "mfa_setup_required"];

// The "code" field of a 403 body, when it is one of the two-step codes (string or one-item list).
export function mfaCodeOf(fieldErrors) {
  const raw = fieldErrors?.code;
  const value = Array.isArray(raw) ? raw[0] : raw;
  return MFA_CODES.includes(value) ? value : null;
}

// Turn the server's {data, errors, message} envelope into something easy to show.
//   err.friendly    one sentence for the user
//   err.fieldErrors {field: ["message", ...]} for form fields
//   err.status      HTTP status (undefined = the server could not be reached)
function normalizeError(err) {
  const body = err.response?.data;
  err.status = err.response?.status;
  err.friendly =
    (body && typeof body.message === "string" && body.message) ||
    (err.response ? "Something went wrong. Please try again." : "Cannot reach the server. Is the backend running?");
  err.fieldErrors = body && body.errors && typeof body.errors === "object" ? body.errors : {};
  // Two-step verification: the server answers 403 with a machine-readable code (see backend core/permissions.py).
  err.code = mfaCodeOf(err.fieldErrors);
  if (err.code && typeof window !== "undefined") {
    // Tell the app (AuthContext listens) that this session needs a code or the setup screen.
    window.dispatchEvent(new CustomEvent(MFA_EVENT, { detail: err.code }));
  }
  return Promise.reject(err);
}

// Admin client: all requests go to /api/v1 on the same origin (Vite proxies it to Django in development)
// and carry the session cookie + CSRF header.
export const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
  xsrfCookieName: "csrftoken", // Django's CSRF cookie ...
  xsrfHeaderName: "X-CSRFToken", // ... sent back in this header on every unsafe request
  withXSRFToken: true,
});
api.interceptors.response.use((res) => res, normalizeError);

// Public client: anonymous reads only. No cookies, no CSRF, so it works for visitors who never log in and keeps
// working even if the login/CSRF calls fail.
export const publicApi = axios.create({ baseURL: "/api/v1" });
publicApi.interceptors.response.use((res) => res, normalizeError);

export const data = (res) => res.data.data;
export const paged = (res) => ({ items: res.data.data, pagination: res.data.pagination });
export const ensureCsrf = () => api.get("/auth/csrf/");
