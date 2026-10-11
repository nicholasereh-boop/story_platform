import { useState } from "react";
import { useNavigate } from "react-router-dom";
import * as API from "../api";
import AuthCard from "../components/auth/AuthCard";
import TextField from "../components/auth/TextField";
import { useAuth } from "./AuthContext";

// Shown by the admin guard when a staff member has two-step verification but has not entered a code in this session.
// The code (or one recovery code) unlocks the staff area; the server checks it and remembers it for this session.
export default function MfaStepUp() {
  const { refreshUser, logout } = useAuth();
  const navigate = useNavigate();
  const [useRecovery, setUseRecovery] = useState(false);
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await API.mfaVerify(useRecovery ? { recovery_code: value.trim() } : { code: value.replace(/\s+/g, "") });
      await refreshUser(); // user.mfa.verified is now true: the guard lets the admin render
    } catch (err) {
      setError(err.fieldErrors?.code?.[0] || err.friendly);
      setBusy(false);
    }
  };

  const leave = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <AuthCard title="Two-step verification" subtitle={useRecovery ? "Enter one of your recovery codes. Each works once." : "Enter the 6-digit code from your authenticator app."}>
      {error && <div className="notice error" role="alert">{error}</div>}
      <form onSubmit={submit} noValidate>
        <TextField
          id="mfa-code"
          label={useRecovery ? "Recovery code" : "Code"}
          autoComplete="one-time-code"
          inputMode={useRecovery ? "text" : "numeric"}
          value={value}
          onChange={setValue}
          autoFocus
        />
        <button className="btn block" disabled={busy || !value.trim()}>{busy ? "Checking…" : "Continue"}</button>
      </form>
      <p className="small">
        <button type="button" className="link-button" onClick={() => { setUseRecovery((v) => !v); setValue(""); setError(""); }}>
          {useRecovery ? "Use an authenticator code instead" : "Use a recovery code instead"}
        </button>
      </p>
      <p className="small"><button type="button" className="link-button" onClick={leave}>Log out</button></p>
    </AuthCard>
  );
}
