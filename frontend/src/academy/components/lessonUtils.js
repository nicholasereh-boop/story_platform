// Small display helpers for lessons and courses.
export function formatDuration(seconds) {
  const s = Number(seconds) || 0;
  if (s <= 0) return "";
  const m = Math.round(s / 60);
  if (m < 60) return `${Math.max(1, m)} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? `${h} h ${rest} min` : `${h} h`;
}

export const STATE_LABEL = {
  completed: "Completed",
  awaiting_comment: "Comment to unlock the next lesson",
  in_progress: "In progress",
  available: "Ready",
  locked: "Locked",
};
export const STATE_ICON = { completed: "✓", awaiting_comment: "💬", in_progress: "▶", available: "▶", locked: "🔒" };

export const REASON_TEXT = {
  login_required: "Log in to open this lesson.",
  locked_previous: "Finish the previous lesson (watch it, then comment) to open this one.",
  purchase_required: "Buy this course to open this lesson.",
};

export const kindOf = (course) => (course.access_type === "paid" ? "paid" : "free");
export const courseUrl = (course) => `/academy/${kindOf(course)}/courses/${course.slug}`;