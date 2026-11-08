import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { fmtDate } from "../../utils/format";
import { deleteLessonComment, listLessonComments, postLessonComment } from "../api/learning";
import { firstError } from "./formHelpers";

const MAX = 5000;

// The comments under a lesson. In a free course, a lesson that asks for a comment opens the next lesson once the learner has
// watched enough and posted one. The server enforces all of that; this component only shows the right messages.
export default function LessonComments({ lessonId, access, onAccessChange }) {
  const { user } = useAuth() || {};
  const location = useLocation();
  const qc = useQueryClient();
  const key = ["ac-comments", lessonId];
  const [text, setText] = useState("");
  const [error, setError] = useState(null);

  const list = useQuery({ queryKey: key, queryFn: () => listLessonComments(lessonId), enabled: Boolean(access?.can_view) });
  const post = useMutation({
    mutationFn: () => postLessonComment(lessonId, text),
    onSuccess: (result) => { setText(""); setError(null); qc.invalidateQueries({ queryKey: key }); onAccessChange?.(result.access); },
    onError: setError,
  });
  const remove = useMutation({
    mutationFn: deleteLessonComment,
    onSuccess: () => { qc.invalidateQueries({ queryKey: key }); qc.invalidateQueries({ queryKey: ["ac-lesson", lessonId] }); },
  });

  const items = list.data?.items || [];
  const needsWatch = access?.requires_comment && !access?.watch_met;
  const waitingForComment = access?.requires_comment && access?.watch_met && !access?.comment_met;

  return (
    <section className="ac-panel ac-comments" aria-labelledby="ac-comments-h">
      <h2 id="ac-comments-h">Comments</h2>
      {waitingForComment && <p className="ac-callout" role="status">💬 Share what you learned in a comment to open the next lesson.</p>}
      {access?.requires_comment && access?.comment_met && <p className="ac-callout ac-callout-ok" role="status">✓ Your comment unlocked the next lesson.</p>}

      {!user ? (
        <p className="ac-muted"><Link to="/login" state={{ from: location.pathname, message: "Log in to comment." }}>Log in</Link> to join the conversation.</p>
      ) : !access?.can_view ? null : (
        <form className="ac-comment-form" onSubmit={(e) => { e.preventDefault(); post.mutate(); }}>
          <label htmlFor="ac-comment-text" className="ac-label">Add a comment</label>
          <textarea id="ac-comment-text" rows={3} value={text} maxLength={MAX} onChange={(e) => setText(e.target.value)} disabled={needsWatch} placeholder={needsWatch ? "Watch the lesson first, then you can comment." : "What did you learn? Any questions?"} />
          {error && <p className="ac-error" role="alert">{firstError(error, "body")}</p>}
          <div className="ac-actions">
            <button type="submit" className="ac-btn ac-btn-primary" disabled={post.isPending || needsWatch || !text.trim()}>{post.isPending ? "Posting…" : "Post comment"}</button>
            <span className="ac-muted">{text.length}/{MAX}</span>
          </div>
        </form>
      )}

      {list.isLoading && <p className="ac-muted">Loading comments…</p>}
      {list.data && items.length === 0 && <p className="ac-muted">No comments yet. Be the first.</p>}
      <ul className="ac-comment-list">
        {items.map((c) => (
          <li key={c.id} className="ac-comment">
            <div className="ac-comment-head">
              <strong>{c.author}</strong>
              <span className="ac-muted">{fmtDate(c.created_at)}</span>
              {c.status === "pending" && <span className="ac-badge ac-badge-warn">Awaiting approval</span>}
            </div>
            <p className="ac-comment-body">{c.body}</p>
            {c.mine && <button type="button" className="ac-link-btn" onClick={() => { if (window.confirm("Delete your comment?")) remove.mutate(c.id); }}>Delete</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}