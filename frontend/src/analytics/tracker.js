import { cleanMode, consentAllows, readConsent } from "../privacy/consent";

// First-party page-view tracking. Privacy rules (docs/ANALYTICS.md):
//   - no cookies: a random visitor id lives in localStorage, a random session id in sessionStorage;
//   - nothing is sent when the browser says Do Not Track / Global Privacy Control, or the visitor switched analytics off;
//   - in consent mode "opt_in" nothing is sent until the visitor accepted; in "opt_out" nothing after they rejected (Phase 10);
//   - nothing is sent for the admin, login/sign-up/password pages or /account;
//   - only the PATH is sent (never the query string), plus the referrer the browser reports for the first page of a visit.
// EVERY storage access is wrapped in try/catch: blocked storage must never break the page or the tracking rule.
export const VISITOR_KEY = "sb.visitor-id";
export const SESSION_KEY = "sb.session-id";
export const OPT_OUT_KEY = "sb.analytics-off";
export const COLLECT_URL = "/api/v1/analytics/collect/";

// What the server said about this site (from /api/v1/public-config/): the consent mode and whether analytics are on at all.
// Until the app has loaded it, nothing is sent (useTracker waits).
let runtime = { mode: "notice", enabled: true };
export function configureTracker({ mode, enabled }) {
  runtime = { mode: cleanMode(mode), enabled: enabled !== false };
}

// Pages that are never tracked (the server ignores them too).
const EXCLUDED_PREFIXES = ["/admin", "/login", "/register", "/forgot-password", "/reset-password", "/verify-email", "/account"];

export function isExcludedPath(pathname) {
  return EXCLUDED_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

// The browser asks not to be tracked (Do Not Track or Global Privacy Control).
export function browserSaysNo() {
  if (typeof navigator === "undefined") return false;
  const dnt = navigator.doNotTrack ?? window.doNotTrack ?? navigator.msDoNotTrack;
  return dnt === "1" || dnt === "yes" || navigator.globalPrivacyControl === true;
}

// The visitor switched analytics off with the footer toggle.
export function isOptedOut() {
  try {
    return window.localStorage.getItem(OPT_OUT_KEY) === "1";
  } catch {
    return false;
  }
}

// Returns false when the browser would not store the choice (the toggle then only lasts for this page).
export function setOptedOut(off) {
  try {
    if (off) window.localStorage.setItem(OPT_OUT_KEY, "1");
    else window.localStorage.removeItem(OPT_OUT_KEY);
    return true;
  } catch {
    return false;
  }
}

// All the reasons not to track, in one place: the site setting, the browser's signals, the footer switch and the consent choice.
export function trackingAllowed() {
  return runtime.enabled && !browserSaysNo() && !isOptedOut() && consentAllows(runtime.mode, readConsent());
}

function randomId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // Older browsers: a UUID-shaped random string (the server only checks the shape).
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    return (c === "x" ? r : (r & 3) | 8).toString(16);
  });
}

function storedId(storage, key) {
  try {
    const existing = window[storage].getItem(key);
    if (existing) return existing;
    const fresh = randomId();
    window[storage].setItem(key, fresh);
    return fresh;
  } catch {
    return randomId(); // storage blocked: this view counts as a one-off anonymous visit
  }
}

export const getVisitorId = () => storedId("localStorage", VISITOR_KEY);
export const getSessionId = () => storedId("sessionStorage", SESSION_KEY);

// Send one page view. Never throws, never retries, never waits: analytics must not slow down or break the site.
export function sendPageView({ pathname, referrer = "" }) {
  try {
    const payload = { path: pathname, visitor_id: getVisitorId(), session_id: getSessionId(), referrer };
    if (runtime.mode === "opt_in") payload.consent = true; // the server ignores events without it in this mode
    const body = JSON.stringify(payload);
    if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
      const queued = navigator.sendBeacon(COLLECT_URL, new Blob([body], { type: "application/json" }));
      if (queued) return;
    }
    if (typeof fetch === "function") {
      fetch(COLLECT_URL, { method: "POST", body, keepalive: true, headers: { "Content-Type": "application/json" } }).catch(() => {});
    }
  } catch {
    /* ignore: a failed page-view event is simply lost */
  }
}
