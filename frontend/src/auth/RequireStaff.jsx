import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import MfaStepUp from "./MfaStepUp";

// Frontend guard = convenience only. The REAL security boundary is the backend: every /api/v1/admin/* endpoint
// checks is_staff itself.
//   not logged in -> /login (and come back here afterwards)
//   reader        -> the public home page
//   staff         -> the admin (after the two-step code, when they have two-step verification)
export default function RequireStaff({ children }) {
  const { user, ready } = useAuth();
  const location = useLocation();

  if (!ready) {
    return (
      <div className="page-center">
        <p className="muted">Loading…</p>
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname, message: "Please log in to continue." }} />;
  }
  if (!user.is_staff) {
    return <Navigate to="/" replace />;
  }
  // Two-step verification (the server enforces it on every admin request; this only shows the right screen):
  //   required but no device yet  -> the setup section of the account page
  //   has a device, not yet proven in this session -> the code prompt
  const mfa = user.mfa;
  if (mfa?.required && !mfa.enabled) {
    return <Navigate to="/account" replace state={{ message: "Two-step verification is required for staff. Set it up below to continue.", section: "security" }} />;
  }
  if (mfa?.enabled && !mfa.verified) return <MfaStepUp />;
  return children;
}
