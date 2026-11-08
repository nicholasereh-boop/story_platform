import { useId } from "react";

// Step 1: paste a link. Nothing is fetched from it: the server only reads the address and tells us what is possible.
export default function VideoUrlForm({ value, onChange, onSubmit, busy, error }) {
  const id = useId();
  return (
    <form className="vt-form" onSubmit={(e) => { e.preventDefault(); onSubmit(); }} noValidate>
      <div className="field">
        <label htmlFor={id}>Video link</label>
        <input
          id={id} type="url" inputMode="url" autoComplete="off" spellCheck="false" value={value} maxLength={2048}
          onChange={(e) => onChange(e.target.value)} placeholder="https://…"
          aria-invalid={error ? "true" : undefined} aria-describedby={error ? `${id}-err` : `${id}-hint`}
        />
        {error ? <p className="field-error" id={`${id}-err`} role="alert">{error}</p> : <p className="hint" id={`${id}-hint`}>YouTube, Facebook, Instagram, TikTok or X.</p>}
      </div>
      <button type="submit" className="btn" disabled={busy || !value.trim()}>{busy ? "Checking…" : "Check link"}</button>
    </form>
  );
}
