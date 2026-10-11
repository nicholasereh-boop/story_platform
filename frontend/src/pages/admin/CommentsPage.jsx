import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminListComments, dismissCommentReports, getCommentSettings, listCommentReports, setCommentSettings, setCommentStatus } from "../../api";
import Modal from "../../components/Modal";
import Pagination from "../../components/Pagination";
import { fmtDateTime } from "../../utils/format";

const TABS = [
  { value: "pending", label: "Pending", params: { status: "pending" } },
  { value: "approved", label: "Approved", params: { status: "approved" } },
  { value: "hidden", label: "Hidden", params: { status: "hidden" } },
  { value: "deleted", label: "Deleted", params: { status: "deleted" } },
  { value: "reported", label: "Reported", params: { reported: 1 } }, // any status, with open reports
];
const MODES = [
  { value: "off", label: "Off: publish comments immediately" },
  { value: "approve_first", label: "Approve first: hold every new comment" },
  { value: "approve_first_time", label: "Approve first-time commenters only" },
];

function ModerationMode() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["admin", "comment-settings"], queryFn: getCommentSettings });
  const [saved, setSaved] = useState(false);
  const save = useMutation({
    mutationFn: (mode) => setCommentSettings({ comment_moderation: mode }),
    onSuccess: (result) => {
      queryClient.setQueryData(["admin", "comment-settings"], result);
      setSaved(true);
    },
  });
  return (
    <div className="field mode-field">
      <label htmlFor="moderation-mode">Moderation mode</label>
      <select
        id="moderation-mode"
        value={settings.data?.comment_moderation || ""}
        disabled={settings.isLoading || save.isPending}
        onChange={(e) => { setSaved(false); save.mutate(e.target.value); }} // saves immediately
      >
        {!settings.data && <option value="">Loading…</option>}
        {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
      </select>
      <p className="hint" role="status">
        {save.isPending ? "Saving…" : saved ? "Saved." : settings.isError ? "Could not load the setting." : ""}
        {save.isError && <span className="field-error"> {save.error.friendly}</span>}
      </p>
    </div>
  );
}

// Who reported a comment, and why. "Dismiss reports" clears them without changing the comment's status.
function ReportsDrawer({ comment, onClose, onDismissed }) {
  const reports = useQuery({ queryKey: ["admin", "comment-reports", comment.id], queryFn: () => listCommentReports(comment.id) });
  const dismiss = useMutation({ mutationFn: () => dismissCommentReports(comment.id), onSuccess: onDismissed });
  return (
    <Modal title={`Reports (${comment.report_count})`} onClose={onClose} drawer>
      <p className="comment-body">{comment.body}</p>
      {reports.isLoading && <p className="muted">Loading…</p>}
      {reports.isError && <div className="notice error" role="alert">{reports.error.friendly}</div>}
      {reports.data?.length === 0 && <p className="muted">No open reports.</p>}
      <ul className="report-list">
        {reports.data?.map((r) => (
          <li key={r.id}>
            <strong>{r.reporter.display_name}</strong> <span className="muted small">{r.reporter.email} · {fmtDateTime(r.created_at)}</span>
            <p>{r.reason || <span className="muted">No reason given.</span>}</p>
          </li>
        ))}
      </ul>
      {dismiss.isError && <div className="notice error" role="alert">{dismiss.error.friendly}</div>}
      <div className="row end">
        <button type="button" className="btn secondary" onClick={onClose}>Close</button>
        <button type="button" className="btn" disabled={dismiss.isPending || !reports.data?.length} onClick={() => dismiss.mutate()}>
          {dismiss.isPending ? "Working…" : "Dismiss reports"}
        </button>
      </div>
    </Modal>
  );
}

