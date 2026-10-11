import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

// Header search. Trims the text, ignores an empty submit and goes to /search?q=...
export default function SearchBar({ onDone }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [value, setValue] = useState("");

  // Show the current query while on the results page.
  useEffect(() => {
    setValue(location.pathname === "/search" ? new URLSearchParams(location.search).get("q") || "" : "");
  }, [location.pathname, location.search]);

  const submit = (event) => {
    event.preventDefault();
    const q = value.trim();
    if (!q) return;
    navigate(`/search?q=${encodeURIComponent(q)}`);
    onDone?.();
  };

  return (
    <form className="search-bar" role="search" onSubmit={submit}>
      <label htmlFor="site-search" className="sr-only">Search stories</label>
      <input id="site-search" type="search" placeholder="Search stories…" value={value} onChange={(e) => setValue(e.target.value)} autoComplete="off" />
      <button type="submit" className="btn small">Search</button>
    </form>
  );
}
