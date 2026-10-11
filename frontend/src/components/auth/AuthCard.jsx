import { Link } from "react-router-dom";
import { SITE_NAME } from "../../config";

// The centred card shared by the login, sign-up and password pages.
export default function AuthCard({ title, subtitle, children, footer }) {
  return (
    <div className="page-center">
      <div className="auth-card">
        <h1>{title}</h1>
        {subtitle && <p className="muted small">{subtitle}</p>}
        {children}
        {footer && <p className="auth-footer small">{footer}</p>}
        <p className="auth-footer small"><Link to="/">← Back to {SITE_NAME}</Link></p>
      </div>
    </div>
  );
}
