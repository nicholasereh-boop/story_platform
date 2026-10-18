import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";

// Top-right of the header.
//   visitor   -> "Log in" and "Sign up" links
//   logged in -> the person's name; a menu with Account, Admin (staff only) and Log out
export default function UserMenu() {
  const { user, ready, logout } = useAuth() || {};
  const location = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  useEffect(() => setOpen(false), [location.pathname]);

  // Close on Esc and on a click anywhere outside the menu.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    const onDown = (e) => box.current && !box.current.contains(e.target) && setOpen(false);
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open]);

  if (!ready) return null; // do not flash "Log in" at someone who is already logged in

  if (!user) {
    const state = { from: location.pathname };
    return (
      <div className="auth-links">
        <Link to="/login" state={state}>Log in</Link>
        <Link className="btn small" to="/register" state={state}>Sign up</Link>
      </div>
    );
  }

  const name = user.display_name || user.email.split("@")[0];
  const onLogout = async () => {
    setOpen(false);
    await logout();
    navigate("/", { replace: true });
  };

  return (
    <div className="user-menu" ref={box}>
      <button type="button" className="btn ghost small" aria-expanded={open} aria-controls="user-menu-list" onClick={() => setOpen((v) => !v)}>
        {name} <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <ul id="user-menu-list" className="user-menu-list">
          <li><Link to="/account">Account</Link></li>
          {user.is_staff && <li><Link to="/admin/stories">Admin</Link></li>}
          <li><button type="button" onClick={onLogout}>Log out</button></li>
        </ul>
      )}
    </div>
  );
}
