import { useId, useState } from "react";
import { engagementError } from "../../engagement/errors";

export const COMMENT_MAX = 2000;

// Write (or edit) a comment: plain text only, 1-2000 characters, with a live counter.
//   onSubmit(text)  async; resolves when saved. If it rejects, the error message is shown (err.friendly).
export default function CommentForm({ onSubmit, onCancel, initialValue = "", submitLabel = "Post comment", placeholder = "Write a comment…", label = "Your comment", autoFocus = false }) {
  const id = useId();
  const [value, setValue] = useState(initialValue);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const length = value.length;
  const over = length > COMMENT_MAX;
  const empty = value.trim().length === 0;

  const submit = async (event) => {
    event.preventDefault();
    if (empty) return setError("Please write something before posting.");
    if (over) return setError(`Comments can be at most ${COMMENT_MAX} characters.`);
    setBusy(true);
    setError("");
    try {
      await onSubmit(value);
      setValue("");
    } catch (err) {
      setError(engagementError(err)); // 400 spam/validation, 403 not allowed, 429 too fast ...
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="comment-form" onSubmit={submit} noValidate>
      <label htmlFor={id} className="sr-only">{label}</label>
      <textarea id={id} rows={3} value={value} placeholder={placeholder} autoFocus={autoFocus} onChange={(e) => setValue(e.target.value)} aria-invalid={over || error ? "true" : undefined} aria-describedby={`${id}-count`} />
      <div className="row wrap">
        <span id={`${id}-count`} className={`counter${over ? " over" : ""}`} aria-live="polite">{length} / {COMMENT_MAX}</span>
        <span className="grow" />
        {onCancel && <button type="button" className="btn ghost small" onClick={onCancel}>Cancel</button>}
        <button className="btn small" disabled={busy || empty || over}>{busy ? "Saving…" : submitLabel}</button>
      </div>
      {error && <p className="field-error" role="alert">{error}</p>}
    </form>
  );
}
