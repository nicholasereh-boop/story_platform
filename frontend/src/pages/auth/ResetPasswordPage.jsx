import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import AuthCard from "../../components/auth/AuthCard";
import PasswordField from "../../components/auth/PasswordField";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { fieldMessage } from "../../utils/format";
import { MIN_PASSWORD_LENGTH, passwordProblem } from "../../utils/password";

// Choose a new password. The link in the email is /reset-password?uid=...&token=...
export default function ResetPasswordPage() {
  const { resetPassword } = useAuth();
  useDocumentMeta({ title: "Choose a new password — StoryBoard", robots: "noindex, nofollow" });
  const [params] = useSearchParams();
  const uid = params.get("uid");
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  if (!uid || !token) {
    return (
      <AuthCard title="Reset link problem">
        <div className="notice error" role="alert">This reset link is incomplete. Request a new one.</div>
        <Link className="btn block" to="/forgot-password">Request a new link</Link>
      </AuthCard>
    );
  }
  if (done) {
    return (
      <AuthCard title="Password updated">
        <div className="notice info" role="status">Your password was changed. You can log in now.</div>
        <Link className="btn block" to="/login">Log in</Link>
      </AuthCard>
    );
  }

  const submit = async (event) => {
    event.preventDefault();
    setFormError("");
    const found = {};
    const problem = passwordProblem(password);
    if (problem) found.password = problem;
    if (confirm !== password) found.confirm = "The passwords do not match.";
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      await resetPassword({ uid, token, password });
      setDone(true);
    } catch (err) {
      const message = fieldMessage(err, "password");
      if (message) setErrors({ password: message });
      else setFormError(err.friendly); // e.g. "This reset link is invalid or has expired."
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Choose a new password">
      {formError && (
        <div className="notice error" role="alert">
          <p>{formError}</p>
          <Link to="/forgot-password">Request a new link</Link>
        </div>
      )}
      <form onSubmit={submit} noValidate>
        <PasswordField id="reset-password" label="New password" autoComplete="new-password" value={password} onChange={setPassword} error={errors.password} hint={`At least ${MIN_PASSWORD_LENGTH} characters, not too common, not only numbers.`} />
        <PasswordField id="reset-confirm" label="Confirm new password" autoComplete="new-password" value={confirm} onChange={setConfirm} error={errors.confirm} />
        <button className="btn block" disabled={busy}>{busy ? "Saving…" : "Save new password"}</button>
      </form>
    </AuthCard>
  );
}
