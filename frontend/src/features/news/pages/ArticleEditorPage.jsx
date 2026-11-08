import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { listMedia } from "../../../api";
import ArticleBody from "../components/ArticleBody";
import NewsroomTabs from "../components/NewsroomTabs";
import {
  createNewsArticle, createNewsAsset, deleteNewsAsset, getNewsroomArticle, listNewsCategoriesAdmin, listNewsRevisions,
  listSources, newsArticleAction, newsAssetAction, updateNewsArticle, updateNewsAsset,
} from "../api/newsroom";
import { STATUS_LABEL, errorText, explainBlocker, formatDate, localToIso } from "../utils/text";
import "../news.css";

const EMPTY = { source: "", title: "", standfirst: "", author_name: "", category: "", language: "en", canonical_url: "", original_url: "", is_featured: false, is_breaking: false, body: "" };
const fromArticle = (a) => ({ source: a.source.id, title: a.title, standfirst: a.standfirst, author_name: a.author_name, category: a.category?.id || "", language: a.language, canonical_url: a.canonical_url, original_url: a.original_url, is_featured: a.is_featured, is_breaking: a.is_breaking, body: a.body });

function AssetRow({ asset, onChanged, onError }) {
  const [form, setForm] = useState({ credit: asset.credit, licence: asset.licence, evidence_url: asset.evidence_url, caption: asset.caption, alt_text: asset.alt_text, allows_commercial_use: asset.allows_commercial_use });
  const run = (fn) => fn().then(onChanged).catch((e) => onError(errorText(e)));
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  return (
    <li className="nw-asset">
      <p><strong>{asset.kind === "video" ? `Video ${asset.video_id}` : `Image #${asset.image}`}</strong> <span className={`nw-status nw-status-${asset.approval_state}`}>{asset.approval_state}</span>{asset.displayable && <span className="nw-tag">shown</span>}</p>
      <div className="nw-grid2">
        <label>Credit<input value={form.credit} onChange={set("credit")} /></label>
        <label>Licence<input value={form.licence} onChange={set("licence")} /></label>
        <label>Evidence link<input value={form.evidence_url} onChange={set("evidence_url")} /></label>
        <label>Caption<input value={form.caption} onChange={set("caption")} /></label>
        <label>Alt text<input value={form.alt_text} onChange={set("alt_text")} /></label>
        <label className="nw-check"><input type="checkbox" checked={form.allows_commercial_use} onChange={set("allows_commercial_use")} /> Commercial use allowed</label>
      </div>
      <div className="nw-actions">
        <button type="button" className="btn secondary small" onClick={() => run(() => updateNewsAsset(asset.id, form))}>Save asset</button>
        <button type="button" className="btn small" onClick={() => run(() => newsAssetAction(asset.id, "clear"))}>Clear for use</button>
        <button type="button" className="btn secondary small" onClick={() => run(() => newsAssetAction(asset.id, "reject"))}>Reject</button>
        <button type="button" className="btn danger small" onClick={() => run(() => deleteNewsAsset(asset.id))}>Remove</button>
      </div>
    </li>
  );
}

