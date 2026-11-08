import { useId, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { importFromGitHub, removePackage, uploadPackage } from "../../api/marketplace";
import { formatBytes } from "../../utils/money";
import { KIND_LABELS, firstError } from "./shared";

// What the server's upload check did to a package, in plain words.
function ScanReport({ report }) {
  if (!report) return null;
  const lines = [];
  if (report.excluded_count > 0) lines.push(`${report.excluded_count} file${report.excluded_count === 1 ? "" : "s"} left out (secrets, keys, databases or dependency folders).`);
  if (report.symlinks_removed > 0) lines.push(`${report.symlinks_removed} shortcut${report.symlinks_removed === 1 ? "" : "s"} removed.`);
  if (report.root_folder_removed) lines.push(`The top folder "${report.root_folder_removed}" was removed so the files unpack directly.`);
  if (lines.length === 0) return null;
  return (
    <>
      <ul className="mp-report">{lines.map((l) => <li key={l}>{l}</li>)}</ul>
      {report.excluded?.length > 0 && (
        <details className="mp-report">
          <summary>Which files?</summary>
          <ul>{report.excluded.map((e) => <li key={e.path}><code>{e.path}</code>: {e.reason}</li>)}</ul>
        </details>
      )}
    </>
  );
}

// Upload or import ONE package (frontend or backend) for a project.
export default function PackageEditor({ projectId, kind, current, disabled, onChanged }) {
  const label = KIND_LABELS[kind];
  const uid = useId();
  const fileRef = useRef(null);
  const [version, setVersion] = useState(current?.version || "");
  const [progress, setProgress] = useState(0);
  const [repo, setRepo] = useState("");
  const [ref, setRef] = useState("");
  const [token, setToken] = useState("");
  const [notice, setNotice] = useState("");

  const done = (project) => {
    setNotice(project.sent_back_to_review ? "Saved. Because this project is live, it has gone back to review." : `${label} package saved.`);
    onChanged(project);
  };

  const upload = useMutation({
    mutationFn: (file) => uploadPackage(projectId, { kind, file, version: version.trim() }, setProgress),
    onSuccess: (project) => {
      if (fileRef.current) fileRef.current.value = "";
      setProgress(0);
      done(project);
    },
    onError: () => setProgress(0),
  });

  const github = useMutation({
    mutationFn: () => importFromGitHub(projectId, { kind, repository: repo.trim(), ref: ref.trim(), token: token.trim(), version: version.trim() }),
    onSuccess: (project) => {
      setToken(""); // the token is gone from the page as soon as it was used
      done(project);
    },
    onError: () => setToken(""),
  });

  const remove = useMutation({
    mutationFn: () => removePackage(projectId, kind),
    onSuccess: (project) => {
      setNotice(`${label} package removed.`);
      onChanged(project);
    },
  });

  const submitUpload = (e) => {
    e.preventDefault();
    setNotice("");
    const file = fileRef.current?.files?.[0];
    if (file) upload.mutate(file);
  };
  const submitGithub = (e) => {
    e.preventDefault();
    setNotice("");
    github.mutate();
  };

  return (
    <section className="mp-section" aria-labelledby={`${uid}-h`}>
      <h2 id={`${uid}-h`}>{label} package</h2>
      {current ? (
        <p className="mp-meta">
          Current: version {current.version} · {formatBytes(current.size_bytes)} · {current.file_count} files · from {current.source === "github" ? `GitHub (${current.source_ref})` : "a ZIP upload"}
        </p>
      ) : (
        <p className="muted">Nothing uploaded yet. Add the {label.toLowerCase()} code as a ZIP, or import it from GitHub.</p>
      )}
      <ScanReport report={current?.scan_report} />

      <div className="field">
        <label htmlFor={`${uid}-version`}>Version</label>
        <input id={`${uid}-version`} value={version} onChange={(e) => setVersion(e.target.value)} placeholder="1.0.0" maxLength={30} disabled={disabled} />
      </div>

      <form onSubmit={submitUpload} className="stack">
        <div className="field">
          <label htmlFor={`${uid}-file`}>{current ? "Replace with a new ZIP" : "Upload a ZIP"}</label>
          <input id={`${uid}-file`} ref={fileRef} type="file" accept=".zip,application/zip" disabled={disabled || upload.isPending} aria-describedby={`${uid}-hint`} />
          <p className="hint" id={`${uid}-hint`}>We check every archive. Files such as <code>.env</code>, private keys and <code>node_modules</code> are left out automatically.</p>
        </div>
        {upload.isPending && <progress className="mp-progress" value={Math.round(progress * 100)} max="100" aria-label="Upload progress" />}
        {upload.isError && <p className="field-error" role="alert">{firstError(upload.error, "file", "version")}</p>}
        <button type="submit" className="btn small" disabled={disabled || upload.isPending}>{upload.isPending ? "Checking and uploading…" : "Upload ZIP"}</button>
      </form>

      <details style={{ marginTop: "1rem" }}>
        <summary>Import from GitHub instead</summary>
        <form onSubmit={submitGithub} className="stack" style={{ marginTop: "0.75rem" }}>
          <div className="field">
            <label htmlFor={`${uid}-repo`}>Repository</label>
            <input id={`${uid}-repo`} value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="owner/name or https://github.com/owner/name" disabled={disabled} />
          </div>
          <div className="field">
            <label htmlFor={`${uid}-ref`}>Branch, tag or commit (optional)</label>
            <input id={`${uid}-ref`} value={ref} onChange={(e) => setRef(e.target.value)} placeholder="main" disabled={disabled} />
          </div>
          <div className="field">
            <label htmlFor={`${uid}-token`}>Access token (private repositories only)</label>
            <input id={`${uid}-token`} type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} disabled={disabled} aria-describedby={`${uid}-token-hint`} />
            <p className="hint" id={`${uid}-token-hint`}>Create a read-only token limited to this one repository, and delete it afterwards. It is used for this import only and is never saved.</p>
          </div>
          {github.isError && <p className="field-error" role="alert">{firstError(github.error, "repository", "version")}</p>}
          <button type="submit" className="btn small secondary" disabled={disabled || github.isPending || !repo.trim()}>{github.isPending ? "Importing…" : "Import from GitHub"}</button>
        </form>
      </details>

      {notice && <p className="notice" role="status">{notice}</p>}
      {current && (
        <p style={{ marginTop: "0.75rem" }}>
          <button type="button" className="link-button" disabled={disabled || remove.isPending} onClick={() => { if (window.confirm(`Remove the ${label.toLowerCase()} package?`)) remove.mutate(); }}>
            Remove this package
          </button>
          {remove.isError && <span className="field-error" role="alert"> {firstError(remove.error)}</span>}
        </p>
      )}
    </section>
  );
}
