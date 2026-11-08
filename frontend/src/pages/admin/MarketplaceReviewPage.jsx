import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { adminProjects, moderateProject } from "../../api/marketplace";
import Pagination from "../../components/Pagination";
import QueryState from "../../components/public/QueryState";
import { ProjectStatus, KIND_LABELS } from "../../components/marketplace/shared";
import { formatBytes, formatPrice } from "../../utils/money";
import "../marketplace/marketplace.css";

const TABS = [["pending", "Waiting"], ["published", "Published"], ["rejected", "Rejected"], ["archived", "Archived"], ["", "All"]];

function Item({ project, onChanged }) {
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const act = useMutation({
    mutationFn: ({ action, body }) => moderateProject(project.id, action, body),
    onSuccess: () => { setRejecting(false); setNote(""); onChanged(); },
  });
  const noteError = act.error?.fieldErrors?.note?.[0];
  return (
    <li className="mp-queue-item">
      <h2><Link to={`/marketplace/projects/${project.slug}`}>{project.title}</Link> <ProjectStatus status={project.status} /></h2>
      <p className="mp-meta">{project.seller} · {project.owner_email} · rights confirmed: {project.rights_confirmed_at ? "yes" : "no"}</p>
      {project.summary ? <p>{project.summary}</p> : null}
      <p className="mp-text">{project.description.slice(0, 400)}{project.description.length > 400 ? "…" : ""}</p>
      <ul className="plain-list">
        {project.packages.map((p) => (
          <li key={p.kind}>
            {KIND_LABELS[p.kind]} v{p.version}: {formatBytes(p.size_bytes)}, {p.file_count} files, {formatPrice(p.price, p.currency)}, from {p.source === "github" ? `GitHub ${p.source_ref}` : "ZIP upload"}
            {p.scan_report?.excluded_count ? ` · ${p.scan_report.excluded_count} files left out by the upload check` : ""}
          </li>
        ))}
        {project.packages.length === 0 && <li className="muted">No packages.</li>}
      </ul>
      {project.review_note ? <p className="mp-meta">Last review note: {project.review_note}</p> : null}
      {act.isError && !noteError && <p className="field-error" role="alert">{act.error.friendly}</p>}
      {rejecting ? (
        <form className="stack" onSubmit={(e) => { e.preventDefault(); act.mutate({ action: "reject", body: { note } }); }}>
          <div className="field">
            <label htmlFor={`note-${project.id}`}>What should the seller fix?</label>
            <textarea id={`note-${project.id}`} rows={3} value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
            {noteError && <p className="field-error" role="alert">{noteError}</p>}
          </div>
          <div className="row">
            <button type="submit" className="btn small" disabled={act.isPending}>Send rejection</button>
            <button type="button" className="btn small secondary" onClick={() => setRejecting(false)}>Cancel</button>
          </div>
        </form>
      ) : (
        <div className="row">
          {project.status !== "published" && <button type="button" className="btn small" disabled={act.isPending} onClick={() => act.mutate({ action: "approve" })}>Approve and publish</button>}
          {project.status !== "rejected" && <button type="button" className="btn small secondary" onClick={() => setRejecting(true)}>Reject…</button>}
          {project.status !== "archived" && <button type="button" className="btn small secondary" disabled={act.isPending} onClick={() => act.mutate({ action: "archive" })}>Archive</button>}
        </div>
      )}
    </li>
  );
}

export default function MarketplaceReviewPage() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["mp-admin", status, page], queryFn: () => adminProjects({ status: status || undefined, page }), placeholderData: (p) => p });
  return (
    <div>
      <div className="mp-head">
        <h1>Marketplace review</h1>
        <div className="row">
          <Link className="btn secondary" to="/marketplace/my">My projects</Link>
          <Link className="btn" to="/marketplace/publish">Add source code</Link>
        </div>
      </div>
      <div className="tabs" role="group" aria-label="Filter by status">
        {TABS.map(([value, label]) => (
          <button key={label} type="button" className={`btn small ${status === value ? "" : "secondary"}`} aria-pressed={status === value} onClick={() => { setStatus(value); setPage(1); }}>{label}</button>
        ))}
      </div>
      <QueryState query={query} skeleton={<p className="muted">Loading…</p>} isEmpty={(d) => d.items.length === 0} empty={<div className="empty"><p>Nothing here. <Link to="/marketplace/publish">Add source code</Link> to list a project yourself.</p></div>}>
        {(data) => (
          <>
            <ul className="plain-list">{data.items.map((p) => <Item key={p.id} project={p} onChanged={() => qc.invalidateQueries({ queryKey: ["mp-admin"] })} />)}</ul>
            <Pagination pagination={data.pagination} onPage={setPage} />
          </>
        )}
      </QueryState>
    </div>
  );
}
