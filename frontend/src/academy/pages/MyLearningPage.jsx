import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { getMyLearning } from "../api/learning";
import CourseCard from "../components/CourseCard";
import "../academy-learning.css";

export default function MyLearningPage() {
  useDocumentMeta({ title: "My learning", robots: "noindex" });
  const mine = useQuery({ queryKey: ["ac-my-learning"], queryFn: getMyLearning });
  const items = mine.data?.items || [];
  return (
    <div className="ac-container">
      <header className="ac-page-head"><div><h1 className="ac-h1">My learning</h1><p className="ac-lede">Pick up where you left off.</p></div><Link to="/academy/orders" className="ac-btn ac-btn-ghost">My orders</Link></header>
      {mine.isLoading && <p className="ac-muted">Loading…</p>}
      {mine.isError && <p className="ac-error" role="alert">Could not load your courses. Please try again.</p>}
      {mine.data && items.length === 0 && <p className="ac-empty">You have not started a course yet. <Link to="/academy/free">Browse the free tutorials</Link>.</p>}
      <ul className="ac-course-grid">
        {items.map((c) => (
          <li key={c.id} className="ac-mine">
            <ul className="ac-course-grid ac-course-grid-single"><CourseCard course={c} progress={c} /></ul>
            {c.next_lesson_id ? <Link className="ac-btn ac-btn-primary" to={`/academy/learn/${c.next_lesson_id}`}>{c.completed > 0 ? "Continue" : "Start"}</Link> : <span className="ac-chip ac-chip-free">All done 🎉</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}