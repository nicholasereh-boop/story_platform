import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Pagination from "../../components/Pagination";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { listCourses } from "../api/learning";
import CourseCard from "../components/CourseCard";
import "../academy-learning.css";

const COPY = {
  free: { title: "Free tutorials", lede: "Beginner-friendly courses. Watch a lesson, leave a comment, and the next one opens.", empty: "No free courses yet. Check back soon." },
  paid: { title: "Paid tutorials", lede: "In-depth premium courses. Buy once and every lesson is yours.", empty: "No premium courses yet. Check back soon." },
};

export default function CourseCatalogPage({ access }) {
  const copy = COPY[access];
  useDocumentMeta({ title: copy.title, description: copy.lede });
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const courses = useQuery({
    queryKey: ["ac-courses", { access, q, page }],
    queryFn: () => listCourses({ access, q: q.trim() || undefined, page }),
    placeholderData: (previous) => previous,
  });
  const items = courses.data?.items || [];
  return (
    <div className="ac-container">
      <header className="ac-page-head">
        <div>
          <h1 className="ac-h1">{copy.title}</h1>
          <p className="ac-lede">{copy.lede}</p>
        </div>
      </header>
      <form className="ac-filters" role="search" aria-label="Search courses" onSubmit={(e) => e.preventDefault()}>
        <label>Search<input type="search" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="HTML, React, CSS…" /></label>
      </form>
      {courses.isLoading && <p className="ac-muted">Loading courses…</p>}
      {courses.isError && <p className="ac-error" role="alert">Could not load the courses. Please try again.</p>}
      {courses.data && items.length === 0 && <p className="ac-empty">{q ? "No courses match your search." : copy.empty}</p>}
      <ul className="ac-course-grid">{items.map((c) => <CourseCard key={c.id} course={c} />)}</ul>
      {courses.data && <Pagination pagination={courses.data.pagination} onPage={(n) => { setPage(n); window.scrollTo?.(0, 0); }} />}
    </div>
  );
}