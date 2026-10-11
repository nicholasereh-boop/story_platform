import { useAuth } from "../../auth/AuthContext";
import DataPanel from "./DataPanel";
import MfaPanel from "./MfaPanel";
import SessionsPanel from "./SessionsPanel";

// The "Security and privacy" part of the account page: two-step verification (staff), sessions, my data.
export default function SecuritySection() {
  const { user } = useAuth();
  const isStaff = Boolean(user?.is_staff || user?.is_superuser);
  return (
    <section id="security" aria-labelledby="acct-security" className="security-section">
      <h2 id="acct-security">Security and privacy</h2>
      {isStaff && (
        <div className="card">
          <h3>Two-step verification</h3>
          <MfaPanel />
        </div>
      )}
      <div className="card">
        <h3>Where you are signed in</h3>
        <SessionsPanel />
      </div>
      <div className="card">
        <h3>Your data</h3>
        <DataPanel />
      </div>
    </section>
  );
}
