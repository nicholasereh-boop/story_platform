import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { deleteMyAccount, exportMyData } from "../../api/security";
import { useAuth } from "../../auth/AuthContext";
import Modal from "../Modal";
import { downloadText } from "../../utils/download";

// "Download my data" and "Delete my account". Deleting ANONYMISES the account: it cannot be undone.
export default function DataPanel() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ password: "", email: "", code: "", understood: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const needsCode = Boolean(user?.mfa?.enabled);

  const download = async () => {
    setExporting(true);
    setExportError("");
    try {
      const data = await exportMyData();
      downloadText("my-data.json", JSON.stringify(data, null, 2), "application/json");
    } catch (err) {
      setExportError(err.friendly);
    } finally {
      setExporting(false);
    }
  };

  const remove = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body = form.password ? { password: form.password } : { email: form.email.trim() };
    if (needsCode && form.code.trim()) body.code = form.code.replace(/\s+/g, "");
    try {
      await deleteMyAccount(body);
    } catch (err) {
      setError(err.fieldErrors?.password?.[0] || err.fieldErrors?.email?.[0] || err.fieldErrors?.code?.[0] || err.friendly);
      setBusy(false);
      return;
    }
    try { await logout(); } catch { /* the server already ended the session */ }
    navigate("/", { replace: true });
  };

  return (
    <div className="stack">
      <div>
        <p>Get a copy of everything this site holds about you (account, profile, comments, likes, reports) as a JSON file.</p>
        <button type="button" className="btn secondary" disabled={exporting} onClick={download}>{exporting ? "Preparing…" : "Download my data"}</button>
        {exportError && <p className="field-error" role="alert">{exportError}</p>}
      </div>
      <div>
        <h3>Delete my account</h3>
        <p>This erases your email address, name, bio and picture, removes your likes and takes your comments off the site. It cannot be undone.</p>
        <button type="button" className="btn danger" onClick={() => { setError(""); setOpen(true); }}>Delete my account…</button>
      </div>
      {open && (
        <Modal title="Delete your account for good?" onClose={() => !busy && setOpen(false)}>
          <form onSubmit={remove} className="stack" noValidate>
            <div className="notice error" role="alert"><strong>This cannot be undone.</strong> You will be logged out and cannot sign in with this account again.</div>
            <div className="field">
              <label htmlFor="del-password">Your password</label>
              <input id="del-password" type="password" autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-autofocus />
            </div>
            <div className="field">
              <label htmlFor="del-email">Or, if you only sign in with Google, type your email address</label>
              <input id="del-email" type="email" autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            {needsCode && (
              <div className="field">
                <label htmlFor="del-code">Code from your authenticator app</label>
                <input id="del-code" autoComplete="one-time-code" inputMode="numeric" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
              </div>
            )}
            <label className="check">
              <input type="checkbox" checked={form.understood} onChange={(e) => setForm({ ...form, understood: e.target.checked })} /> I understand my account will be deleted permanently
            </label>
            {error && <p className="field-error" role="alert">{error}</p>}
            <div className="row end">
              <button type="button" className="btn secondary" disabled={busy} onClick={() => setOpen(false)}>Cancel</button>
              <button className="btn danger" disabled={busy || !form.understood || !(form.password || form.email)}>{busy ? "Deleting…" : "Delete my account permanently"}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
