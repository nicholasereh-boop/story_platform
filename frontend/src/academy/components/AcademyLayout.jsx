import { useEffect, useRef } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { SITE_NAME } from "../../config";
import "../academy.css";

// The Academy's own frame: its own header, navigation and footer, so it feels like a separate site, while it shares the same
// login session and API as the rest of the project (docs/ARCHITECTURE.md). Routes inside it fill <main>.
export default function AcademyLayout() {
  const { user, ready, isStaff, logout } = useAuth() || {};
  const { pathname } = useLocation();
  const main = useRef(null);

  // New page: scroll to the top and move focus to <main> so keyboard and screen-reader users start at the content.
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    window.scrollTo?.(0, 0);
    main.current?.focus({ preventScroll: true });
  }, [pathname]);

  const link = ({ isActive }) => (isActive ? "ac-link is-active" : "ac-link");
  return (
    <div className="ac-shell">
      <a className="ac-skip" href="#ac-main" onClick={(e) => { e.preventDefault(); main.current?.focus(); }}>Skip to content</a>
      <header className="ac-header">
        <div className="ac-header-inner">
          <Link to="/academy" className="ac-brand" aria-label={`${SITE_NAME} Academy home`}>
            <span className="ac-logo" aria-hidden="true">🎓</span>
            <span><strong>{SITE_NAME}</strong> Academy</span>
          </Link>
          <nav className="ac-nav" aria-label="Academy">
            <NavLink to="/academy" end className={link}>Home</NavLink>
            <NavLink to="/academy/free" className={link}>Free tutorials</NavLink>
            <NavLink to="/academy/paid" className={link}>Paid tutorials</NavLink>
            <NavLink to="/academy/my-learning" className={link}>My learning</NavLink>
            {isStaff && <NavLink to="/academy/admin" className={link}>Manage</NavLink>}
          </nav>
          <div className="ac-account">
            <Link to="/" className="ac-link">← {SITE_NAME}</Link>
            {ready && (user ? (
              <button type="button" className="ac-btn ac-btn-ghost" onClick={() => logout?.()}>Log out</button>
            ) : (
              <Link to="/login" state={{ from: pathname, message: "Log in to track your learning." }} className="ac-btn ac-btn-ghost">Log in</Link>
            ))}
          </div>
        </div>
      </header>
      <main id="ac-main" ref={main} tabIndex={-1} className="ac-main">
        <Outlet />
      </main>
      <footer className="ac-footer">
        <p>© {new Date().getFullYear()} {SITE_NAME} Academy · Learn to build websites</p>
        <nav aria-label="Academy footer">
          <Link to="/academy/free">Free tutorials</Link>
          <Link to="/academy/paid">Paid tutorials</Link>
          <Link to="/privacy">Privacy</Link>
        </nav>
      </footer>
    </div>
  );
}