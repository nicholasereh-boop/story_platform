import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import AuthCard from "../components/auth/AuthCard";
import GoogleButton from "../components/auth/GoogleButton";
import PasswordField from "../components/auth/PasswordField";
import TextField from "../components/auth/TextField";
import { useDocumentMeta } from "../hooks/useDocumentMeta";
import { afterLoginPath } from "../utils/redirect";

// One login page for everybody. After logging in, staff go back to where they came from (or the admin) and
// readers go back to where they came from (or the home page). The /admin guard still bounces non-staff.
export default function LoginPage() {
  const { user, ready, login } = useAuth();
  useDocumentMeta({ title: "Log in — StoryBoard", robots: "noindex, nofollow" });
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const from = location.state?.from;
  const message = location.state?.message;
  const googleFailed = params.get("error") === "google";

  // Already logged in (any account type): nothing to do here.
  if (ready && user) return <Navigate to={afterLoginPath(user, from)} replace />;

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const loggedIn = await login(email.trim(), password);
      navigate(afterLoginPath(loggedIn, from), { replace: true });
    } catch (err) {
      setError(err.friendly);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title="Log in"
      subtitle="Welcome back."
      footer={<>New here? <Link to="/register" state={location.state}>Create an account</Link></>}
    >
      {message && !error && <div className="notice info" role="status">{message}</div>}
      {googleFailed && !error && <div className="notice error" role="alert">Google sign-in did not complete. Please try again.</div>}
      {error && <div className="notice error" role="alert">{error}</div>}
      <form onSubmit={submit} noValidate>
        <TextField id="login-email" label="Email" type="email" autoComplete="email" required value={email} onChange={setEmail} />
        <PasswordField id="login-password" label="Password" autoComplete="current-password" value={password} onChange={setPassword} />
        <button className="btn block" disabled={busy || !email || !password}>
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
      <p className="small"><Link to="/forgot-password">Forgot your password?</Link></p>
      <GoogleButton />
    </AuthCard>
  );
}
