// Pure helpers for the audit-log screen.

// Action families offered in the filter. "story.*" matches every story event (the server understands the trailing star).
export const ACTION_FAMILIES = [
  { value: "", label: "All actions" },
  { value: "story.*", label: "Stories" },
  { value: "category.*", label: "Categories" },
  { value: "tag.*", label: "Tags" },
  { value: "media.*", label: "Media" },
  { value: "comment.*", label: "Comments" },
  { value: "settings.*", label: "Settings" },
  { value: "analytics.*", label: "Analytics" },
  { value: "audit.*", label: "Audit log" },
  { value: "user.*", label: "Users" },
  { value: "auth.*", label: "Staff logins" },
  { value: "mfa.*", label: "Two-step verification" },
];

const shorten = (text, max = 80) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

// One metadata value as short plain text: [a, b] -> "a → b", {k: v} -> "k: v, ...", null -> "none".
export function formatValue(value) {
  if (value === null || value === undefined) return "none";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) {
    if (value.length === 2 && value.every((v) => v === null || ["string", "number", "boolean"].includes(typeof v))) {
      return `${formatValue(value[0])} → ${formatValue(value[1])}`;
    }
    return shorten(value.map(formatValue).join(", "));
  }
  if (typeof value === "object") return shorten(Object.entries(value).map(([k, v]) => `${k}: ${formatValue(v)}`).join(", "));
  return shorten(String(value));
}

// metadata object -> [{key, text}] for display. Always text (React escapes it); never HTML.
export function describeMetadata(metadata) {
  if (!metadata || typeof metadata !== "object") return [];
  return Object.entries(metadata).map(([key, value]) => ({ key: key.replace(/_/g, " "), text: formatValue(value) }));
}

// Only send the filters that have a value (an empty string would be a different question to the server).
export function cleanParams(filters, page) {
  const params = {};
  for (const [key, value] of Object.entries(filters)) {
    const text = String(value ?? "").trim();
    if (text) params[key] = text;
  }
  if (page > 1) params.page = page;
  return params;
}
