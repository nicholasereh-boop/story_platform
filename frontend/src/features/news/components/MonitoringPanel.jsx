import { useQuery } from "@tanstack/react-query";
import { getMonitoring } from "../api/newsroom";

// A small health strip at the top of the newsroom: counts, and a plain sentence for every problem. Quiet when all is well.
export default function MonitoringPanel() {
  const q = useQuery({ queryKey: ["newsroom", "monitoring"], queryFn: getMonitoring, refetchInterval: 120_000, retry: false });
  if (!q.data) return null;
  const { articles, open_complaints: complaints, pending_comments: comments, alerts } = q.data;
  return (
    <section className="nw-health" aria-label="Newsroom health">
      <p className="nw-muted">
        {articles.published} live · {articles.pending} waiting for review · {articles.scheduled} scheduled · {complaints} open complaint(s) · {comments} comment(s) waiting
      </p>
      {alerts.length === 0 ? <p className="nw-ok">Everything looks healthy.</p> : (
        <ul className="nw-alerts">{alerts.map((a) => <li key={`${a.code}-${a.message}`} className={a.level === "error" ? "nw-error" : "nw-warn"}>{a.message}</li>)}</ul>
      )}
    </section>
  );
}
