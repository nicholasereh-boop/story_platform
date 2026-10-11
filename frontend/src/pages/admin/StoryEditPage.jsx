import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useBlocker, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createStory, getStory, listCategories, patchStory, storyAction } from "../../api";
import ConfirmDialog from "../../components/ConfirmDialog";
import ErrorBoundary from "../../components/ErrorBoundary";
import MediaPicker from "../../components/media/MediaPicker";
import RevisionsDrawer from "../../components/RevisionsDrawer";
import StatusBadge from "../../components/StatusBadge";
import TagsInput from "../../components/TagsInput";
import StoryEditor from "../../editor/StoryEditor";
import { useAutosave } from "../../hooks/useAutosave";
import { changedKeys, pickChanged } from "../../utils/autosave";
import { clearDraft, readDraft, writeDraft } from "../../utils/draftStore";
import { defaultScheduleValue, fmtClock, fmtDateTime } from "../../utils/format";
import { ERROR_KEY, PAYLOAD_KEYS, blankForm, formFromStory, metaFrom, toPayloadForm } from "./storyForm";

// /admin/stories/new and /admin/stories/:id/edit. Keyed by id so creating a story (new -> :id) starts a clean screen.
export default function StoryEditPage() {
  const { id } = useParams();
  return <StoryEditScreen key={id || "new"} id={id} />;
}

const errText = (e) => (Array.isArray(e) ? e.filter((x) => typeof x === "string").join(" ") : typeof e === "string" ? e : "");
const FieldError = ({ errors }) => (errText(errors) ? <p className="field-error" role="alert">{errText(errors)}</p> : null);
const Counter = ({ value, max }) => <span className={`counter${value > max ? " over" : ""}`}>{value}/{max}</span>;

function newStoryRecovery() {
  const stored = readDraft("new");
  return stored && JSON.stringify(toPayloadForm(stored.form)) !== JSON.stringify(toPayloadForm(blankForm())) ? stored : null;
}

