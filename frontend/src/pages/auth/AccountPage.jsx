import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import SecuritySection from "../../components/account/SecuritySection";
import { useAuth } from "../../auth/AuthContext";
import TextField from "../../components/auth/TextField";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { fieldMessage } from "../../utils/format";

const BIO_MAX = 500;

// The reader's account: edit display name and bio, resend the verification email, log out.
export default function AccountPage() {
  const { user, ready, updateProfile, resendVerification, logout } = useAuth();
  useDocumentMeta({ title: "Your account — StoryBoard", robots: "noindex, nofollow" });
  const navigate = useNavigate();
  const location = useLocation();
  const [name, setName] = useState(user?.display_name || "");
  const [bio, setBio] = useState(user?.bio || "");
  const [errors, setErrors] = useState({});
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [resend, setResend] = useState({ busy: false, message: "", error: "" });

  // Arriving from the staff guard ("two-step verification is required"): bring the security section into view.
  useEffect(() => {
    if (ready && user && location.state?.section === "security") document.getElementById("security")?.scrollIntoView?.();
  }, [ready, user, location.state]);

  if (!ready) return <div className="container"><p className="muted">Loading…</p></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: "/account", message: "Please log in to see your account." }} />;

  const save = async (event) => {
    event.preventDefault();
    setSaved(false);
    setFormError("");
    const found = {};
    if (!name.trim()) found.display_name = "Display name cannot be empty.";
    if (name.length > 80) found.display_name = "Use 80 characters or fewer.";
    if (bio.length > BIO_MAX) found.bio = `Use ${BIO_MAX} characters or fewer.`;
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      await updateProfile({ display_name: name.trim(), bio });
      setSaved(true);
    } catch (err) {
      const server = {};
      for (const field of ["display_name", "bio"]) {
        const message = fieldMessage(err, field);
        if (message) server[field] = message;
      }
      setErrors(server);
      if (!Object.keys(server).length) setFormError(err.friendly);
    } finally {
      setBusy(false);
    }
  };

  const sendVerification = async () => {
    setResend({ busy: true, message: "", error: "" });
    try {
      const result = await resendVerification();
      setResend({ busy: false, message: result?.message || "Verification email sent.", error: "" });
    } catch (err) {
      setResend({ busy: false, message: "", error: err.friendly });
    }
  };

  const onLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  return (
    <div className="container account-page">
      <h1>Your account</h1>
      {location.state?.message && <div className="notice info" role="status">{location.state.message}</div>}
      <section aria-labelledby="acct-email">
        <h2 id="acct-email">Email</h2>
        <p>{user.email} {user.email_verified ? <span className="badge published">Verified</span> : <span className="badge scheduled">Not verified</span>}</p>
        {!user.email_verified && (
          <>
            <p className="muted small">Verify your email to be able to comment.</p>
            <button type="button" className="btn secondary small" disabled={resend.busy} onClick={sendVerification}>
              {resend.busy ? "Sending…" : "Resend verification email"}
            </button>
            {resend.message && <p className="small" role="status">{resend.message}</p>}
            {resend.error && <p className="field-error" role="alert">{resend.error}</p>}
          </>
        )}
      </section>

      <section aria-labelledby="acct-profile">
        <h2 id="acct-profile">Profile</h2>
        {formError && <div className="notice error" role="alert">{formError}</div>}
        {saved && <div className="notice info" role="status">Profile saved.</div>}
        <form onSubmit={save} noValidate>
          <TextField id="acct-name" label="Display name" value={name} onChange={(v) => { setName(v); setSaved(false); }} error={errors.display_name} hint="Shown next to your comments." />
          <div className="field">
            <label htmlFor="acct-bio">Bio <span className={`counter${bio.length > BIO_MAX ? " over" : ""}`}>{bio.length} / {BIO_MAX}</span></label>
            <textarea id="acct-bio" rows={4} value={bio} onChange={(e) => { setBio(e.target.value); setSaved(false); }} aria-invalid={errors.bio ? "true" : undefined} />
            {errors.bio && <p className="field-error">{errors.bio}</p>}
          </div>
          <button className="btn" disabled={busy}>{busy ? "Saving…" : "Save profile"}</button>
        </form>
      </section>

      <SecuritySection />

      <section>
        <button type="button" className="btn secondary" onClick={onLogout}>Log out</button>
      </section>
    </div>
  );
}
