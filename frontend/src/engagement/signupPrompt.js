// Rules and storage for the "join us" prompt shown to anonymous visitors. Pure functions, easy to test.
//
// Nothing here tracks anyone: the only things stored are (1) a number of page views in sessionStorage and
// (2) the time until which the prompt stays quiet after a visitor closed it (localStorage, 14 days).
// EVERY storage access is wrapped in try/catch: private mode, blocked storage or a full quota must never crash the page.
export const DISMISS_KEY = "sb.signup-prompt.quiet-until";
export const VIEWS_KEY = "sb.page-views";
export const DISMISS_DAYS = 14;
export const VIEWS_TRIGGER = 3; // the prompt may appear on the 3rd page view of a session
export const READ_TRIGGER = 0.6; // ... or after about 60% of a story has been read

const DAY_MS = 24 * 60 * 60 * 1000;

// Pages where the prompt must never appear.
const BLOCKED_PREFIXES = ["/login", "/register", "/forgot-password", "/reset-password", "/verify-email", "/admin"];

export function isBlockedPath(pathname) {
  return BLOCKED_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

// True while the 14-day quiet period is running. An expired or unreadable flag counts as "not dismissed".
export function isDismissed(now = Date.now()) {
  try {
    const raw = window.localStorage.getItem(DISMISS_KEY);
    if (!raw) return false;
    const until = Number(raw);
    if (Number.isFinite(until) && until > now) return true;
    window.localStorage.removeItem(DISMISS_KEY); // expired (or garbage): clean up
    return false;
  } catch {
    return false;
  }
}

// Start the quiet period. Returns false if the browser would not store it (the caller then remembers it in memory).
export function dismiss(now = Date.now()) {
  try {
    window.localStorage.setItem(DISMISS_KEY, String(now + DISMISS_DAYS * DAY_MS));
    return true;
  } catch {
    return false;
  }
}

// Count one page view for this browser session and return the new total. Falls back to an in-memory
// counter when sessionStorage is unavailable, so the rule still works for the lifetime of the page.
let memoryViews = 0;
export function recordPageView() {
  try {
    const next = (Number(window.sessionStorage.getItem(VIEWS_KEY)) || 0) + 1;
    window.sessionStorage.setItem(VIEWS_KEY, String(next));
    return next;
  } catch {
    memoryViews += 1;
    return memoryViews;
  }
}

// Test helper: forget the in-memory fallback counter.
export function resetMemoryViews() {
  memoryViews = 0;
}
