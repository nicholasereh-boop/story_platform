import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { SITE_NAME } from "../../config";
import SearchBar from "./SearchBar";
import UserMenu from "./UserMenu";

const LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/stories", label: "Stories" },
  { to: "/categories", label: "Categories" },
  { to: "/tags", label: "Tags" },
];

export default function Header() {
  const [open, setOpen] = useState(false); // menu on narrow screens
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link to="/" className="site-name">{SITE_NAME}</Link>
        <button type="button" className="btn ghost small menu-toggle" aria-expanded={open} aria-controls="site-menu" onClick={() => setOpen((v) => !v)}>
          {open ? "Close" : "Menu"}
        </button>
        <div id="site-menu" className={`site-menu${open ? " open" : ""}`}>
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
