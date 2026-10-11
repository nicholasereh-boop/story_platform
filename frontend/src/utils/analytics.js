import { format, parseISO } from "date-fns";

// The six numbers shown as tiles, in display order.
export const KPIS = [
  { key: "unique_visitors", label: "Visitors" },
  { key: "page_views", label: "Page views" },
  { key: "story_views", label: "Story views" },
  { key: "registered_users", label: "New accounts" },
  { key: "likes", label: "Likes" },
  { key: "comments", label: "Comments" },
];

// Change versus the previous period, as text that does not rely on colour: an arrow AND words.
//   null / undefined -> nothing to compare with
export function formatChange(pct) {
  if (pct === null || pct === undefined) {
    return { direction: "none", text: "No previous data", spoken: "No previous data to compare with" };
  }
  if (pct === 0) return { direction: "flat", text: "No change", spoken: "No change from the previous period" };
  const size = `${Math.abs(pct).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
  return pct > 0
    ? { direction: "up", text: `▲ ${size}`, spoken: `Up ${size} from the previous period` }
    : { direction: "down", text: `▼ ${size}`, spoken: `Down ${size} from the previous period` };
}

// Axis / table label for the start date of a day, week or month point.
export function pointLabel(iso, granularity) {
  const date = parseISO(iso);
  if (granularity === "month") return format(date, "MMM yyyy");
  if (granularity === "week") return `Week of ${format(date, "MMM d")}`;
  return format(date, "MMM d");
}

export const DEVICE_LABELS = { desktop: "Desktop", mobile: "Mobile", tablet: "Tablet", other: "Other" };

// Share of the total as a whole percent (0 when there is nothing).
export const share = (value, total) => (total > 0 ? Math.round((value / total) * 100) : 0);
