import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { mfaConfirm, mfaDisable, mfaNewRecoveryCodes, mfaSetup, mfaStatus } from "../../api/security";
import { useAuth } from "../../auth/AuthContext";
import { copyText, downloadText } from "../../utils/download";

const clean = (code) => code.replace(/\s+/g, "");

// Recovery codes are shown ONCE. The "I saved them" box gates the Done button so nobody closes the page by accident.
function RecoveryCodes({ codes, onDone }) {
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState("");
  const text = codes.join("\n");
  return (
    <div className="recovery-codes">
      <div className="notice warn" role="alert">
        <strong>Save these recovery codes now.</strong> Each one works once if you lose your phone. They will not be shown again.
      </div>
      <ul className="code-list" aria-label="Recovery codes">
        {codes.map((c) => <li key={c}><code>{c}</code></li>)}
      </ul>
      <div className="row wrap">
        <button type="button" className="btn secondary small" onClick={async () => setCopied((await copyText(text)) ? "Copied." : "Could not copy: select the codes and copy them by hand.")}>Copy</button>
        <button type="button" className="btn secondary small" onClick={() => downloadText("recovery-codes.txt", `${text}\n`)}>Download as a text file</button>
        <span role="status" className="small">{copied}</span>
      </div>
      <label className="check">
        <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} /> I saved these codes somewhere safe
      </label>
      <button type="button" className="btn" disabled={!saved} onClick={onDone}>Done</button>
    </div>
  );
}

// A password + fresh-code form used to turn two-step off or to replace the recovery codes.
function SensitiveForm({ label, danger, mutation, onSuccess }) {
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const submit = (event) => {
    event.preventDefault();
    mutation.mutate({ password, code: clean(code) }, { onSuccess });
  };
  const fieldError = mutation.error?.fieldErrors;
  return (
    <form onSubmit={submit} className="stack" noValidate>
      <div className="field">
        <label htmlFor={`mfa-pw-${label}`}>Password <span className="muted small">(if your account has one)</span></label>
        <input id={`mfa-pw-${label}`} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {fieldError?.password && <p className="field-error">{[].concat(fieldError.password).join(" ")}</p>}
      </div>
      <div className="field">
        <label htmlFor={`mfa-code-${label}`}>Code from your authenticator app</label>
        <input id={`mfa-code-${label}`} autoComplete="one-time-code" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} />
        {fieldError?.code && <p className="field-error">{[].concat(fieldError.code).join(" ")}</p>}
      </div>
      {mutation.isError && !fieldError?.password && !fieldError?.code && <p className="field-error" role="alert">{mutation.error.friendly}</p>}
      <button className={`btn${danger ? " danger" : ""}`} disabled={mutation.isPending || !code.trim()}>{mutation.isPending ? "Working…" : label}</button>
    </form>
  );
}

// Two-step verification for staff accounts: set up, show recovery codes once, replace them, turn off.
export default function MfaPanel() {
  const { refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["mfa-status"], queryFn: mfaStatus, retry: false });
  const [setup, setSetup] = useState(null); // {secret, otpauth_uri}
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState(null); // recovery codes to show once
  const [mode, setMode] = useState(""); // "", "codes" or "disable"

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["mfa-status"] });
    try { await refreshUser(); } catch { /* the status query already shows the state */ }
  };
  const start = useMutation({ mutationFn: mfaSetup, onSuccess: (r) => { setSetup(r); setCode(""); } });
  const confirm = useMutation({ mutationFn: () => mfaConfirm(clean(code)), onSuccess: (r) => { setCodes(r.recovery_codes); setSetup(null); } });
  const regenerate = useMutation({ mutationFn: mfaNewRecoveryCodes });
  const disable = useMutation({ mutationFn: mfaDisable });

  if (status.isLoading) return <p className="muted">Loading…</p>;
  if (status.isError) return <p className="field-error" role="alert">{status.error.friendly}</p>;
  const info = status.data;

  if (codes) return <RecoveryCodes codes={codes} onDone={async () => { setCodes(null); setMode(""); await refresh(); }} />;

  if (!info.enabled) {
    return (
      <div className="stack">
        <p>Two-step verification adds a 6-digit code from an authenticator app (Google Authenticator, Authy, 1Password and similar) to your staff login.</p>
        {info.required && <div className="notice info" role="note">Two-step verification is required for staff on this site.</div>}
        {!setup ? (
          <>
            {start.isError && <p className="field-error" role="alert">{start.error.friendly}</p>}
            <button type="button" className="btn" disabled={start.isPending} onClick={() => start.mutate()}>{start.isPending ? "Starting…" : "Set up two-step verification"}</button>
          </>
        ) : (
          <form className="stack" onSubmit={(e) => { e.preventDefault(); confirm.mutate(); }} noValidate>
            <ol>
              <li>In your authenticator app choose &ldquo;enter a setup key&rdquo; and type this key (spaces do not matter):<br /><code className="secret" data-testid="mfa-secret">{setup.secret}</code></li>
              <li>Or open this link on the device that has the app: <a href={setup.otpauth_uri}>add to authenticator</a>.</li>
              <li>Enter the 6-digit code the app shows:</li>
            </ol>
            <div className="field">
              <label htmlFor="mfa-confirm-code">Code</label>
              <input id="mfa-confirm-code" autoComplete="one-time-code" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} aria-invalid={confirm.isError ? "true" : undefined} />
              {confirm.isError && <p className="field-error" role="alert">{[].concat(confirm.error.fieldErrors?.code || confirm.error.friendly).join(" ")}</p>}
            </div>
            <div className="row">
              <button className="btn" disabled={confirm.isPending || !code.trim()}>{confirm.isPending ? "Checking…" : "Turn on"}</button>
              <button type="button" className="btn ghost" onClick={() => setSetup(null)}>Cancel</button>
            </div>
          </form>
        )}
      </div>
    );
  }

  return (
    <div className="stack">
      <p><span className="badge published">On</span> You have {info.recovery_codes_left} recovery code{info.recovery_codes_left === 1 ? "" : "s"} left.</p>
      <div className="row wrap">
        <button type="button" className="btn secondary" aria-expanded={mode === "codes"} onClick={() => setMode(mode === "codes" ? "" : "codes")}>New recovery codes</button>
        <button type="button" className="btn secondary" aria-expanded={mode === "disable"} onClick={() => setMode(mode === "disable" ? "" : "disable")}>Turn off</button>
      </div>
      {mode === "codes" && (
        <SensitiveForm label="Create new codes" mutation={regenerate} onSuccess={(r) => setCodes(r.recovery_codes)} />
      )}
      {mode === "disable" && (
        <>
          <p className="muted small">Turning it off makes your staff login depend on your password alone.</p>
          <SensitiveForm label="Turn off two-step verification" danger mutation={disable} onSuccess={async () => { setMode(""); await refresh(); }} />
        </>
      )}
    </div>
  );
}
