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
//   unverified user  -> "Verify your email to comment" + Resend
//   verified user    -> the comment form
export default function CommentSection({ slug, count = 0 }) {
  const { user, ready, resendVerification } = useAuth() || {};
  const { request } = useSignupPrompt();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState("");
  const [resend, setResend] = useState({ busy: false, message: "", error: "" });

  const post = async (text) => {
    const created = await createComment(slug, text);
    setNotice(created.status === "pending" ? "Thanks! Your comment is waiting for approval and only you can see it for now." : "");
    queryClient.invalidateQueries({ queryKey: ["comments", slug] });
    queryClient.invalidateQueries({ queryKey: ["public", "story", slug] });
  };

  const sendVerification = async () => {
    setResend({ busy: true, message: "", error: "" });
    try {
      const result = await resendVerification();
      setResend({ busy: false, message: result?.message || "Verification email sent.", error: "" });
    } catch (err) {
      setResend({ busy: false, message: "", error: err.friendly });
    }
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

      {user && !user.email_verified && (
        <div className="notice info">
          <p>Verify your email to comment.</p>
          <button type="button" className="btn secondary small" disabled={resend.busy} onClick={sendVerification}>
            {resend.busy ? "Sending…" : "Resend verification email"}
          </button>
          {resend.message && <p className="small" role="status">{resend.message}</p>}
          {resend.error && <p className="field-error" role="alert">{resend.error}</p>}
        </div>
      )}

      {user?.email_verified && (
        <>
          {notice && <div className="notice info" role="status">{notice}</div>}
          <CommentForm onSubmit={post} />
        </>
      )}

      <CommentList slug={slug} user={user} />
    </section>
  );
}
