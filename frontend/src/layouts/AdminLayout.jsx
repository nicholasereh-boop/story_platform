import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { adminListComments } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useDocumentMeta } from "../hooks/useDocumentMeta";

// Every link is visible to staff; the server decides what each person may do (for example role changes are superuser-only).
const LINKS = [
  { to: "/admin/stories", label: "Stories" },
  { to: "/admin/media", label: "Media" },
  { to: "/admin/comments", label: "Comments", badge: true }, // badge = number of comments waiting for approval
  { to: "/admin/analytics", label: "Analytics" },
  { to: "/admin/users", label: "Users" },
  { to: "/admin/audit-logs", label: "Audit log" },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  useDocumentMeta({ title: "Admin — StoryBoard", robots: "noindex, nofollow" }); // never index the admin area
  const navigate = useNavigate();
  const [open, setOpen] = useState(false); // sidebar visibility on narrow screens

  // Pending-comment count for the sidebar badge, refreshed every 60 seconds (one tiny request: page_size=1).
  const pending = useQuery({
    queryKey: ["admin", "comments", "pending-count"],
    queryFn: () => adminListComments({ status: "pending", page_size: 1 }).then((r) => r.pagination.count),
    refetchInterval: 60_000,
    retry: false,
  });

  const onLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="admin-shell">
      <aside className={`admin-side${open ? " open" : ""}`} aria-label="Admin navigation">
        <div className="brand">StoryBoard</div>
        <nav>
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} onClick={() => setOpen(false)} className={({ isActive }) => (isActive ? "active" : undefined)}>
              {link.label}
              {link.badge && pending.data > 0 && (
                <span className="nav-badge">{pending.data}<span className="sr-only"> pending</span></span>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="admin-body">
        <header className="admin-top">
          <button type="button" className="btn ghost small menu-btn" aria-expanded={open} aria-label="Toggle navigation" onClick={() => setOpen((v) => !v)}>
            ☰ Menu
          </button>
          <span className="grow" />
          <span className="who">{user?.display_name || user?.email}</span>
          <button type="button" className="btn secondary small" onClick={onLogout}>Log out</button>
        </header>
        <main className="admin-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
