import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import MediaPicker from "../../components/media/MediaPicker";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { adminCourseAction, adminCreateCourse, adminDeleteCourse, adminGetCourse, adminUpdateCourse } from "../api/authoring";
import { getAcademyConfig } from "../api/academy";
import { Field, StatusChip, firstError } from "../components/formHelpers";
import LessonManager from "../components/LessonManager";
import "../academy-admin.css";

const BLANK = { title: "", slug: "", summary: "", description: "", level: "beginner", category: "", access_type: "free", price: "0", rights: false, thumbnail: null };
const fromCourse = (c) => ({
  title: c.title, slug: c.slug, summary: c.summary, description: c.description, level: c.level, category: c.category,
  access_type: c.access_type, price: String(c.price), rights: c.video_rights_confirmed, thumbnail: c.thumbnail,
});
const toBody = (f, creating) => ({
  title: f.title.trim(), ...(creating && f.slug.trim() ? { slug: f.slug.trim() } : {}), summary: f.summary.trim(), description: f.description,
  level: f.level, category: f.category.trim(), access_type: f.access_type, price: f.access_type === "paid" ? f.price.trim() || "0" : "0",
  thumbnail_id: f.thumbnail?.id ?? null, video_rights_confirmed: f.rights,
});

export default function CourseEditorPage() {
  const { id } = useParams();
  const creating = !id;
  const navigate = useNavigate();
  const qc = useQueryClient();
  useDocumentMeta({ title: creating ? "New course" : "Edit course", robots: "noindex" });

  const config = useQuery({ queryKey: ["ac-config"], queryFn: getAcademyConfig, staleTime: 5 * 60 * 1000 });
  const course = useQuery({ queryKey: ["ac-admin-course", id], queryFn: () => adminGetCourse(id), enabled: !creating });
  const [form, setForm] = useState(BLANK);
  const [picker, setPicker] = useState(false);
  const [problems, setProblems] = useState([]);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (course.data) setForm(fromCourse(course.data)); }, [course.data]);
  const set = (k) => (e) => { setSaved(false); setForm((p) => ({ ...p, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value })); };
  const refresh = () => { qc.invalidateQueries({ queryKey: ["ac-admin-course", id] }); qc.invalidateQueries({ queryKey: ["ac-admin-courses"] }); };

  const save = useMutation({
    mutationFn: () => (creating ? adminCreateCourse(toBody(form, true)) : adminUpdateCourse(id, toBody(form, false))),
    onSuccess: (c) => { setError(null); setSaved(true); refresh(); if (creating) navigate(`/academy/admin/courses/${c.id}`, { replace: true }); },
    onError: setError,
  });
  const act = useMutation({
    mutationFn: (action) => adminCourseAction(id, action),
    onSuccess: () => { setProblems([]); setError(null); refresh(); },
    onError: (e) => { const list = e.fieldErrors?.publish; if (Array.isArray(list)) setProblems(list); else setError(e); },
  });
  const remove = useMutation({
    mutationFn: () => adminDeleteCourse(id),
    onSuccess: () => { refresh(); navigate("/academy/admin", { replace: true }); },
    onError: setError,
  });

  const fe = (k) => (error?.fieldErrors?.[k] ? firstError(error, k) : "");
  const c = course.data;
  const currency = config.data?.currency || "USD";

  if (!creating && course.isLoading) return <div className="ac-container"><p className="ac-muted">Loading…</p></div>;
  if (!creating && course.isError) return <div className="ac-container"><p className="ac-error" role="alert">That course could not be found. <Link to="/academy/admin">Back to all courses</Link></p></div>;

  return (
    <div className="ac-container">
      <p><Link to="/academy/admin" className="ac-back">← All courses</Link></p>
      <div className="ac-page-head">
        <h1 className="ac-h1">{creating ? "New course" : c?.title || "Edit course"}</h1>
        {c && <StatusChip status={c.status} />}
      </div>

      <form className="ac-panel ac-form" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        <Field id="c-title" label="Course title" error={fe("title")}>
          <input id="c-title" value={form.title} onChange={set("title")} maxLength={160} required />
        </Field>
        {creating && (
          <Field id="c-slug" label="Web address (optional)" hint="Leave empty to make one from the title." error={fe("slug")}>
            <input id="c-slug" value={form.slug} onChange={set("slug")} placeholder="html-basics" />
          </Field>
        )}
        <Field id="c-summary" label="Short summary" error={fe("summary")}>
          <input id="c-summary" value={form.summary} onChange={set("summary")} maxLength={300} />
        </Field>
        <Field id="c-desc" label="About this course" error={fe("description")}>
          <textarea id="c-desc" rows={6} value={form.description} onChange={set("description")} />
        </Field>
        <div className="ac-grid-2">
          <Field id="c-level" label="Level">
            <select id="c-level" value={form.level} onChange={set("level")}>
              <option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option>
            </select>
          </Field>
          <Field id="c-cat" label="Category" error={fe("category")}>
            <input id="c-cat" value={form.category} onChange={set("category")} maxLength={60} placeholder="HTML, React…" />
          </Field>
        </div>
        <div className="ac-grid-2">
          <Field id="c-access" label="Type" hint={c?.locked_type ? "This course already has learners or orders, so its type is locked." : ""} error={fe("access_type")}>
            <select id="c-access" value={form.access_type} onChange={set("access_type")} disabled={Boolean(c?.locked_type)}>
              <option value="free">Free</option><option value="paid">Paid</option>
            </select>
          </Field>
          {form.access_type === "paid" && (
            <Field id="c-price" label={`Price (${currency})`} hint="Learners are charged the equivalent in naira at checkout." error={fe("price")}>
              <input id="c-price" type="number" min="1" step="0.01" value={form.price} onChange={set("price")} />
            </Field>
          )}
        </div>
        <div className="ac-field">
          <span className="ac-label">Course image</span>
          <div className="ac-thumb-row">
            {form.thumbnail?.url ? <img src={form.thumbnail.url} alt={form.thumbnail.alt_text || ""} className="ac-thumb" /> : <span className="ac-thumb ac-thumb-empty" aria-hidden="true">🎓</span>}
            <button type="button" className="ac-btn ac-btn-ghost" onClick={() => setPicker(true)}>{form.thumbnail ? "Change image" : "Choose image"}</button>
            {form.thumbnail && <button type="button" className="ac-btn ac-btn-ghost" onClick={() => { setSaved(false); setForm((p) => ({ ...p, thumbnail: null })); }}>Remove</button>}
          </div>
          {fe("thumbnail_id") && <p className="ac-error" role="alert">{fe("thumbnail_id")}</p>}
        </div>
        <div className="ac-checks">
          <label><input type="checkbox" checked={form.rights} onChange={set("rights")} /> I confirm I have the right to use the videos in this course.</label>
        </div>
        {error && !Object.keys(error.fieldErrors || {}).length && <p className="ac-error" role="alert">{error.friendly}</p>}
        {saved && <p className="ac-ok" role="status">Saved.</p>}
        <div className="ac-actions">
          <button type="submit" className="ac-btn ac-btn-primary" disabled={save.isPending}>{save.isPending ? "Saving…" : creating ? "Create course" : "Save changes"}</button>
        </div>
      </form>
      {picker && <MediaPicker title="Choose a course image" onPick={(asset) => { setSaved(false); setForm((p) => ({ ...p, thumbnail: { id: asset.id, url: asset.url || asset.file, alt_text: asset.alt_text } })); }} onClose={() => setPicker(false)} />}

      {c && (
        <>
          <section className="ac-panel" aria-labelledby="publish-h">
            <h2 id="publish-h">Publishing</h2>
            <p className="ac-muted">{c.status === "published" ? "This course is live." : c.status === "archived" ? "This course is archived and hidden." : "This course is a draft. Learners cannot see it yet."}</p>
            {problems.length > 0 && (
              <div className="ac-problems" role="alert">
                <strong>Not ready to publish yet:</strong>
                <ul>{problems.map((p) => <li key={p}>{p}</li>)}</ul>
              </div>
            )}
            <div className="ac-actions">
              {c.status !== "published" && <button type="button" className="ac-btn ac-btn-primary" disabled={act.isPending} onClick={() => act.mutate("publish")}>Publish</button>}
              {c.status === "published" && <button type="button" className="ac-btn ac-btn-ghost" disabled={act.isPending} onClick={() => act.mutate("unpublish")}>Unpublish</button>}
              {c.status !== "archived" && <button type="button" className="ac-btn ac-btn-ghost" disabled={act.isPending} onClick={() => act.mutate("archive")}>Archive</button>}
              <button type="button" className="ac-btn ac-btn-ghost ac-danger" onClick={() => { if (window.confirm("Delete this course for good?")) remove.mutate(); }}>Delete</button>
            </div>
          </section>
          <LessonManager courseId={String(c.id)} />
        </>
      )}
    </div>
  );
}