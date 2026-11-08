import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import NewsroomTabs from "../components/NewsroomTabs";
import { createRights, createSource, getSource, listSources, pollSource, rightsAction, sourceAction } from "../api/newsroom";
import { errorText, explainBlocker, formatDate } from "../utils/text";
import "../news.css";

const TYPES = [["original", "ResourceBoard original"], ["licensed", "Licensed (written permission or agreement)"], ["open_licensed", "Open licence"], ["public_domain", "Public domain"], ["metadata_only", "Headlines and links only"]];
const BASES = [["original", "Our own work"], ["written_permission", "Written permission"], ["syndication_agreement", "Syndication agreement"], ["open_licence", "Open licence"], ["public_domain", "Public domain"]];
const NEW_SOURCE = { name: "", slug: "", source_type: "licensed", website_url: "", terms_url: "", adapter: "", feed_url: "", allows_full_text: false, allows_commercial_use: false, attribution_template: "Source: {source}. By {author}.", evidence_ref: "" };
const NEW_RIGHTS = { title: "", licence: "", basis: "written_permission", allows_full_text: false, allows_commercial_use: false, allows_modification: false, requires_attribution: true, requires_counter: false, evidence_url: "", evidence_note: "", effective_until: "" };
const slugify = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80);

function SourcePanel({ id, onMessage }) {
  const qc = useQueryClient();
  const [rights, setRights] = useState(NEW_RIGHTS);
  const [reason, setReason] = useState("");
  const detail = useQuery({ queryKey: ["newsroom", "source", id], queryFn: () => getSource(id) });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["newsroom", "source", id] }); qc.invalidateQueries({ queryKey: ["newsroom", "sources"] }); };
  const run = useMutation({ mutationFn: (fn) => fn(), onSuccess: (r) => { refresh(); onMessage({ kind: "ok", text: r?.status ? `Poll ${r.status}${r.reason ? ` (${r.reason})` : ""}: ${r.created} new.` : "Done." }); }, onError: (e) => onMessage({ kind: "error", text: errorText(e) }) });
  const s = detail.data;
  if (detail.isLoading) return <p className="nw-muted">Loading…</p>;
  if (!s) return <p className="nw-error">Could not load this source.</p>;
  const set = (k) => (e) => setRights((r) => ({ ...r, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const body = { ...rights, effective_until: rights.effective_until ? new Date(rights.effective_until).toISOString() : null };
  return (
    <div className="nw-panel">
      <p><strong>Rights check now:</strong> {s.decision.allowed ? "text may be republished" : `not allowed (${s.decision.reasons.map(explainBlocker).join(" ")})`}</p>
      <div className="nw-actions">
        {["pending", "suspended"].includes(s.approval_state) && <button type="button" className="btn small" onClick={() => run.mutate(() => sourceAction(id, "approve"))}>Approve source</button>}
        {s.approval_state === "approved" && !s.is_active && <button type="button" className="btn small" onClick={() => run.mutate(() => sourceAction(id, "activate"))}>Switch on</button>}
        {s.approval_state === "approved" && s.is_active && <button type="button" className="btn secondary small" onClick={() => run.mutate(() => sourceAction(id, "deactivate"))}>Switch off</button>}
        {s.approval_state === "approved" && <button type="button" className="btn danger small" onClick={() => run.mutate(() => sourceAction(id, "suspend", { reason }))}>Suspend (quarantines its articles)</button>}
        {s.approval_state !== "approved" && s.approval_state !== "rejected" && <button type="button" className="btn secondary small" onClick={() => run.mutate(() => sourceAction(id, "reject"))}>Reject</button>}
        {s.adapter && s.is_active && <button type="button" className="btn secondary small" onClick={() => run.mutate(() => pollSource(id))}>Poll now</button>}
      </div>
      <h3>Rights records</h3>
      {s.rights.length === 0 && <p className="nw-muted">No rights records yet. Nothing from this source can be published until one is approved.</p>}
      <ul className="nw-rights">
        {s.rights.map((r) => (
          <li key={r.id}>
            <strong>{r.title}</strong> · {r.licence} · <span className={`nw-status nw-status-${r.status}`}>{r.status}</span>{r.in_force && <span className="nw-tag">in force</span>}
            <div className="nw-muted">{r.allows_full_text ? "full text" : "no full text"} · {r.allows_commercial_use ? "commercial use" : "no commercial use"} · {r.allows_modification ? "edits allowed" : "no edits"}{r.effective_until ? ` · until ${formatDate(r.effective_until)}` : ""}</div>
            {r.revoked_reason && <div className="nw-warn">Revoked: {r.revoked_reason}</div>}
            <div className="nw-actions">
              {r.status === "draft" && <button type="button" className="btn small" onClick={() => run.mutate(() => rightsAction(r.id, "approve"))}>Approve</button>}
              {["draft", "approved"].includes(r.status) && <button type="button" className="btn danger small" onClick={() => run.mutate(() => rightsAction(r.id, "revoke", { reason }))}>Revoke</button>}
            </div>
          </li>
        ))}
      </ul>
      <label>Reason (needed to revoke)<input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} /></label>
      <h3>Add a rights record</h3>
      <form className="nw-form" onSubmit={(e) => { e.preventDefault(); run.mutate(() => createRights(id, body).then((r) => { setRights(NEW_RIGHTS); return r; })); }}>
        <div className="nw-grid2">
          <label>Title<input required value={rights.title} onChange={set("title")} /></label>
          <label>Licence<input required value={rights.licence} onChange={set("licence")} placeholder="CC BY-ND 4.0, or the agreement name" /></label>
          <label>Basis<select value={rights.basis} onChange={set("basis")}>{BASES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label>Ends on (optional)<input type="date" value={rights.effective_until} onChange={set("effective_until")} /></label>
          <label>Evidence link<input type="url" value={rights.evidence_url} onChange={set("evidence_url")} /></label>
          <label>Evidence note<input value={rights.evidence_note} onChange={set("evidence_note")} placeholder="Where the signed agreement is kept" /></label>
        </div>
        {[["allows_full_text", "Full text allowed"], ["allows_commercial_use", "Commercial use (advertising) allowed"], ["allows_modification", "Editing or translating allowed"], ["requires_attribution", "Attribution required"], ["requires_counter", "Page-view counter required"]].map(([k, l]) => (
          <label key={k} className="nw-check"><input type="checkbox" checked={rights[k]} onChange={set(k)} /> {l}</label>
        ))}
        <button type="submit" className="btn secondary" disabled={run.isPending}>Save as draft</button>
      </form>
    </div>
  );
}

export default function SourcesPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(null);
  const [form, setForm] = useState(NEW_SOURCE);
  const [message, setMessage] = useState({ kind: "", text: "" });
  const list = useQuery({ queryKey: ["newsroom", "sources"], queryFn: () => listSources({ page_size: 50 }) });
  const create = useMutation({
    mutationFn: () => createSource({ ...form, slug: form.slug || slugify(form.name) }),
    onSuccess: (s) => { setForm(NEW_SOURCE); setOpen(s.id); setMessage({ kind: "ok", text: "Source added. It waits for approval." }); qc.invalidateQueries({ queryKey: ["newsroom", "sources"] }); },
    onError: (e) => setMessage({ kind: "error", text: errorText(e) }),
  });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  return (
    <div className="nw-admin">
      <h1>Sources and rights</h1>
      <NewsroomTabs />
      <p className="nw-muted">A feed, an API key or a public web page does not give the right to republish. A source must be approved and have an approved rights record before anything from it can go live.</p>
      {message.text && <p className={message.kind === "error" ? "nw-error" : "nw-ok"} role={message.kind === "error" ? "alert" : "status"}>{message.text}</p>}
      {list.isLoading && <p className="nw-muted">Loading…</p>}
      <ul className="nw-sources">
        {(list.data?.items || []).map((s) => (
          <li key={s.id}>
            <button type="button" className="nw-source-head" aria-expanded={open === s.id} onClick={() => setOpen(open === s.id ? null : s.id)}>
              <strong>{s.name}</strong> <span className={`nw-status nw-status-${s.approval_state}`}>{s.approval_state}</span>
              {s.is_active && <span className="nw-tag">on</span>}<span className="nw-muted"> · {s.approved_records} approved rights record(s)</span>
            </button>
            {open === s.id && <SourcePanel id={s.id} onMessage={setMessage} />}
          </li>
        ))}
      </ul>
      <section className="nw-panel" aria-label="Add a source">
        <h2>Add a source</h2>
        <form className="nw-form" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div className="nw-grid2">
            <label>Name<input required value={form.name} onChange={set("name")} /></label>
            <label>Short name for links<input value={form.slug} onChange={set("slug")} placeholder={slugify(form.name)} /></label>
            <label>Type<select value={form.source_type} onChange={set("source_type")}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Website<input type="url" value={form.website_url} onChange={set("website_url")} /></label>
            <label>Terms or licence page<input type="url" value={form.terms_url} onChange={set("terms_url")} /></label>
            <label>Where the agreement is kept<input value={form.evidence_ref} onChange={set("evidence_ref")} /></label>
            <label>Automatic feed<select value={form.adapter} onChange={set("adapter")}><option value="">None (manual entry only)</option><option value="rss">RSS or Atom</option></select></label>
            {form.adapter && <label>Feed address (https)<input type="url" required value={form.feed_url} onChange={set("feed_url")} /></label>}
          </div>
          <label>Credit line template (tokens: {"{author} {source} {original_url} {licence} {published}"})<input value={form.attribution_template} onChange={set("attribution_template")} /></label>
          <label className="nw-check"><input type="checkbox" checked={form.allows_full_text} onChange={set("allows_full_text")} /> Full text can be republished</label>
          <label className="nw-check"><input type="checkbox" checked={form.allows_commercial_use} onChange={set("allows_commercial_use")} /> Commercial use is allowed</label>
          <button type="submit" className="btn" disabled={create.isPending}>Add source</button>
        </form>
      </section>
    </div>
  );
}
