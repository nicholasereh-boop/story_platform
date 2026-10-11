import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import AuthCard from "../../components/auth/AuthCard";
import TextField from "../../components/auth/TextField";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { fieldMessage } from "../../utils/format";

// Ask for a reset link. The server answers the same way whether or not the email has an account.
export default function ForgotPasswordPage() {
  const { requestPasswordReset } = useAuth();
  useDocumentMeta({ title: "Forgot password — StoryBoard", robots: "noindex, nofollow" });
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [sent, setSent] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setFieldError("");
    setBusy(true);
    try {
      const result = await requestPasswordReset(email.trim());
      setSent(result?.message || "If that email has an account, a reset link is on its way.");
    } catch (err) {
      const message = fieldMessage(err, "email");
      if (message) setFieldError(message);
      else setError(err.friendly);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Forgot your password?" subtitle="Enter your email and we will send you a link to choose a new one." footer={<Link to="/login">Back to log in</Link>}>
      {sent ? (
        <div className="notice info" role="status">{sent}</div>
      ) : (
        <>
          {error && <div className="notice error" role="alert">{error}</div>}
          <form onSubmit={submit} noValidate>
            <TextField id="forgot-email" label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} error={fieldError} />
            <button className="btn block" disabled={busy || !email.trim()}>{busy ? "Sending…" : "Send reset link"}</button>
          </form>
        </>
      )}
    </AuthCard>
  );
}
