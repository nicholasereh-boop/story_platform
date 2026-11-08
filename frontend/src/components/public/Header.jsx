import { useCallback, useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { SITE_NAME } from "../../config";
import SearchBar from "./SearchBar";
import { EXTENSION_NAV_LINKS } from "../../features";
import UserMenu from "./UserMenu";
import "../../styles/public-responsive.css";

const LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/stories", label: "Stories" },
  { to: "/categories", label: "Categories" },
  { to: "/tags", label: "Tags" },
  ...EXTENSION_NAV_LINKS, // Marketplace, Video tools (each only when its feature is on)
];

// Same breakpoint as the CSS in styles/public-responsive.css: at this width and below the menu is a sidebar.
const SIDEBAR_QUERY = "(max-width: 1024px)";
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function Header() {
  const [open, setOpen] = useState(false); // sidebar open (tablets and phones only; the toggle is hidden on desktop)
  const location = useLocation();
  const toggleRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => setOpen(false), [location.pathname]);

  const close = useCallback(() => {
    setOpen(false);
    toggleRef.current?.focus(); // keyboard users land back on the button they used
  }, []);

  // While the sidebar is open: Esc closes it, Tab stays inside it, the page behind does not scroll, and it closes by
  // itself if the window grows to desktop width (so the page can never be left locked).
  useEffect(() => {
    if (!open) return undefined;
    const menu = menuRef.current;
    menu?.querySelector(FOCUSABLE)?.focus();

    const onKey = (e) => {
      if (e.key === "Escape") {
        close();
        return;
      }
      if (e.key !== "Tab" || !menu) return;
      const items = [...menu.querySelectorAll(FOCUSABLE)]; // everything in the open sidebar is visible
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (!menu.contains(document.activeElement)) {
        e.preventDefault();
        first.focus();
      } else if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const query = typeof window.matchMedia === "function" ? window.matchMedia(SIDEBAR_QUERY) : null;
    const onChange = (e) => !e.matches && setOpen(false);
    query?.addEventListener?.("change", onChange);

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      query?.removeEventListener?.("change", onChange);
    };
  }, [open, close]);

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link to="/" className="site-name">{SITE_NAME}</Link>
        <button ref={toggleRef} type="button" className="btn ghost small menu-toggle" aria-expanded={open} aria-controls="site-menu" onClick={() => setOpen((v) => !v)}>
          Menu
        </button>
        {open && <div className="menu-backdrop" onClick={() => setOpen(false)} aria-hidden="true" />}
        <div id="site-menu" ref={menuRef} className={`site-menu${open ? " open" : ""}`}>
          <button type="button" className="btn ghost small menu-close" onClick={close}>Close menu</button>
          {/* NavLink adds aria-current="page" to the active link by itself. */}
          <nav aria-label="Main">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end}>{l.label}</NavLink>
            ))}
          </nav>
          <SearchBar />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
