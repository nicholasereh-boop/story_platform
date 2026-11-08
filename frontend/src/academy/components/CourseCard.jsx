import { Link } from "react-router-dom";
import { courseUrl, formatDuration } from "./lessonUtils";
import { money } from "./formHelpers";

const LEVEL = { beginner: "Beginner", intermediate: "Intermediate", advanced: "Advanced" };

export default function CourseCard({ course, progress }) {
  const paid = course.access_type === "paid";
  const duration = formatDuration(course.duration_seconds);
  return (
    <li className="ac-course">
      <Link to={courseUrl(course)} className="ac-course-link">
        <span className="ac-course-media">
          {course.thumbnail?.url ? <img src={course.thumbnail.url} alt={course.thumbnail.alt_text || ""} loading="lazy" /> : <span className="ac-course-noimg" aria-hidden="true">🎓</span>}
          <span className={`ac-chip ac-course-price ${paid ? "ac-chip-paid" : "ac-chip-free"}`}>{paid ? money(course.price, course.currency) : "Free"}</span>
        </span>
        <span className="ac-course-body">
          <span className="ac-course-meta">{[LEVEL[course.level], course.category].filter(Boolean).join(" · ")}</span>
          <h2 className="ac-course-title">{course.title}</h2>
          {course.summary ? <p className="ac-course-summary">{course.summary}</p> : null}
          <span className="ac-course-foot">{course.lesson_count} {course.lesson_count === 1 ? "lesson" : "lessons"}{duration ? ` · ${duration}` : ""}</span>
          {progress ? (
            <span className="ac-progress" aria-label={`${progress.percent}% complete`}>
              <span className="ac-progress-bar"><span style={{ width: `${progress.percent}%` }} /></span>
              <span className="ac-progress-text">{progress.completed} of {progress.total} done</span>
            </span>
          ) : null}
        </span>
      </Link>
    </li>
  );
}