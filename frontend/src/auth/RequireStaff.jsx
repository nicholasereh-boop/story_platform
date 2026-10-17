import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

// Frontend guard = convenience only. The REAL security boundary is the backend: every /api/v1/admin/* endpoint
// checks is_staff itself.
//   not logged in -> /login (and come back here afterwards)
//   reader        -> the public home page
//   staff         -> the admin
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
  return children;
}
