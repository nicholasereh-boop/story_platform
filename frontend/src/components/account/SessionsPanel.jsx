import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listMySessions, revokeAllSessions } from "../../api/security";
import { useAuth } from "../../auth/AuthContext";
import ConfirmDialog from "../ConfirmDialog";
import { fmtDateTime } from "../../utils/format";

// Where I am logged in: device, first seen, last seen. No IP address and no browser text are ever shown or stored.
export default function SessionsPanel() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const sessions = useQuery({ queryKey: ["my-sessions"], queryFn: listMySessions });
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const signOutEverywhere = async () => {
    setBusy(true);
    setError("");
    try {
      await revokeAllSessions(); // ends every session of mine, this one included
    } catch (err) {
      setError(err.friendly);
      setBusy(false);
      return;
    }
    try { await logout(); } catch { /* the server already ended the session */ }
    navigate("/login", { replace: true, state: { message: "You have been signed out of all devices." } });
  };

  return (
    <div className="stack">
      {sessions.isLoading && <p className="muted">Loading…</p>}
      {sessions.isError && <p className="field-error" role="alert">{sessions.error.friendly}</p>}
      {sessions.isSuccess && (
        <ul className="session-list" aria-label="Active sessions">
          {sessions.data.map((s) => (
            <li key={s.id}>
              <strong>{s.device}</strong> {s.current && <span className="badge published">This device</span>}
              <span className="muted small block">Signed in {fmtDateTime(s.created_at)} · last active {fmtDateTime(s.last_seen_at)}</span>
            </li>
          ))}
        </ul>
      )}
      <div>
        <button type="button" className="btn secondary" onClick={() => { setError(""); setConfirming(true); }}>Sign out of all devices</button>
      </div>
      {confirming && (
        <ConfirmDialog
          title="Sign out of all devices?"
          message="You will be signed out here too and will need to log in again everywhere."
          confirmLabel="Sign out of all devices"
          danger
          busy={busy}
          onConfirm={signOutEverywhere}
          onCancel={() => setConfirming(false)}
        >
          {error && <p className="field-error" role="alert">{error}</p>}
        </ConfirmDialog>
      )}
    </div>
  );
}
