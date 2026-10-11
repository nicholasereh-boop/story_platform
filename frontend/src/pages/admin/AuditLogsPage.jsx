import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listAuditLogs } from "../../api/security";
import Pagination from "../../components/Pagination";
import { ACTION_FAMILIES, cleanParams, describeMetadata } from "../../utils/audit";
import { fmtDateTime } from "../../utils/format";

const EMPTY = { action: "", actor: "", object_type: "", from: "", to: "", q: "" };
const OBJECT_TYPES = ["", "story", "category", "tag", "media", "comment", "user", "setting"];

// Admin: the audit log. Read-only on purpose: there is no way to edit or delete an entry here or in the API.
export default function AuditLogsPage() {
  const [draft, setDraft] = useState(EMPTY);
  const [filters, setFilters] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const params = cleanParams(filters, page);
  const logs = useQuery({ queryKey: ["admin", "audit-logs", params], queryFn: () => listAuditLogs(params), placeholderData: (prev) => prev });
  const set = (name) => (e) => setDraft({ ...draft, [name]: e.target.value });
  const rows = logs.data?.items || [];

  return (
    <div className="audit-page">
      <h1>Audit log</h1>
      <p className="muted">Who did what, and when. Entries cannot be changed or deleted; old ones are removed automatically after the retention period.</p>
      <form className="filters row wrap" onSubmit={(e) => { e.preventDefault(); setPage(1); setFilters(draft); }} role="search" aria-label="Filter the audit log">
        <div className="field">
          <label htmlFor="audit-action">Action</label>
          <select id="audit-action" value={draft.action} onChange={set("action")}>
            {ACTION_FAMILIES.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="audit-type">Object type</label>
          <select id="audit-type" value={draft.object_type} onChange={set("object_type")}>
            {OBJECT_TYPES.map((t) => <option key={t} value={t}>{t || "Any type"}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="audit-actor">Actor (user id)</label>
          <input id="audit-actor" inputMode="numeric" pattern="[0-9]*" value={draft.actor} onChange={set("actor")} />
        </div>
        <div className="field">
          <label htmlFor="audit-from">From</label>
          <input id="audit-from" type="date" value={draft.from} onChange={set("from")} />
        </div>
        <div className="field">
          <label htmlFor="audit-to">To</label>
          <input id="audit-to" type="date" value={draft.to} onChange={set("to")} />
        </div>
        <div className="field">
          <label htmlFor="audit-q">Search</label>
          <input id="audit-q" type="search" value={draft.q} placeholder="Name, action or id" onChange={set("q")} />
        </div>
        <button className="btn">Apply</button>
        <button type="button" className="btn ghost" onClick={() => { setDraft(EMPTY); setFilters(EMPTY); setPage(1); }}>Clear</button>
      </form>

      {logs.isLoading && <p className="muted">Loading the audit log…</p>}
      {logs.isError && <div className="notice error" role="alert">{logs.error.friendly} <button type="button" className="link-button" onClick={() => logs.refetch()}>Try again</button></div>}
      {logs.isSuccess && rows.length === 0 && <p className="empty">No entries match these filters.</p>}

      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table audit-table">
            <caption className="sr-only">Audit log entries, newest first</caption>
            <thead>
              <tr><th scope="col">When</th><th scope="col">Who</th><th scope="col">What</th><th scope="col">Object</th><th scope="col">Details</th></tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const details = describeMetadata(row.metadata);
                return (
                  <tr key={row.id}>
                    <td className="nowrap">{fmtDateTime(row.created_at)}</td>
                    <td>{row.actor_label}</td>
                    <td>{row.action_label}<span className="muted small block"><code>{row.action}</code></span></td>
                    <td>{row.object_type ? `${row.object_type} #${row.object_id}` : "—"}</td>
                    <td>
                      {details.length === 0 ? <span className="muted">—</span> : (
                        <dl className="meta-list">
                          {details.map((d) => (<div key={d.key}><dt>{d.key}</dt><dd>{d.text}</dd></div>))}
                        </dl>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <Pagination pagination={logs.data?.pagination} onPage={setPage} />
    </div>
  );
}
