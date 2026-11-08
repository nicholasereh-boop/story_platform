import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import Pagination from "../../components/Pagination";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { adminListCourses } from "../api/authoring";
import { StatusChip, money } from "../components/formHelpers";
import "../academy-admin.css";

export default function AcademyAdminPage() {
  useDocumentMeta({ title: "Manage Academy", robots: "noindex" });
  const [status, setStatus] = useState("");
  const [access, setAccess] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const courses = useQuery({
    queryKey: ["ac-admin-courses", { status, access, q, page }],
    queryFn: () => adminListCourses({ status: status || undefined, access: access || undefined, q: q.trim() || undefined, page }),
    placeholderData: (previous) => previous,
  });
  const items = courses.data?.items || [];
  const reset = (setter) => (e) => { setter(e.target.value); setPage(1); };

  return (
    <div className="ac-container">
      <div className="ac-page-head">
        <div>
          <h1 className="ac-h1">Manage courses</h1>
          <p className="ac-muted">Create courses, add lessons, then publish them when they are ready.</p>
        </div>
        <div className="ac-actions">
          <Link to="/academy/admin/orders" className="ac-btn ac-btn-ghost">Orders and access</Link>
          <Link to="/academy/admin/courses/new" className="ac-btn ac-btn-primary">New course</Link>
        </div>
      </div>

      <form className="ac-filters" role="search" aria-label="Filter courses" onSubmit={(e) => e.preventDefault()}>
        <label>Search<input type="search" value={q} onChange={reset(setQ)} placeholder="Course title…" /></label>
        <label>Status
          <select value={status} onChange={reset(setStatus)}>
            <option value="">All</option><option value="draft">Draft</option><option value="published">Published</option><option value="archived">Archived</option>
          </select>
        </label>
        <label>Type
          <select value={access} onChange={reset(setAccess)}>
            <option value="">All</option><option value="free">Free</option><option value="paid">Paid</option>
          </select>
        </label>
      </form>

      {courses.isLoading && <p className="ac-muted">Loading…</p>}
      {courses.isError && <p className="ac-error" role="alert">Could not load the courses.</p>}
      {courses.data && items.length === 0 && <p className="ac-empty">No courses match. <Link to="/academy/admin/courses/new">Create the first one</Link>.</p>}
      <ul className="ac-admin-list">
        {items.map((c) => (
          <li key={c.id} className="ac-admin-item">
            <div className="ac-admin-main">
              <h2><Link to={`/academy/admin/courses/${c.id}`}>{c.title}</Link></h2>
              <p className="ac-muted">{c.published_lesson_count} of {c.lesson_count} lessons published · {c.learner_count} {c.learner_count === 1 ? "learner" : "learners"}</p>
            </div>
            <div className="ac-admin-meta">
              <StatusChip status={c.status} />
              <span className={`ac-chip ${c.access_type === "paid" ? "ac-chip-paid" : "ac-chip-free"}`}>{c.access_type === "paid" ? money(c.price, c.currency) : "Free"}</span>
              <Link to={`/academy/admin/courses/${c.id}`} className="ac-btn ac-btn-ghost">Edit</Link>
            </div>
          </li>
        ))}
      </ul>
      {courses.data && <Pagination pagination={courses.data.pagination} onPage={(n) => { setPage(n); window.scrollTo?.(0, 0); }} />}
    </div>
  );
}