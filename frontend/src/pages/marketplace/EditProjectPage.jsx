import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { archiveProject, createProject, getMarketplaceConfig, myProject, submitProject, unpublishProject, updateProject } from "../../api/marketplace";
import PackageEditor from "../../components/marketplace/PackageEditor";
import ScreenshotManager from "../../components/marketplace/ScreenshotManager";
import { ProjectStatus, firstError } from "../../components/marketplace/shared";
import QueryState from "../../components/public/QueryState";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import "./marketplace.css";

const blank = { title: "", summary: "", description: "", notes: "", technologies: "", youtube: "",  frontendVideo: "", backendVideo: "", frontendPrice: "0", backendPrice: "0", rights: false };

function fromProject(p) {
  return {
    title: p.title, summary: p.summary, description: p.description, notes: p.notes,
    technologies: p.technologies.map((t) => t.name).join(", "), youtube: p.youtube_id ? `https://youtu.be/${p.youtube_id}` : "",
    frontendVideo: p.frontend_video_id ? `https://youtu.be/${p.frontend_video_id}` : "",
    backendVideo: p.backend_video_id ? `https://youtu.be/${p.backend_video_id}` : "",
    frontendPrice: String(p.frontend_price ?? "0"), backendPrice: String(p.backend_price ?? "0"), rights: Boolean(p.rights_confirmed_at),
  };
}
const toBody = (f) => ({
  title: f.title.trim(), summary: f.summary.trim(), description: f.description, notes: f.notes,
  technologies: f.technologies.split(",").map((s) => s.trim()).filter(Boolean), youtube_url: f.youtube.trim(),
  frontend_video_url: f.frontendVideo.trim(), backend_video_url: f.backendVideo.trim(),
  frontend_price: f.frontendPrice.trim() || "0", backend_price: f.backendPrice.trim() || "0", rights_confirmed: f.rights,
});

function Field({ id, label, error, hint, children }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {error ? <p className="field-error" role="alert">{error}</p> : hint ? <p className="hint">{hint}</p> : null}
    </div>
  );
}

function DetailsForm({ project, onSaved }) {
  // Prices are in the site currency (US dollars); an older project keeps the currency it was priced in.
  const config = useQuery({ queryKey: ["mp-config"], queryFn: getMarketplaceConfig, staleTime: 10 * 60 * 1000 });
  const currency = project?.currency || config.data?.currency || "USD";
  const [form, setForm] = useState(project ? fromProject(project) : blank);
  const [saved, setSaved] = useState("");
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const save = useMutation({
    mutationFn: () => (project ? updateProject(project.id, toBody(form)) : createProject(toBody(form))),
    onSuccess: (p) => {
      setSaved(p.sent_back_to_review ? "Saved. Because this project is live, it has gone back to review." : "Saved.");
      onSaved(p);
    },
  });
  const err = (f) => save.error?.fieldErrors?.[f]?.[0];
  const locked = project?.status === "archived";

  return (
    <form className="mp-section stack" onSubmit={(e) => { e.preventDefault(); setSaved(""); save.mutate(); }} aria-labelledby="details-h">
      <h2 id="details-h">Project details</h2>
      <Field id="p-title" label="Title" error={err("title")}><input id="p-title" value={form.title} onChange={set("title")} maxLength={160} required disabled={locked} /></Field>
      <Field id="p-summary" label="One-line summary" error={err("summary")} hint="Shown on the project card."><input id="p-summary" value={form.summary} onChange={set("summary")} maxLength={300} disabled={locked} /></Field>
      <Field id="p-desc" label="Description" error={err("description")} hint="What it is, what is included, who it is for. Plain text.">
        <textarea id="p-desc" rows={7} value={form.description} onChange={set("description")} maxLength={20000} disabled={locked} />
      </Field>
      <Field id="p-notes" label="Setup and usage notes" error={err("notes")} hint="Requirements and how to run it. Plain text; code is fine.">
        <textarea id="p-notes" rows={5} value={form.notes} onChange={set("notes")} maxLength={20000} disabled={locked} />
      </Field>
      <Field id="p-tech" label="Technologies" error={err("technologies")} hint="Separate with commas, for example React, Django, Tailwind. Up to 12."><input id="p-tech" value={form.technologies} onChange={set("technologies")} disabled={locked} /></Field>
      <Field id="p-vf" label="Frontend description video (YouTube link, optional)" error={err("frontend_video_url")}><input id="p-vf" value={form.frontendVideo} onChange={set("frontendVideo")} placeholder="https://www.youtube.com/watch?v=…" disabled={locked} /></Field>
      <Field id="p-vb" label="Backend description video (YouTube link, optional)" error={err("backend_video_url")}><input id="p-vb" value={form.backendVideo} onChange={set("backendVideo")} placeholder="https://www.youtube.com/watch?v=…" disabled={locked} /></Field>
      <Field id="p-yt" label="Frontend and backend description video (YouTube link, optional)" error={err("youtube_url")}><input id="p-yt" value={form.youtube} onChange={set("youtube")} placeholder="https://www.youtube.com/watch?v=…" disabled={locked} /></Field>
      <div className="mp-two">
        <Field id="p-fp" label={`Frontend price in ${currency} (0 = free)`} error={err("frontend_price")}><input id="p-fp" inputMode="decimal" value={form.frontendPrice} onChange={set("frontendPrice")} disabled={locked} /></Field>
        <Field id="p-bp" label={`Backend price in ${currency}`} error={err("backend_price")} hint={config.data?.backend_requires_payment === false ? "Paid packages are sold through Paystack." : "Backend source code is always paid: buyers pay with Paystack before they can download it."}><input id="p-bp" inputMode="decimal" value={form.backendPrice} onChange={set("backendPrice")} disabled={locked} /></Field>
      </div>
      <div className="field">
        <label className="check">
          <input type="checkbox" checked={form.rights} onChange={set("rights")} disabled={locked} aria-describedby="rights-hint" />
          I own this code, or I have the right to distribute it.
        </label>
        {err("rights_confirmed") ? <p className="field-error" role="alert">{err("rights_confirmed")}</p> : <p className="hint" id="rights-hint">Required before you can submit.</p>}
      </div>
      {save.isError && !Object.keys(save.error?.fieldErrors || {}).length && <p className="field-error" role="alert">{firstError(save.error)}</p>}
      {saved && <p className="notice" role="status">{saved}</p>}
      <div className="row"><button type="submit" className="btn" disabled={save.isPending || locked}>{save.isPending ? "Saving…" : project ? "Save changes" : "Create draft"}</button></div>
    </form>
  );
}

