import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import Pagination from "../../components/Pagination";
import { fmtDate } from "../../utils/format";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { adminListCourses } from "../api/authoring";
import { adminCourseAccess, adminGrantAccess, adminListOrders, adminRefundOrder, adminRevokeAccess } from "../api/paid";
import { Field, firstError, money } from "../components/formHelpers";
import "../academy-admin.css";
import "../academy-paid.css";

function AccessSection() {
  const qc = useQueryClient();
  const courses = useQuery({ queryKey: ["ac-admin-courses", "paid-list"], queryFn: () => adminListCourses({ access: "paid" }) });
  const [courseId, setCourseId] = useState("");
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [until, setUntil] = useState("");
  const [error, setError] = useState(null);
  const key = ["ac-admin-access", courseId];
  const access = useQuery({ queryKey: key, queryFn: () => adminCourseAccess(courseId), enabled: Boolean(courseId) });
  const grant = useMutation({
    mutationFn: () => adminGrantAccess(courseId, { email: email.trim(), note: note.trim(), ...(until ? { expires_on: until } : {}) }),
    onSuccess: () => { setEmail(""); setNote(""); setUntil(""); setError(null); qc.invalidateQueries({ queryKey: key }); },
    onError: setError,
  });
  const revoke = useMutation({ mutationFn: (mail) => adminRevokeAccess(courseId, mail), onSuccess: () => qc.invalidateQueries({ queryKey: key }) });
  const fe = (k) => (error?.fieldErrors?.[k] ? firstError(error, k) : "");

  return (
    <section className="ac-panel" aria-labelledby="access-h">
      <h2 id="access-h">Complimentary access</h2>
      <p className="ac-muted">Give someone a paid course for free, for example a prize or a review copy. Every grant and removal is recorded in the audit log.</p>
      <Field id="a-course" label="Paid course">
        <select id="a-course" value={courseId} onChange={(e) => { setCourseId(e.target.value); setError(null); }}>
          <option value="">Choose a course…</option>
          {(courses.data?.items || []).map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
        </select>
      </Field>
      {courseId && (
        <>
          <form className="ac-grant-form" onSubmit={(e) => { e.preventDefault(); grant.mutate(); }}>
            <Field id="a-email" label="Learner's email" error={fe("email")}><input id="a-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
            <Field id="a-note" label="Note (optional)"><input id="a-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} /></Field>
            <Field id="a-until" label="Ends on (optional)" hint="Leave empty for lifetime access." error={fe("expires_on")}><input id="a-until" type="date" value={until} onChange={(e) => setUntil(e.target.value)} /></Field>
            {error && !Object.keys(error.fieldErrors || {}).length && <p className="ac-error" role="alert">{error.friendly}</p>}
            <button type="submit" className="ac-btn ac-btn-primary" disabled={grant.isPending}>{grant.isPending ? "Granting…" : "Grant access"}</button>
          </form>
          <h3 className="ac-h3">Who has access</h3>
          {access.data?.length === 0 && <p className="ac-muted">Nobody yet.</p>}
          <ul className="ac-access-list">
            {(access.data || []).map((a) => (
              <li key={a.id}>
                <span><strong>{a.learner_email}</strong> <span className="ac-muted">· {a.source === "grant" ? "complimentary" : "purchased"}{a.expires_at ? ` · ends ${fmtDate(a.expires_at)}` : ""}{a.note ? ` · ${a.note}` : ""}</span></span>
                <span>
                  <span className={`ac-status ac-status-${a.status === "active" ? "published" : "archived"}`}>{a.status === "active" ? "Active" : "Revoked"}</span>
                  {a.status === "active" && <button type="button" className="ac-link-btn" onClick={() => { if (window.confirm(`Remove ${a.learner_email}'s access?`)) revoke.mutate(a.learner_email); }}>Remove</button>}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function OrdersSection() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const orders = useQuery({ queryKey: ["ac-admin-orders", { status, page }], queryFn: () => adminListOrders({ status: status || undefined, page }), placeholderData: (p) => p });
  const refund = useMutation({ mutationFn: adminRefundOrder, onSuccess: () => qc.invalidateQueries({ queryKey: ["ac-admin-orders"] }) });
  const items = orders.data?.items || [];
  return (
    <section className="ac-panel" aria-labelledby="orders-h">
      <div className="ac-panel-head">
        <h2 id="orders-h">Orders</h2>
        <label className="ac-inline-select">Status
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All</option><option value="success">Paid</option><option value="pending">Pending</option><option value="failed">Failed</option><option value="refunded">Refunded</option>
          </select>
        </label>
      </div>
      <p className="ac-muted">Refunding here records the refund and ends the access. Return the money itself from your Paystack dashboard.</p>
      {orders.data && items.length === 0 && <p className="ac-muted">No orders match.</p>}
      {items.length > 0 && (
        <div className="ac-table-wrap">
          <table className="ac-table">
            <thead><tr><th>Date</th><th>Learner</th><th>Course</th><th>Price</th><th>Charged</th><th>Status</th><th /></tr></thead>
            <tbody>
              {items.map((o) => (
                <tr key={o.id}>
                  <td>{fmtDate(o.created_at)}</td><td>{o.learner_email}</td><td>{o.course.title}</td>
                  <td>{money(o.list_price ?? o.amount, o.list_currency || o.currency)}</td><td>{money(o.amount, o.currency)}</td>
                  <td>{o.status}</td>
                  <td>{o.status === "success" && <button type="button" className="ac-link-btn" onClick={() => { if (window.confirm(`Refund ${o.learner_email}'s order and end their access?`)) refund.mutate(o.id); }}>Refund</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {refund.isError && <p className="ac-error" role="alert">{refund.error?.friendly || "Could not refund this order."}</p>}
      {orders.data && <Pagination pagination={orders.data.pagination} onPage={(n) => setPage(n)} />}
    </section>
  );
}

export default function AcademyOrdersAdminPage() {
  useDocumentMeta({ title: "Academy orders and access", robots: "noindex" });
  return (
    <div className="ac-container">
      <p><Link to="/academy/admin" className="ac-back">← Manage courses</Link></p>
      <h1 className="ac-h1">Orders and access</h1>
      <AccessSection />
      <OrdersSection />
    </div>
  );
}