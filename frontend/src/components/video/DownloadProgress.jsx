import { formatBytes } from "../../utils/money";

const WORKING = { queued: "Waiting in line…", processing: "Preparing your file…" };

// Step 3: follow the job. The page polls the server; this component only shows the state it is given.
export default function DownloadProgress({ job, busy, error, onSave, onRemove, onReset }) {
  const working = job.status in WORKING;
  return (
    <div className="vt-panel" aria-live="polite">
      <h2>{job.provider_label} download</h2>
      {working && (
        <>
          <p role="status">{WORKING[job.status]}</p>
          <progress className="vt-progress" aria-label="Working" />
          <p><button type="button" className="link-button" onClick={onRemove}>Cancel</button></p>
        </>
      )}
      {job.status === "done" && job.artifact && (
        <>
          <p role="status">Your file is ready: <strong>{job.artifact.filename}</strong> ({formatBytes(job.artifact.size_bytes)}).</p>
          <p className="vt-small">It is kept for a limited time, until {new Date(job.artifact.expires_at).toLocaleString()}, and then deleted automatically.</p>
          <div className="row">
            <button type="button" className="btn" disabled={busy} onClick={onSave}>{busy ? "Preparing…" : "Save file"}</button>
            <button type="button" className="btn secondary" onClick={onRemove}>Delete it now</button>
          </div>
        </>
      )}
      {job.status === "failed" && <p className="notice error" role="alert">{job.error_message || "The download could not be completed."}</p>}
      {job.status === "cancelled" && <p role="status">Cancelled.</p>}
      {job.status === "expired" && <p role="status">This file has been deleted.</p>}
      {error && <p className="field-error" role="alert">{error}</p>}
      {!working && <p><button type="button" className="btn secondary small" onClick={onReset}>Check another link</button></p>}
    </div>
  );
}