function PublishSection({ project, onChanged }) {
  const options = (fn) => ({ mutationFn: () => fn(project.id), onSuccess: onChanged });
  const submit = useMutation(options(submitProject));
  const unpublish = useMutation(options(unpublishProject));
  const archive = useMutation(options(archiveProject));
  const failed = [submit, unpublish, archive].find((m) => m.isError);
  const fields = failed?.error?.fieldErrors ? Object.values(failed.error.fieldErrors).flat() : [];
  const canSubmit = project.status === "draft" || project.status === "rejected";

  return (
    <section className="mp-section" aria-labelledby="publish-h">
      <h2 id="publish-h">Publishing</h2>
      <p>Status: <ProjectStatus status={project.status} /></p>
      {project.status === "rejected" && project.review_note ? <p className="notice error" role="alert">The reviewer asked for changes: {project.review_note}</p> : null}
      {project.status === "pending" ? <p className="muted">A reviewer will check this project before it appears in the marketplace.</p> : null}
      {project.status === "published" ? <p><Link to={`/marketplace/projects/${project.slug}`}>View the public page</Link></p> : null}
      {failed && <ul className="field-error" role="alert">{(fields.length ? fields : [failed.error.friendly]).map((m) => <li key={m}>{m}</li>)}</ul>}
      <div className="row">
        {canSubmit && <button type="button" className="btn" disabled={submit.isPending} onClick={() => submit.mutate()}>Submit for publishing</button>}
        {(project.status === "published" || project.status === "pending") && <button type="button" className="btn secondary" disabled={unpublish.isPending} onClick={() => unpublish.mutate()}>Take offline</button>}
        {project.status !== "archived" && <button type="button" className="btn secondary" disabled={archive.isPending} onClick={() => { if (window.confirm("Archive this project? New buyers will no longer see it.")) archive.mutate(); }}>Archive</button>}
      </div>
    </section>
  );
}

function Editor({ project: initial }) {
  const qc = useQueryClient();
  const [project, setProject] = useState(initial);
  useEffect(() => setProject(initial), [initial]);
  const changed = (p) => {
    setProject(p);
    qc.invalidateQueries({ queryKey: ["mp-my"] });
    qc.invalidateQueries({ queryKey: ["mp-projects"] });
  };
  const offer = (kind) => project.packages.find((p) => p.kind === kind);
  const locked = project.status === "archived";
  return (
    <>
      <DetailsForm project={project} onSaved={changed} />
      <ScreenshotManager projectId={project.id} screenshots={project.screenshots} onChanged={async () => changed(await myProject(project.id))} />
      <div className="mp-two">
        <PackageEditor projectId={project.id} kind="frontend" current={offer("frontend")} disabled={locked} onChanged={changed} />
        <PackageEditor projectId={project.id} kind="backend" current={offer("backend")} disabled={locked} onChanged={changed} />
      </div>
      <PublishSection project={project} onChanged={changed} />
    </>
  );
}

export default function EditProjectPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const creating = !id;
  useDocumentMeta({ title: creating ? "Sell your source code" : "Edit project", robots: "noindex" });
  const query = useQuery({ queryKey: ["mp-my", id], queryFn: () => myProject(id), enabled: !creating });

  return (
    <div className="container">
      <p><Link to="/marketplace/my">← My projects</Link></p>
      <h1>{creating ? "Sell your source code" : "Edit project"}</h1>
      {creating ? (
        <>
          <p className="muted">Start with the basics. After you create the draft you can add screenshots and your frontend or backend files.</p>
          <DetailsForm project={null} onSaved={(p) => navigate(`/marketplace/projects/${p.id}/edit`, { replace: true })} />
        </>
      ) : (
        <QueryState query={query} skeleton={<p className="muted">Loading…</p>} notFound={<p className="notice error">That project was not found.</p>}>
          {(project) => <Editor project={project} />}
        </QueryState>
      )}
    </div>
  );
}
