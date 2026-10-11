import { useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import AuthCard from "../../components/auth/AuthCard";
import GoogleButton from "../../components/auth/GoogleButton";
import PasswordField from "../../components/auth/PasswordField";
import TextField from "../../components/auth/TextField";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { fieldMessage } from "../../utils/format";
import { MIN_PASSWORD_LENGTH, passwordProblem } from "../../utils/password";
import { afterLoginPath, safeFrom } from "../../utils/redirect";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Reader sign-up. Client checks mirror the server's rules; whatever the server still rejects is shown on its field.
export default function RegisterPage() {
  const { user, ready, register } = useAuth();
  useDocumentMeta({ title: "Sign up — StoryBoard", robots: "noindex, nofollow" });
  const location = useLocation();
  const from = safeFrom(location.state?.from);
  const [form, setForm] = useState({ email: "", display_name: "", password: "", confirm: "" });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sentTo, setSentTo] = useState(""); // the address we answered for (the answer is the same whether or not it was already registered)

  const set = (name) => (value) => setForm((f) => ({ ...f, [name]: value }));

  if (ready && user && !sentTo) return <Navigate to={afterLoginPath(user, from)} replace />;

  // Sign-up does not log anyone in and never reveals whether the address already had an account (no account enumeration).
  if (sentTo) {
    return (
      <AuthCard title="Check your email">
        <div className="notice info" role="status">
          <p>
            If <strong>{sentTo}</strong> can be used for a new account, we have sent a message with the next steps. Open the link in it to
            verify your address, then log in. If you already have an account, you can log in or reset your password instead.
          </p>
        </div>
        <Link className="btn block" to="/login" state={location.state}>Go to log in</Link>
      </AuthCard>
    );
  }

  const validate = () => {
    const found = {};
    if (!EMAIL_RE.test(form.email.trim())) found.email = "Enter a valid email address.";
    const problem = passwordProblem(form.password, form.email);
    if (problem) found.password = problem;
    if (form.confirm !== form.password) found.confirm = "The passwords do not match.";
    if (form.display_name.length > 80) found.display_name = "Use 80 characters or fewer.";
    return found;
  };

  const submit = async (event) => {
    event.preventDefault();
    setFormError("");
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      await register({ email: form.email.trim(), password: form.password, display_name: form.display_name.trim() });
      setSentTo(form.email.trim());
    } catch (err) {
      const server = {};
      for (const name of ["email", "password", "display_name"]) {
        const message = fieldMessage(err, name);
        if (message) server[name] = message;
      }
      setErrors(server);
      if (!Object.keys(server).length) setFormError(err.friendly);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Create your account" subtitle="Like stories and join the discussion." footer={<>Already have an account? <Link to="/login" state={location.state}>Log in</Link></>}>
      {formError && <div className="notice error" role="alert">{formError}</div>}
      <form onSubmit={submit} noValidate>
        <TextField id="reg-email" label="Email" type="email" autoComplete="email" value={form.email} onChange={set("email")} error={errors.email} />
        <TextField id="reg-name" label="Display name (optional)" autoComplete="nickname" value={form.display_name} onChange={set("display_name")} error={errors.display_name} hint="Shown next to your comments." />
        <PasswordField id="reg-password" label="Password" autoComplete="new-password" value={form.password} onChange={set("password")} error={errors.password} hint={`At least ${MIN_PASSWORD_LENGTH} characters, not too common, not only numbers.`} />
        <PasswordField id="reg-confirm" label="Confirm password" autoComplete="new-password" value={form.confirm} onChange={set("confirm")} error={errors.confirm} />
        <button className="btn block" disabled={busy}>{busy ? "Creating account…" : "Sign up"}</button>
      </form>
      <GoogleButton label="Sign up with Google" />
    </AuthCard>
  );
}
