import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../../../auth/AuthContext";
import CommentForm from "../../../components/engagement/CommentForm";
import Pagination from "../../../components/Pagination";
import { engagementError } from "../../../engagement/errors";
import { deleteNewsComment, listNewsComments, postNewsComment } from "../api/news";
import { formatDate } from "../utils/text";

// Reader comments under a News article. Plain text only: React escapes the body and CSS keeps the line breaks.
// Visitors can read but must log in to write (the server enforces it). Own comments waiting for approval are marked.
export default function NewsComments({ slug }) {
  const { user, ready } = useAuth() || {};
  const location = useLocation();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(null);
  const key = ["news", "comments", slug];
  const list = useQuery({ queryKey: [...key, page], queryFn: () => listNewsComments(slug, page), placeholderData: (p) => p, retry: false });
  const remove = useMutation({
    mutationFn: (id) => deleteNewsComment(id),
    onSuccess: () => { setConfirming(null); setError(""); qc.invalidateQueries({ queryKey: key }); },
    onError: (e) => setError(engagementError(e)),
  });
  const post = async (text) => {
    const created = await postNewsComment(slug, text);
    setNotice(created.status === "pending" ? "Thanks! Your comment is waiting for approval and only you can see it for now." : "");
    qc.invalidateQueries({ queryKey: key });
  };
  const items = list.data?.items || [];
  return (
    <section className="nw-comments" aria-labelledby="nw-comments-heading">
      <h2 id="nw-comments-heading" className="nw-h2">Comments</h2>
      {ready && !user && (
        <div className="comment-gate" role="note">
          <p>Only logged-in readers can write comments. Reading is open to everyone.</p>
          <p className="comment-gate-actions">
            <Link className="btn small" to="/login" state={{ from: location.pathname }}>Log in to comment</Link>
            <Link className="btn secondary small" to="/register" state={{ from: location.pathname }}>Create an account</Link>
          </p>
        </div>
      )}
      {user && (<>{notice && <p className="nw-ok" role="status">{notice}</p>}<CommentForm onSubmit={post} /></>)}
      {error && <p className="nw-error" role="alert">{error}</p>}
      {list.isLoading && <p className="nw-muted">Loading comments…</p>}
      {list.isError && <p className="nw-muted">Comments are not available right now.</p>}
      {list.data && items.length === 0 && <p className="nw-muted">No comments yet.</p>}
      <ul className="nw-comment-list">
        {items.map((c) => (
          <li key={c.id} className="nw-comment">
            <p className="nw-meta"><strong>{c.author}</strong> · {formatDate(c.created_at, true)}{c.status === "pending" && <span className="nw-tag">waiting for approval</span>}</p>
            <p className="nw-comment-body">{c.body}</p>
            {c.can_delete && (confirming === c.id ? (
              <span className="nw-actions">
                <button type="button" className="btn danger small" disabled={remove.isPending} onClick={() => remove.mutate(c.id)}>Yes, delete</button>
                <button type="button" className="btn ghost small" onClick={() => setConfirming(null)}>Keep it</button>
              </span>
            ) : <button type="button" className="btn ghost small" onClick={() => setConfirming(c.id)}>Delete</button>)}
          </li>
        ))}
      </ul>
      {list.data && <Pagination pagination={list.data.pagination} onPage={setPage} />}
    </section>
  );
}
