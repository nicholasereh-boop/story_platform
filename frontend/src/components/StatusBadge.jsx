const LABELS = { draft: "Draft", scheduled: "Scheduled", published: "Published", archived: "Archived" };

export default function StatusBadge({ status }) {
  return <span className={`badge ${status}`}>{LABELS[status] || status}</span>;
}
