import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminCreateLesson, adminDeleteLesson, adminListLessons, adminReorderLessons, adminUpdateLesson } from "../api/authoring";
import { Field, firstError } from "./formHelpers";

const BLANK = { title: "", youtube: "", description: "", duration: "0", is_intro: false, is_preview: false, gate: true, threshold: "90", published: false };

const fromLesson = (l) => ({
  title: l.title, youtube: l.youtube_id ? `https://youtu.be/${l.youtube_id}` : "", description: l.description, duration: String(l.duration_seconds),
  is_intro: l.is_intro, is_preview: l.is_preview, gate: l.requires_comment_to_unlock_next, threshold: String(l.completion_threshold), published: l.is_published,
});
const toBody = (f) => ({
  title: f.title.trim(), youtube_url: f.youtube.trim(), description: f.description, duration_seconds: Number(f.duration) || 0,
  is_intro: f.is_intro, is_preview: f.is_preview, requires_comment_to_unlock_next: f.gate, completion_threshold: Number(f.threshold) || 90, is_published: f.published,
});

function LessonForm({ initial, onSave, onCancel, saving, error }) {
  const [f, setF] = useState(initial);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const err = (...keys) => (error ? firstError({ fieldErrors: Object.fromEntries(keys.map((k) => [k, error.fieldErrors?.[k]]).filter(([, v]) => v)) }, ...keys) : "");
  const hasFieldError = (k) => Boolean(error?.fieldErrors?.[k]);
  return (
    <form className="ac-lesson-form" onSubmit={(e) => { e.preventDefault(); onSave(toBody(f)); }}>
      <Field id="l-title" label="Lesson title" error={hasFieldError("title") ? err("title") : ""}>
        <input id="l-title" value={f.title} onChange={set("title")} maxLength={160} required />
      </Field>
      <Field id="l-yt" label="YouTube link" hint="Paste the video link. Only the video id is kept." error={hasFieldError("youtube_url") ? err("youtube_url") : ""}>
        <input id="l-yt" value={f.youtube} onChange={set("youtube")} placeholder="https://www.youtube.com/watch?v=…" />
      </Field>
      <Field id="l-desc" label="Lesson notes (optional)">
        <textarea id="l-desc" rows={3} value={f.description} onChange={set("description")} />
      </Field>
      <div className="ac-grid-2">
        <Field id="l-dur" label="Video length in seconds (optional)" hint="Used to work out how much was watched." error={hasFieldError("duration_seconds") ? err("duration_seconds") : ""}>
          <input id="l-dur" type="number" min="0" max="86400" value={f.duration} onChange={set("duration")} />
        </Field>
        <Field id="l-th" label="Counts as watched at (%)" error={hasFieldError("completion_threshold") ? err("completion_threshold") : ""}>
          <input id="l-th" type="number" min="10" max="100" value={f.threshold} onChange={set("threshold")} />
        </Field>
      </div>
      <div className="ac-checks">
        <label><input type="checkbox" checked={f.is_intro} onChange={set("is_intro")} /> This is the course introduction (always open, never needs a comment)</label>
        <label><input type="checkbox" checked={f.is_preview} onChange={set("is_preview")} /> Free preview (anyone can watch it)</label>
        <label><input type="checkbox" checked={f.gate && !f.is_intro} disabled={f.is_intro} onChange={set("gate")} /> A comment is needed to unlock the next lesson</label>
        <label><input type="checkbox" checked={f.published} onChange={set("published")} /> Published</label>
      </div>
      {hasFieldError("is_intro") && <p className="ac-error" role="alert">{err("is_intro")}</p>}
      {hasFieldError("is_published") && <p className="ac-error" role="alert">{err("is_published")}</p>}
      {error && !Object.keys(error.fieldErrors || {}).length && <p className="ac-error" role="alert">{error.friendly}</p>}
      <div className="ac-actions">
        <button type="submit" className="ac-btn ac-btn-primary" disabled={saving}>{saving ? "Saving…" : "Save lesson"}</button>
        <button type="button" className="ac-btn ac-btn-ghost" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

// The lessons of one course: add, edit, reorder (buttons, so it works with a keyboard), unpublish and delete.
export default function LessonManager({ courseId }) {
  const qc = useQueryClient();
  const key = ["ac-admin-lessons", courseId];
  const lessons = useQuery({ queryKey: key, queryFn: () => adminListLessons(courseId) });
  const [editing, setEditing] = useState(null); // lesson id, "new", or null
  const [error, setError] = useState(null);
  const done = () => { setEditing(null); setError(null); qc.invalidateQueries({ queryKey: key }); qc.invalidateQueries({ queryKey: ["ac-admin-course", courseId] }); };

  const save = useMutation({
    mutationFn: (body) => (editing === "new" ? adminCreateLesson(courseId, body) : adminUpdateLesson(editing, body)),
    onSuccess: done,
    onError: setError,
  });
  const remove = useMutation({ mutationFn: adminDeleteLesson, onSuccess: done, onError: (e) => setError(e) });
  const move = useMutation({ mutationFn: (order) => adminReorderLessons(courseId, order), onSuccess: () => qc.invalidateQueries({ queryKey: key }) });

  const items = lessons.data || [];
  const swap = (i, j) => {
    const ids = items.map((l) => l.id);
    [ids[i], ids[j]] = [ids[j], ids[i]];
    move.mutate(ids);
  };

  return (
    <section className="ac-panel" aria-labelledby="lessons-h">
      <div className="ac-panel-head">
        <h2 id="lessons-h">Lessons</h2>
        {editing === null && <button type="button" className="ac-btn ac-btn-primary" onClick={() => { setError(null); setEditing("new"); }}>Add lesson</button>}
      </div>
      {lessons.isLoading && <p className="ac-muted">Loading lessons…</p>}
      {!lessons.isLoading && items.length === 0 && editing !== "new" && <p className="ac-muted">No lessons yet. Add the first one.</p>}
      {editing === "new" && <LessonForm initial={BLANK} onSave={(b) => save.mutate(b)} onCancel={() => setEditing(null)} saving={save.isPending} error={error} />}
      <ol className="ac-lessons">
        {items.map((l, i) => (
          <li key={l.id} className="ac-lesson">
            <div className="ac-lesson-row">
              <span className="ac-lesson-n" aria-hidden="true">{i + 1}</span>
              <div className="ac-lesson-main">
                <strong>{l.title}</strong>
                <span className="ac-badges">
                  {l.is_intro && <span className="ac-badge">Intro</span>}
                  {l.is_preview && <span className="ac-badge">Preview</span>}
                  {l.requires_comment_to_unlock_next && !l.is_intro && <span className="ac-badge">Comment unlocks next</span>}
                  <span className={`ac-badge ${l.is_published ? "ac-badge-ok" : "ac-badge-warn"}`}>{l.is_published ? "Published" : "Draft"}</span>
                  {!l.youtube_id && <span className="ac-badge ac-badge-warn">No video</span>}
                </span>
              </div>
              <div className="ac-lesson-actions">
                <button type="button" className="ac-icon-btn" aria-label={`Move ${l.title} up`} disabled={i === 0 || move.isPending} onClick={() => swap(i, i - 1)}>▲</button>
                <button type="button" className="ac-icon-btn" aria-label={`Move ${l.title} down`} disabled={i === items.length - 1 || move.isPending} onClick={() => swap(i, i + 1)}>▼</button>
                <button type="button" className="ac-btn ac-btn-ghost" onClick={() => { setError(null); setEditing(l.id); }}>Edit</button>
                <button type="button" className="ac-btn ac-btn-ghost ac-danger" onClick={() => { if (window.confirm(`Delete “${l.title}”?`)) remove.mutate(l.id); }}>Delete</button>
              </div>
            </div>
            {editing === l.id && <LessonForm initial={fromLesson(l)} onSave={(b) => save.mutate(b)} onCancel={() => setEditing(null)} saving={save.isPending} error={error} />}
          </li>
        ))}
      </ol>
      {error && editing === null && <p className="ac-error" role="alert">{error.friendly}</p>}
    </section>
  );
}