export default function CommentsPage() {
  const queryClient = useQueryClient();
  // Filters live in the URL so a refresh or a shared link keeps them.
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.value === params.get("tab")) ? params.get("tab") : "pending";
  const q = params.get("q") || "";
  const page = Number(params.get("page")) || 1;
  const [search, setSearch] = useState(q);
  const [reportsFor, setReportsFor] = useState(null);
  const [actionError, setActionError] = useState("");

  const update = (changes) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next, { replace: true });
  };

  // Search runs 300 ms after typing stops and goes back to page 1.
  useEffect(() => {
    const t = setTimeout(() => {
      if (search.trim() !== q) update({ q: search.trim(), page: "" });
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const tabParams = TABS.find((t) => t.value === tab).params;
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["admin", "comments", { tab, q, page }],
    queryFn: () => adminListComments({ ...tabParams, q: q || undefined, page }),
    placeholderData: (prev) => prev,
  });

  const changed = () => queryClient.invalidateQueries({ queryKey: ["admin", "comments"] }); // lists AND the sidebar badge
  const moderate = useMutation({
    mutationFn: ({ id, status }) => setCommentStatus(id, status),
    onSuccess: () => { setActionError(""); changed(); },
    onError: (err) => setActionError(err.friendly),
  });

  const items = data?.items || [];

  return (
    <>
      <h1>Comments</h1>
      <ModerationMode />

      <div className="row wrap">
        <div className="tabs" role="tablist" aria-label="Filter comments">
          {TABS.map((t) => (
            <button key={t.value} type="button" role="tab" aria-selected={tab === t.value} className={tab === t.value ? "active" : undefined} onClick={() => update({ tab: t.value === "pending" ? "" : t.value, page: "" })}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="field grow">
          <label htmlFor="comment-search" className="sr-only">Search comments</label>
          <input id="comment-search" type="search" placeholder="Search text or author email…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      {actionError && <div className="notice error" role="alert">{actionError}</div>}
      {isLoading && <p className="muted">Loading comments…</p>}
      {isError && (
        <div className="notice error" role="alert">
          {error.friendly} <button type="button" className="btn secondary small" onClick={() => refetch()}>Retry</button>
        </div>
      )}
      {!isLoading && !isError && items.length === 0 && <div className="empty">{q ? "No comments match this search." : "Nothing here."}</div>}

      {items.length > 0 && (
        <div className={`table-wrap${isFetching ? " busy" : ""}`}>
          <table className="table comments-table">
            <thead>
              <tr><th>Comment</th><th>Author</th><th>Story</th><th>Posted</th><th>Status</th><th className="num">Reports</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id}>
                  <td className="comment-cell"><p className="comment-body">{c.body}</p>{c.parent && <span className="muted small">Reply</span>}</td>
                  <td>{c.author.display_name}<br /><span className="muted small">{c.author.email}</span></td>
                  <td><Link to={`/stories/${c.story.slug}`}>{c.story.title}</Link></td>
                  <td>{fmtDateTime(c.created_at)}</td>
                  <td><span className={`badge cstatus-${c.status}`}>{c.status}</span></td>
                  <td className="num">
                    {c.report_count > 0 ? (
                      <button type="button" className="btn secondary small" onClick={() => setReportsFor(c)}>{c.report_count} {c.report_count === 1 ? "report" : "reports"}</button>
                    ) : "0"}
                  </td>
                  <td>
                    <div className="row-actions">
                      {c.status !== "approved" && <button type="button" className="btn secondary small" disabled={moderate.isPending} onClick={() => moderate.mutate({ id: c.id, status: "approved" })}>Approve</button>}
                      {c.status !== "hidden" && <button type="button" className="btn secondary small" disabled={moderate.isPending} onClick={() => moderate.mutate({ id: c.id, status: "hidden" })}>Hide</button>}
                      {c.status !== "deleted" && <button type="button" className="btn secondary small" disabled={moderate.isPending} onClick={() => moderate.mutate({ id: c.id, status: "deleted" })}>Delete</button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pagination pagination={data?.pagination} onPage={(p) => update({ page: p > 1 ? String(p) : "" })} />

      {reportsFor && (
        <ReportsDrawer
          comment={reportsFor}
          onClose={() => setReportsFor(null)}
          onDismissed={() => { setReportsFor(null); changed(); }}
        />
      )}
    </>
  );
}
