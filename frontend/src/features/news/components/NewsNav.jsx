import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { listNewsCategories } from "../api/news";

// The News section's own sub-navigation: all news, one link per category, and a search box.
export default function NewsNav({ initialQuery = "" }) {
  const categories = useQuery({ queryKey: ["news", "categories"], queryFn: listNewsCategories, staleTime: 5 * 60_000 });
  const [q, setQ] = useState(initialQuery);
  const navigate = useNavigate();
  const link = ({ isActive }) => (isActive ? "nw-tab is-active" : "nw-tab");
  const submit = (e) => {
    e.preventDefault();
    const term = q.trim();
    if (term.length >= 2) navigate(`/news/search?q=${encodeURIComponent(term)}`);
  };
  return (
    <div className="nw-nav">
      <nav aria-label="News sections" className="nw-tabs">
        <NavLink to="/news" end className={link}>Latest</NavLink>
        {(categories.data || []).map((c) => <NavLink key={c.slug} to={`/news/category/${c.slug}`} className={link}>{c.name}</NavLink>)}
      </nav>
      <form role="search" aria-label="Search news" onSubmit={submit} className="nw-search">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search news" aria-label="Search news" minLength={2} maxLength={100} />
        <button type="submit" className="btn secondary small">Search</button>
      </form>
      <Link to="/news/report" className="nw-report">Report a problem</Link>
    </div>
  );
}
