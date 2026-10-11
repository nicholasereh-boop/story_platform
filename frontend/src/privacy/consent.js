// The visitor's analytics choice, kept ONLY in this browser (localStorage). The server never receives it as a record: in
// "opt_in" mode the tracker adds consent:true to each page view, and that is all the server ever learns.
//
// Modes (PRIVACY_CONSENT_MODE on the server, delivered by /api/v1/public-config/):
//   notice  no banner; counting is on unless the visitor switches it off in the footer (default)
//   opt_in  counting stays OFF until the visitor presses Accept
//   opt_out counting is on until the visitor presses Reject; a banner asks
export const CONSENT_KEY = "sb.consent";
export const CONSENT_MONTHS = 6;
const MONTH_MS = 30 * 24 * 60 * 60 * 1000;
export const CONSENT_TTL_MS = CONSENT_MONTHS * MONTH_MS;
export const MODES = ["notice", "opt_in", "opt_out"];

export const cleanMode = (mode) => (MODES.includes(mode) ? mode : "notice");

// Used ONLY when the browser refuses to store the choice (blocked storage): the choice then still holds until the page
// is closed, so a visitor who pressed Reject is not counted just because storage is blocked.
let memory = null;

function valid(parsed, now) {
  return Boolean(parsed) && (parsed.choice === "accepted" || parsed.choice === "rejected") && typeof parsed.at === "number" && now - parsed.at <= CONSENT_TTL_MS && parsed.at <= now + 60_000;
}

/** "accepted" | "rejected" | null (no choice yet, expired, unreadable or storage blocked). Never throws. */
export function readConsent(now = Date.now()) {
  try {
    const raw = window.localStorage.getItem(CONSENT_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (valid(parsed, now)) return parsed.choice;
    if (raw) window.localStorage.removeItem(CONSENT_KEY); // expired, garbage or from the future: ask again
  } catch {
    /* storage blocked or unreadable: fall through to the in-memory copy */
  }
  return valid(memory, now) ? memory.choice : null;
}

/** Remember the choice for six months. Returns false when the browser would not store it (the choice then lasts for this page). */
export function writeConsent(choice, now = Date.now()) {
  try {
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ choice, at: now }));
    memory = null;
    return true;
  } catch {
    memory = { choice, at: now };
    return false;
  }
}

export function clearConsent() {
  memory = null;
  try {
    window.localStorage.removeItem(CONSENT_KEY);
  } catch {
    /* nothing to clear */
  }
}

/** May analytics run, judging by the mode and the visitor's choice alone? (DNT/GPC and the footer switch are separate checks.) */
export function consentAllows(mode, choice) {
  switch (cleanMode(mode)) {
    case "opt_in":
      return choice === "accepted";
    case "opt_out":
      return choice !== "rejected";
    default:
      return true;
  }
}

/** Must the banner be shown? Only for the two banner modes, and only while there is no remembered choice. */
export const needsChoice = (mode, choice) => cleanMode(mode) !== "notice" && choice === null;
