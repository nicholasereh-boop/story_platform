import { format } from "date-fns";

export const fmtDate = (iso) => (iso ? format(new Date(iso), "MMM d, yyyy") : "");
export const fmtDateTime = (iso) => (iso ? format(new Date(iso), "MMM d, yyyy h:mm a") : "");
export const fmtClock = (ms) => format(new Date(ms), "HH:mm");
export const num = (n) => new Intl.NumberFormat().format(n ?? 0);

export function fileSize(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} bytes`;
}

// Value for <input type="datetime-local"> one hour from now (local time).
export function defaultScheduleValue() {
  const d = new Date(Date.now() + 60 * 60 * 1000);
  d.setMinutes(0, 0, 0);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// First readable message for one of several field names in err.fieldErrors ({field: ["msg"] | "msg"}).
export function fieldMessage(err, ...names) {
  for (const name of names) {
    const value = err?.fieldErrors?.[name];
    if (Array.isArray(value) && value.length && value.every((v) => typeof v === "string")) return value.join(" ");
    if (typeof value === "string") return value;
  }
  return null;
}
