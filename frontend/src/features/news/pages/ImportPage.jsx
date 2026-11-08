import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import ArticleBody from "../components/ArticleBody";
import NewsroomTabs from "../components/NewsroomTabs";
import { importArticle, ingestionHealth, listSources, previewImport } from "../api/newsroom";
import { errorText, explainBlocker, formatDate } from "../utils/text";
import "../news.css";

const EMPTY = { source: "", title: "", author_name: "", canonical_url: "", body: "" };

// Import by hand: paste an article you have the right to use, preview what would happen (cleaned text, duplicate, rights verdict), then import it into the review queue.
export default function ImportPage() {
  const [form, setForm] = useState(EMPTY);
  const [preview, setPreview] = useState(null);
  const [message, setMessage] = useState({ kind: "", text: "" });
  const [created, setCreated] = useState(null);
  const sources = useQuery({ queryKey: ["newsroom", "sources-all"], queryFn: () => listSources({ page_size: 50 }) });
  const health = useQuery({ queryKey: ["newsroom", "health"], queryFn: ingestionHealth, refetchInterval: 60_000, retry: false });
  const payload = () => ({ ...form, source: Number(form.source), original_url: form.canonical_url });
  const set = (k) => (e) => { setForm((f) => ({ ...f, [k]: e.target.value })); setPreview(null); setCreated(null); };

  const doPreview = useMutation({ mutationFn: () => previewImport(payload()), onSuccess: (p) => { setPreview(p); setMessage({ kind: "", text: "" }); }, onError: (e) => setMessage({ kind: "error", text: errorText(e) }) });
  const doImport = useMutation({ mutationFn: () => importArticle(payload()), onSuccess: (a) => { setCreated(a); setPreview(null); setForm(EMPTY); setMessage({ kind: "ok", text: "Imported into the review queue." }); }, onError: (e) => setMessage({ kind: "error", text: errorText(e) }) });
  const ready = form.source && form.title.trim() && form.body.trim();

  return (
    <div className="nw-admin">
      <h1>Import an article</h1>
      <NewsroomTabs />
      <p className="nw-muted">Only paste text you have written permission or an open licence to republish. Imports always wait in the review queue.</p>
      {message.text && <p className={message.kind === "error" ? "nw-error" : "nw-ok"} role={message.kind === "error" ? "alert" : "status"}>{message.text}{created && <> <Link to={`/admin/news/articles/${created.id}`}>Open it</Link></>}</p>}
      <form className="nw-form" onSubmit={(e) => { e.preventDefault(); doPreview.mutate(); }}>
        <label>Source
          <select required value={form.source} onChange={set("source")}>
            <option value="">Choose the source…</option>
            {(sources.data?.items || []).map((s) => <option key={s.id} value={s.id}>{s.name}{s.approval_state !== "approved" ? ` (${s.approval_state})` : ""}</option>)}
          </select>
        </label>
        <label>Title<input required value={form.title} onChange={set("title")} maxLength={220} /></label>
        <label>Author<input value={form.author_name} onChange={set("author_name")} maxLength={160} /></label>
        <label>Link to the original<input type="url" value={form.canonical_url} onChange={set("canonical_url")} placeholder="https://…" /></label>
        <label>Article text (HTML)<textarea required rows={10} value={form.body} onChange={set("body")} /></label>
        <div className="nw-actions">
          <button type="submit" className="btn secondary" disabled={!ready || doPreview.isPending}>Preview</button>
          <button type="button" className="btn" disabled={!preview || Boolean(preview?.duplicate) || doImport.isPending} onClick={() => doImport.mutate()}>Import to review queue</button>
        </div>
      </form>
      {preview && (
        <section className="nw-panel" aria-label="Import preview">
          <h2>Preview</h2>
          {preview.duplicate && <p className="nw-warn">Already in the newsroom (matched by {preview.duplicate.matched_by.replace("_", " ")}): {preview.duplicate.title}</p>}
          <p>{preview.words} words. Credit line: {preview.attribution || "(none)"}</p>
          {preview.can_publish ? <p className="nw-ok">The rights checks would pass.</p> : <><p className="nw-warn">It could not be published as it is:</p><ul>{preview.blockers.map((b) => <li key={b}>{explainBlocker(b)}</li>)}</ul></>}
          <ArticleBody html={preview.body} />
        </section>
      )}
      <section className="nw-panel" aria-label="Ingestion health">
        <h2>Automatic imports</h2>
        {health.isError && <p className="nw-muted">Health information is not available.</p>}
        {health.data && health.data.length === 0 && <p className="nw-muted">No source has an automatic feed.</p>}
        {(health.data || []).length > 0 && (
          <table className="nw-table">
            <thead><tr><th>Source</th><th>Last run</th><th>Failures in a row</th><th>Used today</th><th>Next poll</th></tr></thead>
            <tbody>
              {health.data.map((h) => (
                <tr key={h.source}>
                  <td>{h.name}</td>
                  <td>{h.last_status ? `${h.last_status}${h.last_reason ? ` (${h.last_reason})` : ""} · ${formatDate(h.last_run_at, true)}` : "never"}</td>
                  <td>{h.failure_streak}</td><td>{h.runs_today} / {h.daily_request_quota}</td>
                  <td>{h.next_skip_reason ? `waiting: ${h.next_skip_reason.replace(/_/g, " ")}` : "ready"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