function StoryEditScreen({ id }) {
  const isNew = !id;
  const draftKey = id || "new";
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // ---- state ----
  const [form, setForm] = useState(isNew ? blankForm() : null); // null while an existing story loads
  const [saved, setSaved] = useState(isNew ? toPayloadForm(blankForm()) : null); // last server-confirmed values
  const [meta, setMeta] = useState({ status: "draft" });
  const [fieldErrors, setFieldErrors] = useState({});
  const [notice, setNotice] = useState(null); // {type: "ok"|"error"|"info", text}
  const [busy, setBusy] = useState(null);
  const [editorKey, setEditorKey] = useState(0); // bump to reload the editor with different content
  const [recovery, setRecovery] = useState(isNew ? newStoryRecovery : null);
  const [picker, setPicker] = useState(false);
  const [revisions, setRevisions] = useState(false);
  const [scheduleAt, setScheduleAt] = useState(defaultScheduleValue);
  const [scheduleError, setScheduleError] = useState("");

  // Refs hold the latest values for code that runs later (timers, autosave, editor callbacks).
  const savedRef = useRef(saved);
  const formRef = useRef(form);
  formRef.current = form;
  const editorInitRef = useRef(form?.content_json); // the document handed to the editor
  const initialized = useRef(isNew);
  const skipBlock = useRef(false);

  const current = useMemo(() => (form ? toPayloadForm(form) : null), [form]);
  const currentRef = useRef(current);
  currentRef.current = current;
  const dirty = Boolean(form) && changedKeys(saved, current, PAYLOAD_KEYS).length > 0;
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;

  const getChanges = () => pickChanged(savedRef.current, currentRef.current, PAYLOAD_KEYS);

  // ---- loading an existing story ----
  const storyQuery = useQuery({ queryKey: ["story", id], queryFn: () => getStory(id), enabled: !isNew, gcTime: 0, staleTime: 0 });

  const initFrom = useCallback((story, { skipRecovery = false } = {}) => {
    const f = formFromStory(story);
    const payload = toPayloadForm(f);
    savedRef.current = payload;
    setSaved(payload);
    setForm(f);
    setMeta(metaFrom(story));
    editorInitRef.current = f.content_json;
    setEditorKey((k) => k + 1);
    if (skipRecovery) return;
    // Offer the sessionStorage copy only when it is newer than the server copy and actually different.
    const stored = readDraft(draftKey);
    if (stored && stored.savedAt > Date.parse(story.updated_at) && JSON.stringify(toPayloadForm(stored.form)) !== JSON.stringify(payload)) {
      setRecovery(stored);
    } else if (stored) {
      clearDraft(draftKey);
    }
  }, [draftKey]);

  useEffect(() => {
    if (storyQuery.data && !initialized.current) {
      initialized.current = true;
      initFrom(storyQuery.data);
    }
  }, [storyQuery.data, initFrom]);

  // ---- saving ----
  const refreshLists = () => queryClient.invalidateQueries({ queryKey: ["stories"] });

  // Record what the server now holds. `payload` is what we sent; the form may already have moved on.
  const commitSaved = (payload, result) => {
    savedRef.current = { ...savedRef.current, ...payload };
    if (result) {
      setMeta(metaFrom(result));
      // The server may have generated the slug; adopt it unless the person is editing the slug themselves.
      const untouched = formRef.current.slug === savedRef.current.slug;
      if (!("slug" in payload) && result.slug && result.slug !== savedRef.current.slug && untouched) {
        savedRef.current = { ...savedRef.current, slug: result.slug };
        setForm((f) => ({ ...f, slug: result.slug }));
      }
    }
    setSaved(savedRef.current);
    setFieldErrors({});
    refreshLists();
  };

  const autosave = useAutosave({
    enabled: !isNew && Boolean(form) && meta.status !== "published", // see README: published stories are saved manually
    getChanges,
    send: (payload) => patchStory(id, payload, { autosave: true }),
    onSaved: commitSaved,
    onFailed: (err) => { if (err.status === 400) setFieldErrors(err.fieldErrors || {}); },
  });

  // Manual save: a normal PATCH (or the first POST for a new story), queued behind any autosave in flight.
  const saveNow = () => {
    autosave.cancel();
    return autosave.exclusive(async () => {
      setNotice(null);
      autosave.setStatus("saving");
      try {
        if (isNew) {
          const payload = toPayloadForm(formRef.current);
          if (!payload.slug) delete payload.slug; // blank = let the server generate it
          const story = await createStory(payload);
          clearDraft("new");
          skipBlock.current = true; // saved: do not ask "leave without saving?"
          refreshLists();
          navigate(`/admin/stories/${story.id}/edit`, { replace: true });
          return true;
        }
        const payload = getChanges();
        if (Object.keys(payload).length === 0) {
          autosave.setStatus("saved");
          return true;
        }
        const story = await patchStory(id, payload);
        commitSaved(payload, story);
        autosave.setStatus("saved");
        setNotice({ type: "ok", text: "Saved." });
        if (Object.keys(getChanges()).length) autosave.trigger();
        return true;
      } catch (err) {
        setFieldErrors(err.fieldErrors || {});
        setNotice({ type: "error", text: err.friendly });
        autosave.setStatus("failed");
        return false;
      }
    });
  };

  const onSaveClick = async () => {
    setBusy("save");
    await saveNow();
    setBusy(null);
  };

  // Publish / Unpublish / Archive / Schedule: save pending edits first, then call the action URL.
  const doAction = async (action, body, okText) => {
    setBusy(action);
    setNotice(null);
    try {
      if (dirtyRef.current && !(await saveNow())) return;
      const story = await storyAction(id, action, body);
      setMeta(metaFrom(story));
      refreshLists();
      setNotice({ type: "ok", text: okText });
    } catch (err) {
      setNotice({ type: "error", text: err.friendly });
      if (action === "schedule") setScheduleError(errText(err.fieldErrors?.scheduled_at) || err.friendly);
    } finally {
      setBusy(null);
    }
  };

  const schedule = () => {
    const when = new Date(scheduleAt);
    if (!scheduleAt || Number.isNaN(when.getTime()) || when <= new Date()) {
      setScheduleError("Pick a date and time in the future.");
      return;
    }
    setScheduleError("");
    doAction("schedule", { scheduled_at: when.toISOString() }, `Scheduled for ${fmtDateTime(when.toISOString())}.`);
  };

  // ---- editing ----
  const setField = (patch) => {
    setForm((f) => ({ ...f, ...patch }));
    setFieldErrors((errs) => {
      const next = { ...errs };
      Object.keys(patch).forEach((k) => delete next[ERROR_KEY[k] || k]);
      return next;
    });
    autosave.trigger();
  };

  // First report from the editor: its normalised copy of the document is the baseline for "dirty".
  const onEditorReady = useCallback((normalized) => {
    setForm((f) => (f ? { ...f, content_json: normalized } : f));
    if (JSON.stringify(editorInitRef.current) === JSON.stringify(savedRef.current?.content_json)) {
      savedRef.current = { ...savedRef.current, content_json: normalized };
      setSaved(savedRef.current);
    }
  }, []);

  // ---- crash protection copy (sessionStorage) ----
  useEffect(() => {
    if (!form || recovery) return undefined; // do not touch the stored copy while the person is deciding
    const t = setTimeout(() => (dirty ? writeDraft(draftKey, form) : clearDraft(draftKey)), 500);
    return () => clearTimeout(t);
  }, [form, dirty, recovery, draftKey]);

  const restoreLocal = () => {
    setForm(recovery.form);
    editorInitRef.current = recovery.form.content_json;
    setEditorKey((k) => k + 1);
    setRecovery(null);
    autosave.trigger();
  };
  const discardLocal = () => {
    clearDraft(draftKey);
    setRecovery(null);
  };

  // ---- leaving with unsaved changes ----
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    dirtyRef.current && !skipBlock.current && currentLocation.pathname !== nextLocation.pathname);

  // After a revision is restored: reload from the server and reset the editor.
  const reloadAfterRestore = async () => {
    autosave.cancel();
    try {
      const story = await getStory(id);
      clearDraft(draftKey);
      initFrom(story, { skipRecovery: true });
      refreshLists();
      setNotice({ type: "ok", text: "Version restored." });
    } catch (err) {
      setNotice({ type: "error", text: err.friendly });
    }
  };

  // ---- render ----
  const categories = useQuery({ queryKey: ["categories"], queryFn: listCategories });

  if (!isNew && storyQuery.isError) {
    return (
      <div className="notice error" role="alert">
        {storyQuery.error.status === 404 ? "That story does not exist." : storyQuery.error.friendly} <Link to="/admin/stories">Back to stories</Link>
      </div>
    );
  }
  if (!form) return <p className="muted">Loading story…</p>;

  const status = autosave.status;
  const statusText =
    status === "saving" ? "Saving…"
    : status === "retrying" ? "Autosave failed — retrying…"
    : status === "failed" ? "Not saved — see the messages on this page"
    : dirty ? "Unsaved changes"
    : autosave.savedAt ? `Saved ${fmtClock(autosave.savedAt)}`
    : isNew ? "Not saved yet" : "All changes saved";

  const saving = busy !== null || status === "saving";
  const published = meta.status === "published";
  const contentError = errText(fieldErrors.content_json);

  return (
    <>
      <div className="row wrap edit-top">
        <Link to="/admin/stories" className="btn ghost small">← Stories</Link>
        <h1 className="grow">{isNew ? "New story" : "Edit story"}</h1>
        <span className={`save-state ${status}${dirty ? " dirty" : ""}`} role="status" aria-live="polite">{statusText}</span>
        {!isNew && <button type="button" className="btn secondary small" onClick={() => setRevisions(true)}>Revisions</button>}
      </div>

      {recovery && (
        <div className="notice info" role="alert">
          We found unsaved changes from {fmtClock(recovery.savedAt)} that were never saved to the server.
          <div className="row">
            <button type="button" className="btn small" onClick={restoreLocal}>Restore them</button>
            <button type="button" className="btn secondary small" onClick={discardLocal}>Discard</button>
          </div>
        </div>
      )}
      {notice && <div className={`notice ${notice.type === "ok" ? "info" : notice.type}`} role={notice.type === "error" ? "alert" : "status"}>{notice.text}</div>}
      {errText(fieldErrors.detail) && <div className="notice error" role="alert">{errText(fieldErrors.detail)}</div>}

      <div className="edit-grid">
        <div className="edit-main">
          <label htmlFor="story-title" className="sr-only">Title</label>
          <input id="story-title" className="title-input" placeholder="Story title" value={form.title} onChange={(e) => setField({ title: e.target.value })} aria-invalid={Boolean(errText(fieldErrors.title))} />
          <FieldError errors={fieldErrors.title} />
          <ErrorBoundary title="The editor hit a problem.">
            <StoryEditor key={editorKey} initialContent={editorInitRef.current} onChange={(doc) => setField({ content_json: doc })} onReady={onEditorReady} error={contentError} />
          </ErrorBoundary>
        </div>

        <aside className="edit-side" aria-label="Story settings">
          <section className="side-section">
            <h2>Publish</h2>
            <p><StatusBadge status={meta.status} />{" "}
              {meta.status === "scheduled" && meta.scheduled_at && <span className="muted small">for {fmtDateTime(meta.scheduled_at)}</span>}
              {published && meta.published_at && <span className="muted small">since {fmtDateTime(meta.published_at)}</span>}
            </p>
            {isNew && <p className="hint">Save the draft once to unlock publishing and autosave.</p>}
            {published && <p className="hint">Autosave is off for published stories so half-finished edits never go live. Use “Save changes”.</p>}
            <div className="row wrap">
              <button type="button" className="btn" disabled={saving || (!isNew && !dirty)} onClick={onSaveClick}>
                {busy === "save" ? "Saving…" : meta.status === "draft" || isNew ? "Save draft" : "Save changes"}
              </button>
              {!isNew && !published && <button type="button" className="btn secondary" disabled={saving} onClick={() => doAction("publish", undefined, "Published.")}>{busy === "publish" ? "Publishing…" : "Publish"}</button>}
              {published && <button type="button" className="btn secondary" disabled={saving} onClick={() => doAction("unpublish", undefined, "Moved back to draft.")}>Unpublish</button>}
              {!isNew && meta.status !== "archived" && <button type="button" className="btn secondary" disabled={saving} onClick={() => doAction("archive", undefined, "Archived.")}>Archive</button>}
              {!isNew && <Link className="btn ghost" to={`/admin/stories/${id}/preview`}>Preview</Link>}
            </div>
            {!isNew && !published && (
              <div className="field schedule">
                <label htmlFor="schedule-at">Schedule for</label>
                <input id="schedule-at" type="datetime-local" value={scheduleAt} onChange={(e) => { setScheduleAt(e.target.value); setScheduleError(""); }} aria-invalid={Boolean(scheduleError)} />
                <FieldError errors={scheduleError} />
                <button type="button" className="btn secondary small" disabled={saving} onClick={schedule}>Schedule</button>
              </div>
            )}
          </section>

          <section className="side-section">
            <h2>Cover image</h2>
            {form.cover?.url ? (
              <img className="cover-preview" src={form.cover.url} alt={form.cover.alt_text || "Cover image"} />
            ) : <p className="muted small">No cover image.</p>}
            <div className="row wrap">
              <button type="button" className="btn secondary small" onClick={() => setPicker(true)}>{form.cover ? "Change" : "Choose image"}</button>
              {form.cover && <button type="button" className="btn ghost small" onClick={() => setField({ cover: null })}>Remove</button>}
            </div>
            <FieldError errors={fieldErrors.cover_image} />
          </section>

          <section className="side-section">
            <h2>Categories</h2>
            {categories.isLoading && <p className="muted small">Loading…</p>}
            {categories.isError && <p className="field-error">{categories.error.friendly}</p>}
            {categories.data?.length === 0 && <p className="muted small">No categories yet.</p>}
            <ul className="check-list">
              {(categories.data || []).map((c) => (
                <li key={c.id}>
                  <label>
                    <input type="checkbox" checked={form.category_ids.includes(c.id)} onChange={(e) => setField({ category_ids: e.target.checked ? [...form.category_ids, c.id] : form.category_ids.filter((x) => x !== c.id) })} />
                    {c.name}
                  </label>
                </li>
              ))}
            </ul>
            <FieldError errors={fieldErrors.category_ids} />
          </section>

          <section className="side-section">
            <h2>Tags</h2>
            <TagsInput value={form.tags} onChange={(tags) => setField({ tags })} onError={(text) => setNotice({ type: "error", text })} />
            <FieldError errors={fieldErrors.tag_ids} />
          </section>

          <section className="side-section">
            <h2>Excerpt</h2>
            <div className="field">
              <label htmlFor="excerpt" className="sr-only">Excerpt</label>
              <textarea id="excerpt" rows={4} maxLength={500} value={form.excerpt} onChange={(e) => setField({ excerpt: e.target.value })} />
              <p className="hint">Leave blank and one is made from the first words of the story. <Counter value={form.excerpt.length} max={500} /></p>
              <FieldError errors={fieldErrors.excerpt} />
            </div>
          </section>

          <section className="side-section">
            <h2>URL slug</h2>
            <div className="field">
              <label htmlFor="slug" className="sr-only">URL slug</label>
              <input id="slug" value={form.slug} placeholder="made from the title" onChange={(e) => setField({ slug: e.target.value })} aria-invalid={Boolean(errText(fieldErrors.slug))} />
              <p className="hint">Lowercase letters, digits and hyphens.</p>
              <FieldError errors={fieldErrors.slug} />
            </div>
          </section>

          <section className="side-section">
            <label className="switch">
              <input type="checkbox" checked={form.is_featured} onChange={(e) => setField({ is_featured: e.target.checked })} />
              Featured story
            </label>
            <FieldError errors={fieldErrors.is_featured} />
          </section>

          <section className="side-section">
            <h2>SEO</h2>
            <div className="field">
              <label htmlFor="seo-title">SEO title <Counter value={form.seo_title.length} max={70} /></label>
              <input id="seo-title" maxLength={70} value={form.seo_title} onChange={(e) => setField({ seo_title: e.target.value })} />
              <FieldError errors={fieldErrors.seo_title} />
            </div>
            <div className="field">
              <label htmlFor="seo-desc">SEO description <Counter value={form.seo_description.length} max={200} /></label>
              <textarea id="seo-desc" rows={3} maxLength={200} value={form.seo_description} onChange={(e) => setField({ seo_description: e.target.value })} />
              <FieldError errors={fieldErrors.seo_description} />
            </div>
          </section>
        </aside>
      </div>

      {picker && <MediaPicker title="Choose cover image" onPick={(a) => setField({ cover: { id: a.id, url: a.url, alt_text: a.alt_text, width: a.width, height: a.height } })} onClose={() => setPicker(false)} />}
      {revisions && <RevisionsDrawer storyId={id} hasUnsaved={dirty} onRestored={reloadAfterRestore} onClose={() => setRevisions(false)} />}
      {blocker.state === "blocked" && (
        <ConfirmDialog
          title="Leave without saving?"
          message="You have changes that are not saved to the server yet."
          confirmLabel="Leave anyway"
          danger
          onCancel={() => blocker.reset()}
          onConfirm={() => blocker.proceed()}
        />
      )}
    </>
  );
}
