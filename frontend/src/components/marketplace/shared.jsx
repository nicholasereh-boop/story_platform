import { formatPrice } from "../../utils/money";

const STATUS_LABELS = {
  draft: "Draft", pending: "Waiting for review", published: "Published", rejected: "Needs changes", archived: "Archived",
  success: "Paid", failed: "Failed",
};

export function ProjectStatus({ status }) {
  return <span className={`mp-status ${status}`}>{STATUS_LABELS[status] || status}</span>;
}

// Only our own images (relative) or absolute http(s) addresses (object storage / CDN) may be shown.
export function safeImageSrc(src) {
  return typeof src === "string" && (/^\/(?!\/)/.test(src) || /^https?:\/\//i.test(src)) ? src : null;
}

export const KIND_LABELS = { frontend: "Frontend", backend: "Backend" };

export function PriceTag({ offer }) {
  return (
    <span className={`mp-price${offer.is_free ? " free" : ""}`}>
      {KIND_LABELS[offer.kind] || offer.kind} · {formatPrice(offer.price, offer.currency)}
    </span>
  );
}

// The first message the server gave for a form field, else the general one.
export function firstError(err, ...fields) {
  for (const f of fields) {
    const v = err?.fieldErrors?.[f];
    const text = Array.isArray(v) ? v[0] : v;
    if (typeof text === "string" && text) return text;
  }
  const any = Object.values(err?.fieldErrors || {}).flat().find((x) => typeof x === "string");
  return any || err?.friendly || "Something went wrong. Please try again.";
}
