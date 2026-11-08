import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import Pagination from "../../../components/Pagination";
import { listNewsroom } from "../api/newsroom";
import MonitoringPanel from "../components/MonitoringPanel";
import NewsroomTabs from "../components/NewsroomTabs";
import { STATUS_LABEL, STATUS_TABS, formatDate } from "../utils/text";
import "../news.css";

export default function NewsroomPage() {
  const [status, setStatus] = useState("pending");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const list = useQuery({
    queryKey: ["newsroom", "articles", { status, q, page }],
    queryFn: () => listNewsroom({ page, ...(status ? { status } : {}), ...(q.trim() ? { q: q.trim() } : {}) }),
    placeholderData: (previous) => previous,
  });
  const items = list.data?.items || [];
  return (
    <div className="nw-admin">
      <div className="nw-admin-head">
        <h1>Newsroom</h1>
        <Link to="/admin/news/articles/new" className="btn">New article</Link>
      </div>
      <NewsroomTabs />
      <MonitoringPanel />
      <div className="nw-status-tabs" role="tablist" aria-label="Article status">
        {STATUS_TABS.map((t) => (
          <button key={t.value || "all"} type="button" role="tab" aria-selected={status === t.value} className={status === t.value ? "nw-pill is-active" : "nw-pill"} onClick={() => { setStatus(t.value); setPage(1); }}>{t.label}</button>
        ))}
      </div>
      <label className="nw-inline">Search<input type="search" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Title" /></label>
      {list.isLoading && <p className="nw-muted">Loading…</p>}
      {list.isError && <p className="nw-error" role="alert">Could not load the articles.</p>}
      {list.data && items.length === 0 && <p className="nw-empty">No articles here.</p>}
      {items.length > 0 && (
        <table className="nw-table">
          <thead><tr><th>Title</th><th>Source</th><th>Status</th><th>Updated</th></tr></thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id}>
                <td><Link to={`/admin/news/articles/${a.id}`}>{a.title}</Link>{a.imported && <span className="nw-tag">imported</span>}</td>
                <td>{a.source.name}</td>
                <td><span className={`nw-status nw-status-${a.status}`}>{STATUS_LABEL[a.status] || a.status}</span>{a.quarantine_reason && <div className="nw-muted">{a.quarantine_reason}</div>}</td>
                <td>{formatDate(a.updated_at, true)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {list.data && <Pagination pagination={list.data.pagination} onPage={setPage} />}
    </div>
  );
}
