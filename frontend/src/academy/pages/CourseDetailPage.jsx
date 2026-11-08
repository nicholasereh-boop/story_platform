import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { enrollInCourse, getCourse } from "../api/learning";
import Curriculum from "../components/Curriculum";
import PurchasePanel from "../components/PurchasePanel";
import { courseUrl, formatDuration, kindOf } from "../components/lessonUtils";
import { money } from "../components/formHelpers";
import "../academy-learning.css";

export default function CourseDetailPage({ kind }) {
  const { slug } = useParams();
  const { user } = useAuth() || {};
  const location = useLocation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const course = useQuery({ queryKey: ["ac-course", slug, user?.id ?? null], queryFn: () => getCourse(slug), retry: (n, err) => err.status !== 404 && n < 1 });
  const c = course.data;
  useDocumentMeta({ title: c?.title || "Course", description: c?.summary, robots: c ? "index,follow" : "noindex" });

  const start = useMutation({
    mutationFn: () => enrollInCourse(slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ac-course"] });
      const target = c.viewer.next_lesson_id || c.lessons[0]?.id;
      if (target) navigate(`/academy/learn/${target}`);
    },
  });

  if (course.isLoading) return <div className="ac-container"><p className="ac-muted">Loading…</p></div>;
  if (course.isError) return <div className="ac-container"><h1 className="ac-h1">Course not found</h1><p className="ac-muted">That course does not exist or is not published. <Link to="/academy/free">Browse the free tutorials</Link>.</p></div>;
  if (kind && kind !== kindOf(c)) return <Navigate to={courseUrl(c)} replace />; // opened under the wrong /free or /paid address

  const paid = c.access_type === "paid";
  const v = c.viewer;
  const duration = formatDuration(c.duration_seconds);
  const firstLesson = c.lessons.find((l) => l.can_view);
  return (
    <div className="ac-container">
      <p><Link to={`/academy/${kindOf(c)}`} className="ac-back">← {paid ? "Paid" : "Free"} tutorials</Link></p>
      <div className="ac-detail">
        <div className="ac-detail-main">
          <header className="ac-detail-head">
            <span className={`ac-chip ${paid ? "ac-chip-paid" : "ac-chip-free"}`}>{paid ? money(c.price, c.currency) : "Free"}</span>
            <h1 className="ac-h1">{c.title}</h1>
            {c.summary && <p className="ac-lede">{c.summary}</p>}
            <p className="ac-muted">{c.lesson_count} {c.lesson_count === 1 ? "lesson" : "lessons"}{duration ? ` · ${duration}` : ""}{c.category ? ` · ${c.category}` : ""}</p>
          </header>
          {c.thumbnail?.url && <img className="ac-detail-img" src={c.thumbnail.url} alt={c.thumbnail.alt_text || ""} />}
          {c.description && <section className="ac-panel"><h2>About this course</h2><p className="ac-text">{c.description}</p></section>}
          <section className="ac-panel" aria-labelledby="ac-outline-h">
            <h2 id="ac-outline-h">What you will learn</h2>
            <Curriculum lessons={c.lessons} />
          </section>
        </div>
        <aside className="ac-detail-side" aria-label="Start this course">
          {v.authenticated && v.total > 0 && (
            <div className="ac-buy">
              <p className="ac-buy-title">Your progress</p>
              <span className="ac-progress"><span className="ac-progress-bar"><span style={{ width: `${v.percent}%` }} /></span><span className="ac-progress-text">{v.completed} of {v.total} lessons done</span></span>
            </div>
          )}
          {paid ? (
            <PurchasePanel course={c} viewer={v} firstLessonId={firstLesson?.id} />
          ) : (
            <div className="ac-buy">
              <p className="ac-buy-price">Free</p>
              {v.authenticated ? (
                <button type="button" className="ac-btn ac-btn-primary" disabled={start.isPending || !c.lessons.length} onClick={() => start.mutate()}>
                  {v.enrolled && v.completed > 0 ? "Continue learning" : v.enrolled ? "Resume" : "Start learning"}
                </button>
              ) : (
                <>
                  <Link className="ac-btn ac-btn-primary" to="/login" state={{ from: location.pathname, message: "Log in to start this course." }}>Log in to start</Link>
                  {firstLesson?.is_intro && <Link className="ac-btn ac-btn-ghost" to={`/academy/learn/${firstLesson.id}`}>Watch the introduction</Link>}
                </>
              )}
              {start.isError && <p className="ac-error" role="alert">Could not start the course. Please try again.</p>}
              <p className="ac-hint">Watch each lesson, then leave a comment to open the next one.</p>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}