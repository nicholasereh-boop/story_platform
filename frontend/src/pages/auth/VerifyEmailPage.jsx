import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import AuthCard from "../../components/auth/AuthCard";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";

// Confirms the email address with the key from the emailed link: /verify-email?key=...
// The key is single-use, so the request is sent exactly once even if React runs the effect twice in development.
export default function VerifyEmailPage() {
  const { verifyEmail } = useAuth();
  useDocumentMeta({ title: "Verify your email — StoryBoard", robots: "noindex, nofollow" });
  const [params] = useSearchParams();
  const key = params.get("key");
  const [state, setState] = useState(key ? "working" : "missing"); // working | ok | failed | missing
  const [message, setMessage] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (!key || started.current) return;
    started.current = true;
    verifyEmail(key)
      .then(() => setState("ok"))
      .catch((err) => {
        setMessage(err.friendly);
        setState("failed");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return (
    <AuthCard title="Verify your email">
      {state === "working" && <p role="status">Verifying…</p>}
      {state === "ok" && (
        <>
          <div className="notice info" role="status">Thank you. Your email is verified, so you can comment now.</div>
          <Link className="btn block" to="/">Continue</Link>
        </>
      )}
      {state === "failed" && (
        <>
          <div className="notice error" role="alert">{message || "This verification link is invalid or has expired."}</div>
          <p className="small">Log in and use “Resend verification email” on your <Link to="/account">account page</Link> to get a new link.</p>
        </>
      )}
      {state === "missing" && <div className="notice error" role="alert">This verification link is incomplete.</div>}
    </AuthCard>
  );
}