export default function ArticleEditorPage() {
  const { id } = useParams();
  const isNew = !id;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [form, setForm] = useState(EMPTY);
  const [message, setMessage] = useState({ kind: "", text: "" });
  const [reason, setReason] = useState("");
  const [when, setWhen] = useState("");
  const [asset, setAsset] = useState({ kind: "video", video_id: "", image: "" });

  const article = useQuery({ queryKey: ["newsroom", "article", id], queryFn: () => getNewsroomArticle(id), enabled: !isNew });
  const sources = useQuery({ queryKey: ["newsroom", "sources-all"], queryFn: () => listSources({ page_size: 50 }) });
  const categories = useQuery({ queryKey: ["newsroom", "categories"], queryFn: listNewsCategoriesAdmin });
  const revisions = useQuery({ queryKey: ["newsroom", "revisions", id], queryFn: () => listNewsRevisions(id), enabled: !isNew });
  const media = useQuery({ queryKey: ["newsroom", "media"], queryFn: () => listMedia({ page_size: 50 }), enabled: !isNew && asset.kind === "image" });

  useEffect(() => { if (article.data) setForm(fromArticle(article.data)); }, [article.data]);
  const a = article.data;
  const refresh = (fresh) => {
    qc.setQueryData(["newsroom", "article", id], fresh);
    qc.invalidateQueries({ queryKey: ["newsroom", "articles"] });
    qc.invalidateQueries({ queryKey: ["newsroom", "revisions", id] });
  };
  const say = (kind, text) => setMessage({ kind, text });
  const body = () => ({ ...form, category: form.category || null, source: undefined, ...(isNew ? { source: Number(form.source) } : {}) });

  const save = useMutation({
    mutationFn: () => (isNew ? createNewsArticle(body()) : updateNewsArticle(id, body())),
    onSuccess: (saved) => { say("ok", "Saved."); if (isNew) navigate(`/admin/news/articles/${saved.id}`, { replace: true }); else refresh(saved); },
    onError: (e) => say("error", errorText(e)),
  });
  const act = useMutation({
    mutationFn: ({ action, extra }) => newsArticleAction(id, action, extra),
    onSuccess: (fresh, { action }) => { refresh(fresh); setReason(""); say("ok", `Done: ${action}.`); },
    onError: (e) => say("error", errorText(e)),
  });
  const addAsset = useMutation({
    mutationFn: () => createNewsAsset(id, asset.kind === "video" ? { kind: "video", video_id: asset.video_id.trim() } : { kind: "image", image: Number(asset.image) }),
    onSuccess: () => { setAsset({ ...asset, video_id: "", image: "" }); qc.invalidateQueries({ queryKey: ["newsroom", "article", id] }); },
    onError: (e) => say("error", errorText(e)),
  });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const refetchArticle = () => qc.invalidateQueries({ queryKey: ["newsroom", "article", id] });
  const status = a?.status;

  if (!isNew && article.isLoading) return <p className="nw-muted">Loading…</p>;
  if (!isNew && article.isError) return <p className="nw-error" role="alert">Could not load this article.</p>;
  return (
    <div className="nw-admin">
      <h1>{isNew ? "New article" : a.title}</h1>
      <NewsroomTabs />
      {!isNew && <p className="nw-meta"><span className={`nw-status nw-status-${status}`}>{STATUS_LABEL[status]}</span> · {a.source.name}{a.published_at ? ` · published ${formatDate(a.published_at, true)}` : ""}{a.scheduled_for ? ` · scheduled for ${formatDate(a.scheduled_for, true)}` : ""}</p>}
      {message.text && <p className={message.kind === "error" ? "nw-error" : "nw-ok"} role={message.kind === "error" ? "alert" : "status"}>{message.text}</p>}

      <form className="nw-form" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        {isNew && (
          <label>Source
            <select required value={form.source} onChange={set("source")}>
              <option value="">Choose the source…</option>
              {(sources.data?.items || []).map((s) => <option key={s.id} value={s.id}>{s.name}{s.approval_state !== "approved" ? ` (${s.approval_state})` : ""}</option>)}
            </select>
          </label>
        )}
        <label>Title<input required maxLength={220} value={form.title} onChange={set("title")} /></label>
        <label>Standfirst (one-line summary)<input maxLength={500} value={form.standfirst} onChange={set("standfirst")} /></label>
        <div className="nw-grid2">
          <label>Author<input maxLength={160} value={form.author_name} onChange={set("author_name")} /></label>
          <label>Category
            <select value={form.category} onChange={set("category")}>
              <option value="">None</option>
              {(categories.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label>Original article link<input type="url" value={form.original_url} onChange={set("original_url")} placeholder="https://…" /></label>
          <label>Canonical link<input type="url" value={form.canonical_url} onChange={set("canonical_url")} placeholder="https://…" /></label>
          <label>Language<input value={form.language} onChange={set("language")} maxLength={8} /></label>
        </div>
        <label className="nw-check"><input type="checkbox" checked={form.is_featured} onChange={set("is_featured")} /> Featured</label>
        <label className="nw-check"><input type="checkbox" checked={form.is_breaking} onChange={set("is_breaking")} /> Breaking</label>
        <label>Article text (HTML: p, h2–h4, ul, ol, li, blockquote, strong, em, a)<textarea rows={14} value={form.body} onChange={set("body")} /></label>
        <button type="submit" className="btn" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save"}</button>
      </form>

      {!isNew && (
        <>
          <section className="nw-panel" aria-label="Rights check and actions">
            <h2>Publishing</h2>
            {a.can_publish ? <p className="nw-ok">All rights checks pass.</p> : (
              <>
                <p className="nw-error">This article cannot be published yet:</p>
                <ul>{a.blockers.map((b) => <li key={b}>{explainBlocker(b)}</li>)}</ul>
              </>
            )}
            {a.denylisted_publisher && <p className="nw-warn">This publisher needs written permission recorded before any full-text republication.</p>}
            {a.attribution && <p className="nw-muted">Credit line: {a.attribution}</p>}
            <label>Reason (needed to reject or withdraw)<input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} /></label>
            <label>Schedule for<input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></label>
            <div className="nw-actions">
              {["draft", "rejected"].includes(status) && <button type="button" className="btn secondary" onClick={() => act.mutate({ action: "submit" })}>Send for review</button>}
              {["draft", "pending", "scheduled"].includes(status) && <button type="button" className="btn" disabled={!a.can_publish} onClick={() => act.mutate({ action: "publish" })}>Publish now</button>}
              {["draft", "pending"].includes(status) && <button type="button" className="btn secondary" disabled={!a.can_publish || !localToIso(when)} onClick={() => act.mutate({ action: "schedule", extra: { scheduled_for: localToIso(when) } })}>Schedule</button>}
              {["draft", "pending"].includes(status) && <button type="button" className="btn secondary" onClick={() => act.mutate({ action: "reject", extra: { reason } })}>Reject</button>}
              {["published", "scheduled", "quarantined"].includes(status) && <button type="button" className="btn danger" onClick={() => act.mutate({ action: "withdraw", extra: { reason } })}>Withdraw</button>}
              {["quarantined", "withdrawn"].includes(status) && <button type="button" className="btn secondary" onClick={() => act.mutate({ action: "restore" })}>Restore to review</button>}
            </div>
            {a.quarantine_reason && <p className="nw-warn">Quarantined: {a.quarantine_reason}</p>}
            {a.review_note && <p className="nw-muted">Note: {a.review_note}</p>}
          </section>

          <section className="nw-panel" aria-label="Images and video">
            <h2>Images and video</h2>
            <p className="nw-muted">Each picture or video has its own rights. Only cleared, unexpired, commercially usable items are shown to readers.</p>
            <ul className="nw-assets">{a.assets.map((x) => <AssetRow key={`${x.id}-${x.approval_state}`} asset={x} onChanged={refetchArticle} onError={(t) => say("error", t)} />)}</ul>
            <div className="nw-grid2">
              <label>Add<select value={asset.kind} onChange={(e) => setAsset({ ...asset, kind: e.target.value })}><option value="video">YouTube video</option><option value="image">Image from the library</option></select></label>
              {asset.kind === "video" ? (
                <label>YouTube video id (11 characters)<input value={asset.video_id} maxLength={11} onChange={(e) => setAsset({ ...asset, video_id: e.target.value })} /></label>
              ) : (
                <label>Library image
                  <select value={asset.image} onChange={(e) => setAsset({ ...asset, image: e.target.value })}>
                    <option value="">Choose…</option>
                    {(media.data?.items || []).map((m) => <option key={m.id} value={m.id}>{m.original_name || m.alt_text || `Image ${m.id}`}</option>)}
                  </select>
                </label>
              )}
            </div>
            <button type="button" className="btn secondary small" onClick={() => addAsset.mutate()} disabled={addAsset.isPending || (asset.kind === "video" ? asset.video_id.trim().length !== 11 : !asset.image)}>Add</button>
          </section>

          <section className="nw-panel" aria-label="Preview">
            <h2>Preview of the saved text</h2>
            <ArticleBody html={a.body} />
          </section>

          <section className="nw-panel" aria-label="History">
            <h2>History</h2>
            <ol className="nw-history">
              {(revisions.data || []).map((r) => <li key={r.id}><strong>{r.action}</strong> by {r.user} · {formatDate(r.created_at, true)}{r.note ? ` · ${r.note}` : ""}</li>)}
            </ol>
          </section>
        </>
      )}
    </div>
  );
}
