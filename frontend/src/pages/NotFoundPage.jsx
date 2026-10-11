import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="page-center">
      <div className="auth-card">
        <h1>Page not found</h1>
        <p className="muted">That address does not exist.</p>
        <Link className="btn" to="/admin/stories">Go to the admin</Link>
      </div>
    </div>
  );
}
