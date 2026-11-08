import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

// Convenience guard for pages that only make sense when signed in (seller tools, purchases). The REAL check is the server:
// every endpoint behind these pages answers 401/403 to anonymous requests.
export default function RequireLogin({ children, message = "Please log in to continue." }) {
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
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}`, message }} />;
  }
  return children;
}
