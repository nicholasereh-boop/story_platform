import { Link } from "react-router-dom";
import { REASON_TEXT, STATE_ICON, STATE_LABEL, formatDuration } from "./lessonUtils";

// The course outline: every lesson with its state. Open lessons are links; locked ones say why. The server decides all of it.
export default function Curriculum({ lessons, currentId }) {
  return (
    <ol className="ac-curriculum" aria-label="Lessons">
      {lessons.map((l, i) => {
        const dur = formatDuration(l.duration_seconds);
        const label = l.can_view ? STATE_LABEL[l.state] : REASON_TEXT[l.reason] || STATE_LABEL.locked;
        const inner = (
          <>
            <span className={`ac-cur-icon ac-cur-${l.state}`} aria-hidden="true">{STATE_ICON[l.state]}</span>
            <span className="ac-cur-main">
              <span className="ac-cur-title">{l.is_intro ? "Introduction: " : `${i + (lessons[0]?.is_intro ? 0 : 1)}. `}{l.title}</span>
              <span className="ac-cur-sub">{l.is_preview && !l.is_intro ? "Free preview · " : ""}{label}{dur ? ` · ${dur}` : ""}</span>
            </span>
          </>
        );
        return (
          <li key={l.id} className={`ac-cur-item${l.id === currentId ? " is-current" : ""}${l.can_view ? "" : " is-locked"}`}>
            {l.can_view ? <Link to={`/academy/learn/${l.id}`} aria-current={l.id === currentId ? "step" : undefined}>{inner}</Link> : <span className="ac-cur-locked">{inner}</span>}
          </li>
        );
      })}
    </ol>
  );
}