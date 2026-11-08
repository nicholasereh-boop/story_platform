// Plain-language helpers for the News screens (no React here, so they are easy to test).

// What each machine-readable blocker from the rights gate means for an editor.
export const BLOCKER_TEXT = {
  no_rights_record: "There is no approved rights record in force for this source.",
  source_not_approved: "The source is not approved.",
  source_inactive: "The source is switched off.",
  rights_not_in_force: "The rights record has not started yet or has ended.",
  record_belongs_to_another_source: "The rights record belongs to a different source.",
  metadata_only_source: "This source allows headlines and links only, not article text.",
  metadata_only_article: "This is a headline-and-link item, so it cannot be published as a full article.",
  title_missing: "Add a title.",
  body_missing: "Add the article text.",
  full_text_not_permitted: "The licence does not allow republishing the full text.",
  commercial_use_not_permitted: "The licence does not explicitly allow commercial use (the site shows advertising).",
  attribution_missing: "Attribution is missing. Fill in the source's attribution template.",
  edits_not_permitted: "The licence does not allow changes, but the text was edited. Restore the original text.",
  original_link_missing: "Add the link to the original article.",
  record_narrows_full_text: "Note: the rights record is narrower than the source on full text.",
  record_narrows_commercial_use: "Note: the rights record is narrower than the source on commercial use.",
};

export const explainBlocker = (code) => BLOCKER_TEXT[code] || String(code).replace(/_/g, " ");

export const STATUS_LABEL = {
  draft: "Draft", pending: "Waiting for review", scheduled: "Scheduled", published: "Published", rejected: "Rejected",
  withdrawn: "Withdrawn", quarantined: "Quarantined",
};

export const STATUS_TABS = [
  { value: "pending", label: "Review queue" }, { value: "draft", label: "Drafts" }, { value: "scheduled", label: "Scheduled" },
  { value: "published", label: "Published" }, { value: "quarantined", label: "Quarantined" }, { value: "rejected", label: "Rejected" },
  { value: "withdrawn", label: "Withdrawn" }, { value: "", label: "All" },
];

// The most useful sentence from a failed request: the server's own explanation first.
export function errorText(err, fallback = "Something went wrong. Please try again.") {
  const f = err?.fieldErrors || {};
  const first = (v) => (Array.isArray(v) ? v[0] : v);
  const detail = first(f.detail);
  if (detail) return String(detail);
  const blockers = Array.isArray(f.blockers) ? f.blockers : [];
  if (blockers.length) return blockers.map(explainBlocker).join(" ");
  const field = Object.keys(f).find((k) => k !== "blockers" && first(f[k]));
  return field ? `${field.replace(/_/g, " ")}: ${first(f[field])}` : err?.friendly || fallback;
}

export function formatDate(value, withTime = false) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("en-GB", withTime ? { dateStyle: "medium", timeStyle: "short" } : { dateStyle: "medium" });
}

// <input type="datetime-local"> value ("2026-11-06T14:30") to an ISO string, or "" when empty or invalid.
export function localToIso(value) {
  if (!value) return "";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "" : d.toISOString();
}
