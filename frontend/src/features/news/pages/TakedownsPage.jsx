import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import Pagination from "../../../components/Pagination";
import NewsroomTabs from "../components/NewsroomTabs";
import { listTakedowns, takedownAction } from "../api/newsroom";
import { errorText, formatDate } from "../utils/text";
import "../news.css";

const FILTERS = [["open", "Open"], ["on_hold", "On hold"], ["upheld", "Upheld"], ["dismissed", "Dismissed"], ["", "All"]];

function Row({ item, onMessage }) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const act = useMutation({
    mutationFn: (action) => takedownAction(item.id, action, { note }),
    onSuccess: () => { setNote(""); onMessage({ kind: "ok", text: "Done." }); qc.invalidateQueries({ queryKey: ["newsroom", "takedowns"] }); },
    onError: (e) => onMessage({ kind: "error", text: errorText(e) }),
  });
  const closed = ["upheld", "dismissed"].includes(item.status);
  return (
    <li className="nw-complaint">
      <p><strong>#{item.id}</strong> <span className={`nw-status nw-status-${item.status}`}>{item.status.replace("_", " ")}</span> · {item.claim} · {formatDate(item.created_at, true)}</p>
      <p>{item.contact_name} &lt;{item.contact_email}&gt;</p>
      <p>Article: {item.article ? <Link to={`/admin/news/articles/${item.article.id}`}>{item.article.title}</Link> : <span className="nw-muted">no match ({item.article_ref || "nothing entered"})</span>}{item.article && ` (${item.article.status})`}</p>
      <blockquote className="nw-quote">{item.message}</blockquote>
      {item.resolution_note && <p className="nw-muted">Resolution: {item.resolution_note}</p>}
      {!closed && (
        <>
          <label>Resolution note<input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} /></label>
          <div className="nw-actions">
            {item.status === "open" && item.article && <button type="button" className="btn secondary small" onClick={() => act.mutate("hold")}>Put article on hold</button>}
            <button type="button" className="btn danger small" onClick={() => act.mutate("uphold")}>Uphold (withdraw article)</button>
            <button type="button" className="btn small" onClick={() => act.mutate("dismiss")}>Dismiss (restore to review)</button>
          </div>
        </>
      )}
    </li>
  );
}

export default function TakedownsPage() {
  const [status, setStatus] = useState("open");
  const [page, setPage] = useState(1);
  const [message, setMessage] = useState({ kind: "", text: "" });
  const list = useQuery({ queryKey: ["newsroom", "takedowns", { status, page }], queryFn: () => listTakedowns({ page, ...(status ? { status } : {}) }), placeholderData: (p) => p });
  const items = list.data?.items || [];
  return (
    <div className="nw-admin">
      <h1>Complaints</h1>
      <NewsroomTabs />
      <p className="nw-muted">For a credible complaint, put the article on hold first. It is restored only after you dismiss the complaint, and then it goes back to the review queue.</p>
      <div className="nw-status-tabs">{FILTERS.map(([v, l]) => <button key={l} type="button" className={status === v ? "nw-pill is-active" : "nw-pill"} aria-pressed={status === v} onClick={() => { setStatus(v); setPage(1); }}>{l}</button>)}</div>
      {message.text && <p className={message.kind === "error" ? "nw-error" : "nw-ok"} role={message.kind === "error" ? "alert" : "status"}>{message.text}</p>}
      {list.isLoading && <p className="nw-muted">Loading…</p>}
      {list.data && items.length === 0 && <p className="nw-empty">No complaints here.</p>}
      <ul className="nw-complaints">{items.map((t) => <Row key={t.id} item={t} onMessage={setMessage} />)}</ul>
      {list.data && <Pagination pagination={list.data.pagination} onPage={setPage} />}
    </div>
  );
}
