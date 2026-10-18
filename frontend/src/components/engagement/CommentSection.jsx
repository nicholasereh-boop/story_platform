import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../auth/AuthContext";
import { createComment } from "../../api/engagement";
import { useSignupPrompt } from "../../engagement/SignupPromptContext";
import CommentForm from "./CommentForm";
import CommentList from "./CommentList";

// "Comments" block of the story page. What the reader sees at the top depends on who they are:
//   visitor          -> "Log in to join the discussion" (+ a button that opens the signup prompt)
//   logged-in user   -> the comment form (no email verification is needed)
export default function CommentSection({ slug, count = 0 }) {
  const { user, ready } = useAuth() || {};
  const { request } = useSignupPrompt();
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
        <div className="comment-gate">
          <Link to="/login" state={{ from: location.pathname }}>Log in to join the discussion</Link>
          <button type="button" className="btn secondary small" onClick={() => request("comment")}>Write a comment</button>
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
