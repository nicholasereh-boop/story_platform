import { useId, useState } from "react";
import { Link, useLocation } from "react-router-dom";

// Step 2. When no permitted method exists for this platform we say so plainly and point to what the platform itself allows;
// we never offer a button that cannot work.
export default function DownloadOptions({ info, user, busy, error, onStart }) {
  const uid = useId();
  const location = useLocation();
  const { download } = info;
  const [format, setFormat] = useState(download.formats?.[0]?.key || "");
  const [confirmed, setConfirmed] = useState(false);

  if (!download.available) {
    return (
      <div className="vt-panel" role="status">
        <h2>Downloading is not available for this link</h2>
        <p>{download.reason}</p>
        <p>{info.guidance}</p>
        <p className="vt-small">{info.notice}</p>
      </div>
    );
  }
  if (info.needs_resolution) {
    return (
      <div className="vt-panel" role="status">
        <h2>This is a shortened link</h2>
        <p>Open it in your browser, then paste the full address of the video here.</p>
      </div>
    );
  }
  if (!user) {
    return (
      <div className="vt-panel">
        <h2>Log in to download</h2>
        <p>Downloads are only available to signed-in members.</p>
        <Link className="btn" to="/login" state={{ from: location.pathname, message: "Log in to download videos." }}>Log in</Link>
      </div>
    );
  }
  return (
    <form className="vt-panel stack" onSubmit={(e) => { e.preventDefault(); onStart({ format, confirmed }); }}>
      <h2>Download</h2>
      <p className="vt-small">Method: {download.method}</p>
      {download.formats.length > 1 && (
        <div className="field">
          <label htmlFor={`${uid}-format`}>Format</label>
          <select id={`${uid}-format`} value={format} onChange={(e) => setFormat(e.target.value)}>
            {download.formats.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
          </select>
        </div>
      )}
      <label className="check">
        <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
        I own this video or have permission from the rights holder to download it, and I will only use it as the platform&apos;s terms allow.
      </label>
      <p className="vt-small">{info.notice}</p>
      {error && <p className="field-error" role="alert">{error}</p>}
      <div className="row"><button type="submit" className="btn" disabled={busy || !confirmed}>{busy ? "Requesting…" : "Start download"}</button></div>
    </form>
  );
}
