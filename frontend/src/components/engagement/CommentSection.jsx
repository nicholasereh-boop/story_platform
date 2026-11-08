import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../auth/AuthContext";
import { createComment } from "../../api/engagement";
import CommentForm from "./CommentForm";
import CommentList from "./CommentList";

// "Comments" block of the story page. What the reader sees at the top depends on who they are:
//   visitor          -> can READ comments but not write one: a note with Log in / Create account links
//   logged-in user   -> the comment form (no email verification is needed)
// (Liking a story is open to visitors too, see LikeButton. Only commenting needs an account, and the server enforces it.)
export default function CommentSection({ slug, count = 0 }) {
  const { user, ready } = useAuth() || {};
  const location = useLocation();
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState("");

  const post = async (text) => {
    const created = await createComment(slug, text);
    setNotice(created.status === "pending" ? "Thanks! Your comment is waiting for approval and only you can see it for now." : "");
    queryClient.invalidateQueries({ queryKey: ["comments", slug] });
    queryClient.invalidateQueries({ queryKey: ["public", "story", slug] });
  };

  return (
    <section className="comments" aria-labelledby="comments-heading">
      <h2 id="comments-heading">Comments{count > 0 && <span className="muted"> ({count})</span>}</h2>

      {ready && !user && (
        <div className="comment-gate" role="note">
          <p>Only logged-in readers can write comments. Reading and liking are open to everyone.</p>
          <p className="comment-gate-actions">
            <Link className="btn small" to="/login" state={{ from: location.pathname }}>Log in to comment</Link>
            <Link className="btn secondary small" to="/register" state={{ from: location.pathname }}>Create an account</Link>
          </p>
        </div>
      )}

      {user && (
        <>
          {notice && <div className="notice info" role="status">{notice}</div>}
          <CommentForm onSubmit={post} />
        </>
      )}

      <CommentList slug={slug} user={user} />
    </section>
  );
}
