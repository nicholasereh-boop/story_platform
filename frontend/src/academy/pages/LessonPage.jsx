import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { getCourse, getLesson } from "../api/learning";
import Curriculum from "../components/Curriculum";
import LessonComments from "../components/LessonComments";
import LessonPlayer from "../components/LessonPlayer";
import { REASON_TEXT, courseUrl } from "../components/lessonUtils";
import { useAuth } from "../../auth/AuthContext";
import "../academy-learning.css";

function Step({ done, active, label, detail }) {
  return (
    <li className={`ac-step-item${done ? " is-done" : ""}${active ? " is-active" : ""}`}>
      <span className="ac-step-dot" aria-hidden="true">{done ? "✓" : ""}</span>
      <span><strong>{label}</strong><span className="ac-muted"> {detail}</span></span>
    </li>
  );
}

export default function LessonPage() {
  const { lessonId } = useParams();
  const { user } = useAuth() || {};
  const location = useLocation();
  const qc = useQueryClient();
  const key = ["ac-lesson", lessonId];
  const lesson = useQuery({ queryKey: [...key, user?.id ?? null], queryFn: () => getLesson(lessonId), retry: (n, err) => err.status !== 404 && n < 1 });
  const slug = lesson.data?.course.slug;
  const outline = useQuery({ queryKey: ["ac-course", slug, user?.id ?? null], queryFn: () => getCourse(slug), enabled: Boolean(slug) });
  useDocumentMeta({ title: lesson.data?.lesson.title || "Lesson", robots: "noindex" });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: key });
    qc.invalidateQueries({ queryKey: ["ac-course"] });
    qc.invalidateQueries({ queryKey: ["ac-my-learning"] });
  };
  // A progress save or a new comment returns the learner's new access: apply it at once, then refresh the outline.
  const apply = (access, progress) => {
    qc.setQueryData([...key, user?.id ?? null], (old) => (old ? { ...old, access: { ...old.access, ...access }, ...(progress ? { progress: { ...old.progress, ...progress } } : {}) } : old));
    qc.invalidateQueries({ queryKey: ["ac-course"] });
  };

  if (lesson.isLoading) return <div className="ac-container"><p className="ac-muted">Loading the lesson…</p></div>;
  if (lesson.isError) return <div className="ac-container"><h1 className="ac-h1">Lesson not found</h1><p className="ac-muted"><Link to="/academy/free">Back to the tutorials</Link></p></div>;

  const { lesson: l, course, access, progress } = lesson.data;
  const back = courseUrl(course);
  const next = lesson.data.next_lesson_id;
  const canWatch = access.can_view && l.youtube_id;

  return (
    <div className="ac-container ac-lesson-page">
      <p><Link to={back} className="ac-back">← {course.title}</Link></p>
      <div className="ac-lesson-layout">
        <div className="ac-lesson-main-col">
          <h1 className="ac-h1">{l.title}</h1>
          {canWatch ? (
            <LessonPlayer key={l.id} lesson={l} progress={progress} onSaved={(r) => apply(r.access, r.progress)} />
          ) : (
            <div className="ac-locked" role="status">
              <p className="ac-locked-icon" aria-hidden="true">🔒</p>
              <p><strong>{REASON_TEXT[access.reason] || "This lesson is not open yet."}</strong></p>
              {access.reason === "login_required" && <Link className="ac-btn ac-btn-primary" to="/login" state={{ from: location.pathname, message: "Log in to open this lesson." }}>Log in</Link>}
              {access.reason !== "login_required" && <Link className="ac-btn ac-btn-ghost" to={back}>See the course</Link>}
            </div>
          )}

          {canWatch && !l.is_intro && l.requires_comment && (
            <ol className="ac-steps-row" aria-label="How to unlock the next lesson">
              <Step done={access.watch_met} active={!access.watch_met} label="Watch" detail={`${progress.percent}% watched`} />
              <Step done={access.comment_met} active={access.watch_met && !access.comment_met} label="Comment" detail={access.watch_met ? "share what you learned" : "after watching"} />
              <Step done={access.next_unlocked} active={false} label="Next lesson" detail={access.next_unlocked ? "open" : "locked"} />
            </ol>
          )}

          <div className="ac-nav-row">
            {lesson.data.previous_lesson_id ? <Link className="ac-btn ac-btn-ghost" to={`/academy/learn/${lesson.data.previous_lesson_id}`}>← Previous</Link> : <span />}
            {next ? (
              access.next_unlocked
                ? <Link className="ac-btn ac-btn-primary" to={`/academy/learn/${next}`}>Next lesson →</Link>
                : <button type="button" className="ac-btn ac-btn-primary" disabled title="Finish this lesson first">Next lesson 🔒</button>
            ) : <Link className="ac-btn ac-btn-primary" to={back} onClick={refresh}>Back to the course</Link>}
          </div>

          {l.description && <section className="ac-panel"><h2>Lesson notes</h2><p className="ac-text">{l.description}</p></section>}
          <LessonComments lessonId={String(l.id)} access={access} onAccessChange={(a) => apply(a)} />
        </div>

        <aside className="ac-lesson-side" aria-label="Course outline">
          <h2 className="ac-side-title">{course.title}</h2>
          {outline.data && <Curriculum lessons={outline.data.lessons} currentId={l.id} />}
        </aside>
      </div>
    </div>
  );
}