import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import Pagination from "../../../components/Pagination";
import NewsroomTabs from "../components/NewsroomTabs";
import { commentAction, listCommentsAdmin } from "../api/newsroom";
import { errorText, formatDate } from "../utils/text";
import "../news.css";

const FILTERS = [["pending", "Waiting"], ["approved", "Approved"], ["hidden", "Hidden"], ["deleted", "Deleted"], ["", "All"]];

export default function CommentsPage() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const [message, setMessage] = useState({ kind: "", text: "" });
  const list = useQuery({ queryKey: ["newsroom", "comments", { status, page }], queryFn: () => listCommentsAdmin({ page, ...(status ? { status } : {}) }), placeholderData: (p) => p });
  const act = useMutation({
    mutationFn: ({ id, action }) => commentAction(id, action),
    onSuccess: () => { setMessage({ kind: "ok", text: "Done." }); qc.invalidateQueries({ queryKey: ["newsroom", "comments"] }); qc.invalidateQueries({ queryKey: ["newsroom", "monitoring"] }); },
    onError: (e) => setMessage({ kind: "error", text: errorText(e) }),
  });
  const items = list.data?.items || [];
  return (
    <div className="nw-admin">
      <h1>Comments</h1>
      <NewsroomTabs />
      <div className="nw-status-tabs">{FILTERS.map(([v, l]) => <button key={l} type="button" className={status === v ? "nw-pill is-active" : "nw-pill"} aria-pressed={status === v} onClick={() => { setStatus(v); setPage(1); }}>{l}</button>)}</div>
      {message.text && <p className={message.kind === "error" ? "nw-error" : "nw-ok"} role={message.kind === "error" ? "alert" : "status"}>{message.text}</p>}
      {list.isLoading && <p className="nw-muted">Loading…</p>}
      {list.data && items.length === 0 && <p className="nw-empty">No comments here.</p>}
      <ul className="nw-complaints">
        {items.map((c) => (
          <li key={c.id} className="nw-complaint">
            <p><strong>{c.author}</strong> &lt;{c.email}&gt; · {formatDate(c.created_at, true)} · <span className={`nw-status nw-status-${c.status}`}>{c.status}</span></p>
            <p className="nw-muted">On <Link to={`/admin/news/articles/${c.article.id}`}>{c.article.title}</Link></p>
            <blockquote className="nw-quote">{c.body}</blockquote>
            <div className="nw-actions">
              {c.status !== "approved" && c.status !== "deleted" && <button type="button" className="btn small" onClick={() => act.mutate({ id: c.id, action: "approve" })}>Approve</button>}
              {c.status !== "hidden" && c.status !== "deleted" && <button type="button" className="btn secondary small" onClick={() => act.mutate({ id: c.id, action: "hide" })}>Hide</button>}
              {c.status !== "deleted" && <button type="button" className="btn danger small" onClick={() => act.mutate({ id: c.id, action: "delete" })}>Delete</button>}
            </div>
          </li>
        ))}
      </ul>
      {list.data && <Pagination pagination={list.data.pagination} onPage={setPage} />}
    </div>
  );
}
