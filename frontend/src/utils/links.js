// Link rules. Same as the server: http, https or mailto only, no whitespace or control characters, <= 2000 chars.
const ALLOWED = /^(https?:\/\/|mailto:)/i;
const BAD_CHARS = /[\s\u0000-\u001f\u007f]/;

/** True when `href` may be stored/rendered as a link. Deliberately strict: nothing is trimmed or "fixed" here. */
export function isSafeHref(href) {
  if (typeof href !== "string" || href.length === 0 || href.length > 2000) return false;
  if (BAD_CHARS.test(href)) return false;
  return ALLOWED.test(href);
}

/**
 * Turn what a person typed into a safe href, or null.
 *   "example.com"        -> "https://example.com"
 *   "me@example.com"     -> "mailto:me@example.com"
 *   "javascript:alert()" -> null
 */
export function normalizeLink(input) {
  const text = String(input ?? "").trim();
  if (!text) return null;
  let candidate = text;
  if (!/^[a-z][a-z0-9+.-]*:/i.test(text)) {
    candidate = /^[^\s/@]+@[^\s/@]+$/.test(text) ? `mailto:${text}` : `https://${text}`;
  }
  return isSafeHref(candidate) ? candidate : null;
}
