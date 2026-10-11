import { useEffect, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import ConfirmDialog from "../ConfirmDialog";
import Modal from "../Modal";
import CommentForm from "./CommentForm";

const REASON_MAX = 300;

// Edit is offered only while the server says so AND the window has not closed on this screen either.
function canEditNow(comment, now) {
  return Boolean(comment.can_edit && comment.edit_expires_at && new Date(comment.edit_expires_at).getTime() > now);
}

// One comment. The body is rendered as TEXT (React escapes it; CSS keeps the line breaks), never as HTML.
// `actions` = {reply, edit, remove, report}: async functions supplied by CommentList.
export default function CommentItem({ comment, canReply = false, canReport = false, actions, isReply = false }) {
  const [mode, setMode] = useState("view"); // view | edit | reply
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [now, setNow] = useState(() => Date.now());

  // Re-check the edit window every 30 s so the Edit button disappears by itself when time runs out.
  useEffect(() => {
    if (!comment.can_edit) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, [comment.can_edit]);

  const deleted = comment.status === "deleted";
  const pending = comment.status === "pending";
  const editable = canEditNow(comment, now);

  const remove = async () => {
    setBusy(true);
    setError("");
    try {
      await actions.remove(comment);
      setConfirmDelete(false);
    } catch (err) {
      setConfirmDelete(false);
      setError(err.friendly || "Could not delete the comment.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className={`comment${isReply ? " reply" : ""}${deleted ? " deleted" : ""}`} id={`comment-${comment.id}`}>
      <div className="comment-head">
        <strong>{deleted ? "Deleted" : comment.author}</strong>
        <time dateTime={comment.created_at} className="muted small">{formatDistanceToNow(new Date(comment.created_at), { addSuffix: true })}</time>
        {comment.edited_at && !deleted && <span className="muted small">(edited)</span>}
        {pending && <span className="badge scheduled">Pending approval</span>}
      </div>

      {mode === "edit" ? (
        <CommentForm
          initialValue={comment.body}
          submitLabel="Save"
          label="Edit your comment"
          autoFocus
          onCancel={() => setMode("view")}
          onSubmit={async (text) => {
            await actions.edit(comment, text);
            setMode("view");
          }}
        />
      ) : (
        <p className="comment-body">{comment.body}</p>
      )}

      {!deleted && mode === "view" && (
        <div className="comment-actions">
          {canReply && !isReply && !pending && <button type="button" className="btn ghost small" onClick={() => setMode("reply")}>Reply</button>}
          {editable && <button type="button" className="btn ghost small" onClick={() => setMode("edit")}>Edit</button>}
          {comment.can_delete && <button type="button" className="btn ghost small" onClick={() => setConfirmDelete(true)}>Delete</button>}
          {canReport && !comment.is_mine && !pending && <button type="button" className="btn ghost small" onClick={() => setReporting(true)}>Report</button>}
        </div>
      )}
      {error && <p className="field-error" role="alert">{error}</p>}

      {mode === "reply" && (
        <CommentForm
          submitLabel="Post reply"
          label={`Reply to ${comment.author}`}
          placeholder="Write a reply…"
          autoFocus
          onCancel={() => setMode("view")}
          onSubmit={async (text) => {
            await actions.reply(comment, text);
            setMode("view");
          }}
        />
      )}

      {/* One level of replies only. */}
      {comment.replies?.length > 0 && (
        <ul className="comment-list replies">
          {comment.replies.map((reply) => (
            <CommentItem key={reply.id} comment={reply} isReply canReport={canReport} actions={actions} />
          ))}
        </ul>
      )}

      {confirmDelete && (
        <ConfirmDialog title="Delete this comment?" message="This cannot be undone." confirmLabel="Delete" danger busy={busy} onConfirm={remove} onCancel={() => setConfirmDelete(false)} />
      )}
      {reporting && <ReportDialog onClose={() => setReporting(false)} onSend={(reason) => actions.report(comment, reason)} />}
    </li>
  );
}

// Dialog asking why the comment is being reported (optional, up to 300 characters).
function ReportDialog({ onClose, onSend }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (reason.length > REASON_MAX) return setError(`Use ${REASON_MAX} characters or fewer.`);
    setBusy(true);
    setError("");
    try {
      await onSend(reason.trim());
      setSent(true);
    } catch (err) {
      setError(err.status === 429 ? "You are reporting too often. Please try again later." : err.friendly || "Could not send the report.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Report this comment" onClose={onClose}>
      {sent ? (
        <>
          <p role="status">Thank you. A moderator will take a look.</p>
          <div className="row end"><button type="button" className="btn" data-autofocus onClick={onClose}>Close</button></div>
        </>
      ) : (
        <form onSubmit={submit} noValidate>
          <div className="field">
            <label htmlFor="report-reason">Why are you reporting it? <span className="muted">(optional)</span></label>
            <textarea id="report-reason" rows={3} data-autofocus value={reason} onChange={(e) => setReason(e.target.value)} />
            <p className={`counter${reason.length > REASON_MAX ? " over" : ""}`}>{reason.length} / {REASON_MAX}</p>
          </div>
          {error && <p className="field-error" role="alert">{error}</p>}
          <div className="row end">
            <button type="button" className="btn secondary" onClick={onClose}>Cancel</button>
            <button className="btn" disabled={busy || reason.length > REASON_MAX}>{busy ? "Sending…" : "Send report"}</button>
          </div>
        </form>
      )}
    </Modal>
  );
}
